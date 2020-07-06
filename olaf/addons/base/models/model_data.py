from olaf import models, fields, registry


@registry.add
class ModelData(models.Model):
    _name = "base.model.data"

    name = fields.Char(required=True)
    model = fields.Char(required=True)
    res_id = fields.Identifier(required=True)
