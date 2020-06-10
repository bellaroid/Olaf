# Read .env file before doing anything else
from dotenv import load_dotenv
load_dotenv()

from .db import ModelRegistry

# Initialize Registry
registry = ModelRegistry()

from . import tools
from . import security
from . import fields
from . import models
from . import jsonrpc