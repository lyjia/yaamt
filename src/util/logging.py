import logging
import sys


def create_logger(log_name='YAAMT', log_level=logging.DEBUG):
    hand = logging.StreamHandler(sys.stderr)
    hand.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(funcName)s: %(message)s', "%Y%m%d-%H%M%S"))

    logger = logging.getLogger(name=log_name)
    logger.setLevel(log_level)
    logger.addHandler(hand)

    return logger

log = create_logger()
