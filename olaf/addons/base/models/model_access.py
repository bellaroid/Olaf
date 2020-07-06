from olaf import models, fields, registry

@registry.add
class ModelAccess(models.Model):
    _name = "base.model.access"

    name =          fields.Char(unique=True)
    model =         fields.Char(required=True)
    group_id =      fields.Many2one("base.group")
    allow_read =    fields.Boolean(required=True, default=False)
    allow_write =   fields.Boolean(required=True, default=False)
    allow_create =  fields.Boolean(required=True, default=False)
    allow_unlink =  fields.Boolean(required=True, default=False)
