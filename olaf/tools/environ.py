from olaf import registry
from frozendict import frozendict

class Environment(object):
    def __init__(self, uid, session=None):
        self.context = frozendict({"uid": uid})
        self.session = session
        self.registry = registry


