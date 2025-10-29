"""
MusicalKeyCNN key analyzer using deep learning.

This analyzer detects musical key using a Convolutional Neural Network (CNN)
based on the paper by Korzeniowski & Widmer (2018). The model analyzes
log-magnitude CQT spectrograms to classify keys into 24 classes (12 major + 12 minor).

Reference: https://github.com/a1ex90/MusicalKeyCNN
Paper: "Genre-Agnostic Key Classification With Convolutional Neural Networks"
       by F. Korzeniowski and G. Widmer (ISMIR 2018)
"""

from typing import Optional, List, TYPE_CHECKING
from pathlib import Path
import sys
import numpy as np

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

from providers.analysis import AnalyzerBase, AnalyzerResult, AnalyzerCategory
from providers import register_analyzer
from providers.audio.format_descriptor import AudioFormatDescriptor
from util.analyzer_options import AnalyzerOption, build_widget_from_option
from util.const import KEY_INITIAL_KEY
from util.logging import log


# Camelot Wheel mapping (from MusicalKeyCNN dataset.py)
# Maps key names to indices 0-23 (0-11 = minor, 12-23 = major)
CAMELOT_MAPPING = {
    'G# minor': 0, 'Ab minor': 0,
    'D# minor': 1, 'Eb minor': 1,
    'A# minor': 2, 'Bb minor': 2,
    'F minor': 3,
    'C minor': 4,
    'G minor': 5,
    'D minor': 6,
    'A minor': 7,
    'E minor': 8,
    'B minor': 9,
    'F# minor': 10, 'Gb minor': 10,
    'C# minor': 11, 'Db minor': 11,
    'B major': 12,
    'F# major': 13, 'Gb major': 13,
    'C# major': 14, 'Db major': 14,
    'G# major': 15, 'Ab major': 15,
    'D# major': 16, 'Eb major': 16,
    'A# major': 17, 'Bb major': 17,
    'F major': 18,
    'C major': 19,
    'G major': 20,
    'D major': 21,
    'A major': 22,
    'E major': 23
}

# Inverse mapping from index to key name (use sharp notation as default)
INDEX_TO_KEY = {
    0: 'G#m', 1: 'D#m', 2: 'A#m', 3: 'Fm', 4: 'Cm', 5: 'Gm',
    6: 'Dm', 7: 'Am', 8: 'Em', 9: 'Bm', 10: 'F#m', 11: 'C#m',
    12: 'B', 13: 'F#', 14: 'C#', 15: 'G#', 16: 'D#', 17: 'A#',
    18: 'F', 19: 'C', 20: 'G', 21: 'D', 22: 'A', 23: 'E'
}


class MusicalKeyCNNAnalyzer(AnalyzerBase):
    """
    Musical key analyzer using a Convolutional Neural Network.

    This analyzer uses a pretrained CNN model (KeyNet) to detect musical keys.
    The model was trained on the GiantSteps-MTG dataset and achieves competitive
    performance with commercial DJ software like Mixed In Key and RekordBox.

    The analyzer:
    1. Converts audio to mono and resamples to 44100 Hz
    2. Extracts a log-magnitude CQT spectrogram (105 frequency bins)
    3. Feeds the spectrogram to the CNN for classification
    4. Returns the predicted key in standard notation

    Performance (MIREX weighted score on GiantSteps dataset):
    - MusicalKeyCNN: 73.51%
    - Mixed In Key 8.3: 75.70%
    - RekordBox 7.12: 65.53%

    Analyzer-specific options:
        - 'model_path' (str): Path to model checkpoint file (default: auto-detect)
        - 'device' (str): Computation device ("auto", "cpu", or "cuda")
    """

    name = "MusicalKeyCNN Key Analyzer"
    description = "Deep learning key detector using CNN (Korzeniowski & Widmer 2018)"
    category = "key"
    version = "1.0.0"
    debug_only = True  # PyTorch cannot be compiled with nuitka

    def analyze(self) -> AnalyzerResult:
        """
        Perform musical key analysis using the CNN model.

        Returns:
            AnalyzerResult with key string or error/skip status
        """
        audio_stream = None

        try:
            # Check for cancellation
            if self.is_cancelled:
                return AnalyzerResult(
                    success=False,
                    error="Analysis cancelled by user"
                )

            # Check if key already exists (skip if requested)
            skip_if_exists = self.options.get('skip_if_tag_exists', False)
            existing_key = self.media_file.get_tag_simple(KEY_INITIAL_KEY)

            if existing_key and skip_if_exists:
                return AnalyzerResult(
                    success=True,
                    skipped=True,
                    error="Key already set"
                )

            # Import PyTorch dependencies (fail gracefully if not available)
            try:
                import torch
                import torchaudio
                import librosa
            except ImportError as e:
                return AnalyzerResult(
                    success=False,
                    error=f"Required libraries not available (torch/torchaudio/librosa): {e}"
                )

            # Determine device
            device_option = self.options.get('device', 'auto')
            if device_option == 'auto':
                device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            else:
                device = torch.device(device_option)

            # Load model
            model_path = self._get_model_path()
            if not model_path.exists():
                return AnalyzerResult(
                    success=False,
                    error=f"Model checkpoint not found at {model_path}"
                )

            log.debug(f"Loading MusicalKeyCNN model from {model_path}")
            model = self._load_model(model_path, device)

            # Create format descriptor requesting mono float32 audio at 44100 Hz
            format_descriptor = AudioFormatDescriptor(
                channels=1,
                sample_width=4,
                sample_format='float',
                sample_rate=44100
            )

            # Open audio stream
            audio_stream = self.media_file.get_audio_stream(format_descriptor)
            sample_rate = audio_stream.sample_rate

            log.debug(f"MusicalKeyCNN analyzer starting: {self.media_file.file_path}")
            log.debug(f"  Sample rate: {sample_rate}Hz, device: {device}")

            # Convert audio stream to numpy array
            from util.audio_numpy import audio_stream_to_numpy
            y, sr = audio_stream_to_numpy(audio_stream)

            # Close stream early to free resources
            audio_stream.close()
            audio_stream = None

            if len(y) == 0:
                return AnalyzerResult(
                    success=False,
                    error="No audio data available"
                )

            log.debug(f"  Loaded {len(y)} samples ({len(y)/sr:.2f}s)")

            # Check for cancellation before preprocessing
            if self.is_cancelled:
                return AnalyzerResult(
                    success=False,
                    error="Analysis cancelled by user"
                )

            # Preprocess: compute log-magnitude CQT spectrogram
            spec_tensor = self._preprocess_audio(y, sr, librosa)

            # Move to device and add batch dimension
            spec_tensor = spec_tensor.to(device)
            if spec_tensor.ndim == 3:
                spec_tensor = spec_tensor.unsqueeze(0)  # (1, 1, freq, time)

            log.debug(f"  Spectrogram shape: {spec_tensor.shape}")

            # Check for cancellation before inference
            if self.is_cancelled:
                return AnalyzerResult(
                    success=False,
                    error="Analysis cancelled by user"
                )

            # Run inference
            with torch.no_grad():
                outputs = model(spec_tensor)
                pred_idx = int(torch.argmax(outputs, dim=1).cpu().item())
                confidence = torch.softmax(outputs, dim=1).max().cpu().item()

            # Convert prediction to key string
            key_str = INDEX_TO_KEY.get(pred_idx, 'C')

            log.info(f"MusicalKeyCNN detected key: {key_str} (index: {pred_idx}, "
                    f"confidence: {confidence:.3f}) for {self.media_file.file_path}")

            # Return key string (Tag Transformation system handles notation conversion)
            return AnalyzerResult(
                success=True,
                data={KEY_INITIAL_KEY: key_str}
            )

        except ImportError as e:
            log.error(f"Required libraries import failed: {e}")
            return AnalyzerResult(
                success=False,
                error=f"Required libraries not available: {e}"
            )
        except Exception as e:
            log.error(f"MusicalKeyCNN analysis failed for {self.media_file.file_path}: {e}")
            return AnalyzerResult(
                success=False,
                error=str(e)
            )
        finally:
            # Always close audio stream
            if audio_stream:
                try:
                    audio_stream.close()
                except Exception as e:
                    log.warning(f"Error closing audio stream: {e}")

    def _get_model_path(self) -> Path:
        """
        Get the path to the model checkpoint.

        Returns:
            Path to the model checkpoint file
        """
        # Check if user specified a custom model path
        model_path_str = self.options.get('model_path', None)
        if model_path_str:
            return Path(model_path_str)

        # Default: look in references/MusicalKeyCNN/checkpoints/keynet.pt
        # Get project root (go up from src/providers/analysis/key/)
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent.parent.parent

        default_path = project_root / "references" / "MusicalKeyCNN" / "checkpoints" / "keynet.pt"
        return default_path

    def _load_model(self, model_path: Path, device):
        """
        Load the KeyNet model from checkpoint.

        Args:
            model_path: Path to model checkpoint
            device: Torch device to load model onto

        Returns:
            Loaded model in evaluation mode
        """
        import torch

        # Add MusicalKeyCNN to Python path so we can import the model
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent.parent.parent
        musical_key_cnn_path = project_root / "references" / "MusicalKeyCNN"

        if str(musical_key_cnn_path) not in sys.path:
            sys.path.insert(0, str(musical_key_cnn_path))

        # Import KeyNet model
        from model import KeyNet

        # Create model and load weights
        model = KeyNet(num_classes=24, in_channels=1, Nf=20).to(device)
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.eval()

        return model

    def _preprocess_audio(self, waveform: np.ndarray, sample_rate: int, librosa) -> "torch.Tensor":
        """
        Preprocess audio to CQT spectrogram as expected by KeyNet.

        Args:
            waveform: Audio samples as numpy array (mono, float32)
            sample_rate: Sample rate in Hz
            librosa: librosa module

        Returns:
            Torch tensor with shape (1, freq_bins, time_frames)
        """
        import torch

        # Constants from MusicalKeyCNN preprocessing
        N_BINS = 105
        HOP_LENGTH = 8820
        BINS_PER_OCTAVE = 24
        FMIN = 65  # C2

        # Compute CQT
        cqt = librosa.cqt(
            waveform,
            sr=sample_rate,
            hop_length=HOP_LENGTH,
            n_bins=N_BINS,
            bins_per_octave=BINS_PER_OCTAVE,
            fmin=FMIN
        )

        # Convert to log-magnitude
        spec = np.abs(cqt)
        spec = np.log1p(spec)

        # Remove last frequency bin (as done in MusicalKeyCNN preprocessing)
        chunk = spec[:, 0:-2]

        # Convert to torch tensor
        spec_tensor = torch.tensor(chunk, dtype=torch.float32)

        # Add channel dimension: (freq, time) -> (1, freq, time)
        if spec_tensor.ndim == 2:
            spec_tensor = spec_tensor.unsqueeze(0)

        return spec_tensor

    @classmethod
    def get_options_metadata(cls) -> List[AnalyzerOption]:
        """
        Return option metadata for this analyzer.

        Returns:
            List of AnalyzerOption instances for MusicalKeyCNN analyzer options
        """
        return [
            AnalyzerOption(
                name='device',
                type='choice',
                default='auto',
                help='Computation device for neural network inference',
                choices=[
                    ('auto', 'Automatic (use GPU if available)'),
                    ('cpu', 'CPU only'),
                    ('cuda', 'GPU (CUDA)')
                ]
            ),
            AnalyzerOption(
                name='model_path',
                type='str',
                default='',
                help='Custom path to model checkpoint file (leave empty for default)'
            )
        ]

    @classmethod
    def get_settings_widget(cls) -> Optional["QWidget"]:
        """
        Return a QWidget for configuring MusicalKeyCNN analyzer parameters.

        Returns:
            QWidget with controls for CNN key detection parameters
        """
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

        widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)

        # Info label
        info_label = QLabel(
            "MusicalKeyCNN uses a deep learning model to detect musical keys. "
            "The model was trained on the GiantSteps-MTG dataset and achieves "
            "73.51% weighted MIREX score, comparable to commercial DJ software.\n\n"
            "Reference: Korzeniowski & Widmer (2018) - 'Genre-Agnostic Key "
            "Classification With Convolutional Neural Networks'"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        main_layout.addWidget(info_label)

        options = cls.get_options_metadata()
        settings_group = f"analyzers/{cls.__name__}"

        # Add device option
        for option in options:
            if option.name == 'device':
                option_widget = build_widget_from_option(option, settings_group)
                main_layout.addWidget(option_widget)

        main_layout.addStretch()

        widget.setLayout(main_layout)
        return widget


# Register this analyzer with the Key category
register_analyzer(AnalyzerCategory.KEY, MusicalKeyCNNAnalyzer)
