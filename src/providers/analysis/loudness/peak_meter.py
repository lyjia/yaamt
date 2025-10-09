"""
Peak loudness meter analyzer.

This analyzer measures the maximum peak level of an audio file by reading
the entire audio stream and finding the absolute maximum sample value across
all channels. The result is reported in dBFS (decibels relative to full scale).
"""

import struct
from typing import Optional

from providers.analysis.base import AnalyzerBase, AnalyzerResult
from providers.audio.base import AudioStreamBase
from util.const import KEY_COMMENT
from util.logging import log


class PeakMeterAnalyzer(AnalyzerBase):
    """
    Analyzer that measures peak loudness (maximum sample value) in dBFS.

    This analyzer reads the entire audio stream and finds the absolute maximum
    peak across all channels. The result is stored in the comments field.

    The peak is measured as the maximum absolute sample value normalized to the
    range [0.0, 1.0], then converted to dBFS using the formula:
        dBFS = 20 * log10(peak)

    A peak of 1.0 (digital full scale) equals 0 dBFS.
    A peak of 0.5 equals approximately -6 dBFS.

    Analyzer-specific options:
        None currently supported
    """

    name = "Peak Loudness Meter"
    description = "Measures peak audio level in dBFS"
    category = "loudness"
    version = "1.0.0"

    # Marker used to identify our result in the comments field
    RESULT_MARKER = "Peak:"

    def analyze(self) -> AnalyzerResult:
        """
        Perform peak loudness analysis.

        Returns:
            AnalyzerResult with peak level in dBFS
        """
        try:
            # Check for cancellation
            if self.is_cancelled:
                return AnalyzerResult(
                    success=False,
                    error="Analysis cancelled by user"
                )

            # Check if we should overwrite existing results
            overwrite = self.options.get('overwrite_existing', False)
            if not overwrite and self._has_existing_result():
                return AnalyzerResult(
                    success=True,
                    skipped=True,
                    error="Peak level already measured"
                )

            # Get audio stream from MediaFile
            log.debug(f"Starting peak analysis for {self.media_file.file_path}")
            audio_stream = self.media_file.get_audio_stream()

            try:
                peak_dbfs = self._measure_peak(audio_stream)
            finally:
                # Always close the audio stream
                audio_stream.close()

            # Format result and update comments
            result_str = f"{self.RESULT_MARKER} {peak_dbfs:.2f} dBFS"
            updated_comments = self._update_comments(result_str)

            log.debug(f"Peak analysis complete: {result_str} for {self.media_file.file_path}")

            return AnalyzerResult(
                success=True,
                data={KEY_COMMENT: updated_comments}
            )

        except Exception as e:
            log.error(f"Peak analysis failed for {self.media_file.file_path}: {e}")
            return AnalyzerResult(
                success=False,
                error=str(e)
            )

    def _has_existing_result(self) -> bool:
        """
        Check if the comments field already contains a peak measurement.

        Returns:
            True if a peak measurement exists in comments
        """
        existing_comments = self.media_file.get_tag_simple(KEY_COMMENT)
        if not existing_comments:
            return False

        # Check if our marker exists in the comments
        return self.RESULT_MARKER in existing_comments

    def _update_comments(self, new_result: str) -> str:
        """
        Update the comments field with the new peak measurement.

        If a previous peak measurement exists, replace it. Otherwise, append.

        Args:
            new_result: The formatted result string (e.g., "Peak: -3.45 dBFS")

        Returns:
            The updated comments string
        """
        existing_comments = self.media_file.get_tag_simple(KEY_COMMENT)

        if not existing_comments:
            # No existing comments, just return our result
            return new_result

        # Check if we have an existing peak measurement
        if self.RESULT_MARKER in existing_comments:
            # Replace the existing measurement
            lines = existing_comments.split('\n')
            updated_lines = []

            for line in lines:
                if self.RESULT_MARKER in line:
                    # Replace this line with the new result
                    updated_lines.append(new_result)
                else:
                    updated_lines.append(line)

            return '\n'.join(updated_lines)
        else:
            # Append to existing comments
            return f"{existing_comments}\n{new_result}"

    def _measure_peak(self, audio_stream: AudioStreamBase) -> float:
        """
        Measure the peak level by reading the entire audio stream.

        Args:
            audio_stream: Audio stream to analyze

        Returns:
            Peak level in dBFS
        """
        import math

        sample_width = audio_stream.sample_width
        nchannels = audio_stream.nchannels

        # Determine the format string for struct.unpack based on sample width
        if sample_width == 1:
            # 8-bit unsigned
            format_char = 'B'
            max_value = 128.0  # 8-bit audio is unsigned, centered at 128
            is_unsigned = True
        elif sample_width == 2:
            # 16-bit signed
            format_char = 'h'
            max_value = 32768.0
            is_unsigned = False
        elif sample_width == 3:
            # 24-bit (will be handled specially)
            format_char = None
            max_value = 8388608.0  # 2^23
            is_unsigned = False
        elif sample_width == 4:
            # 32-bit signed integer or float
            format_char = 'i'  # Try as integer first
            max_value = 2147483648.0
            is_unsigned = False
        else:
            raise ValueError(f"Unsupported sample width: {sample_width} bytes")

        max_peak = 0.0
        chunk_size = 4096  # Read in chunks of 4096 frames

        # Read the entire stream
        while True:
            if self.is_cancelled:
                raise Exception("Analysis cancelled by user")

            chunk_bytes = audio_stream.read(chunk_size)
            if not chunk_bytes:
                break

            # Process the chunk
            chunk_peak = self._process_chunk(
                chunk_bytes, sample_width, nchannels,
                format_char, max_value, is_unsigned
            )

            max_peak = max(max_peak, chunk_peak)

        # Convert to dBFS
        if max_peak == 0.0:
            # Silence
            return float('-inf')
        else:
            dbfs = 20.0 * math.log10(max_peak)
            return dbfs

    def _process_chunk(
        self,
        chunk_bytes: bytes,
        sample_width: int,
        nchannels: int,
        format_char: Optional[str],
        max_value: float,
        is_unsigned: bool
    ) -> float:
        """
        Process a chunk of audio data and find the peak.

        Args:
            chunk_bytes: Raw audio bytes
            sample_width: Sample width in bytes
            nchannels: Number of channels
            format_char: Format character for struct.unpack
            max_value: Maximum sample value for normalization
            is_unsigned: Whether the format is unsigned

        Returns:
            Peak value in the chunk (normalized to 0.0-1.0)
        """
        bytes_per_sample = sample_width
        num_samples = len(chunk_bytes) // bytes_per_sample

        chunk_peak = 0.0

        if sample_width == 3:
            # Handle 24-bit audio specially
            for i in range(num_samples):
                offset = i * 3
                # 24-bit little-endian signed integer
                sample_bytes = chunk_bytes[offset:offset + 3]
                if len(sample_bytes) < 3:
                    break

                # Convert to signed 32-bit integer
                # Extend to 4 bytes by padding with sign byte
                sign_byte = b'\xff' if (sample_bytes[2] & 0x80) else b'\x00'
                sample_bytes_32 = sample_bytes + sign_byte

                sample_value = struct.unpack('<i', sample_bytes_32)[0]
                # Scale down from 32-bit to 24-bit range
                sample_value = sample_value >> 8

                normalized = abs(sample_value) / max_value
                chunk_peak = max(chunk_peak, normalized)
        else:
            # Use struct to unpack the samples
            format_str = f'<{num_samples}{format_char}'
            try:
                samples = struct.unpack(format_str, chunk_bytes[:num_samples * bytes_per_sample])

                for sample in samples:
                    if is_unsigned:
                        # Convert unsigned to signed (centered at 128 for 8-bit)
                        sample_value = abs(sample - 128)
                    else:
                        sample_value = abs(sample)

                    normalized = sample_value / max_value
                    chunk_peak = max(chunk_peak, normalized)
            except struct.error as e:
                log.warning(f"Struct unpack error: {e}")
                # Skip this chunk if there's an unpacking error

        return chunk_peak

    @classmethod
    def validate_file(cls, media_file) -> tuple[bool, Optional[str]]:
        """
        Check if this analyzer can process the given file.

        Args:
            media_file: The MediaFile instance to validate

        Returns:
            Tuple of (is_valid, reason)
        """
        # This analyzer should work with all audio files
        if not media_file.is_readable():
            return (False, "File is not readable")

        return (True, None)
