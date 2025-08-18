import logging

def setup_logging(log_level):
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s-%(levelname)s-%(name)s: %(message)s')

def log(message, level=logging.DEBUG):
    logging.log(level, message)