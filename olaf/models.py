from . import db
from . import fields
from . import registry
from bson import ObjectId

class RequiredError(Exception):
    pass


class DocumentSet(object):
    """ A set of documents of a certain model.
    Operations performed over the set should apply
    to each document in it.
    """

    def __init__(self, model, query=None):
        self.__documents__ = set()

        # Compute model
        if isinstance(model, str):
            self.__model__ = registry[model]
        elif isinstance(model, Model):
            self.__model__ = registry[model._name]
        else:
            raise TypeError("Model should be str or Model, but got {} instead".format(
                model.__class__.__name__))
        
        # Compute query
        if isinstance(query, dict):
            self.__query__ = query
        elif query is None:
            self.__query__ = {"_id": None}
        else:
            raise TypeError("Query should be dict or NoneType, but got {} instead".format(
                query.__class__.__name__))

    def __repr__(self):
        return "<DocumentSet {} - Length: {}>".format(self.__model__._name, len(self.__documents__))

    def __getattribute__(self, name):
        """ Try to return DocumentSet attribute in the first place.
        If not found, forward the request to the underlying model.
        If still it's not found, raises an AttributeError.
        """
        try:
            return super().__getattribute__(name)
        except AttributeError:
            try:
                return self.__model__.__getattribute__(name)
            except AttributeError:
                raise AttributeError(
                    "DocumentSet nor Document have an attribute '{}'".format(name))
            
    def count(self):
        """ Returns the amount of documents in the set
        """
        return db[self.__model__._name].count_documents(self.__query__)

    def create(self, values):
        """ Creates a new model instance and returns
        a new DocumentSet containing it
        """
        return self.__model__.create(values)

    def search(self, query):
        """ Finds documents meeting the query criteria,
        and instantiates a model for each document found.
        """
        self.__query__ = query
        docs = db[self.__model__._name].find(self.__query__, {"_id": 1})
        for doc in docs:
            self.__documents__.add(self.__model__(doc["_id"]))
        return self

    def read(self, fields=[]):
        """ Reads all values in the set
        """
        result = list()
        for doc in self.__documents__:
            result.append(doc.read(fields))
        return result


class Model(object):
    """ A Python interface to an individual
    MongoDB Document.
    """

    def __init__(self, id=None):
        self.__id__ = ObjectId()
        self.__isnew__ = True
        self.__fields__ = self.__get_fields__()
        if id is not None:
            self.__id__ = ObjectId(id)
            self.__isnew__ = False

    def __repr__(self):
        new = ""
        if self.__isnew__:
            new = "New "
        return "<{}Document {} {}>".format(new, self._name, self.__id__)

    id = fields.Identifier()

    def __get_fields__(self):
        """ Returns a dictionary with
        the model's fields.
        """
        flds = dict()
        for name in dir(self):
            attr = getattr(self, name)
            if isinstance(attr, fields.BaseField):
                flds[name] = attr
        return flds

    def create(self, values):
        """ Creates a new document
        """
        if not isinstance(values, dict):
            raise ValueError("Values must be a dictionary")
        vals = dict()
        for name, field in self.__fields__.items():
            # Validate each field
            if field._required:
                if name not in values.keys() or values.get(name, None) is None:
                    raise RequiredError(
                        "Required field '{}' in model '{}' not provided".format(name, self._name))
            if field._default:
                if name not in values.keys() or values.get(name, None) is None:
                    values[name] = field._default
            if name == "id" and values.get(name, None) is None:
                # Ignore missing ID on creation
                continue
            vals[name] = values[name]
        db[self._name].insert_one(vals)

    def read(self, fields=[]):
        """ Reads the underlying document
        """
        fields = set(fields)
        model_fields = set(self.__fields__.keys())
        if len(fields) == 0:
            fields = model_fields
        intrsc = model_fields.intersection(fields)
        result = db[self._name].find_one(
            {"_id": self.__id__}, {field: 1 for field in intrsc})
        return result

    def update(self, values):
        """ Updates the underlying document
        """
        if not isinstance(values, dict):
            raise ValueError("Values must be a dictionary")
        vals = dict()
        for name, field in self.__fields__.items():
            # Iterate over existing fields in order to discard
            # any unmatching values.
            if name == "id" and "id" in values:
                raise ValueError(
                    "You cannot update the ID of an existing document")
            vals[name] = values[name]
        db[self._name].update_one({"_id": self.id}, vals)

    def delete(self):
        """ Deletes the underlying document
        """
        db[self._name].delete_one({"_id": self.id})
        return True
