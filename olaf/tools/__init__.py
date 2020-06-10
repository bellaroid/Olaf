import logging
from .config import config
from .bootstrap import initialize
from .logger import setup_logger

logger = logging.getLogger("olaf")
setup_logger(logger)
