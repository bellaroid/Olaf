from frozendict import frozendict


class GlobalStorageMeta(type):
    """ This class ensures there's always a single
    instance of the GlobalStorage class along the entire
    application. 
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                GlobalStorageMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class GlobalStorage(metaclass=GlobalStorageMeta):
    """ Global Storage """

    def __init__(self):
        self.__data__ = dict()

    def __setitem__(self, key, value):
        self.__data__[key] = value

    def __getitem__(self, key):
        return self.__data__[key]


# Instantiate GlobalStorage
g = GlobalStorage()


class AppContextMeta(type):
    """ This class ensures there's always a single
    instance of the AppContext class along the entire
    application. 
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                AppContextMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class AppContext(metaclass=AppContextMeta):
    """ Global Storage """

    def __init__(self):
        self.__data__ = frozendict()

    def __setitem__(self, key, value):
        raise RuntimeError("Application Context is Read-Only")

    def __getitem__(self, key):
        return self.__data__[key]

    def read(self, key):
        if key not in self.__data__:
            return None
        return self.__data__[key]

    def write(self, key, value):
        unfrozen = {k: v for k, v in self.__data__.items()}
        unfrozen[key] = value
        self.__data__ = frozendict(unfrozen)
