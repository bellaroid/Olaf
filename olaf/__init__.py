import logging

_logger = logging.getLogger("werkzeug")

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

from . import fields
from . import models
