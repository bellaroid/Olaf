import pytest
from bson import ObjectId
from olaf.security import AccessError

@pytest.mark.usefixtures("root")
class TestDLS:

    def test_init(self, root):
        # Create a group with an ACL
        self.group = root.env["base.group"].create({
            "name": "__TEST_acl_Group",
            "acl_ids": [("create", {
                "name": "__TEST ACL",
                "model": "base.user",
                "allow_read": True,
                "allow_write": True,
                "allow_create": True,
                "allow_unlink": True
            })],
            "dls_ids": [("create", {
                "name": "__TEST DLS",
                "model": "base.user",
                "query": '{"email": "test@document.com"}',
                "on_read": False,
                "on_write": False,
                "on_create": False,
                "on_unlink": False
            })]
        })

        # Create a new user
        self.user = root.create({
            "name": "__TEST User",
            "email": "test@user.com",
            "password": "Banana",
            "group_ids": [("add", self.group)]
        })

        # Create a test record
        self.test_document = root.create({
            "name": "__TEST Document",
            "email": "test@document.com",
            "password": "Banana"
        })

        # Impersonate User
        self.impersonated = root.env["base.user"].with_context(uid=self.user._id)

        import pdb; pdb.set_trace()


    def test_DLS_read(self, root):
        # Attempt to read users
        # DLS on_read is disabled
        result = self.impersonated.search({})

        # User should be able to read all users
        # Including root, admin, the test user and itself 
        assert(result.count() >= 4)

        # Modify the DLS setting
        self.group.dls_ids.on_read = True

        # Now DLS on_read is active
        # User should be able to read only the test document
        result = self.impersonated.search({})
        result.ensure_one()

        # Attempting to obtain any other document
        # by browse or get should raise access errors
        with pytest.raises(AccessError):
            self.impersonated.browse(ObjectId("000000000000000000000000"))

        with pytest.raises(AccessError):
            self.impersonated.get("base.user.admin")

    def test_DLS_write():
        # Attempt to modify own data
        # First, disable on_read from previous test
        group.dls_ids.on_read = False

        # DLS on_write is disabled
        # User should be able to write on any document
        usr = impersonated.search({"name": "__TEST User"})
        usr.name = "__TEST User Modified"
        assert(usr.name == "__TEST User Modified")

        # Change it back
        usr.name = "__TEST User"
        assert(usr.name == "__TEST User")

        # Change the DLS on_write setting
        group.dls_ids.on_write = True

        # Now DLS on_write is active
        # User should be able to modify only the test document
        with pytest.raises(AccessError):
            usr.name = "__TEST User Modified Again"

        # But we should be able to modify the test document
        td = impersonated.search({"name": "__TEST Document"})
        td.name = "__TEST Document Modified"
        assert(td.name == "__TEST Document Modified")

        # Change it back
        td.name = "__TEST Document"
        assert(td.name == "__TEST Document")


    def test_DLS_unlink():
        # Activate DLS on_unlink setting
        group.dls_ids.on_unlink = True

        # Look for own user
        usr = impersonated.search({"name": "__TEST User"})
        usr.ensure_one()

        # While DLS on_unlink is activated
        # The only document user may erase is the test document
        with pytest.raises(AccessError):
            usr.unlink()
        
        # Look for the test document
        td = impersonated.search({"name": "__TEST Document"})
        td.ensure_one()
        
        # Delete it
        td.unlink()
        assert(td.count() == 0)


    def test_DLS_create():
        # Activate DLS on_create setting
        group.dls_ids.on_create = True

        # Attempt to create a user
        # that doesn't satisfy the DLS query
        with pytest.raises(AccessError):
            impersonated.create({
                "name": "__TEST Document",
                "email": "somethingthatdoesnotsatisfythedlsquery@document.com",
                "password": "Banana"
            })