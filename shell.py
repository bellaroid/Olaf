"""
The following file is meant to provide a 
basic shell context. Use it by running:

python -i shell.py

or 

ipython -i shell.py
(in case you have ipython installed)
"""
from bson import ObjectId
from olaf import registry
from olaf.tools import initialize
from olaf.tools.environ import Environment

initialize()

uid = ObjectId("000000000000000000000000")
env = Environment(uid)
self = registry["base.user"](env, {"_id": uid})