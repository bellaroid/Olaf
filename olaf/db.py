import os
import logging
import click
from pymongo import MongoClient, DESCENDING
from pymongo.errors import ServerSelectionTimeoutError

logger = logging.getLogger(__name__)

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
        self.__deletion_constraints__ = dict()
        self.__models__ = dict()

    def __iter__(self):
        return iter(self.__models__)

    def __len__(self):
        return len(self.__models__)

    def __getitem__(self, key):
        """ Return an instance of the requested model class """
        if not key in self.__models__:
            raise KeyError("Model not found in registry")
        return self.__models__[key]

    def add(self, cls):
        """ Classes wrapped around this method
        will be added to the registry.
        """
        # Handle Index and Compound Indexes creation
        from olaf.fields import BaseField
        conn = Connection()
        attrs = dir(cls)
        for attr_name in attrs:
            attr = getattr(cls, attr_name)
            if attr_name == "_compound_indexes":
                for tup_ind in attr:
                    conn.db[cls._name].create_index(
                        [(ind, DESCENDING) for ind in tup_ind], unique=True)
            if issubclass(attr.__class__, BaseField):
                if attr._unique:
                    conn.db[cls._name].create_index(attr_name, unique=True)
        # Add class to the Registry
        self.__models__[cls._name] = cls
        return cls


class ConnectionMeta(type):
    """ This class ensures there's always a single
    instance of the Connection class for each
    application instance.
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                ConnectionMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Connection(metaclass=ConnectionMeta):
    """ An instance of the Connection Client """

    def __init__(self):
        color = click.style
        logger.info("Initializing {} Connection".format(color("MongoDB", fg="white", bold=True)))
        from olaf.tools import config
        database =  config.DB_NAME
        pswd =      config.DB_PASS
        user =      config.DB_USER
        host =      config.DB_HOST
        port =      config.DB_PORT
        tout =      config.DB_TOUT
        if user and pswd:
            connstr = "mongodb://{}:{}@{}:{}/".format(user, pswd, host, port)
        elif not user and not pswd:
            connstr = "mongodb://{}:{}".format(host, port)
        else:
            raise ValueError("MongoDB user or password were not specified")
        
        # Create Client
        params = {
            "serverSelectionTimeoutMS": tout
        }

        # Activate Replicaset
        if config.DB_REPLICASET_ENABLE:
            params["replicaset"] = config.DB_REPLICASET_ID
        else:
            logger.warning("REPLICASET DISABLED. Database transactions are off.")
        
        client = MongoClient(connstr, **params)

        # Verify Connection
        try:
            client.server_info()
        except ServerSelectionTimeoutError as e:
            raise RuntimeError("Unable to connect to MongoDB: {}".format(e))

        self.cl = client
        self.db = client[database]
