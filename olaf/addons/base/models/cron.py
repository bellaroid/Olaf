from olaf import models, fields, registry

@registry.add
class Cron(models.Model):
    _name = "base.cron"

    name =      fields.Char(max_length=255, required=True)
    status =    fields.Char(max_length=32, required=True)
    nextcall =  fields.DateTime(required=True)
    interval =  fields.Integer(required=True)
    user_id =   fields.Many2one("base.user")
    code =      fields.Char()
