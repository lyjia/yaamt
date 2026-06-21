"""
Unit tests for AudioFormatDescriptor.

Tests the format descriptor class used to specify desired audio formats
for stream adaptation.
"""

import pytest
from providers.audio.format_descriptor import AudioFormatDescriptor


class TestAudioFormatDescriptorCreation:
    """Test creating AudioFormatDescriptor instances."""

    def test_create_with_all_parameters(self):
        """Test creating a descriptor with all parameters specified."""
        desc = AudioFormatDescriptor(
            sample_rate=44100,
            channels=2,
            sample_width=2,
            sample_format='int'
        )

        assert desc.sample_rate == 44100
        assert desc.channels == 2
        assert desc.sample_width == 2
        assert desc.sample_format == 'int'

    def test_create_with_partial_parameters(self):
        """Test creating a descriptor with only some parameters."""
        desc = AudioFormatDescriptor(sample_rate=48000, channels=1)

        assert desc.sample_rate == 48000
        assert desc.channels == 1
        assert desc.sample_width is None
        assert desc.sample_format is None

    def test_create_with_no_parameters(self):
        """Test creating a descriptor with no parameters (all None)."""
        desc = AudioFormatDescriptor()

        assert desc.sample_rate is None
        assert desc.channels is None
        assert desc.sample_width is None
        assert desc.sample_format is None

    def test_create_mono_descriptor(self):
        """Test creating a mono-only descriptor."""
        desc = AudioFormatDescriptor(channels=1)

        assert desc.channels == 1
        assert desc.sample_rate is None

    def test_create_float_format_descriptor(self):
        """Test creating a float format descriptor."""
        desc = AudioFormatDescriptor(sample_format='float', sample_width=4)

        assert desc.sample_format == 'float'
        assert desc.sample_width == 4


class TestAudioFormatDescriptorMatches:
    """Test the matches() method for format comparison."""

    def test_matches_exact_same_values(self):
        """Test that two identical descriptors match."""
        desc1 = AudioFormatDescriptor(sample_rate=44100, channels=2)
        desc2 = AudioFormatDescriptor(sample_rate=44100, channels=2)

        assert desc1.matches(desc2)
        assert desc2.matches(desc1)

    def test_matches_with_wildcard_none(self):
        """Test that None acts as a wildcard in matches()."""
        desc1 = AudioFormatDescriptor(sample_rate=44100, channels=1)
        desc2 = AudioFormatDescriptor(sample_rate=44100)  # channels=None

        # desc2's None channels should match desc1's 1 channel
        assert desc1.matches(desc2)
        assert desc2.matches(desc1)

    def test_matches_both_none(self):
        """Test that two None values match each other."""
        desc1 = AudioFormatDescriptor(channels=1)
        desc2 = AudioFormatDescriptor(channels=1)

        # Both have sample_rate=None, should match
        assert desc1.matches(desc2)

    def test_does_not_match_different_sample_rate(self):
        """Test that different sample rates don't match."""
        desc1 = AudioFormatDescriptor(sample_rate=44100, channels=1)
        desc2 = AudioFormatDescriptor(sample_rate=48000, channels=1)

        assert not desc1.matches(desc2)
        assert not desc2.matches(desc1)

    def test_does_not_match_different_channels(self):
        """Test that different channel counts don't match."""
        desc1 = AudioFormatDescriptor(sample_rate=44100, channels=1)
        desc2 = AudioFormatDescriptor(sample_rate=44100, channels=2)

        assert not desc1.matches(desc2)
        assert not desc2.matches(desc1)

    def test_does_not_match_different_sample_width(self):
        """Test that different sample widths don't match."""
        desc1 = AudioFormatDescriptor(sample_width=2, sample_format='int')
        desc2 = AudioFormatDescriptor(sample_width=4, sample_format='int')

        assert not desc1.matches(desc2)

    def test_does_not_match_different_sample_format(self):
        """Test that different sample formats don't match."""
        desc1 = AudioFormatDescriptor(sample_width=4, sample_format='int')
        desc2 = AudioFormatDescriptor(sample_width=4, sample_format='float')

        assert not desc1.matches(desc2)

    def test_matches_all_none_descriptors(self):
        """Test that two all-None descriptors match."""
        desc1 = AudioFormatDescriptor()
        desc2 = AudioFormatDescriptor()

        assert desc1.matches(desc2)

    def test_matches_partial_overlap(self):
        """Test matching with partial parameter overlap."""
        desc1 = AudioFormatDescriptor(sample_rate=44100, channels=2, sample_width=2)
        desc2 = AudioFormatDescriptor(sample_rate=44100, sample_format='int')

        # They share sample_rate, other params are None in one or both
        assert desc1.matches(desc2)


class TestAudioFormatDescriptorEquality:
    """Test the __eq__ method for exact equality."""

    def test_exact_equality(self):
        """Test that identical descriptors are equal."""
        desc1 = AudioFormatDescriptor(sample_rate=44100, channels=2)
        desc2 = AudioFormatDescriptor(sample_rate=44100, channels=2)

        assert desc1 == desc2

    def test_not_equal_different_sample_rate(self):
        """Test that different sample rates mean not equal."""
        desc1 = AudioFormatDescriptor(sample_rate=44100)
        desc2 = AudioFormatDescriptor(sample_rate=48000)

        assert desc1 != desc2

    def test_not_equal_none_vs_value(self):
        """Test that None vs a value means not equal."""
        desc1 = AudioFormatDescriptor(channels=1)
        desc2 = AudioFormatDescriptor()

        # desc1 has channels=1, desc2 has channels=None
        assert desc1 != desc2

    def test_equal_all_none(self):
        """Test that two all-None descriptors are equal."""
        desc1 = AudioFormatDescriptor()
        desc2 = AudioFormatDescriptor()

        assert desc1 == desc2

    def test_not_equal_to_non_descriptor(self):
        """Test that a descriptor is not equal to other types."""
        desc = AudioFormatDescriptor(sample_rate=44100)

        assert desc != "not a descriptor"
        assert desc != 44100
        assert desc != None


class TestAudioFormatDescriptorRepr:
    """Test the __repr__ method for string representation."""

    def test_repr_all_parameters(self):
        """Test repr with all parameters specified."""
        desc = AudioFormatDescriptor(
            sample_rate=44100,
            channels=2,
            sample_width=2,
            sample_format='int'
        )

        repr_str = repr(desc)
        assert '44100Hz' in repr_str
        assert '2ch' in repr_str
        assert '16bit' in repr_str
        assert 'int' in repr_str
        assert 'AudioFormatDescriptor' in repr_str

    def test_repr_mono(self):
        """Test repr with mono channel."""
        desc = AudioFormatDescriptor(channels=1)

        repr_str = repr(desc)
        assert 'mono' in repr_str

    def test_repr_native(self):
        """Test repr with no parameters (native format)."""
        desc = AudioFormatDescriptor()

        repr_str = repr(desc)
        assert 'native' in repr_str
        assert 'AudioFormatDescriptor' in repr_str

    def test_repr_partial_parameters(self):
        """Test repr with only some parameters."""
        desc = AudioFormatDescriptor(sample_rate=48000, sample_format='float')

        repr_str = repr(desc)
        assert '48000Hz' in repr_str
        assert 'float' in repr_str

    def test_repr_24bit(self):
        """Test repr correctly shows 24-bit."""
        desc = AudioFormatDescriptor(sample_width=3)

        repr_str = repr(desc)
        assert '24bit' in repr_str


class TestAudioFormatDescriptorUseCases:
    """Test real-world use cases for AudioFormatDescriptor."""

    def test_mono_analyzer_use_case(self):
        """Test descriptor for an analyzer that needs mono audio."""
        # Analyzer wants mono at native sample rate
        desc = AudioFormatDescriptor(channels=1)

        assert desc.channels == 1
        assert desc.sample_rate is None  # Accept native
        assert 'mono' in repr(desc)

    def test_hardware_playback_use_case(self):
        """Test descriptor for hardware with specific requirements."""
        # Hardware supports max 48kHz, 16-bit, stereo
        desc = AudioFormatDescriptor(
            sample_rate=48000,
            channels=2,
            sample_width=2,
            sample_format='int'
        )

        assert desc.sample_rate == 48000
        assert desc.channels == 2
        assert desc.sample_width == 2
        assert desc.sample_format == 'int'

    def test_high_quality_float_use_case(self):
        """Test descriptor for high-quality float processing."""
        # Processing pipeline wants 32-bit float
        desc = AudioFormatDescriptor(
            sample_format='float',
            sample_width=4
        )

        assert desc.sample_format == 'float'
        assert desc.sample_width == 4
        assert desc.sample_rate is None  # Accept native
        assert desc.channels is None  # Accept native
