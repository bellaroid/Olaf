class ModelRegistry(object):

    def __init__(self):
        self.__models__ = dict()

    def __getitem__(self, key):
        if not key in self.__models__:
            raise KeyError("Model not found in registry")
        return self.__models__[key]
        
    def add(self, cls):
        """ Classes wrapped around this method
        will be added to the registry.
        """
        self.__models__[cls._name] = cls
        return cls



