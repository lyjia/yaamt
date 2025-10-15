"""
Audio stream adapters for format conversion.

This package contains adapters that wrap AudioStreamBase instances to provide
on-the-fly format conversion using the decorator pattern.
"""

from .base import AdapterBase

__all__ = ['AdapterBase']
