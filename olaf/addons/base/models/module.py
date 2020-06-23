from olaf import models, fields, registry

@registry.add
class Module(models.Model):
    _name = "base.module"

    name = fields.Char(unique=True)
    status = fields.Char()