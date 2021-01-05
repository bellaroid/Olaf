import pytest
from bson import ObjectId
from olaf import registry
from olaf.tools.environ import Environment
from olaf.security import AccessError

uid = ObjectId("000000000000000000000000")
env = Environment(uid)
self = registry["base.user"](env, {"_id": uid})

def test_ACL():
    """
    Test ACL (Access Control List) checks.
    """
    # Create a group with an ACL
    group = self.env["base.group"].create({
        "name": "__TEST_acl_Group",
        "acl_ids": [("create", {
            "name": "__TEST ACL",
            "model": "base.user",
            "allow_read": False,
            "allow_write": False,
            "allow_create": False,
            "allow_unlink": False
        })]
    })

    # Create a new user
    user = self.create({
        "name": "__TEST User",
        "email": "__TEST@email.com",
        "age": 100,
        "password": "Banana",
        "group_ids": [("add", group)]
    })

    # Impersonate User
    impersonated = self.env["base.user"].with_context(uid=user._id)

    # Attempt to create a document
    with pytest.raises(AccessError):
        impersonated.create({
            "name": "__TEST Doesn't matter, should fail",
            "email": "__TEST doesntmattercozitwillfail",
            "password": "itsgonnafailso",
        })


def test_finish():
    """ Clean previous tests """
    user = self.search({"email": {"$regex": "^__TEST"}})
    user.unlink()
    group = self.env["base.group"].search({"name": {"$regex": "^__TEST"}})
    group.unlink()
    acls = self.env["base.acl"].search({"name": {"$regex": "^__TEST"}})
    acls.unlink()

