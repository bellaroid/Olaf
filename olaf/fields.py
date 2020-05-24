import bson
from olaf.db import Connection, ModelRegistry

database = Connection()
registry = ModelRegistry()

class NoPersist:
    """ Allows performing field assignments
    without persisting changes into database
    """
    def __init__(self, instance):
        self.instance = instance

    def __enter__(self):
        self.instance._implicit_save = False

    def __exit__(self, type, value, traceback):
        self.instance._implicit_save = True

class BaseField:
    """ Base field with default initializations
    and validations. All other fields should extend
    this class.
    """

    def __init__(self, *args, **kwargs):
        self.attr = None    # Silence Linters
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
            count = instance.count()
            if count == 1:
                attr = self.attr if self.attr != "id" else "_id"
                instance._cursor.rewind()
                item = instance._cursor.next()
            elif count == 0:
                return
            else:
                # Call ensure_one to raise ValueError
                instance.ensure_one()
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


class RelationshipField(BaseField):
    """ Provides a set of common utilities
    for relational fields.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        comodel_name = (args[0:1] or (None,))[0]
        if comodel_name is None:
            raise ValueError("comodel_name not specified")
        self._comodel_name = comodel_name

    def _get_comodel(self):
        if self._comodel_name is None:
            raise ValueError("comodel_name not specified")
        if self._comodel_name not in registry:
            raise ValueError("comodel_name not found in registry")
        return registry[self._comodel_name]

    def _ensure_oid(self, value):
        """ Ensure the provided value is an ObjectId or a compatible string """
        if not isinstance(value, bson.ObjectId):
            from olaf.models import Model  # FIXME: Importing this here to avoid circular import
            if issubclass(value.__class__, Model):
                # The provided value is a DocSet
                value.ensure_one()
                return value._id
            try:
                value = bson.ObjectId(value)
            except TypeError:
                raise TypeError(
                    "Cannot convert value of type {} to ObjectId".format(type(value).__name__))
            except bson.errors.InvalidId:
                raise TypeError(
                    "The supplied value '{}' is not a valid ObjectId".format(str(value)))
        return value

    def _is_comodel_oid(self, oid):
        """ Ensure the provided oid exists in the co-model """
        item = registry[self._comodel_name].browse(oid)
        if item.count() == 0:
            raise ValueError(
                "The supplied ObjectId does not exist in the target model")
        return item


class Many2one(RelationshipField):
    """ Field Class for storing a representation of
    a record from a different collection or the same one
    """

    def __get__(self, instance, owner):
        """ Returns a DocSet containing a single document
        associated to the corresponding comodel and the
        requested ObjectId
        """
        value = super().__get__(instance, owner)
        if value is None or not isinstance(value, bson.ObjectId):
            return value
        cmod = self._get_comodel()
        return cmod.browse(value)

    def __set__(self, instance, value):
        if value is not None:
            _ = self._get_comodel()
            value = self._ensure_oid(value)
            self._is_comodel_oid(value)
        super().__set__(instance, value)


class One2many(RelationshipField):
    """ Field Class for storing a list
    of references to a given model
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inversed_by = (args[1:2] or (None,))[0]
        if inversed_by is None:
            raise ValueError("inversed_by not specified")
        self._inversed_by = inversed_by

    def __get__(self, instance, owner):
        if instance is None:
            return self
        instance.ensure_one()
        cmod = self._get_comodel()
        if not hasattr(cmod, self._inversed_by):
            raise AttributeError(
                "Inverse relation '{}' not found in model '{}'".format(
                    self._inversed_by, cmod._name))
        return cmod.search({self._inversed_by: instance._id})

    def __set__(self, instance, value):
        """ Sets the value of a One2many relationship

        Since x2many fields are virtual, and in order to allow a write()
        operation on this type of field without having the need of calling
        methods such as add(), remove(), clear(), and so on, assignment of 
        values must be done through the following special syntax.

        Unlike Odoo, which uses tuples identified by a number, Olaf expects
        a much more intuitive string in exchange.
        
        Odoo Syntax         | Olaf Syntax         | Description
        -----------------------------------------------------------------------------------------------------
        (0, 0,  { values }) | ('create', {v})     | Link to a new record that needs to be created with the given values dictionary
        (1, ID, { values }) | ('write', OID, {v}) | Update the linked record with id = ID (write *values* on it)
        (2, ID)             | ('purge', OID)      | Remove and delete the linked record with id = ID (calls unlink on ID, that will delete the object completely, and the link to it as well)
        (3, ID)             | ('remove', OID)     | Cut the link to the linked record with id = ID (delete the relationship between the two objects but does not delete the target object itself)
        (4, ID)             | ('add', OID)        | Link to existing record with id = ID (adds a relationship)
        (5)                 | ('clear')           | Unlink all (like using (3,ID) for all linked records)
        (6, 0, [IDs])       | ('replace', [OIDs]) | Replace the list of linked IDs (like using (5) then (4,ID) for each ID in the list of IDs)
        """
        if value is None:
            # Treat None assignment as clear
            value = ("clear",)

        if not isinstance(value, tuple):
            if value == 'clear':
                # Fix wrong singleton tuple
                value = ('clear',)
            else:
                raise TypeError(
                    "One2many field assignments must be done through tuple syntax. "
                    "Check the documentation for further details.")

        if len(value) == 0:
            raise ValueError("Empty tuple supplied for x2many assignment")

        if value[0] == "create":
            # Create a new record in the co-model
            # and assign its 'inversed_by' field to this record.
            if len(value) != 2:
                raise ValueError(
                    "Invalid tuple length for x2many create assignment")
            if not isinstance(value[1], dict):
                raise TypeError(
                    "Tuple argument #2 must be dict, got {} instead".format(
                        value[1].__class__.__name__))
            values = value[1]
            values[self._inversed_by] = instance._id
            registry[self._comodel_name].create(values)
        elif value[0] == "write":
            # Update an existing record in the co-model
            # by assigning its 'inversed_by' field to this record.
            if len(value) != 3:
                raise ValueError(
                    "Invalid tuple length for x2many write assignment")
            oid = self._ensure_oid(value[1])
            item = self._is_comodel_oid(oid)
            if not isinstance(value[2], dict):
                raise TypeError(
                    "Tuple argument #2 must be dict, got {} instead".format(
                        value[2].__class__.__name__))
            values = value[2]
            item.write(values)
        elif value[0] == "purge":
            # Delete the co-model record
            if len(value) != 2:
                raise ValueError(
                    "Invalid tuple length for x2many purge assignment")
            oid = self._ensure_oid(value[1])
            item = self._is_comodel_oid(oid)
            item.unlink()
        elif value[0] == "remove":
            # Remove the reference to this record by clearing
            # the 'inversed_by' field in the co-model record
            if len(value) != 2:
                raise ValueError(
                    "Invalid tuple length for x2many remove assignment")
            oid = self._ensure_oid(value[1])
            item = self._is_comodel_oid(oid)
            item.write({self._inversed_by: None})
        elif value[0] == "add":
            # Add a reference to this record by setting
            # the 'inversed_by' field in the co-model record
            if len(value) != 2:
                raise ValueError(
                    "Invalid tuple length for x2many add assignment")
            oid = self._ensure_oid(value[1])
            item = self._is_comodel_oid(oid)
            item.write({self._inversed_by: instance._id})
        elif value[0] == "clear":
            # Set all the references to this record to None
            if len(value) != 1:
                raise ValueError(
                    "Invalid tuple length for x2many clear assignment")
            registry[self._comodel_name].search(
                {self._inversed_by: instance._id}).write(
                    {self._inversed_by: None})
        elif value[0] == "replace":
            # Perform a clear and then add each element of the supplied list
            if len(value) != 2:
                raise ValueError(
                    "Invalid tuple length for x2many clear assignment")
            if not isinstance(value[1], list):
                raise TypeError(
                    "Tuple argument #2 must be list, got {} instead".format(
                        value[1].__class__.__name__))

            comodel = self._get_comodel()
            comodel.search({self._inversed_by: instance._id}
                           ).write({self._inversed_by: None})
            comodel.browse(value[1]).write({self._inversed_by: instance._id})
        else:
            raise ValueError(
                "Tuple #1 argument must be 'create', 'write', 'purge', 'remove', 'add', 'clear' or 'replace'")


class Many2many(RelationshipField):
    """ A many2many relationship works by creating an intermediate
    model with two Many2one fields, each one pointing to one of the
    involved models, resulting in a One2many field in  ends.
    """

    def _ensure_intermediate_model(self, instance):
        """ Declare intermediate model exists 
        """
        cmod = self._get_comodel()
        # Get names
        comodel_a_name = instance._name
        comodel_b_name = cmod._name
        # Get normalized names
        comodel_a_norm = comodel_a_name.replace(".", "_")
        comodel_b_norm = comodel_b_name.replace(".", "_")
        rel_name = "{}_{}_rel".format(comodel_a_norm, comodel_b_norm)
        # Compose field names
        rel_fld_a_name = "{}_id".format(comodel_a_norm)
        rel_fld_b_name = "{}_id".format(comodel_b_norm)

        if rel_name not in registry.__models__:
            # Import Model and ModelMeta
            from olaf.models import Model, ModelMeta
            # Create fields
            rel_fld_a = Many2one(comodel_a_name)
            rel_fld_b = Many2one(comodel_b_name)
            # Extract __dict__ (all Model's attributes, methods and descriptors)
            model_dict = dict(Model.__dict__)
            # Inject name and fields
            model_dict["_name"] = rel_name
            model_dict[rel_fld_a_name] = rel_fld_a
            model_dict[rel_fld_b_name] = rel_fld_b
            # Create metaclass
            mod = ModelMeta("Model", (), model_dict)
            registry.add(mod)

        return rel_name, comodel_b_name, rel_fld_a_name, rel_fld_b_name

    def __get__(self, instance, owner):
        """ Search for relationships in the intermediate model
        containing references to the instance id, and with these
        results, browse the comodel for matches.
        """
        if instance is None:
            return self
        instance.ensure_one()
        rel_name, comodel_b_name, rel_fld_a_name, rel_fld_b_name = self._ensure_intermediate_model(
            instance)
        # Perform search and browse
        rels = registry[rel_name].search({rel_fld_a_name: instance._id})
        return registry[comodel_b_name].browse([getattr(rel, rel_fld_b_name)._id for rel in rels])

    def __set__(self, instance, value):
        """ A patched version of the O2M __set__ descriptor.
        """
        if value is None:
            return super().__set__(instance, value)

        if not isinstance(value, tuple):
            if value == 'clear':
                # Fix wrong singleton tuple
                value = ('clear',)
            else:
                raise TypeError(
                    "Many2many field assignments must be done through tuple syntax. "
                    "Check the documentation for further details.")

        rel_name, _, rel_fld_a_name, rel_fld_b_name = self._ensure_intermediate_model(
            instance)

        if value[0] == "create":
            # Create a new record in the co-model and add virtual relationship
            if len(value) != 2:
                raise ValueError(
                    "Invalid tuple length for x2many create assignment")
            if not isinstance(value[1], dict):
                raise TypeError(
                    "Tuple argument #2 must be dict, got {} instead".format(
                        value[1].__class__.__name__))
            values = value[1]
            rec = registry[self._comodel_name].create(values)
            registry[rel_name].create(
                {rel_fld_a_name: instance._id, rel_fld_b_name: rec._id})
        elif value[0] == "write":
            # Update an existing record in the co-model
            # by assigning its 'inversed_by' field to this record.
            if len(value) != 3:
                raise ValueError(
                    "Invalid tuple length for x2many write assignment")
            oid = self._ensure_oid(value[1])
            item = self._is_comodel_oid(oid)
            if not isinstance(value[2], dict):
                raise TypeError(
                    "Tuple argument #2 must be dict, got {} instead".format(
                        value[2].__class__.__name__))
            values = value[2]
            item.write(values)
        elif value[0] == "purge":
            # Delete the co-model record
            if len(value) != 2:
                raise ValueError(
                    "Invalid tuple length for x2many purge assignment")
            oid = self._ensure_oid(value[1])
            item = self._is_comodel_oid(oid)
            item.unlink()
            registry[rel_name].search({rel_fld_b_name: oid}).unlink()
        elif value[0] == "remove":
            # Remove the reference to this record by clearing
            # the 'inversed_by' field in the co-model record
            if len(value) != 2:
                raise ValueError(
                    "Invalid tuple length for x2many remove assignment")
            oid = self._ensure_oid(value[1])
            item = self._is_comodel_oid(oid)
            registry[rel_name].search({rel_fld_b_name: oid}).unlink()
        elif value[0] == "add":
            # Add a reference to this record by setting
            # the 'inversed_by' field in the co-model record
            if len(value) != 2:
                raise ValueError(
                    "Invalid tuple length for x2many add assignment")
            oid = self._ensure_oid(value[1])
            item = self._is_comodel_oid(oid)
            registry[rel_name].create(
                {rel_fld_a_name: instance._id, rel_fld_b_name: item._id})
        elif value[0] == "clear":
            # Set all the references to this record to None
            if len(value) != 1:
                raise ValueError(
                    "Invalid tuple length for x2many clear assignment")
            registry[rel_name].search({rel_fld_a_name: instance._id}).unlink()
        elif value[0] == "replace":
            # Perform a clear and then add each element of the supplied list
            if len(value) != 2:
                raise ValueError(
                    "Invalid tuple length for x2many clear assignment")
            if not isinstance(value[1], list):
                raise TypeError(
                    "Tuple argument #2 must be list, got {} instead".format(
                        value[1].__class__.__name__))

            registry[rel_name].search({rel_fld_a_name: instance._id}).unlink()
            for oid in value[1]:
                oid = self._ensure_oid(oid)
                _ = self._is_comodel_oid(oid)
                registry[rel_name].create(
                    {rel_fld_a_name: instance._id, rel_fld_b_name: oid})
        else:
            raise ValueError(
                "Tuple #1 argument must be 'create', 'write', 'purge', 'remove', 'add', 'clear' or 'replace'")
