import bson
from olaf.db import Database


database = Database()


class BaseField:
    """ Base field with default initializations
    and validations. All other fields should extend
    this class.
    """

    def __init__(self, *args, **kwargs):
        self._required = kwargs.get("required", False)

    def __set__(self, instance, value):
        newvals = { "$set": { self.attr: value }}
        database.db[instance._name].update_many(instance._query, newvals)
        return None

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            instance.ensure_one()
            instance._cursor.rewind()
            item = instance._cursor.next()
            return item.get(self.attr)


class Identifier(BaseField):
    """ Field Class for storing Document ObjectIDs
    """

    def __set__(self, instance, value):
        if not isinstance(value, bson.ObjectId):
            try:
                value = bson.ObjectId(value)
            except TypeError:
                raise TypeError("Cannot convert value of type {} to ObjectId".format(type(value).__name__))
            except bson.errors.InvalidId:
                raise TypeError("The supplied value '{}' is not a valid ObjectId".format(str(value)))
        super().__set__(instance, value)


class Char(BaseField):
    """ Field Class for storing strings
    """

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._max_length = kwargs.get("max_length", 255)

    def __set__(self, instance, value):
        if not isinstance(value, str):
            try:
                value = str(value)
            except TypeError:
                raise TypeError("Cannot convert value of type {} to string".format(type(value).__name__))
        super().__set__(instance, value)


class Integer(BaseField):
    """ Field Class for storing integer numbers
    """
    def __set__(self, instance, value):
        if not isinstance(value, int):
            try:
                value = int(value)
            except ValueError:
                raise ValueError("Cannot convert '{}' to integer".format(str(value)))
        super().__set__(instance, value)
