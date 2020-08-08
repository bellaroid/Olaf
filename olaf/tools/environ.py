from olaf import registry
from olaf.db import Connection, DocumentCache
from frozendict import frozendict

class Environment(object):
    def __init__(self, uid, session=None, context=dict()):
        _context = {"uid": uid}
        for key, value in context.items():
            _context[key] = value
        self.context =  frozendict(_context)
        self.session =  session
        self.registry = registry
        self.conn =     Connection()
        self.cache =    DocumentCache()

    def __iter__(self):
        return iter(self.registry)

    def __getitem__(self, key):
        """ Return an instance of the requested model class """
        if not key in self.registry:
            raise KeyError("Model not found in registry")
        return self.registry[key](self)


