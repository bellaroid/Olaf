import pytest
import pymongo
from bson import ObjectId
from olaf import db, registry, fields
from olaf.tools import initialize
from olaf.models import Model
from olaf.tools.environ import Environment

uid = ObjectId("000000000000000000000000")
env = Environment(uid)
self = registry["base.user"](env, {"_id": uid})


@registry.add
class tModel(Model):
    _name = "TestModel"

    char_max_req = fields.Char(max_length=10, required=True)
    char_with_default = fields.Char(default="Default")
    integer = fields.Integer()
    selection = fields.Selection(choices=["a", "b", "c"])
    m2o = fields.Many2one("TestCoModel")
    m2m = fields.Many2many(
        "TestTagModel", relation="test.model.tag.rel", field_a="a_oid", field_b="b_oid")
    boolean = fields.Boolean()
    date_time = fields.DateTime()


@registry.add
class tCoModel(Model):
    _name = "TestCoModel"
    char = fields.Char()
    o2m = fields.One2many('TestModel', 'm2o')


@registry.add
class tTagModel(Model):
    _name = "TestTagModel"
    name = fields.Char(unique=True)


# Initialize App Engine After All Model Classes Are Declared
initialize()


def test_field_assign():
    """ Multiple assignation tests
    """
    # Create two instances of the tModel object
    tmod = self.env["TestModel"]
    ts_a = tmod.create({"char_max_req": "trm_a"})
    ts_b = tmod.create({"char_max_req": "trm_b"})
    assert(tmod.count() == 0)  # tmod should remain as an empty set
    # Search for them
    tmod2 = tmod.search({"char_max_req": {"$in": ["trm_a", "trm_b"]}})
    # Verify the two of them were found
    assert(tmod2.count() == 2)
    # Perform multiwrite
    tmod2.char_max_req = "z"
    # Verify value can be obtained from previous instances
    assert(ts_a.char_max_req == "z")
    assert(ts_b.char_max_req == "z")
    # Attempt to perform multiget
    # Should raise exception since set has more than one value
    with pytest.raises(ValueError):
        tmod2.char_max_req


def test_char_max_length():
    """ Attempt to overpass the maximum length of a Char field
    """
    t = self.env["TestModel"]
    with pytest.raises(ValueError):
        t.create({"char_max_req": "0123456789A"})


def test_char_required():
    """ Attempt to create a document without a required field
    """
    t = self.env["TestModel"]
    with pytest.raises(ValueError):
        t.create({"integer": 32})  # Missing required char_max_req


def test_integer():
    """ Attempt to set an integer value in different ways
    """
    t = self.env["TestModel"]
    with pytest.raises(ValueError):
        # Wrong integer
        t.create({"char_max_req": "0123456789", "integer": "Thirtytwo"})
    ti = t.create({"char_max_req": "0123456789",
                   "integer": "32"})  # String Integer
    assert(ti.integer == 32)
    ts = t.create({"char_max_req": "0123456789",
                   "integer": 31.4})  # Float convert
    assert(ts.integer == 31)


def test_boolean():
    """ Attempt to set a boolean value in different ways
    """
    t = self.env["TestModel"]
    # Set True
    ti = t.create({"char_max_req": "testbool", "boolean": True})
    assert(ti.boolean is True)
    # Set False
    ti.write({"boolean": False})
    # Set to truthful integer
    ti.write({"boolean": 1})
    assert(ti.boolean is True)
    # Set to untruthful integer
    ti.write({"boolean": 0})
    assert(ti.boolean is False)
    # Set to None
    ti.write({"boolean": None})
    assert(ti.boolean is None)


def test_datetime():
    """ Attempt to set a datetime value in different ways
    """
    import datetime
    t = self.env["TestModel"]
    # BSON can't handle microseconds, so we round up our date to milliseconds
    now = datetime.datetime.now().replace(microsecond=0)
    ti = t.create({"char_max_req": "testdtime", "date_time": now})
    assert(ti.date_time == now)
    datetime_str = "01/02/1988 06:00:00"
    birthdate = datetime.datetime.strptime(datetime_str, '%d/%m/%Y %H:%M:%S')
    ti.write({"date_time": "1988-02-01 06:00:00"})
    assert(ti.date_time == birthdate)
    # ISO 8601 extended format
    ti.write({"date_time": "1988-02-01T06:00:00.000000"})
    assert(ti.date_time == birthdate)


def test_selection():
    """ Test selection field
    """
    t = self.env["TestModel"]
    ti = t.create({"char_max_req": "testselect"})
    # Assign allowed values
    ti.selection = "a"
    assert(ti.selection == "a")
    ti.selection = "b"
    assert(ti.selection == "b")
    ti.selection = "c"
    assert(ti.selection == "c")
    # Assign value not present among choices
    with pytest.raises(ValueError):
        ti.selection = "d"



def test_m2o():
    """ Create a record in a model and reference it
    from another 
    """
    tmo = self.env["TestModel"]
    cmo = self.env["TestCoModel"]
    c = cmo.create({"char": "chartest"})
    # Try assigning an ObjectID
    t = tmo.create({"char_max_req": "0123456789", "m2o": c._id})
    assert(t.m2o._id == c._id)
    # Try assigning a DocSet
    t = tmo.create({"char_max_req": "0123456789", "m2o": c})
    # Perform DocSet level comparison
    assert(t.m2o == c)


def test_o2m():
    """
    Ensure the following operations work properly

    Olaf Syntax         | Description
    -------------------------------------------------------------------------------
    ('create', {v})     | Link to a new record that needs to be created with the given values dictionary
    ('write', OID, {v}) | Update the linked record with id = ID (write *values* on it)
    ('purge', OID)      | Remove and delete the linked record with id = ID (calls unlink on ID, that will delete the object completely, and the link to it as well)
    ('remove', OID)     | Cut the link to the linked record with id = ID (delete the relationship between the two objects but does not delete the target object itself)
    ('add', OID)        | Link to existing record with id = ID (adds a relationship)
    ('clear')           | Unlink all (like using (3,ID) for all linked records)
    ('replace', [OIDs]) | Replace the list of linked IDs (like using (5) then (4,ID) for each ID in the list of IDs)
    """
    rec = self.env["TestCoModel"].create({"name": "O2M Test"})
    assert(rec.o2m.count() == 0)

    # Create
    rec.o2m = [('create', {"char_max_req": "o2m_1"})]
    assert(rec.o2m.count() == 1)
    assert(rec.o2m.char_max_req == "o2m_1")
    recid = rec.o2m._id

    # Create Another
    rec.o2m = [('create', {"char_max_req": "o2m_2"})]
    assert(rec.o2m.count() == 2)

    # Write
    item = self.env["TestModel"].browse(recid)
    assert(item.char_with_default == "Default")
    rec.o2m = [('write', recid, {"char_with_default": "Not Default"})]
    assert(item.char_with_default == "Not Default")

    # Purge
    rec.o2m = [('purge', recid)]
    assert(rec.o2m.count() == 1)
    with pytest.raises(ValueError):
        item.ensure_one()

    # Remove
    recid = rec.o2m     # Take the ID of the remaining document
    rec.o2m = [('remove', recid)]
    assert(rec.o2m.count() == 0)

    # Add
    modrec = self.env["TestModel"].create({"char_max_req": "o2mc_1"})
    rec.o2m = [('add', modrec._id)]
    assert(rec.o2m.count() == 1)

    # Clear
    rec.o2m = [('create', {"char_max_req": "o2mc_2"}),
               ('create', {"char_max_req": "o2mc_3"}),
               ('create', {"char_max_req": "o2mc_4"})]
    assert(rec.o2m.count() == 4)
    rec.o2m = [('clear')]
    assert(rec.o2m.count() == 0)

    # Replace
    recs = self.env["TestModel"].search(
        {"char_max_req":  {'$regex': "o2mc_.*"}})
    assert(recs.count() == 4)
    rec.o2m = [('create', {"char_max_req": "o2mc_5"}),
               ('create', {"char_max_req": "o2mc_6"})]
    assert(rec.o2m.count() == 2)
    rec.o2m = [('replace', recs.ids())]
    assert(rec.o2m == recs)


def test_m2m():
    """ Ensure m2m behaves like a o2m
    """
    rec = self.env["TestModel"].create({"char_max_req": "m2m_1"})
    assert(rec.m2m.count() == 0)

    # Create
    rec.m2m = [("create", {"name": "Ninja"})]
    assert(rec.m2m.count() == 1)
    assert(rec.m2m.name == "Ninja")
    recid = rec.m2m._id

    # Create Another
    rec.m2m = [('create', {"name": "Toronja"})]
    assert(rec.m2m.count() == 2)

    # Write
    item = self.env["TestTagModel"].browse(recid)
    rec.m2m = [('write', recid, {"name": "Ganja"})]
    assert(item.name == "Ganja")

    # Purge
    rec.m2m = [('purge', recid)]
    assert(rec.m2m.count() == 1)
    with pytest.raises(ValueError):
        item.ensure_one()

    # Remove
    recid = rec.m2m     # Take the ID of the remaining document
    rec.m2m = [('remove', recid)]
    assert(rec.m2m.count() == 0)

    # Add
    modrec = self.env["TestTagModel"].create({"name": "m2m_1"})
    rec.m2m = [('add', modrec._id)]
    assert(rec.m2m.count() == 1)

    # Clear
    rec.m2m = [('create', {"name": "m2m_2"}),
               ('create', {"name": "m2m_3"}),
               ('create', {"name": "m2m_4"})]
    assert(rec.m2m.count() == 4)
    rec.m2m = [('clear')]
    assert(rec.m2m.count() == 0)

    # Replace
    recs = self.env["TestTagModel"].search({"name":  {'$regex': "m2m_.*"}})
    assert(recs.count() == 4)
    rec.m2m = [('create', {"name": "m2m_5"}),
               ('create', {"name": "m2m_6"})]
    assert(rec.m2m.count() == 2)
    rec.m2m = [('replace', recs.ids())]
    assert(rec.m2m == recs)

    # Uniqueness of the compound key
    with pytest.raises(pymongo.errors.DuplicateKeyError):
        rec.m2m = [('add', modrec._id)]

    with pytest.raises(pymongo.errors.DuplicateKeyError):
        rec.m2m = [('create', {"name": "m2m_6"})]


def test_unicity():
    """ Make sure unique fields are unique """
    self.env["TestTagModel"].create({"name": "test_tag_1"})
    with pytest.raises(pymongo.errors.DuplicateKeyError):
        self.env["TestTagModel"].create({"name": "test_tag_1"})


def test_finish():
    """ Clean previous tests """
    conn = db.Connection()
    conn.db["TestModel"].drop()
    conn.db["TestCoModel"].drop()
    conn.db["TestTagModel"].drop()
    conn.db["test.model.tag.rel"].drop()
