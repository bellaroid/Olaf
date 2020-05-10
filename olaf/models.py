from olaf.fields import BaseField, Identifier
from olaf.db import Database
from bson import ObjectId


database = Database()


class ModelMeta(type):
    """ This class defines the behavior of
    all model classes.

    An instance of a model is always a set
    of documents. Documents should have no
    representation. If we'd like to work
    with a single object, we have to do so
    through a set of a single document.
    """

    def __new__(mcs, cls, bases, dct):
        for k, v in dct.items():
            if isinstance(v, BaseField):
                dct[k].attr = k
        return super().__new__(mcs, cls, bases, dct)


class Model(metaclass=ModelMeta):
    """ This is a proxy class so model
    classes can extend from here and not from
    ModelMeta and therefore using the metaclass
    parameter.
    """

    # The _name attribute is required for each
    # model definition.
    _name = None

    # The id field should be available for all
    # models and shouldn't be overridden
    id = Identifier()

    def __init__(self, query=None):
        # Ensure _name attribute definition on child
        if (self._name is None):
            raise ValueError(
                "Model {} attribute '_name' was not defined".format(
                    self.__class__.__name__))
        # Create a list of the fields within this model
        cls = self.__class__
        fields = dict()
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, BaseField):
                fields[attr_name] = attr
        self._fields = fields
        # Set default query
        self._query = {"_id": "-1"}
        if query is not None:
            self._query = query
        self._buffer = dict()
        self._implicit_save = True
        self._cursor = database.db[self._name].find(query)

    def __repr__(self):
        return "<DocSet {} - {} items>".format(self._name, self.count())

    def __iter__(self):
        self._cursor.rewind()
        return self

    def __next__(self):
        try:
            document = self._cursor.next()
        except StopIteration:
            self._cursor.rewind()
            raise
        return self.__class__({"_id": document["_id"]})

    def search(self, query):
        """ Return a new set of documents """
        cursor = database.db[self._name].find(query, {"_id": 1})
        ids = [item["_id"] for item in cursor]
        return self.__class__({"_id": {"$in": ids}})

    def browse(self, *args):
        """ Given a set of ObjectIds or strs representing
        an ObjectId, return a document set with the
        corresponding elements.
        """
        # Handle single list parameter
        if len(args) == 1 and isinstance(args[0], list):
            args = args[0]

        # Iterate over arguments
        items = []
        for arg in args:
            if not isinstance(arg, ObjectId):
                items.append(ObjectId(arg))
        return self.__class__({"_id": {"$in": items}})

    def count(self):
        """ Return the amount of documents in the current set """
        return database.db[self._name].count_documents(self._query)

    def create(self, vals):
        self.validate(vals)
        new_id = database.db[self._name].insert_one(self._buffer).inserted_id
        self._buffer.clear()
        return self.__class__({"_id": new_id})

    def write(self, vals):
        """ Write values to the documents in the current set"""
        self.validate(vals)
        database.db[self._name].update_many(self._query, self._buffer)
        self._buffer.clear()
        return

    def read(self, fields=[]):
        """ Reads all values in the set """
        result = list()
        self._cursor.rewind()
        for doc in self._cursor:
            result.append(doc)
        return result

    def _save(self):
        """ Write values in buffer to database and clear it.
        """
        database.db[self._name].update_many(
            self._query, {"$set": self._buffer})
        self._buffer.clear()
        return

    def validate(self, vals):
        """ Ensure a given dict of values passes all
        required field validations for this model
        """
        self._implicit_save = False
        try:
            # Check each model field
            for field_name, field in self._fields.items():
                # If value is not present among vals
                if field_name not in vals:
                    # Check if field is marked as required
                    if field._required:
                        # Check for a default value
                        if hasattr(field, "_default"):
                            vals[field_name] = field._default
                        else:
                            raise ValueError(
                                "Missing value for required field '{}'".format(field_name))
                    else:
                        # Value not present and not required
                        if field_name == "id":
                            continue
                        if hasattr(field, "_default"):
                            vals[field_name] = field._default
                        else:
                            vals[field_name] = None
                # Let each field validate its value.
                setattr(self, field_name, vals[field_name])
        except Exception:
            self._implicit_save = True
            raise

    def ensure_one(self):
        """ Ensures current set contains a single document """
        if self.count() != 1:
            raise ValueError("Expected singleton")
