import pytest
import bson
from bson import ObjectId
from olaf import db, registry, fields, models
from olaf.tools import initialize
from olaf.models import Model, DeletionConstraintError
from olaf.tools.environ import Environment

initialize()

uid = ObjectId("000000000000000000000000")
env = Environment(uid)
self = registry["base.user"](env, {"_id": uid})


@registry.add
class tModel(models.Model):
    _name = "test.load.model"

    name = fields.Char()
    age = fields.Integer()
    boolean = fields.Boolean()
    manytoone_id = fields.Many2one("test.load.comodel")
    onetomany_ids = fields.One2many("test.load.comodel", "inverse_id")
    manytomany_ids = fields.Many2many(
        "test.load.comodel", relation="test.load.comodel.rel", field_a="a_oid", field_b="b_oid")


@registry.add
class tCoModel(models.Model):
    _name = "test.load.comodel"

    name = fields.Char(required=True)
    inverse_id = fields.Many2one("test.load.model")


# Initialize App Engine After All Model Classes Are Declared
initialize()


def test_load_basic():
    tm1 = self.env["test.load.model"]

    # Basic Importation
    outcome = tm1.load(
        ["name", "age"],
        [
            ["name1A", 1],
            ["name2A", 2]
        ])

    # Nothing went wrong
    assert(len(outcome["errors"]) == 0)
    # There are 2 ids
    assert(len(outcome["ids"]) == 2)
    # Those ids represent 2 persisted objects
    docset = tm1.search({"_id": {"$in": outcome["ids"]}})
    assert(docset.count() == 2)
    # Values are correct
    set_names = {item.name for item in docset}
    set_ages = {item.age for item in docset}
    assert(set_names == {"name1A", "name2A"})
    assert(set_ages == {1, 2})


def test_load_basic_with_xid():
    tm1 = self.env["test.load.model"]

    # Basic Importation (with external ids)
    outcome = tm1.load(
        ["id", "name", "age"],
        [
            ["test_load_basic_1", "name1A", 1],
            ["test_load_basic_2", "name2A", 2]
        ])

    # Nothing went wrong
    assert(len(outcome["errors"]) == 0)
    # There are 2 ids
    assert(len(outcome["ids"]) == 2)
    # Those ids represent 2 persisted objects
    docset = tm1.search({"_id": {"$in": outcome["ids"]}})
    assert(docset.count() == 2)
    # Using get on the external ids result in
    # one of the persisted objects
    assert(tm1.get("test_load_basic_1") in docset)
    assert(tm1.get("test_load_basic_2") in docset)


def test_load_m2o():
    tm1 = self.env["test.load.model"]

    # Advanced Importation
    outcome = tm1.load(
        ["id",
         "name",
         "age",
         "manytoone_id/id",
         "manytoone_id/name"
         ],
        [
            [
                "test_load_m2o_1",
                "name1A",
                1,
                "related1",
                "related1_name"
            ],
            [
                "test_load_m2o_2",
                "name2A",
                2,
                "related2",
                "related2_name"
            ]
        ])

    # Nothing went wrong
    assert(len(outcome["errors"]) == 0)
    # There are 2 ids
    assert(len(outcome["ids"]) == 2)
    # Those ids represent 2 persisted objects
    docset = tm1.search({"_id": {"$in": outcome["ids"]}})
    assert(docset.count() == 2)
    # Using get on the external ids result in
    # one of the persisted objects
    assert(tm1.get("test_load_m2o_1") in docset)
    assert(tm1.get("test_load_m2o_2") in docset)


def test_load_o2m():
    tm1 = self.env["test.load.model"]

    # Advanced Importation (O2M)
    outcome = tm1.load(
        [
            "id",
            "name",
            "age",
            "onetomany_ids/id",
            "onetomany_ids/name"
        ],
        [
            [
                "test_load_o2m_1",
                "name1A",
                1,
                "related1_a",
                "related1_a_name"
            ],
            [
                "",
                "",
                "",
                "related1_b",
                "related1_b_name"
            ],
            [
                "test_load_o2m_2",
                "name1A",
                1,
                "related2_a",
                "related2_a_name"
            ],
            [
                "",
                "",
                "",
                "related2_b",
                "related2_b_name"
            ]
        ])

    # Nothing went wrong
    assert(len(outcome["errors"]) == 0)
    # There are 2 ids
    assert(len(outcome["ids"]) == 2)
    # Those ids represent 2 persisted objects
    docset = tm1.search({"_id": {"$in": outcome["ids"]}})
    assert(docset.count() == 2)
    # Using get on the external ids result in
    # one of the persisted objects
    assert(tm1.get("test_load_o2m_1") in docset)
    assert(tm1.get("test_load_o2m_2") in docset)


def test_load_m2m():
    tm1 = self.env["test.load.model"]

    # Advanced Importation (M2M)
    outcome = tm1.load(
        [
            "id",
            "name",
            "age",
            "manytomany_ids/id",
            "manytomany_ids/name"
        ],
        [
            [
                "test_load_m2m_1",
                "name1A",
                1,
                "m2m_related1_a",
                "m2m_related1_a_name"
            ],
            [
                "",
                "",
                "",
                "m2m_related1_b",
                "m2m_related1_b_name"
            ],
            [
                "test_load_m2m_2",
                "name1A",
                1,
                "m2m_related2_a",
                "m2m_related2_a_name"
            ],
            [
                "",
                "",
                "",
                "m2m_related2_b",
                "m2m_related2_b_name"
            ]
        ])

    # Nothing went wrong
    assert(len(outcome["errors"]) == 0)
    # There are 2 ids
    assert(len(outcome["ids"]) == 2)
    # Those ids represent 2 persisted objects
    docset = tm1.search({"_id": {"$in": outcome["ids"]}})
    assert(docset.count() == 2)
    # Using get on the external ids result in
    # one of the persisted objects
    assert(tm1.get("test_load_m2m_1") in docset)
    assert(tm1.get("test_load_m2m_2") in docset)


def test_load_overwrite():
    tm1 = self.env["test.load.model"]
    # Test importation overwriting existing documents
    tm1.load(
        ["id", "name", "age", "boolean"],
        [
            ["test_load_ow_1", "name1B", 1, 1],
            ["test_load_ow_2", "name2B", 2, 0]])

    doc1 = tm1.get("test_load_ow_1")
    doc2 = tm1.get("test_load_ow_2")
    assert(doc1.name == "name1B")
    assert(doc2.name == "name2B")
    assert(doc1.boolean == True)
    assert(doc2.boolean == False)

    # Test importation without providing ids
    outcome = tm1.load(
        ["name", "age"],
        [
            ["name1C", 1],
            ["name2C", 2]])

    # use browse and outcome["ids"]
    assert(tm1.browse(outcome["ids"][0]).name == "name1C")
    # Get by automatically generated external id
    assert(tm1.get("__import__.{}".format(outcome["ids"][1])).name == "name2C")

    # Test failed validation
    outcome = tm1.load(
        ["name", "age"],
        [
            ["name1C", "not an integer"],
            ["name2C", 2]])

    assert(len(outcome["ids"]) == 0)
    assert(len(outcome["errors"]) == 1)


def test_model_finish():
    """ Clean previous tests """
    conn = db.Connection()
    conn.db["test.load.model"].drop()
    conn.db["test.load.comodel"].drop()
    conn.db["test.load.comodel.rel"].drop()
    # Delete records generated by importations
    conn.db["base.model.data"].delete_many({"model": "test.load.model"})
    conn.db["base.model.data"].delete_many({"model": "test.load.comodel"})
