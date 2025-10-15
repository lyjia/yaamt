"""
Audio stream adapters for format conversion.

This package contains adapters that wrap AudioStreamBase instances to provide
on-the-fly format conversion using the decorator pattern.
"""

from .base import AdapterBase
from .channel_mixing_adapter import ChannelMixingAdapter
from .bit_depth_adapter import BitDepthAdapter
from .resampling_adapter import ResamplingAdapter

__all__ = [
    'AdapterBase',
    'ChannelMixingAdapter',
    'BitDepthAdapter',
    'ResamplingAdapter',
]
