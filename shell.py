from olaf.addons.base.models.user import User
from olaf import db, registry

user_a = User({})
user_b = User({})

assert(user_a != user_b)
