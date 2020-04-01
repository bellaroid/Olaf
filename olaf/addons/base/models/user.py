from olaf import models, fields

class User(models.Model):
    name = fields.Char(required=True)