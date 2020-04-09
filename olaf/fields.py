from bson import ObjectId


class BaseField(object):
    """ Base field with default initializations
    and validations. All other fields should extend
    this class.
    """

    def __init__(self, required=False, default=None):
        self.__required__ = required
        self.__default__ = self.__value__ = default

    def __set__(self, inst, value):
        self.__value__ = value

    def validate(self, value):
        return


class Identifier(BaseField):
    """ Field Class for storing Document ObjectIDs
    """

    def __init__(self):
        self.__default__ = ObjectId()
        self.__required__ = True

    def __set__(self, inst, value):
        if isinstance(value, ObjectId):
            self.__value__ = value
        elif isinstance(value, str):
            self.__value__ = ObjectId(value)
        else:
            raise ValueError("Field Identifier requires either a str or an ObjectID, got {} instead".format(
                value.__class__.__name__))


class Char(BaseField):
    """ Field Class for storing strings
    """

    def __init__(self, max_length=255, **kwargs):
        super().__init__(**kwargs)
        self.__max_length__ = max_length

    def __set__(self, inst, value):
        self.__value__ = str(value)

    def validate(self, value):
        strfied = None
        try:
            strfied = str(value)
        except Exception:
            return "Unable to convert value of type {} into string".format(value.__class__.__name__)
        if self.__max_length__:
            if len(strfied) > self.__max_length__:
                return "The entered value exceeds the maximum length for this field"
        return super().validate(value)


class Integer(BaseField):
    """ Field Class for storing integer numbers
    """

    def __set__(self, inst, value):
        self.__value__ = int(value)

    def validate(self, value):
        try:
            value = int(value)
        except ValueError:
            return "Expected integer or numeric string, got {} instead".format(value.__class__.__name__)
        return super().validate(value)
