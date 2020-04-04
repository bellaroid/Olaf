from .db import ModelRegistry
import logging

_logger = logging.getLogger(__name__)

def get_database():
    """
    Returns a connection to the MongoDB
    """
    from pymongo import MongoClient
    database = "olaf"
    host = "localhost"
    port = "27017"
    client = MongoClient('mongodb://{}:{}/'.format(host, port))
    _logger.info("Initialized MongoDB Connection")
    return client[database]


db = get_database()
registry = ModelRegistry()

from . import fields
from . import models
