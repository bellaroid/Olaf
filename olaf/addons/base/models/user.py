from olaf import models, fields, registry
from werkzeug.security import check_password_hash, generate_password_hash

@registry.add
class User(models.Model):
    _name = "base.user"

    name =      fields.Char(required=True, max_length=255)
    email =     fields.Char(unique=True)
    password =  fields.Char(exclude=True, required=True, setter="generate_password")
    group_ids = fields.Many2many("base.group", relation="base.user.group.rel", field_a="user_oid", field_b="group_oid")

    def say_my_name(self):
        for rec in self:
            print("Hi, my name is {}!".format(rec.name))
        return

    def say_our_names(self):
        names = [rec.name for rec in self]
        print("Hi, we're {}".format(", ".join(names)))
        return

    def check_password(self, plain_password):
        self.ensure_one()
        return check_password_hash(self.password, plain_password)

    def generate_password(self, plain_password):
        return generate_password_hash(plain_password)


@registry.add
class Group(models.Model):
    _name = "base.group"

    name =      fields.Char(required=True, max_length=255)

