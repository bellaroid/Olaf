import os
from pymongo import MongoClient


class ModelRegistryMeta(type):
    """ This class ensures there's always a single
    instance of the Model Registry class along the entire
    application. 
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                ModelRegistryMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class ModelRegistry(metaclass=ModelRegistryMeta):
    """ A registry that keeps track of all the 
    model classes available in the application
    environment.
    """

    def __init__(self):
        self.__models__ = dict()

    def __iter__(self):
        return iter(self.__models__)

    def __len__(self):
        return len(self.__models__)

    def __getitem__(self, key):
        if not key in self.__models__:
            raise KeyError("Model not found in registry")
        return self.__models__[key]

    def add(self, cls):
        """ Classes wrapped around this method
        will be added to the registry.
        """
        self.__models__[cls._name] = cls
        return cls


class DatabaseMeta(type):
    """ This class ensures there's always a single
    instance of the Database class along the entire
    application. 
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                DatabaseMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Database(metaclass=DatabaseMeta):
    """ An instance of the Database Client """

    def __init__(self):
        database = os.getenv("MONGODB_NAME", "olaf")
        pswd = os.getenv("MONGODB_PASS", None)
        user = os.getenv("MONGODB_USER", None)
        host = os.getenv("MONGODB_HOST", "localhost")
        port = os.getenv("MONGODB_PORT", "27017")
        if not user and not pswd:
            # Connect using simplified syntax
            client = MongoClient('mongodb://{}:{}/'.format(host, port))
        else:
            # Connect using full syntax
            client = MongoClient(
                'mongodb://{}:{}@{}:{}/'.format(user, pswd, host, port))
        self.cl = client
        self.db = client[database]
