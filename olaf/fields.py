class BaseField(object):
    """ 
    """

    _value = None

    def __init__(self, required=False, default=None):
        self._required = required
        self._default = default

    def __repr__(self):
        return "<Field {}>".format(self.__class__.__name__)

    def __set__(self, value):
        self.validate(value)
        self._value = value

    def to_python(self):
        return self._value

    def to_mongo(self):
        return self._value

    def validate(self, value):
        if value is None:
            raise ValueError("Required field got NoneType value")
        return True


class Identifier(BaseField):
    """ Field Class for storing Document IDs
    """


class Char(BaseField):
    """ Field Class for storing strings
    """
    _max_length = None

    def __init__(self, max_length=255, **kwargs):
        super().__init__(**kwargs)
        self._max_length = max_length

    def validate(self, value):
        if not isinstance(value, str):
            raise ValueError("Expected string, but got {} instead".format(
                value.__class__.__name__))
        if self._max_length:
            if len(self._value) > self._max_length:
                raise ValueError(
                    "The entered value exceeds the maximum length for this field")
        return super().validate(value)


class Integer(BaseField):
    """ Field Class for storing integer numbers
    """

    def to_python(self):
        if self._value:
            return int(self._value)

    def to_mongo(self):
        if self._value:
            return int(self._value)
