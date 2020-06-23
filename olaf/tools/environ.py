from olaf import registry
from olaf.db import Connection
from frozendict import frozendict

class Environment(object):
    def __init__(self, uid, session=None):
        self.context =  frozendict({"uid": uid})
        self.session =  session
        self.registry = registry
        self.conn =     Connection()

    def __iter__(self):
        return iter(self.registry)

    def __getitem__(self, key):
        """ Return an instance of the requested model class """
        if not key in self.registry:
            raise KeyError("Model not found in registry")
        return self.registry[key](self)


