from olaf.fields import BaseField, Identifier, NoPersist
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

    # The _id field should be available for all
    # models and shouldn't be overridden
    _id = Identifier()

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
            if issubclass(attr.__class__, BaseField):
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

    def __eq__(self, other):
        """ Determine if two DocSet instances
        contain exactly the same documents.
        """
        if not isinstance(other, self.__class__):
            raise TypeError(
                "Cannot compare apples with oranges "
                "(nor '{}' with  '{}')".format(self.__class__, other.__class__))
        # FIXME: Can this be done more efficiently?
        set_a = {item._id for item in self}
        set_b = {item._id for item in other}
        return set_a == set_b

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
        cursor = database.db[self._name].find(query)
        ids = [item["_id"] for item in cursor]
        return self.__class__({"_id": {"$in": ids}})

    def browse(self, ids):
        """ Given a list of ObjectIds or strs representing
        an ObjectId, return a document set with the
        corresponding elements.
        """
        items = []
        if isinstance(ids, ObjectId):
            # Handle singleton browse (OId)
            items.append(ids)
        elif isinstance(ids, str):
            # Handle singleton browse (str)
            items.append(ObjectId(ids))
        elif isinstance(ids, list):
            # Iterate over list of OId's
            for oid in ids:
                if isinstance(oid, ObjectId):
                    items.append(oid)
                elif isinstance(oid, str):
                    items.append(ObjectId(oid))
                else:
                    raise TypeError("Expected str or ObjectId, "
                                    "got {} instead".format(oid.__class__.__name__))
        else:
            raise TypeError(
                "Expected list, str or ObjectId, "
                "got {} instead".format(ids.__class__.__name__))

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
        self._implicit_save = False
        try:
            # Let each field validate its value.
            for field_name in vals.keys():
                if field_name in self._fields:
                    setattr(self, field_name, vals[field_name])

            self._save()
        except Exception:
            raise
        finally:
            self._implicit_save = True
        return

    def read(self, fields=[]):
        """ Reads all values in the set """
        result = list()
        self._cursor.rewind()
        for doc in self._cursor:
            result.append(doc)
        return result

    def unlink(self):
        """ Deletes all the documents in the set.
        Return the amount of deleted elements.
        """
        outcome = database.db[self._name].delete_many(self._query)
        return outcome.deleted_count


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
        with NoPersist(self):
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
                        if field_name == "_id":
                            continue
                        if hasattr(field, "_default"):
                            vals[field_name] = field._default
                        else:
                            vals[field_name] = None
                # Let each field validate its value.
                setattr(self, field_name, vals[field_name])

    def ensure_one(self):
        """ Ensures current set contains a single document """
        if self.count() != 1:
            raise ValueError("Expected singleton")

    def ids(self, as_strings=False):
        """ Returns a list of ObjectIds contained 
        in the current DocSet
        """
        if as_strings:
            return [str(item._id) for item in self]
        return [item._id for item in self]
