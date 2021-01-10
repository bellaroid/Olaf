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


def test_ACL_allow_create():
    # Change allow_create setting on group
    group.acl_ids.allow_create = True
    # Attempt to create document
    new_user = impersonated.create({
        "name": "__TEST Create User",
        "email": "__TEST@create.com",
        "password": "Banana"
    })
    # Ensure new document exists
    new_user.ensure_one()


def test_ACL_deny_read():
    # Attempt to access a document using search()
    with pytest.raises(AccessError):
        impersonated.search({"name": "__TEST Create User"})

    # Attempt to access a document using get()
    with pytest.raises(AccessError):
        impersonated.get("base.user.admin")

    # Attempt to access a document using browse()
    with pytest.raises(AccessError):
        impersonated.browse(self.get("base.user.admin")._id)


def test_ACL_allow_read():
    # Change allow_write setting on group
    group.acl_ids.allow_read = True

    # Attempt to access a document using search()
    usr = impersonated.search({"name": "__TEST Create User"})
    usr.ensure_one()

    # Attempt to access a document using get()
    admin = impersonated.get("base.user.admin")
    admin.ensure_one()

    # Attempt to access a document using browse()
    admin = impersonated.browse(self.get("base.user.admin")._id)
    admin.ensure_one()


def test_ACL_deny_write():
    # Get previously created user
    usr = impersonated.search({"name": "__TEST Create User"})
    # Attempt to modify a document
    with pytest.raises(AccessError):
        usr.write({"name": "shouldntchange"})


def test_ACL_allow_write():
    # Change allow_write setting on group
    group.acl_ids.allow_write = True
    # Get previously created user
    usr = impersonated.search({"name": "__TEST Create User"})
    # Attempt to modify a document
    usr.write({"name": "__TEST Modified"})
    assert(usr.name == "__TEST Modified")


def test_ACL_deny_unlink():
    # Attempt to delete a document using unlink()
    with pytest.raises(AccessError):
        impersonated.unlink()

def test_ACL_allow_unlink():
    # Change allow_unlink setting on group
    group.acl_ids.allow_unlink = True
    # Get previously created user
    usr = impersonated.search({"name": "__TEST Modified"})
    # Attempt to delete a document
    usr.unlink()
    assert(usr.count() == 0)


def test_finish():
    """ Clean previous tests """
    user = self.search({"email": {"$regex": "^__TEST"}})
    user.unlink()
    group = self.env["base.group"].search({"name": {"$regex": "^__TEST"}})
    group.unlink()
    acls = self.env["base.acl"].search({"name": {"$regex": "^__TEST"}})
    acls.unlink()
