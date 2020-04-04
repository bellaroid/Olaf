from olaf import models, fields, registry

@registry.add
class User(models.Model):
    _name = "base.users"
    name = fields.Char(required=True, max_length=255)
    age = fields.Integer(required=True)

    def say_my_name(self):
        return "Hi, my name is {}!".format(self.name)