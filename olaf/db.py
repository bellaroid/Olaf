import os
from pymongo import MongoClient, DESCENDING
from pymongo.errors import ServerSelectionTimeoutError

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
        # Handle Index and Compound Indexes creation
        from olaf.fields import BaseField
        conn = Connection()
        attrs = dir(cls)
        for attr_name in attrs:
            attr = getattr(cls, attr_name)
            if attr_name == "_compound_indexes":
                for tup_ind in attr:
                    conn.db[cls._name].create_index([(ind, DESCENDING) for ind in tup_ind], unique=True)
            if issubclass(attr.__class__, BaseField):
                if attr._unique:
                    conn.db[cls._name].create_index(attr_name, unique=True)
        # Add Instance to the Registry
        self.__models__[cls._name] = cls()
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
        database = os.getenv("MONGODB_NAME", "olaf")
        pswd = os.getenv("MONGODB_PASS", None)
        user = os.getenv("MONGODB_USER", None)
        host = os.getenv("MONGODB_HOST", "localhost")
        port = os.getenv("MONGODB_PORT", "27017")
        tout = os.getenv("MONGODB_TIMEOUT", 2000)
        if user and pswd:
            connstr = "mongodb://{}:{}@{}:{}/".format(user, pswd, host, port)
        elif not user and not pswd:
            connstr = "mongodb://{}:{}".format(host, port)
        else:
            raise ValueError("MongoDB user or password were not specified")
        # Create Client
        client = MongoClient(connstr, serverSelectionTimeoutMS=tout)
        
        # Verify Connection
        try:
            client.server_info()
        except ServerSelectionTimeoutError as e:
            raise RuntimeError("Unable to connect to MongoDB: {}".format(e))
    
        self.cl = client
        self.db = client[database]
