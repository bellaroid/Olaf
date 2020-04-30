from olaf.fields import BaseField, Identifier
from olaf.db import Database
from bson import ObjectId
import copy

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

    # The id field should be available for all
    # models and shouldn't be overridden
    id = Identifier()

    def __init__(self, query):
        self._data = dict()
        self._query = query
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
        return self.__class__(query)

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
        new_id = database.db[self._name].insert_one(vals).inserted_id
        return self.__class__({"_id": new_id})

    def write(self, vals):
        """ Write values to the documents in the current set"""
        database.db[self._name].update_many(self._query, vals)

    def read(self, fields=[]):
        """ Reads all values in the set """
        result = list()
        self._cursor.rewind()
        for doc in self._cursor:
            result.append(doc)
        return result

    def ensure_one(self):
        """ Ensures current set contains a single document """
        if self.count() != 1:
            raise ValueError("Expected Singleton")