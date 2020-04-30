from bson import ObjectId


class BaseField:
    """ Base field with default initializations
    and validations. All other fields should extend
    this class.
    """

    def __init__(self, *args, **kwargs):
        self._required = kwargs.get("required", False)

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            return instance.__dict__.get(self.attr, None)


class Identifier(BaseField):
    """ Field Class for storing Document ObjectIDs
    """

    def __set__(self, instance, value):
        if value < 1:
            raise ValueError("{}.{} can't be negative".format(
                instance.__class__.__name__, self.attr))
        else:
            instance.__dict__[self.attr] = value


class Char(BaseField):
    """ Field Class for storing strings
    """

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._max_length = kwargs.get("max_length", 255)

    def __set__(self, instance, value):
        if value < 1:
            raise ValueError("{}.{} can't be negative".format(
                instance.__class__.__name__, self.attr))
        else:
            instance.__dict__[self.attr] = value


class Integer(BaseField):
    """ Field Class for storing integer numbers
    """

    def __set__(self, instance, value):
        if value < 1:
            raise ValueError("{}.{} can't be negative".format(
                instance.__class__.__name__, self.attr))
        else:
            instance.__dict__[self.attr] = value
