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
        from olaf.fields import BaseField
        conn = Connection()
        attrs = dir(cls)
        
        # Create collection if not present
        if cls._name not in conn.db.list_collection_names():
            conn.db.create_collection(cls._name)
        
        # Handle Index and Compound Indexes creation
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


class DocumentCacheMeta(type):
    """ This class ensures there's always a single
    instance of the DocumentCache class for each
    application instance.
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                DocumentCacheMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class DocumentCache(metaclass=DocumentCacheMeta):
    """ A place to store new documents that can't be persisted to
    database yet, e.g. a document related to another, where the
    latter does not exist yet in database.
    """
    def __init__(self, session=None):
        self.__data__ = dict()
        self.__session__ = session

    def __iter__(self):
        return iter(self.__data__)

    def __len__(self):
        return len(self.__data__)

    def __getitem__(self, key):
        if not key in self.__data__:
            raise KeyError("Key '{}' not found in caché".format(key))
        return self.__data__[key]

    def push(self, model, oid, data):
        """
        Adds or update data on a single caché element
        """
        # Initialize model dictionary if it's not already.
        if not model in self.__data__:
            self.__data__[model] = dict()

        # Initialize oid dictionary if it's not already.
        if not oid in self.__data__[model]:
            self.__data__[model][oid] = dict()

        # Update data
        self.__data__[model][oid].update(data)
    
    def pop(self, model, oids):
        """
        Removes one or multiple elements from
        the caché.
        """
        if not isinstance(oids, list):
            oids = [oids]
        for oid in oids:
            self.__data__[model].pop(oid, None)

    def clear(self):
        """
        Wipes the entire caché
        """
        self.__data__.clear()

    def persist(self, model, oids, session=None):
        """
        Persists to database one or many caché elements;
        then pops the elements from it.
        """
        conn = Connection()
        if not isinstance(oids, list):
            oids = [oids]
        for oid in oids:
            if oid in self.__data__[model]:
                data = self.__data__[model][oid]
                conn.db[model].update_one(
                    {"_id": oid}, 
                    {"$set": data}, 
                    session=session, 
                    upsert=True)
        self.pop(model, oids)

    def flush(self, session=None):
        """
        Persists all elements in the caché;
        then wipes all the data in it.
        """
        conn = Connection()
        for model, dict_oids in self.__data__.items():
            for oid, data in dict_oids.items():
                conn.db[model].update_one(
                    {"_id": oid},
                    {"$set": data}, 
                    session=session, 
                    upsert=True)
        self.clear()
