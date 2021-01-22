import pytest
import contextlib

from bson import ObjectId
from olaf import registry
from olaf.db import Connection
from olaf.tools.environ import Environment

@contextlib.contextmanager
def start_session():
    conn = Connection()
    client = conn.cl
    with client.start_session() as session:
        with session.start_transaction():
            uid = ObjectId("000000000000000000000000")
            env = Environment(uid, session)
            baseUser = registry["base.user"]
            rootUser = baseUser(env)
            yield rootUser
            session.abort_transaction()
  
@pytest.fixture(scope="module")
def root():
    with contextlib.ExitStack() as stack:
        yield stack.enter_context(start_session())
