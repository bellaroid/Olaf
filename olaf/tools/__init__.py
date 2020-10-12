import logging
from .config import config
from .bootstrap import initialize
from .logger import setup_logger

# Configure Olaf and Werkzeug loggers
logger = logging.getLogger("olaf")
werkzeug_logger = logging.getLogger("werkzeug")
setup_logger(logger)
setup_logger(werkzeug_logger)
