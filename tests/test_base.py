import pytest
from bson import ObjectId
from olaf import registry
from olaf.tools import initialize
from olaf.tools.environ import Environment

initialize()

uid = ObjectId(b"baseuserroot")
env = Environment(uid)
self = registry["base.user"](env, {"_id": uid})

def test_password():
    """ Verify password assignment and decoding
    functions are working properly
    """
    # Create a new user
    user = self.create({
        "name": "Test User",
        "email": "test@email.com",
        "age": 100,
        "password": "Banana"
    })
    # Verify password
    assert(user.check_password("Banana"))
    # Assign new password and verify
    user.password = "Apple"
    assert(user.check_password("Apple"))
    # Delete user
    user.unlink()

