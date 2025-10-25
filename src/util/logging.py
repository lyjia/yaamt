import logging
import sys

def create_logger(log_name='YAAMT', log_level=logging.DEBUG):
    logger = logging.getLogger(name=log_name)
    logger.setLevel(log_level)
    return logger

log = create_logger()

# Log level string to logging constant mapping
LOG_LEVEL_MAP = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

def configure_logger(use_formatter: bool = True, log_level: str = 'info'):
    """
    Configure the logger with the specified settings.

    Args:
        use_formatter: If True, use a formatted output (default: True)
        log_level: Log level as a string: 'debug', 'info', 'warning', 'error', 'critical' (default: 'info')
    """
    # Map log level string to logging constant
    level = LOG_LEVEL_MAP.get(log_level.lower(), logging.INFO)

    hand = logging.StreamHandler(sys.stderr)
    hand.setLevel(level)

    if use_formatter:
        hand.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(funcName)s: %(message)s', "%Y%m%d-%H%M%S"))

    if log.hasHandlers():
        log.handlers.clear()
    log.addHandler(hand)
    log.propagate = False

    # Also set the logger level
    log.setLevel(level)

configure_logger()
