import logging
import sys


def setup_logging(log_name = 'YAAMT', log_level = logging.DEBUG):
    hand = logging.StreamHandler( sys.stderr )
    hand.setLevel(log_level)
    hand.setFormatter(logging.Formatter('%(asctime)s-%(levelname)s-%(name)s: %(message)s'))

    logger = logging.getLogger(name=log_name)
    logger.addHandler(hand)

    return logger

log = setup_logging()