import pytest
import bson
from olaf import registry, models, fields, db


@registry.add
class tModel(models.Model):
    _name = "test.model"
    name = fields.Char()
    country = fields.Char(default="Argentina")
    age = fields.Integer()


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
    tm1 = registry["test.model"].create({"name": "Test", "age": 10})
    tm2 = registry["test.model"].browse(tm1._id)
    tm3 = registry["test.model"].browse([tm1._id])
    tm4 = registry["test.model"].browse(str(tm1._id))
    tm5 = registry["test.model"].browse([str(tm1._id)])
    assert(tm1._id == tm2._id == tm3._id == tm4._id == tm5._id)
    # Test browsing with list using OId and str
    tma = registry["test.model"].create({"name": "Test_A", "age": 10})
    tmb = registry["test.model"].create({"name": "Test_B", "age": 20})
    tmc = registry["test.model"].browse([tma._id, str(tmb._id)])
    assert(tmc.count() == 2)
    # Browsing a non ObjectId string should fail
    with pytest.raises(bson.errors.InvalidId):
        registry["test.model"].browse("123456789")
    # Browsing a list with a non ObjectId string should fail
    with pytest.raises(bson.errors.InvalidId):
        registry["test.model"].browse([tma._id, "123456789"])
    # Browsing something out of a list, str or OId should fail
    with pytest.raises(TypeError):
        registry["test.model"].browse(23)


def test_model_finish():
    """ Clean previous tests """
    database = db.Connection()
    database.db["test.model"].drop()
