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
        from olaf.fields import BaseField, Many2many, Many2one
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
            if issubclass(attr.__class__, Many2many):
                # Look for m2m fields in the model definition
                # and create intermediate models if necessary.
                if attr._relation not in self.__models__:
                    # Import Model and ModelMeta
                    from olaf.models import Model, ModelMeta
                    # Create fields
                    rel_fld_a = Many2one(cls._name, required=True)
                    rel_fld_b = Many2one(attr._comodel_name, required=True)
                    # Extract __dict__ (all Model's attributes, methods and descriptors)
                    model_dict = dict(Model.__dict__)
                    # Inject name and fields
                    model_dict["_name"] = attr._relation
                    model_dict[attr._field_a] = rel_fld_a
                    model_dict[attr._field_b] = rel_fld_b
                    model_dict["_compound_indexes"] = [
                        (attr._field_a, attr._field_b)]
                    for tup_ind in model_dict["_compound_indexes"]:
                        conn.db[attr._relation].create_index(
                            [(ind, DESCENDING) for ind in tup_ind], unique=True)
                    # Add attribute to distinguish intermediate models from others
                    model_dict["_intermediate"] = True
                    # Create metaclass
                    mod = ModelMeta("Model", (), model_dict)
                    self.__models__[attr._relation] = mod

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
        logger.info("Initializing {} Connection".format(
            color("MongoDB", fg="white", bold=True)))
        from olaf.tools import config
        database = config.DB_NAME
        pswd = config.DB_PASS
        user = config.DB_USER
        host = config.DB_HOST
        port = config.DB_PORT
        tout = config.DB_TOUT
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
        params["replicaset"] = config.DB_REPLICASET_ID

        # Instantiate MongoClient
        client = MongoClient(connstr, **params)

        # Verify Connection
        try:
            client.server_info()
        except ServerSelectionTimeoutError as e:
            raise RuntimeError("Unable to connect to MongoDB: {}".format(e))

        self.cl = client
        self.db = client[database]


class DocumentCache():
    """ A place to store new documents that can't be persisted to
    database yet, e.g. a document related to another, where the
    latter does not exist yet in database.
    """

    def __init__(self, session=None):
        self.__queue__ = list()
        self.__session__ = session
        self.__pending__ = set()

    def append(self, op, model, oids=[], data=None):
        """
        Adds or update data on a single caché element
        """
        # Make sure opcode is valid
        if op not in ["create", "write", "delete"]:
            raise ValueError(
                "Illegal opcode '{}'. "
                "Expected 'create', 'write' or 'delete'.".format(op))

        # Avoid empty writes
        if op == "write" and not bool(data):
            return

        if op == "create":
            # Add OID to pendings, 
            # so ODM knows about them
            if isinstance(data, dict):
                self.__pending__.add(data["_id"])
            elif isinstance(data, list):
                for item in data:
                    self.__pending__.add(item["_id"])
            else:
                raise ValueError(
                    "Expected dict or list of dicts, "
                    "got {} instead".format(data.__class__.__name__))

        # Convert oids into list
        if not isinstance(oids, list):
            oids = [oids]

        self.__queue__.append((op, model, oids, data))

    def clear(self):
        """
        Wipes the entire caché
        """
        self.__queue__.clear()
        self.__pending__.clear()

    def flush(self):
        """
        Persists all elements in the caché;
        then wipes all the data in it.
        """
        conn = Connection()
        try:
            for tpl in self.__queue__:
                modname = tpl[1]
                oids = tpl[2]
                if tpl[0] == "create":
                    if isinstance(tpl[3], dict):
                        conn.db[modname].insert_one(
                            tpl[3],
                            session=self.__session__)
                        self.__pending__.remove(tpl[3]["_id"])
                    elif isinstance(tpl[3], list):    
                        conn.db[modname].insert_many(
                            tpl[3],
                            ordered=True,
                            session=self.__session__)
                        for item in tpl[3]:
                            self.__pending__.remove(item["_id"])
                    else:
                        raise ValueError(
                            "Invalid data format. "
                            "Expected dict or list of dicts, "
                            "got {} instead.".format(
                                tpl[3].__class__.__name__))
                elif tpl[0] == "write":
                    conn.db[modname].update_many(
                        {"_id": {"$in": oids}},
                        {"$set": tpl[3]},
                        session=self.__session__)
                elif tpl[0] == "delete":
                    conn.db[modname].delete_many(
                        {"_id": {"$in": oids}}, 
                        session=self.__session__)
        except Exception:
            self.clear()
            raise
        self.clear()

    def is_pending(self, oid):
        return oid in self.__pending__
