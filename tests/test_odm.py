import pytest
from olaf.models import Model
from olaf import db, registry, fields


@registry.add
class tModel(Model):
    _name = "TestModel"

    char_max_req = fields.Char(max_length=10, required=True)
    char_with_default = fields.Char(default="Default")
    integer = fields.Integer()
    m2o = fields.Many2one("TestCoModel")


@registry.add
class tCoModel(Model):
    _name = "TestCoModel"
    char = fields.Char()


def test_unicity():
    """ Make sure two instances 
    are no the same instance
    """
    t_a = tModel()
    t_b = tModel()
    assert(t_a != t_b)


def test_model_assign():
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


def test_model_create():
    """ Perform a basic creation of a new element.
    Make sure counters are correct and default values
    get assigned.
    """
    t = tModel()
    ti = t.create({"char_max_req": "0123456789", "integer": 32})
    assert(ti.count() == 1)
    assert(ti.char_max_req == "0123456789")
    assert(ti.integer == 32)
    assert(ti.char_with_default == "Default")


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


def test_finish():
    """ Clean previous tests """
    database = db.Database()
    database.db["TestModel"].drop()
    database.db["TestCoModel"].drop()
