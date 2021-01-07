import pytest
from bson import ObjectId
from olaf import registry
from olaf.tools.environ import Environment
from olaf.security import AccessError

uid = ObjectId("000000000000000000000000")
env = Environment(uid)
self = registry["base.user"](env, {"_id": uid})
group = None
user = None
impersonated = None


def test_init():
    # Create a group with an ACL
    global group
    global user
    global impersonated

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


def test_ACL_deny_create():
    # Attempt to create a document
    with pytest.raises(AccessError):
        impersonated.create({
            "name": "__TEST Doesn't matter, should fail",
            "email": "__TEST doesntmattercozitwillfail",
            "password": "itsgonnafailso",
        })


def test_ACL_deny_write():
    # Attempt to modify a document
    with pytest.raises(AccessError):
        impersonated.write({"name": "shouldntchange"})


def test_ACL_deny_read():
    # Attempt to access a document using get()
    with pytest.raises(AccessError):
        impersonated.get("base.user.admin")

    # Attempt to access a document using browse()
    with pytest.raises(AccessError):
        impersonated.browse(self.get("base.user.admin")._id)


def test_ACL_deny_unlink():
    # Attempt to delete a document using unlink()
    with pytest.raises(AccessError):
        impersonated.unlink()


def test_finish():
    """ Clean previous tests """
    user = self.search({"email": {"$regex": "^__TEST"}})
    user.unlink()
    group = self.env["base.group"].search({"name": {"$regex": "^__TEST"}})
    group.unlink()
    acls = self.env["base.acl"].search({"name": {"$regex": "^__TEST"}})
    acls.unlink()
