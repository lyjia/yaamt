import logging
import sys

def create_logger(log_name='YAAMT', log_level=logging.DEBUG):
    logger = logging.getLogger(name=log_name)
    logger.setLevel(log_level)
    return logger

log = create_logger()

def configure_logger(use_formatter=True):
    hand = logging.StreamHandler(sys.stdout)
    if use_formatter:
        hand.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(funcName)s: %(message)s', "%Y%m%d-%H%M%S"))
    
    if log.hasHandlers():
        log.handlers.clear()
    log.addHandler(hand)

configure_logger()
