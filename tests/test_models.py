import pytest
import bson
from olaf import registry, models, fields, db
from olaf.utils import initialize
from olaf.models import DeletionConstraintError


@registry.add
class tModel(models.Model):
    _name = "test.models.model"

    name = fields.Char()
    country = fields.Char(default="Argentina")
    age = fields.Integer()
    cascade_id = fields.Many2one("test.models.comodel", ondelete="CASCADE")
    restrict_id = fields.Many2one("test.models.comodel", ondelete="RESTRICT")
    setnull_id = fields.Many2one("test.models.comodel", ondelete="SET NULL")
    onetomany_ids = fields.One2many("test.models.comodel", "inverse_id")
    many2many_ids = fields.Many2many("test.models.comdodel")


@registry.add
class tCoModel(models.Model):
    _name = "test.models.comodel"

    name = fields.Char(required=True)
    inverse_id = fields.Many2one("test.models.model")


# Initialize App Engine After All Model Classes Are Declared
initialize()


def test_unicity():
    """ Make sure two instances
    are not the same instance """
    t_a = tModel()
    t_b = tModel()
    assert(id(t_a) != id(t_b))


def test_equality():
    """ Test DocSet comparison"""
    t_a = tModel().create({"name": "Mr. Roboto"})
    t_b = tModel().create({"name": "Mr. Roboto"})
    t_c = tModel().search({"_id": t_a._id})
    # t_a and t_c contain the same document
    assert(t_a == t_c)
    # t_a and t_b have the same name but not same OID
    assert(t_a != t_b)


def test_model_create():
    """ Perform a basic creation of a new element.
    Make sure counters are correct and default values
    get assigned.
    """
    t = tModel()
    ti = t.create({"name": "Mr. Roboto", "age": 32})
    assert(ti.count() == 1)
    assert(ti.name == "Mr. Roboto")
    assert(ti.age == 32)
    assert(ti.country == "Argentina")


def test_model_browse():
    # Test all possible singleton browse calls
    tm1 = registry["test.models.model"].create({"name": "Test", "age": 10})
    tm2 = registry["test.models.model"].browse(tm1._id)
    tm3 = registry["test.models.model"].browse([tm1._id])
    tm4 = registry["test.models.model"].browse(str(tm1._id))
    tm5 = registry["test.models.model"].browse([str(tm1._id)])
    assert(tm1._id == tm2._id == tm3._id == tm4._id == tm5._id)
    # Test browsing with list using OId and str
    tma = registry["test.models.model"].create({"name": "Test_A", "age": 10})
    tmb = registry["test.models.model"].create({"name": "Test_B", "age": 20})
    tmc = registry["test.models.model"].browse([tma._id, str(tmb._id)])
    assert(tmc.count() == 2)
    # Browsing a non ObjectId string should fail
    with pytest.raises(bson.errors.InvalidId):
        registry["test.models.model"].browse("123456789")
    # Browsing a list with a non ObjectId string should fail
    with pytest.raises(bson.errors.InvalidId):
        registry["test.models.model"].browse([tma._id, "123456789"])
    # Browsing something out of a list, str or OId should fail
    with pytest.raises(TypeError):
        registry["test.models.model"].browse(23)


def test_delete_cascade():
    """ Verify Cascaded deletion """
    tc1 = registry["test.models.comodel"].create({"name": "Test"})
    tm1 = registry["test.models.model"].create(
        {"name": "Test", "age": 10, "cascade_id": tc1._id})
    assert(tm1.cascade_id._id == tc1._id)
    tc1.unlink()
    assert(tm1.count() == 0)


def test_delete_restrict():
    """ Verify Restricted deletion """
    tc1 = registry["test.models.comodel"].create({"name": "Test"})
    tm1 = registry["test.models.model"].create(
        {"name": "Test", "age": 10, "restrict_id": tc1._id})
    assert(tm1.restrict_id._id == tc1._id)
    with pytest.raises(DeletionConstraintError):
        tc1.unlink()
    tm1.write({"restrict_id": None})
    assert(tc1.unlink() == 1)
    assert(tc1.count() == 0)


def test_delete_set_null():
    """ Verify Set Null on deletion """
    tc1 = registry["test.models.comodel"].create({"name": "Test"})
    tm1 = registry["test.models.model"].create(
        {"name": "Test", "age": 10, "setnull_id": tc1._id})
    assert(tm1.setnull_id._id == tc1._id)
    tc1.unlink()
    assert(tm1.setnull_id == None)


def test_read():
    """ Ensure read values are correct """
    tc1 = registry["test.models.comodel"].create({"name": "Test_01"})
    tc2 = registry["test.models.comodel"].create({"name": "Test_02"})
    tm1 = registry["test.models.model"].create(
        {"name": "Test", "age": 10, "setnull_id": tc1._id, "onetomany_ids": ("replace", [tc1._id, tc2._id])})
    read = tm1.read()
    assert(read[0]["name"] == "Test")
    assert(read[0]["age"] == 10)
    # Test Many2one
    assert(read[0]["setnull_id"][0] == tc1._id)
    # Test One2many
    assert((tc1._id, tc1.name) in read[0]["onetomany_ids"])
    assert((tc2._id, tc2.name) in read[0]["onetomany_ids"])

def test_model_finish():
    """ Clean previous tests """
    conn = db.Connection()
    conn.db["test.models.model"].drop()
    conn.db["test.models.comodel"].drop()
