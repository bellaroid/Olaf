import pytest
from olaf import registry
from olaf.tools import initialize

initialize()


def test_password():
    """ Verify password assignment and decoding
    functions are working properly
    """
    # Create a new user
    user = registry["base.user"].create({
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

