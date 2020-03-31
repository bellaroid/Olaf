class BaseField():
    _value = None

    def __repr__(self):
        return self._value

    def to_python(self):
        return self._value

    def to_mongo(self):
        return self._value
    

class Identifier(BaseField):
    """ Field Class for storing Document IDs
    """

    
    

class Char(BaseField):
    """ Field Class for storing strings
    """
    _max_length = None

    def __init__(self, max_length=255):
        self._max_length = max_length