from .base import AudioStreamBase
from typing import List, Tuple


def get_available_audio_devices() -> List[Tuple[str, str]]:
    """
    Get list of available audio output devices.

    Returns:
        List of (device_name, device_id) tuples.
        Empty list if no devices available or not yet implemented.
    """
    # TODO: Implement actual audio device enumeration
    # For now, return empty list (only system default will be available)
    return []


def set_preferred_audio_device(device_id: str) -> bool:
    """
    Set the preferred audio output device.

    Args:
        device_id: Device ID to use, or empty string for system default

    Returns:
        True if successful, False otherwise
    """
    # TODO: Implement actual audio device selection
    # For now, always return True (accepts but doesn't change device)
    return True