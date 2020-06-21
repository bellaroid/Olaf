from olaf.fields import BaseField, Identifier, NoPersist, RelationalField, One2many, Many2one, Many2many
from olaf.db import Connection
from bson import ObjectId
from olaf import registry


conn = Connection()


class DeletionConstraintError(BaseException):
    pass


class ModelMeta(type):
    """ This class defines the behavior of
    all model classes.

    An instance of a model is always a set
    of documents. Documents should have no
    representation. If we'd like to work
    with a single object, we have to do so
    through a set of a single document.
    """

    def __new__(mcs, cls, bases, dct):
        for k, v in dct.items():
            if isinstance(v, BaseField):
                dct[k].attr = k
        return super().__new__(mcs, cls, bases, dct)


class Model(metaclass=ModelMeta):
    """ This is a proxy class so model
    classes can extend from here and not from
    ModelMeta and therefore using the metaclass
    parameter.
    """

    # The _name attribute is required for each
    # model definition.
    _name = None

    # The _id field should be available for all
    # models and shouldn't be overridden
    _id = Identifier()

    def __init__(self, environment, query=None):
        # Ensure _name attribute definition on child
        if (self._name is None):
            raise ValueError(
                "Model {} attribute '_name' was not defined".format(
                    self.__class__.__name__))
        # Create a list of the fields within this model
        cls = self.__class__
        fields = dict()
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if issubclass(attr.__class__, BaseField):
                fields[attr_name] = attr
        self.env = environment
        self._fields = fields
        # Set default query
        self._query = {"$expr": {"$eq": [0, 1]}}
        if query is not None:
            self._query = query
        self._buffer = dict()
        self._implicit_save = True
        self._cursor = conn.db[self._name].find(
            self._query, session=self.env.session)

    def __repr__(self):
        return "<DocSet {} - {} items>".format(self._name, self.count())

    def __eq__(self, other):
        """ Determine if two DocSet instances
        contain exactly the same documents.
        """
        if not isinstance(other, self.__class__):
            raise TypeError(
                "Cannot compare apples with oranges "
                "(nor '{}' with  '{}')".format(self.__class__, other.__class__))
        # FIXME: Can this be done more efficiently?
        set_a = {item._id for item in self}
        set_b = {item._id for item in other}
        return set_a == set_b

    def __iter__(self):
        self._cursor.rewind()
        return self

    def __next__(self):
        try:
            document = self._cursor.next()
        except StopIteration:
            self._cursor.rewind()
            raise
        return self.__class__(self.env, {"_id": document["_id"]})

    def __bool__(self):
        return self.count() > 0

    def search(self, query):
        """ Return a new set of documents """
        cursor = conn.db[self._name].find(query, session=self.env.session)
        ids = [item["_id"] for item in cursor]
        return self.__class__(self.env, {"_id": {"$in": ids}})

    def browse(self, ids):
        """ Given a list of ObjectIds or strs representing
        an ObjectId, return a document set with the
        corresponding elements.
        """
        items = []
        if isinstance(ids, ObjectId):
            # Handle singleton browse (OId)
            items.append(ids)
        elif isinstance(ids, str):
            # Handle singleton browse (str)
            items.append(ObjectId(ids))
        elif isinstance(ids, list):
            # Iterate over list of OId's
            for oid in ids:
                if isinstance(oid, ObjectId):
                    items.append(oid)
                elif isinstance(oid, str):
                    items.append(ObjectId(oid))
                else:
                    raise TypeError("Expected str or ObjectId, "
                                    "got {} instead".format(oid.__class__.__name__))
        else:
            raise TypeError(
                "Expected list, str or ObjectId, "
                "got {} instead".format(ids.__class__.__name__))

        return self.__class__(self.env, {"_id": {"$in": items}})

    def count(self):
        """ Return the amount of documents in the current set """
        return conn.db[self._name].count_documents(self._query, session=self.env.session)

    def create(self, vals):
        for field in vals.keys():
            if field in self._fields and (
                    isinstance(self._fields[field], One2many) or
                    isinstance(self._fields[field], Many2many)):
                raise ValueError(
                    "Cannot assign value to {} during creation".format(field))
        self.validate(vals)
        new_id = conn.db[self._name].insert_one(
            self._buffer, session=self.env.session).inserted_id
        self._buffer.clear()
        return self.__class__(self.env, {"_id": new_id})

    def write(self, vals):
        """ Write values to the documents in the current set"""
        with NoPersist(self):
            try:
                # Let each field validate its value.
                for field_name in vals.keys():
                    if field_name in self._fields:
                        if field_name != "_id":
                            setattr(self, field_name, vals[field_name])
                        else:
                            raise ValueError(
                                "'_id' field is readonly once document has been persisted")
            except Exception:
                raise
            self._save()

    def read(self, fields=[]):
        """ Returns a list of dictionaries representing
        each document in the set. The optional parameter fields
        allows to specify which field values should be retrieved from
        database. If omitted, all fields will be read. This method also
        renders the representation of relational fields (Many2one and x2many).
        """
        if len(fields) == 0:
            fields = self._fields.keys()
        cache = dict()
        # By calling the list constructor on a PyMongo cursor we retrieve all the records
        # in a single call. This is faster but may take lots of memory.
        data = list(conn.db[self._name].find(
            self._query, {field: 1 for field in fields}, session=self.env.session))
        for field in fields:
            if issubclass(self._fields[field].__class__, RelationalField):
                # Create a caché dict with the representation
                # value of each related document in the dataset
                represent = self._fields[field]._represent
                if isinstance(self._fields[field], Many2one):
                    # Many2one Prefetch
                    related_ids = [item[field]
                                   for item in data if item[field] is not None]
                    rels = list(conn.db[self._fields[field]._comodel_name].find(
                        {"_id": {"$in": related_ids}}, {represent: 1}, session=self.env.session))
                    related_docs = {rel["_id"]: (
                        rel["_id"], rel[represent]) for rel in rels}
                elif isinstance(self._fields[field], One2many):
                    # One2many Prefetch
                    inversed_by = self._fields[field]._inversed_by
                    related_ids = [item["_id"] for item in data]
                    # Retrieve all the records in the co-model for the current
                    # field that are related to any of the oids in the dataset
                    rels = list(conn.db[self._fields[field]._comodel_name].find(
                        {inversed_by: {"$in": related_ids}}, {
                            represent: 1, inversed_by: 1},
                        session=self.env.session))
                    # Build dictionary with the model record oid as key
                    # and a list of tuples with its co-model relations as value.
                    related_docs = dict()
                    for rel in rels:
                        if rel[inversed_by] not in related_docs:
                            related_docs[rel[inversed_by]] = list()
                        related_docs[rel[inversed_by]].append(
                            (rel["_id"], rel[represent]))
                elif isinstance(self._fields[field], Many2many):
                    # Many2many Prefetch
                    related_ids = [item["_id"] for item in data]
                    rel_model_name = self._fields[field]._relation
                    field_a = self._fields[field]._field_a
                    field_b = self._fields[field]._field_b
                    rels_int = list(conn.db[rel_model_name].find(
                        {field_a: {"$in": related_ids}}, session=self.env.session))
                    rels_rep = list(conn.db[self._fields[field]._comodel_name].find(
                        {"_id": {"$in": [rel[field_b]
                                         for rel in rels_int]}}, {represent: 1},
                        session=self.env.session))
                    rels_rep_dict = {rel["_id"]: rel[represent]
                                     for rel in rels_rep}
                    rels_dict = dict()
                    for rel in rels_int:
                        if rel[field_a] not in rels_dict:
                            rels_dict[rel[field_a]] = list()
                        rels_dict[rel[field_a]].append(
                            rel[field_b])

                    related_docs = dict()
                    for oid, rels in rels_dict.items():
                        if oid not in related_docs:
                            related_docs[oid] = list()
                        for rel in rels:
                            related_docs[oid].append(
                                (rel, rels_rep_dict[rel]))

                # Add relations to the caché dictionary
                cache[field] = related_docs

        result = list()
        # Iterate over data
        for dictitem in data:
            doc = dict()
            for field in fields:
                field_inst = self._fields[field]
                if field_inst._exclude:
                    continue
                if issubclass(field_inst.__class__, RelationalField):
                    if isinstance(field_inst, Many2one):
                        # Get Many2one representation from caché
                        value = dictitem.get(field, None)
                        doc[field] = cache[field].get(value, None)
                    elif isinstance(field_inst, One2many) or isinstance(field_inst, Many2many):
                        # Get x2many representation from caché
                        doc[field] = cache[field].get(dictitem["_id"], list())
                else:
                    doc[field] = dictitem[field]
            result.append(doc)
        return result

    def unlink(self):
        """ Deletes all the documents in the set.
        Return the amount of deleted elements.
        """
        ids = self.ids()
        if self._name in registry.__deletion_constraints__:
            for constraint in registry.__deletion_constraints__[self._name]:
                mod, fld, cons = constraint
                related = self.env[mod].search({fld: {"$in": ids}})
                if cons == "RESTRICT":
                    if related.count() > 0:
                        raise DeletionConstraintError(
                            "There are one or more records referencing "
                            "the current set. Deletion aborted.")
                elif cons == "CASCADE":
                    if related.count() > 0:
                        related.unlink()
                elif cons == "SET NULL":
                    if related.count() > 0:
                        related.write({fld: None})
                else:
                    raise ValueError(
                        "Invalid deletion constraint '{}'".format(cons))
        

        # Delete documents
        outcome = conn.db[self._name].delete_many(
            self._query, session=self.env.session)
        
        # Delete any base.model.data documents 
        # referencing any of the deleted documents
        conn.db["base.model.data"].delete_many({
            "model": self._name,
            "res_id": {"$in": ids}
        })

        return outcome.deleted_count

    def _save(self):
        """ Write values in buffer to conn and clear it.
        """
        if len(self._buffer.items()) > 0:
            conn.db[self._name].update_many(
                self._query, {"$set": self._buffer}, session=self.env.session)
            self._buffer.clear()
        return

    def validate(self, vals):
        """ Ensure a given dict of values passes all
        required field validations for this model
        """
        with NoPersist(self):
            # Check each model field
            for field_name, field in self._fields.items():
                # If value is not present among vals
                if field_name not in vals:
                    # Skip x2many assignments
                    if isinstance(field, One2many) or isinstance(field, Many2many):
                        continue
                    # Check if field is marked as required
                    if field._required:
                        # Check for a default value
                        if hasattr(field, "_default"):
                            vals[field_name] = field._default
                        else:
                            raise ValueError(
                                "Missing value for required field '{}'".format(field_name))
                    else:
                        # Value not present and not required
                        if hasattr(field, "_default"):
                            vals[field_name] = field._default
                        else:
                            vals[field_name] = None
                # Let each field validate its value.
                setattr(self, field_name, vals[field_name])

    def ensure_one(self):
        """ Ensures current set contains a single document """
        if self.count() != 1:
            raise ValueError("Expected singleton")

    def ids(self, as_strings=False):
        """ Returns a list of ObjectIds contained 
        in the current DocSet
        """
        if as_strings:
            return [str(item._id) for item in self]
        return [item._id for item in self]

    def get(self, external_id):
        """ Finds a single document by its external id """
        mod_data = self.env["base.model.data"].search({"model": self._name, "name": external_id})
        if not mod_data:
            return None
        return self.search({"_id": mod_data.res_id })

    def load(self, fields, dataset):
        """
        Public method for importing data massively.
        Performs a validation on every single dataset entry,
        collecting any errors that may occur (up to 10).
        If no errors were found, then importation is performed.
        In any case, returns a dictionary with two keys:
        - ids: A list of newly created or updated ids.
        - errors: A list of errors found during the validation
        process.
        If a list contains any items, then the other should not.
        """
        ids = list()
        errors = list()
        for index, data in enumerate(dataset):
            dict_data = {field: data[i] for i, field in enumerate(fields)}
            dict_data.pop("id", None)
            try:
                self.validate(dict_data)
            except Exception as e:
                if len(errors) == 10:
                    break
                errors.append("Item {}: {}".format(str(index), str(e)))
        
        if len(errors) == 0:
            ids = self._load(fields, dataset)

        return {"ids": ids, "errors": errors}

    def _load(self, fields, dataset):
        """
        Private method for loading data.
        This method assumes validation has been already performed.
        Returns list of generated or updated ids.
        """

        def _load_update(dict_data, res_id):
            """ Browse an existing record and update.
            Return its _id
            """
            res_id = mod_data.res_id
            rec = self.browse(res_id)
            if not rec:
                raise ValueError("Record not found (model: {}, _id: {})".format(
                    self._name, str(res_id)))
            del dict_data["id"]
            rec.write(dict_data)
            return rec._id

        def _load_create(dict_data, with_name=False):
            """ Create a new record and a model data
            entry linked to it.
            Return the newly created record _id.
            """
            recid = dict_data.pop("id", None)
            rec = self.create(dict_data)
            res_id = rec._id
            name = recid if with_name else "__import__.{}".format(str(res_id))
            self.env["base.model.data"].create({
                "model": self._name,
                "name": name,
                "res_id": res_id
            })
            return res_id

        ids = list()
        for data in dataset:
            dict_data = {field: data[i] for i, field in enumerate(fields)}
            if "id" in fields and dict_data["id"] is not None:
                # An external id was provided
                # This either means a record has to be created
                # and linked to an external id, or an existing
                # record has to be updated.
                mod_data = self.env["base.model.data"].search(
                    {"model": self._name, "name": dict_data["id"]})
                if mod_data:
                    # External id exists in database, update.
                    res_id = _load_update(dict_data, mod_data.res_id)
                else:
                    # External id does not exist in database,
                    # create new record and generate model data entry.
                    res_id = _load_create(dict_data, True)
            else:
                # An external id was not provided. Create a new record.
                res_id = _load_create(dict_data, False)

            ids.append(res_id)

        return ids
