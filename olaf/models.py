from . import fields
from . import registry
from bson import ObjectId
from olaf.db import Database

db = Database()


class ModelMeta(type):
    """ This class defines the behavior of 
    all model classes.

    An instance of a model is always a set
    of documents. Documents should have no
    representation. If we'd like to work
    with a single object, we have to do so
    through a set of a single document.
    """


class Model(metaclass=ModelMeta):
    """ This is just a proxy class so model
    classes can extend from it and not from
    ModelMeta using the metaclass parameter.
    """

    # The id field should be available for all
    # models and shouldn't be overridden
    id = fields.Identifier()

    # Names should not contain dots
    _name = None

    def __init__(self, query):
        self._query = query
        self._count = db.client[self._name].count_documents(self._query)
        self._cursor = db.client[self._name].find(query)

    def __repr__(self):
        return "<DocSet {} - {} items>".format(self._name, self.count())

    def __iter__(self):
        self._cursor.__iter__()
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

    def count(self):
        """ Return the amount of documents in the current set """
        return self._count

    def read(self, fields=[]):
        """ Reads all values in the set
        """
        result = list()
        for doc in self._cursor:
            result.append(doc.read(fields))
        return result
