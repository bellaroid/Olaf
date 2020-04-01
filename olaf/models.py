from . import db
from . import fields


class RequiredError(Exception):
    pass


class Model(object):
    """ 
    """
    id = fields.Identifier()

    @classmethod
    def fields(cls):
        """ Returns a dictionary with
        the model's fields.
        """
        flds = dict()
        for name in dir(cls):
            attr = getattr(cls, name)
            if not name.startswith('__') and \
                not callable(attr) and \
                    isinstance(attr, fields.BaseField):
                flds[name] = attr
        return flds

    @classmethod
    def create(cls, values):
        if not isinstance(values, dict):
            raise ValueError("Values must be a dictionary")
        fields = cls.fields()
        vals = dict()
        for name, field in fields.items():
            # Validate each field
            if field._required:
                if name not in values.keys() or values.get(name, None) is None:
                    raise RequiredError(
                        "Required field '{}' in model '{}' not provided".format(name, cls.__name__))
            if field._default:
                if name not in values.keys() or values.get(name, None) is None:
                    values[name] = field._default
            if name == "id" and values.get(name, None) is None:
                # Ignore missing ID on creation
                continue
            vals[name] = values[name]
        db[cls.__name__].insert_one(vals)
