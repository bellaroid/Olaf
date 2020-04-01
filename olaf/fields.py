class BaseField(object):
    """ 
    """

    _value = None

    def __init__(self, required=False, null=True, default=None):
        self._required = required
        self._null = null
        self._default = default
        

    # def __repr__(self):
    #     return self._value

    def to_python(self):
        return self._value

    def to_mongo(self):
        return self._value
    
class Identifier(BaseField):
    """ Field Class for storing Document IDs
    """
    def __init__(self, *args, max_length=255, **kwargs):
        super().__init__(*args, **kwargs)

class Char(BaseField):
    """ Field Class for storing strings
    """
    _max_length = None

    def __init__(self, *args, max_length=255, **kwargs):
        super().__init__(*args, **kwargs)
        self._max_length = max_length