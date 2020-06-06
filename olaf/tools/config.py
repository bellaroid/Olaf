import os


class Setting(object):
    """ An object that stores a read-only value
    """

    def __init__(self, value):
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

    APP_URL = Setting(os.environ.get('APP_URL', 'http://localhost:5000'))
    SECRET_KEY = Setting(os.getenv("SECRET_KEY", "SoMeThInGrEaLlYhArDtOgUeSs"))
    DB_NAME = Setting(os.getenv("MONGODB_NAME", "olaf"))
    DB_PASS = Setting(os.getenv("MONGODB_PASS", None))
    DB_USER = Setting(os.getenv("MONGODB_USER", None))
    DB_HOST = Setting(os.getenv("MONGODB_HOST", "localhost"))
    DB_PORT = Setting(os.getenv("MONGODB_PORT", 27017))
    DB_TOUT = Setting(os.getenv("MONGODB_TIMEOUT", 2000))
    JWT_EXPIRATION_TIME = Setting(os.getenv("JWT_EXPIRATION_TIME", 2000))

config = Config