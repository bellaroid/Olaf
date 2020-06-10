
import logging
from .config import config
from .logger import setup_logger

logger = logging.getLogger("olaf")
setup_logger(logger)

from .bootstrap import initialize

