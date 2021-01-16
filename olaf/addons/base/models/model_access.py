from olaf import models, fields, registry

@registry.add
class AccessControlRule(models.Model):
    _name = "base.acl"

    name =          fields.Char(unique=True)
    model =         fields.Char(required=True)
    group_id =      fields.Many2one("base.group")
    allow_read =    fields.Boolean(required=True, default=False)
    allow_write =   fields.Boolean(required=True, default=False)
    allow_create =  fields.Boolean(required=True, default=False)
    allow_unlink =  fields.Boolean(required=True, default=False)


@registry.add
class DocumentLevelSecurityRule(models.Model):
    _name = "base.dls"

    name =          fields.Char(required=True)
    model =         fields.Char(required=True)
    query =         fields.Char(required=True)
    group_ids =     fields.Many2many("base.group", relation="base.group.dls.rel", field_a="dls_oid", field_b="group_oid")
    on_read =       fields.Boolean(required=True, default=True)
    on_write =      fields.Boolean(requried=True, default=True)
    on_create =     fields.Boolean(required=True, default=True)
    on_unlink =     fields.Boolean(required=True, default=True)