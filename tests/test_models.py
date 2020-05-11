import pytest
import bson
from olaf import registry, models, fields, db


@registry.add
class tModel(models.Model):
    _name = "test.model"
    name = fields.Char()
    age = fields.Integer()


def test_model_browse():
    # Test all possible singleton browse calls
    tm1 = registry["test.model"].create({"name": "Test", "age": 10})
    tm2 = registry["test.model"].browse(tm1.id)
    tm3 = registry["test.model"].browse([tm1.id])
    tm4 = registry["test.model"].browse(str(tm1.id))
    tm5 = registry["test.model"].browse([str(tm1.id)])
    assert(tm1.id == tm2.id == tm3.id == tm4.id == tm5.id)
    # Test browsing with list using OId and str
    tma = registry["test.model"].create({"name": "Test_A", "age": 10})
    tmb = registry["test.model"].create({"name": "Test_B", "age": 20})
    tmc = registry["test.model"].browse([tma.id, str(tmb.id)])
    assert(tmc.count() == 2)
    # Browsing a non ObjectId string should fail
    with pytest.raises(bson.errors.InvalidId):
        registry["test.model"].browse("123456789")
    # Browsing a list with a non ObjectId string should fail
    with pytest.raises(bson.errors.InvalidId):
        registry["test.model"].browse([tma.id, "123456789"])
    # Browsing something out of a list, str or OId should fail
    with pytest.raises(TypeError):
        registry["test.model"].browse(23)


def test_model_finish():
    """ Clean previous tests """
    database = db.Database()
    database.db["test.model"].drop()
