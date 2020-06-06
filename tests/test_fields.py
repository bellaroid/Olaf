import pytest
import pymongo
from olaf import db, registry, fields
from olaf.tools import initialize
from olaf.models import Model


@registry.add
class tModel(Model):
    _name = "TestModel"

    char_max_req = fields.Char(max_length=10, required=True)
    char_with_default = fields.Char(default="Default")
    integer = fields.Integer()
    m2o = fields.Many2one("TestCoModel")
    m2m = fields.Many2many("TestTagModel")


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
    tmod = tModel()
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
    t = tModel()
    with pytest.raises(ValueError):
        t.create({"char_max_req": "0123456789A"})


def test_char_required():
    """ Attempt to create a document without a required field
    """
    t = tModel()
    with pytest.raises(ValueError):
        t.create({"integer": 32})  # Missing required char_max_req


def test_integer():
    """ Attempt to set an integer value in different ways
    """
    t = tModel()
    with pytest.raises(ValueError):
        # Wrong integer
        t.create({"char_max_req": "0123456789", "integer": "Thirtytwo"})
    ti = t.create({"char_max_req": "0123456789",
                   "integer": "32"})  # String Integer
    assert(ti.integer == 32)
    ts = t.create({"char_max_req": "0123456789",
                   "integer": 31.4})  # Float convert
    assert(ts.integer == 31)


def test_m2o():
    """ Create a record in a model and reference it
    from another 
    """
    tmo = tModel()
    cmo = tCoModel()
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
    rec = tCoModel().create({"name": "O2M Test"})
    assert(rec.o2m.count() == 0)

    # Create
    rec.o2m = ('create', {"char_max_req": "o2m_1"})
    assert(rec.o2m.count() == 1)
    assert(rec.o2m.char_max_req == "o2m_1")
    recid = rec.o2m._id

    # Create Another
    rec.o2m = ('create', {"char_max_req": "o2m_2"})
    assert(rec.o2m.count() == 2)

    # Write
    item = tModel().browse(recid)
    assert(item.char_with_default == "Default")
    rec.o2m = ('write', recid, {"char_with_default": "Not Default"})
    assert(item.char_with_default == "Not Default")

    # Purge
    rec.o2m = ('purge', recid)
    assert(rec.o2m.count() == 1)
    with pytest.raises(ValueError):
        item.ensure_one()

    # Remove
    recid = rec.o2m     # Take the ID of the remaining document
    rec.o2m = ('remove', recid)
    assert(rec.o2m.count() == 0)

    # Add
    modrec = tModel().create({"char_max_req": "o2mc_1"})
    rec.o2m = ('add', modrec._id)
    assert(rec.o2m.count() == 1)

    # Clear
    rec.o2m = ('create', {"char_max_req": "o2mc_2"})
    rec.o2m = ('create', {"char_max_req": "o2mc_3"})
    rec.o2m = ('create', {"char_max_req": "o2mc_4"})
    assert(rec.o2m.count() == 4)
    rec.o2m = ('clear')
    assert(rec.o2m.count() == 0)

    # Replace
    recs = tModel().search({"char_max_req":  {'$regex': "o2mc_.*"}})
    assert(recs.count() == 4)
    rec.o2m = ('create', {"char_max_req": "o2mc_5"})
    rec.o2m = ('create', {"char_max_req": "o2mc_6"})
    assert(rec.o2m.count() == 2)
    rec.o2m = ('replace', recs.ids())
    assert(rec.o2m == recs)


def test_m2m():
    """ Ensure m2m behaves like a o2m
    """
    rec = tModel().create({"char_max_req": "m2m_1"})
    assert(rec.m2m.count() == 0)

    # Create
    rec.m2m = ("create", {"name": "Ninja"})
    assert(rec.m2m.count() == 1)
    assert(rec.m2m.name == "Ninja")
    recid = rec.m2m._id

    # Create Another
    rec.m2m = ('create', {"name": "Toronja"})
    assert(rec.m2m.count() == 2)

    # Write
    item = tTagModel().browse(recid)
    rec.m2m = ('write', recid, {"name": "Ganja"})
    assert(item.name == "Ganja")

    # Purge
    rec.m2m = ('purge', recid)
    assert(rec.m2m.count() == 1)
    with pytest.raises(ValueError):
        item.ensure_one()

    # Remove
    recid = rec.m2m     # Take the ID of the remaining document
    rec.m2m = ('remove', recid)
    assert(rec.m2m.count() == 0)

    # Add
    modrec = tTagModel().create({"name": "m2m_1"})
    rec.m2m = ('add', modrec._id)
    assert(rec.m2m.count() == 1)

    # Clear
    rec.m2m = ('create', {"name": "m2m_2"})
    rec.m2m = ('create', {"name": "m2m_3"})
    rec.m2m = ('create', {"name": "m2m_4"})
    assert(rec.m2m.count() == 4)
    rec.m2m = ('clear')
    assert(rec.m2m.count() == 0)

    # Replace
    recs = tTagModel().search({"name":  {'$regex': "m2m_.*"}})
    assert(recs.count() == 4)
    rec.m2m = ('create', {"name": "m2m_5"})
    rec.m2m = ('create', {"name": "m2m_6"})
    assert(rec.m2m.count() == 2)
    rec.m2m = ('replace', recs.ids())
    assert(rec.m2m == recs)

    # Uniqueness of the compound key
    with pytest.raises(pymongo.errors.DuplicateKeyError):
        rec.m2m = ('add', modrec._id)

    with pytest.raises(pymongo.errors.DuplicateKeyError):
        rec.m2m = ('create', {"name": "m2m_6"})


def test_unicity():
    """ Make sure unique fields are unique """
    tTagModel().create({"name": "test_tag_1"})
    with pytest.raises(pymongo.errors.DuplicateKeyError):
        tTagModel().create({"name": "test_tag_1"})


def test_finish():
    """ Clean previous tests """
    conn = db.Connection()
    conn.db["TestModel"].drop()
    conn.db["TestCoModel"].drop()
    conn.db["TestTagModel"].drop()
    conn.db["TestModel_TestTagModel_rel"].drop()
