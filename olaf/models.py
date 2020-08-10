import logging
from olaf.fields import BaseField, Identifier, NoPersist, RelationalField, One2many, Many2one, Many2many
from olaf.db import Connection
from bson import ObjectId
from olaf import registry
from olaf.security import check_access

logger = logging.getLogger(__name__)
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
        # Create a dict of fields within this model
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
        # Perform create access check
        check_access(self._name, "create", self.env.context["uid"])
        
        # Make sure x2many assignment does not contain
        # any forbidden operation.
        for field, value in vals.items():
            if field in self._fields and (
                    isinstance(self._fields[field], One2many) or
                    isinstance(self._fields[field], Many2many)):
                for item in value:
                    if item[0] in ["write", "purge", "remove", "clear"]:
                        raise ValueError(
                            "Cannot use x2many operation '{}' on create()".format(item[0]))

        # Validate and Flush, return new DocSet
        raw_data = self.validate(vals)

        # Create two separate dictionaries for handling base and x2many fields
        base_dict = dict()
        x2m_dict =  dict()

        # Map provided values to their dictionaries
        for field_name, value in raw_data.items():
            if isinstance(self._fields[field_name], Many2many) or \
                    isinstance(self._fields[field_name], One2many):
                x2m_dict[field_name] =  value
            else:
                base_dict[field_name] = value

        # Load base_dict into write cache
        self.env.cache.append(self._name, raw_data["_id"], base_dict, "create")
        self.env.cache.flush()
        doc = self.__class__(self.env, {"_id": raw_data["_id"]})

        # Load x2many field data into write cache
        for field_name, value in x2m_dict.items():
            setattr(doc, field_name, value)

        return doc


    def write(self, vals):
        """ Write values to the documents in the current set"""
        # Perform write access check
        check_access(self._name, "write", self.env.context["uid"])
        raw_data = self.validate(vals, True)
        self.env.cache.append(self._name, self.ids(), raw_data)
        self.env.cache.flush()

    def read(self, fields=[]):
        """ Returns a list of dictionaries representing
        each document in the set. The optional parameter fields
        allows to specify which field values should be retrieved from
        database. If omitted, all fields will be read. This method also
        renders the representation of relational fields (Many2one and x2many).
        """
        # Perform read access check
        check_access(self._name, "read", self.env.context["uid"])

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
        # Perform unlink access check
        check_access(self._name, "unlink", self.env.context["uid"])
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

    def _save(self, insert=False):
        """ Write values in buffer to conn and clear it.
        """
        # Create two separate dictionaries for handling base and x2many fields
        base_dict = dict()
        x2m_dict =  dict()

        # Map provided values to their dictionaries
        items = self._buffer.items()
        for field_name, value in items:
            if isinstance(self._fields[field_name], Many2many) or \
                    isinstance(self._fields[field_name], One2many):
                x2m_dict[field_name] =  value
            else:
                base_dict[field_name] = value
                
        # Insert Base Fields
        doc = self
        if len(base_dict.items()) > 0:
            if insert:
                new_id = conn.db[self._name].insert_one(
                    base_dict, session=self.env.session).inserted_id
                doc = self.__class__(self.env, {"_id": new_id})
            else:
                conn.db[self._name].update_many(
                    self._query, {"$set": base_dict}, session=self.env.session)

        # Insert x2m Fields
        for field_name, value in x2m_dict.items():
            setattr(doc, field_name, value)

        self._buffer.clear()
        return doc

    def validate(self, vals, write=False):
        """ Ensure a given dict of values passes all
        required field validations for this model
        """
        raw_data = dict()
        with NoPersist(self):
            if not write:
                # -- Validating a create operation --
                # We've got to make sure required fields
                # are present and default values are assigned
                # if they were omitted by the user.

                # Check each model field
                for field_name, field in self._fields.items():
                    # If value is not present among vals
                    if field_name not in vals:
                        # Treat x2many assignments as empty lists
                        if isinstance(field, One2many) or isinstance(field, Many2many):
                            vals[field_name] = list()
                        else:
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
                    raw_data[field_name] = field.__validate__(self, vals[field_name])
            else:
                # -- Validating a write operation --
                # Let each field validate its value.
                for field_name in vals.keys():
                    if field_name in self._fields:
                        if field_name != "_id":
                            raw_data[field_name] = self._fields[field_name].__validate__(self, vals[field_name])
                        else:
                            raise ValueError(
                                "'_id' field is readonly once document has been persisted")
        return raw_data

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
        mod_data = self.env["base.model.data"].search(
            {"model": self._name, "name": external_id})
        if not mod_data:
            return None
        return self.search({"_id": mod_data.res_id})

    def with_context(self, **kwargs):
        """ Return a new instance of the current
        object with its context modified.
        """
        from olaf.tools.environ import Environment

        # Unfreeze current context
        new_context = {k: v for k, v in self.env.context.items()}

        # Patch context with new arguments
        for k, v in kwargs.items():
            new_context[k] = v

        # Create a new environment
        new_env = Environment(
            self.env.context["uid"],
            session=self.env.session,
            context=new_context)

        return self.__class__(new_env, self._query)

    def sudo(self):
        """ Shortcut method for modifying current
        user context """
        return self.with_context(uid=ObjectId("000000000000000000000000"))

    def load(self, fields, data):
        """ A recursive data loader"""

        def _generate_metadata(import_fields):
            """ Generate field metadata dictionary and 
            a reduced list of fields (e.g. without 
            subfields nor x2m's)
            """

            simple_fields = list()

            meta = {
                "base": dict(),
                "m2o":  dict(),
                "o2m":  dict()
            }

            for index, field in enumerate(import_fields):
                # Skip if field was already added
                if field[0] in simple_fields:
                    continue

                # Get field instance
                field_inst = self._fields.get(field[0], None)

                # Generate field metadata and simplified field list
                if isinstance(field_inst, Many2one):
                    if field[0] not in meta["m2o"]:
                        meta["m2o"][field[0]] = {"original": []}
                    if field[0] not in simple_fields:
                        simple_fields.append(field[0])
                        meta["m2o"][field[0]]["new"] = simple_fields.index(
                            field[0])
                    meta["m2o"][field[0]]["original"].append(index)
                elif isinstance(field_inst, One2many):
                    if field[0] not in meta["o2m"]:
                        meta["o2m"][field[0]] = {"original": []}
                    meta["o2m"][field[0]]["original"].append(index)
                elif isinstance(field_inst, Many2many):
                    logger.warning("Many2many Importation not implemented")
                else:
                    if field[0] not in meta["base"]:
                        meta["base"][field[0]] = {"original": [index]}
                    if field[0] in simple_fields:
                        raise("Base field[0] '{}' is repeated in column header".format(field[0]))
                    simple_fields.append(field[0])
                    meta["base"][field[0]]["new"] = simple_fields.index(field[0])

            return meta, simple_fields

        logger.debug("Importing Data -- {} - {}".format(self._name, fields))

        ids = []
        errors = []

        import_fields = [field.split("/") for field in fields]
        # >>> [["id"], ["field_a"], ["field_b", "subfield_a"], ["field_b", "subfield_b"]]

        # A simplified matrix reducing M2O's into a single field
        # and not including O2M nor o2m.
        simple_data = list()

        norm_fields = [field[0] for field in import_fields]
        # >>> ["id", "field_a", "field_b"]

        # Run sanity check before continuing
        for field in norm_fields:
            if field not in self._fields and field != "id":
                raise KeyError(
                    "Field '{}' not found in model '{}'".format(field, self._name))

        # Get metadata and simplified list
        meta, simple_fields = _generate_metadata(import_fields)

        if len(meta["base"].items()) == 0:
            raise ValueError(
                "Import operation requires at least one base field to be included among the headers")

        idx = -1
        data_length = len(data)

        # Loop over data
        while idx < data_length - 1:

            # Increment index
            idx += 1

            # Current row
            row_data = data[idx]

            # Make sure row isn't empty
            if all("" == d for d in row_data):
                continue

            # Prepare simplified data row
            simple_data_row = [None] * len(simple_fields)

            # Verify row maximum span
            rowspan = 1
            while True:
                if idx + rowspan == data_length:
                    # End of dataset reached
                    break

                # Get next row, only basefields (no m2o nor o2m)
                next_row = data[idx + rowspan]
                for _, base_meta in meta["base"].items():
                    for i in base_meta["original"]:
                        next_row_data = [next_row[i]]

                # Check if the next row basefields are all empty
                if all("" == d for d in next_row_data):
                    rowspan += 1
                else:
                    break

            # Import M2Os
            for m2o_field, m2o_meta in meta["m2o"].items():
                m2o_fields = list()
                m2o_data = list()
                for col_index in m2o_meta["original"]:
                    m2o_fields.append("/".join(import_fields[col_index][1:]))
                for offset in range(0, rowspan):
                    m2o_data.append([data[idx + offset][col_index]
                                     for col_index in m2o_meta["original"]])
                outcome = self.env[self._fields[m2o_field]._comodel_name].load(
                    m2o_fields, m2o_data)
                if len(outcome["errors"]) > 0:
                    for err in outcome["errors"]:
                        errors.append(err)
                    continue
                if len(outcome["ids"]) == 1:
                    simple_data_row[m2o_meta["new"]] = outcome["ids"][0]

            # Move base data to new matrix
            for _, base_data in meta["base"].items():
                simple_data_row[base_data["new"]] = row_data[base_data["original"][0]]

            # Append to simplified data list
            simple_data.append(simple_data_row)

            # # Finally, import One2many data
            # for o2m_field, o2m_meta in meta["o2m"].items():
            #     o2m_fields = list()
            #     o2m_data = list()
            #     inversed_by = self._fields[o2m_field]._inversed_by
            #     for col_index in o2m_meta["original"]:
            #         o2m_fields.append("/".join(import_fields[col_index][1:]))

            #     # Ensure inversed_by field in fields list and get its index
            #     if inversed_by not in o2m_fields:
            #         o2m_fields.append(inversed_by)
            #         inversed_by_index = o2m_fields[-1]
            #     else:
            #         inversed_by_index = o2m_fields.index(inversed_by)

            #     for offset in range(0, rowspan):
            #         data_row = [data[idx + offset][col_index]
            #                     for col_index in o2m_meta["original"]]
            #         if inversed_by_index == len(data_row):
            #             data_row.append(res_id)
            #         else:
            #             data_row[inversed_by] = res_id
            #         o2m_data.append(data_row)

            #     outcome = self.env[self._fields[m2o_field]._inversed_by].load(
            #         o2m_fields, o2m_data)

            #     if len(outcome["errors"]) > 0:
            #         for err in outcome["errors"]:
            #             errors.append(err)
            #         continue
            #     if len(outcome["ids"]) == 1:
            #         simple_data_row[o2m_meta["new"]] = outcome["ids"][0]

        # Data validation phase
        for idx, _data in enumerate(simple_data):
            # Comprehend a dictionary with the current row data
            dict_data = {f: _data[i] for i, f in enumerate(simple_fields)}
            # Determine wether row would require
            # a create() or a write() operation
            if "id" in simple_fields and dict_data["id"] is not None:
                mod_data = self.env["base.model.data"].search(
                    {"model": self._name, "name": dict_data["id"]})
                write = bool(mod_data)
                dict_data.pop("id", None)
            else:
                write = False

            try:
                self.validate(dict_data, write)
            except Exception as e:
                if len(errors) == 10:
                    break
                errors.append("Item {}: {}".format(str(idx), str(e)))

        if len(errors) == 0:
            ids = self._load(simple_fields, simple_data)

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
