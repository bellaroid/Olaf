import os

class Setting(object):
    """ An object that stores a read-only value
    """

    def __init__(self, setting_type, value):
        if setting_type == "int":
            value = int(value)
        elif setting_type == "bool":
            if not isinstance(value, bool):
                if value.upper() in ["FALSE", "OFF", "0"]:
                    value = False
                else:
                    value = True
        self.value = value
    
    def __get__(self, instance, owner):
        return self.value

    def __set__(self, instance, value):
        raise RuntimeError("Settings are Read-Only")


class Config:
    """ 
    Application Settings. This object contains a 
    collection of static attributes available for
    the whole application environment.
    """
    APP_URL =              Setting("str",   os.environ.get("APP_URL", "http://localhost:5000"))
    APP_DEBUG =            Setting("bool",  os.environ.get("APP_DEBUG", True))
    APP_RELOAD =           Setting("bool",  os.environ.get("APP_RELOAD", True))
    SECRET_KEY =           Setting("str",   os.getenv("SECRET_KEY", "SoMeThInGrEaLlYhArDtOgUeSs"))
    DB_NAME =              Setting("str",   os.getenv("MONGODB_NAME", "olaf"))
    DB_PASS =              Setting("str",   os.getenv("MONGODB_PASS", None))
    DB_USER =              Setting("str",   os.getenv("MONGODB_USER", None))
    DB_HOST =              Setting("str",   os.getenv("MONGODB_HOST", "localhost"))
    DB_PORT =              Setting("int",   os.getenv("MONGODB_PORT", 27017))
    DB_TOUT =              Setting("int",   os.getenv("MONGODB_TIMEOUT", 2000))
    DB_REPLICASET_ENABLE = Setting("bool",  os.getenv("MONGODB_REPLICASET_ENABLE", False))
    DB_REPLICASET_ID =     Setting("str",   os.getenv("MONGODB_REPLICASET_ID", "rs0"))
    JWT_EXPIRATION_TIME =  Setting("int",   os.getenv("JWT_EXPIRATION_TIME", 2000))
    ROOT_PASSWORD =        Setting("str",   os.getenv("ROOT_PASSWORD", "olaf"))

config = Config