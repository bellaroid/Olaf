import bson
from olaf.db import Database, ModelRegistry

database = Database()
registry = ModelRegistry()


class BaseField:
    """ Base field with default initializations
    and validations. All other fields should extend
    this class.
    """

    def __init__(self, *args, **kwargs):
        self._required = kwargs.get("required", False)
        if "default" in kwargs:
            self._default = kwargs["default"]

    def __set__(self, instance, value):
        if value is None and self._required:
            raise ValueError("Field {} is required".format(self.attr))
        instance._buffer[self.attr] = value
        if getattr(instance, "_implicit_save", True):
            instance._save()
        return None

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            instance.ensure_one()
            attr = self.attr if self.attr != "id" else "_id"
            instance._cursor.rewind()
            item = instance._cursor.next()
            return item.get(attr)


class Identifier(BaseField):
    """ Field Class for storing Document ObjectIDs
    """
    def __set__(self, instance, value):
        raise ValueError("Identifier field is read-only")


class Char(BaseField):
    """ Field Class for storing strings
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        max_length = kwargs.get("max_length", 255)
        if not isinstance(max_length, int):
            raise TypeError("Parameter max_length must be integer, got {} instead".format(
                max_length.__class__.__name__))
        self._max_length = max_length

    def __set__(self, instance, value):
        if value is not None:
            if not isinstance(value, str):
                try:
                    value = str(value)
                except TypeError:
                    raise TypeError(
                        "Cannot convert value of type {} to string".format(type(value).__name__))
            if len(value) > self._max_length:
                raise ValueError("Value {} exceeds maximum length of {}".format(
                    value, self._max_length))
        super().__set__(instance, value)


class Integer(BaseField):
    """ Field Class for storing integer numbers
    """

    def __set__(self, instance, value):
        if value is not None:
            if not isinstance(value, int):
                try:
                    value = int(value)
                except ValueError:
                    raise ValueError(
                        "Cannot convert '{}' to integer".format(str(value)))
        super().__set__(instance, value)


class Many2one(BaseField):
    """ Field Class for storing a representation of
    a record from a different collection or the same one
    """

    def __init__(self, *args, **kwargs):
        super().__init__()
        comodel_name = args[0] if len(args) > 0 else None
        if comodel_name is None:
            raise ValueError("comodel_name not specified")
        self._comodel_name = comodel_name

    def _check_comodel(self):
        if self._comodel_name is None:
            raise ValueError("comodel_name not specified")
        if self._comodel_name not in registry:
            raise ValueError("comodel_name not found in registry")

    def __get__(self, instance, owner):
        """ Returns a DocSet containing a single document
        associated to the corresponding comodel and the
        requested ObjectId
        """
        if instance is None:
            return self
        self._check_comodel()
        value = super().__get__(instance, owner)
        if value is None:
            return value
        return registry[self._comodel_name].browse(value)

    def __set__(self, instance, value):
        if value is not None:
            self._check_comodel()
            if not isinstance(value, bson.ObjectId):
                try:
                    value = bson.ObjectId(value)
                except TypeError:
                    raise TypeError(
                        "Cannot convert value of type {} to ObjectId".format(type(value).__name__))
                except bson.errors.InvalidId:
                    raise TypeError(
                        "The supplied value '{}' is not a valid ObjectId".format(str(value)))

            # At this point value is valid ObjectId.
            # Make sure referenced record exists in
            # target collection before persisting.
            if database.db[self._comodel_name].find_one({"_id": value}) is None:
                raise ValueError(
                    "The supplied ObjectId does not exist in the target model")

        super().__set__(instance, value)
