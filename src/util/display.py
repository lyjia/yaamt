from datetime import datetime


# Python
def human_readable_size(num_bytes: int | float | None,
                        decimal_places: int = 2,
                        *,
                        binary: bool = True) -> str:
    """
    Turn a byte count into a readable string such as '2.14 MB' or '1.9 GiB'.

    Parameters
    ----------
    num_bytes : int | float | None
        The size in **bytes**.  If None or a false-y value, 'N/A' is returned.
    decimal_places : int, default 2
        How many digits to show after the decimal point.
    binary : bool, default True
        • True  – use powers of 1024 and IEC suffixes (B, KiB, MiB, GiB …)
        • False – use powers of 1000 and SI  suffixes (B, KB, MB, GB …)

    Returns
    -------
    str
        A readable representation of the size.
    """
    if not num_bytes:  # covers None, 0, 0.0, ""
        return "N/A"

    base = 1024 if binary else 1000
    suffixes = (
        ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB"]
        if binary
        else
        ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    )

    size = float(num_bytes)
    i = 0
    while size >= base and i < len(suffixes) - 1:
        size /= base
        i += 1

    formatted_size = format(size, f",.{decimal_places}f")
    return f"{formatted_size} {suffixes[i]}"


def human_readable_timestamp(timestamp: float | None) -> str:
    """
    Convert a timestamp to a human-readable string using system's locale settings.

    Parameters
    ----------
    timestamp : float | None
        Unix timestamp (seconds since epoch). If None or false-y value, 'N/A' is returned.

    Returns
    -------
    str
        A readable representation of the timestamp using system locale.
    """
    if not timestamp:  # covers None, 0, 0.0
        return "N/A"

    return datetime.fromtimestamp(timestamp).strftime("%c")
