import logging
from olaf.fields import BaseField, Identifier, Boolean, NoPersist, RelationalField, One2many, Many2one, Many2many
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

    # Common Fields
    _id = Identifier()
    active = Boolean(default=True)

    @property
    def ids(self):
        return self._ids()

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

    def __len__(self):
        return self.count()

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

    def create(self, vals_list):
        # Perform create access check
        check_access(self, "create")

        # Convert vals to list if a dict was provided
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        # For collecting inserted ids
        ids = list()
        docs = list()
        
        for vals in vals_list:
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

            # Append to buffer lists
            ids.append(base_dict["_id"])
            docs.append(base_dict)
        
        # Load base_dict into write cache & flush caché
        if len(docs) == 1:
            docs = docs[0]

        self.env.cache.append("create", self._name, None, docs)
        self.env.cache.flush()
        doc = self.__class__(self.env, {"_id": {"$in": ids}})

        # Load x2many field data into write cache
        for field_name, value in x2m_dict.items():
            setattr(doc, field_name, value)

        return doc

    def write(self, vals):
        """ Write values to the documents in the current set"""
        # Perform write access check
        check_access(self, "write")
        raw_data = self.validate(vals, True)

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
        self.env.cache.append("write", self._name, self.ids, base_dict)
        
        # Load x2many field data into write cache
        for field_name, value in x2m_dict.items():
            setattr(self, field_name, value)

        self.env.cache.flush()
        return

    def read(self, fields=[]):
        """ Returns a list of dictionaries representing
        each document in the set. The optional parameter fields
        allows to specify which field values should be retrieved from
        database. If omitted, all fields will be read. This method also
        renders the representation of relational fields (Many2one and x2many).
        """
        # Perform read access check
        check_access(self, "read")

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
                    doc[field] = dictitem[field] if field in dictitem else None
            result.append(doc)
        return result

    def unlink(self):
        """ Deletes all the documents in the set.
        Return the amount of deleted elements.
        """
        # Perform unlink access check
        check_access(self, "unlink")
        ids = self.ids
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
                        intrm = getattr(related, "_intermediate", False)
                        if not intrm:
                            related.write({fld: None})
                        else:
                            # If the model we're working with is intermediate,
                            # we've got to delete the relation instead, 
                            # in order to avoid a NOT NULL constraint error 
                            # and keep the collection clean.
                            related.unlink()
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
                
                # Force _id to be validated first
                raw_data["_id"] = self._fields["_id"].__validate__(self, vals.get("_id", None))

                # Check each model field
                for field_name, field in self._fields.items():
                    # Skip _id as it was previously validated
                    if field_name == "_id":
                        continue
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

    def _ids(self, as_strings=False):
        """ Returns a list of ObjectIds contained 
        in the current DocSet
        """
        if as_strings:
            return [str(item._id) for item in self]
        return [item._id for item in self]

    def mapped(self, field):
        if not field in self._fields:
            raise ValueError("Field '{}' not found in model".format(field))
        field_inst = self._fields[field]
        # If field is relational, return a recordset containing the
        # related ids of each document in the set.
        if issubclass(field_inst.__class__, RelationalField):
            ids = set()
            rel_model = self.env[field_inst._comodel_name]
            for rec in self:
                for rel in getattr(rec, field):
                    ids = ids | set(rel.ids)
            return rel_model.search({"_id": {"$in": list(ids)}})
        # Otherwise return mapped list
        return [getattr(rec, field) for rec in self]

    def filtered(self, query):
        """ Returns a docset that fulfills
        the given query and it's also
        a subset of the current one.
        """
        if not isinstance(query, dict):
            raise ValueError(
                "Query should be of type dict, " 
                "got {} instead".format(query.__class__.__name__))
        return self.search({"$and": [self._query, query]})

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
        ids, errors = self._load(fields, data)
        if len(errors) > 0:
            self.env.cache.clear()
            return {"ids": [], "errors": errors }
        self.env.cache.flush()
        return {"ids": ids, "errors": errors }

    def _load(self, fields, dataset, parent_field=None, parent_oid=None):
        """
        Loads massive data into a model.
        """

        def _generate_metadata(import_fields):
            """ Generate field metadata dictionary and 
            a reduced list of fields (e.g. without 
            subfields nor x2m's)
            """

            simple_fields = list()

            meta = {
                "base": dict(),
                "m2o":  dict(),
                "o2m":  dict(),
                "m2m":  dict(),
            }

            for index, field in enumerate(import_fields):
                # Skip if field was already added
                if field[0] in simple_fields:
                    continue

                # Get field instance
                field_inst = self._fields.get(field[0], None)

                # Generate field metadata,
                # keeping record of indices 
                # assigned to each field
                if isinstance(field_inst, Many2one):
                    if field[0] not in meta["m2o"]:
                        meta["m2o"][field[0]] = []
                    meta["m2o"][field[0]].append(index)
                elif isinstance(field_inst, One2many):
                    if field[0] not in meta["o2m"]:
                        meta["o2m"][field[0]] = []
                    meta["o2m"][field[0]].append(index) 
                elif isinstance(field_inst, Many2many):
                    if field[0] not in meta["m2m"]:
                        meta["m2m"][field[0]] = []
                    meta["m2m"][field[0]].append(index)
                else:
                    if field[0] == "id":
                        continue
                    if field[0] not in meta["base"]:
                        meta["base"][field[0]] = [index]
            
            return meta

        def _slice_data(data, meta_base_fields):
            """
            Returns a sliced-by-document version
            of the original data matrix.
            """ 

            idx = -1
            data_length = len(dataset)
            result = list()

            # Loop over data
            while idx < data_length - 1:

                # Increment index
                idx += 1

                # Read row in current index
                row_data = data[idx]

                # If row does not contain any data, skip
                if all("" == d for d in row_data):
                    continue

                # Verify row maximum span
                rowspan = 1
                while True:
                    if idx + rowspan == data_length:
                        # End of dataset reached
                        break

                    # Get next row, only basefields (no m2o nor o2m)
                    next_row = data[idx + rowspan]
                    for _, base_meta in meta_base_fields.items():
                        for i in base_meta:
                            next_row_data = [next_row[i]]

                    # Check if the next row basefields are all empty
                    if all("" == d for d in next_row_data):
                        rowspan += 1
                    else:
                        break

                # Rowspan should now indicate the amount of rows required
                # for a single document.
                result.append(data[idx:idx+rowspan])

                # Set index
                idx = idx + rowspan - 1 

            return result

        def _resolve_insert_update(row, fields):
            """
            Given the first row of a submatrix and 
            all the requested fields, determine wether
            document requires a "create" or "write" operation.
            Return a string with any of those outcomes,
            and the computed ObjectId
            """
            if "id" in fields:
                # id field might have been provided
                ext_id = row[fields.index("id")]
                if ext_id and ext_id != "":
                    # id was provided, 
                    # find or create base.model.data entry
                    moddata = self.env["base.model.data"].search({
                        "name":ext_id,
                        "model": self._name
                    })
                    if moddata:
                        # existing model data found
                        # get the resource oid
                        op = "write"
                        oid = moddata.res_id # pylint: disable=no-member
                    else:
                        # model data not found,
                        # generate entry
                        op = "create"
                        oid = ObjectId()
                        self.env.cache.append(
                            "create",
                            "base.model.data",
                            None,
                            {
                                "_id": ObjectId(),
                                "name": ext_id,
                                "model": self._name,
                                "res_id": oid
                            }
                        )
                else:
                    # id is present in fields
                    # but was not provided for
                    # the current document
                    op = "create"
                    oid = ObjectId()
                    self.env.cache.append(
                        "create",
                        "base.model.data",
                        None,
                        {
                            "_id": ObjectId(),
                            "name": "__import__.{}".format(str(oid)),
                            "model": self._name,
                            "res_id": oid
                        },
                    )
            else:
                # id is not present among
                # fields, generate generic
                # model data entry
                op = "create"
                oid = ObjectId()
                self.env.cache.append(
                    "create",
                    "base.model.data",
                    None,
                    {
                        "_id": ObjectId(),
                        "name": "__import__.{}".format(str(oid)),
                        "model": self._name,
                        "res_id": oid
                    }
                )
            
            return op, oid

        # Initialize results
        ids = []
        errors = []

        # Parse list of fields.
        # Split strings containing slashes.
        # Result will be a list of lists of strings.
        import_fields = [field.split("/") for field in fields]
        # >>> [["id"], ["field_a"], ["field_b", "subfield_a"], ["field_b", "subfield_b"]]

        # Take first element of each string-list
        # in order to create a sanitized list of fields.
        norm_fields = [field[0] for field in import_fields]
        # >>> ["id", "field_a", "field_b"]

        # Also, make sure provided fields belong to the current model.
        # (ignore 'id' if provided)
        for field in norm_fields:
            if field not in self._fields and field != "id":
                raise KeyError(
                    "Field '{}' not found in model '{}'".format(field, self._name))
        
        # Get metadata and simplified list
        meta = _generate_metadata(import_fields)

        # Slice data matrix into submatrices
        sliced_data = _slice_data(dataset, meta["base"])

        for slmatrix in sliced_data:
            # Initialize Simplified Data Dictionary
            # This should contain MongoDB-ready data.
            simple_data = dict()

            op, oid = _resolve_insert_update(slmatrix[0], fields)

            # Prepare Base Fields
            for base_field, base_meta in meta["base"].items():
                simple_data[base_field] = slmatrix[0][base_meta[0]]
            
            # Import M2Os
            # M2Os are resolved into ObjectIds, one at a time
            for m2o_field, m2o_meta in meta["m2o"].items():
                m2o_fields = list()
                m2o_data =   list()
                for col_index in m2o_meta:
                    # Generate field names for current m2o field
                    m2o_fields.append("/".join(import_fields[col_index][1:]))
                for offset in range(0, len(slmatrix)):
                    # Generate m2o data submatrix
                    subrow = list()
                    for col_index in m2o_meta:
                        subrow.append(slmatrix[offset][col_index])
                    if all(x == "" for x in subrow):
                        # Discard empty rows
                        continue
                    m2o_data.append(subrow)
                # Import and get ID
                out_ids, out_errs = self.env[self._fields[m2o_field]._comodel_name]._load(
                    m2o_fields, m2o_data)
                if len(out_errs) > 0:
                    for err in out_errs:
                        errors.append(err)
                    continue
                if len(out_ids) == 1:
                    simple_data[m2o_field] = out_ids[0]

            # Reference parent record if provided
            if parent_field and parent_oid:
                simple_data[parent_field] = parent_oid
            
            # Load data into write cache
            if op == "create":
                simple_data["_id"] = oid
                try:
                    raw_data = self.validate(simple_data)
                except Exception as e:
                    errors.append(e)
                    continue
                self.env.cache.append(op, self._name, None, raw_data)
            elif op == "write":
                try:
                    raw_data = self.validate(simple_data, True)
                except Exception as e:
                    errors.append(e)
                    continue
                self.env.cache.append(op, self._name, [oid], simple_data)

            # Import O2Ms
            # O2Ms are treated like independent records
            # that reference the current one.
            for o2m_field, o2m_meta in meta["o2m"].items():
                o2m_fields = list()
                o2m_data =   list()
                for col_index in o2m_meta:
                    # Generate field names for current o2m field
                    o2m_fields.append("/".join(import_fields[col_index][1:]))
                for offset in range(0, len(slmatrix)):
                    # Generate o2m data submatrix
                    subrow = list()
                    for col_index in o2m_meta:
                        subrow.append(slmatrix[offset][col_index])
                    if all(x == "" for x in subrow):
                        # Discard empty rows
                        continue
                    o2m_data.append(subrow)
                # Import. New documents will reference current one
                # thanks to the parent_field and parend_id params.
                _, out_errs = self.env[self._fields[o2m_field]._comodel_name]._load(
                    o2m_fields, 
                    o2m_data, 
                    parent_field=self._fields[o2m_field]._inversed_by,
                    parent_oid=oid)
                if len(out_errs) > 0:
                    for err in out_errs:
                        errors.append(err)
                    continue

            # Import M2Ms
            for m2m_field, m2m_meta in meta["m2m"].items():
                m2m_fields = list()
                m2m_data =   list()
                for col_index in m2m_meta:
                    # Generate field names for current m2m field
                    m2m_fields.append("/".join(import_fields[col_index][1:]))
                for offset in range(0, len(slmatrix)):
                    # Generate m2m data submatrix
                    subrow = list()
                    for col_index in m2m_meta:
                        subrow.append(slmatrix[offset][col_index])
                    if all(x == "" for x in subrow):
                        # Discard empty rows
                        continue
                    m2m_data.append(subrow)
                # Import.
                out_ids, out_errs = self.env[self._fields[m2m_field]._comodel_name]._load(
                    m2m_fields, 
                    m2m_data)
                if len(out_errs) > 0:
                    for err in out_errs:
                        errors.append(err)
                    continue
                if len(out_ids) > 0:
                    m2m_field = self._fields[m2m_field]
                    rel_name =      m2m_field._relation
                    field_a =       m2m_field._field_a
                    field_b =       m2m_field._field_b
                    items = list()
                    for m2m_oid in out_ids:
                        items.append({
                            "_id": ObjectId(),
                            field_a: oid,
                            field_b: m2m_oid,
                        })
                    self.env.cache.append(
                        "create",
                        rel_name,
                        None,
                        items
                    )
                
            # Consider this document as successfully inserted
            ids.append(oid)

        return ids, errors