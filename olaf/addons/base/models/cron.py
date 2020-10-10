from olaf import models, fields, registry


@registry.add
class Cron(models.Model):
    _name = "base.cron"

    name =      fields.Char(max_length=255, required=True)
    status =    fields.Char(max_length=32, required=True)
    nextcall =  fields.DateTime(required=True)
    interval =  fields.Integer(required=True)
    interval_type = fields.Selection(required=True, choices=["seconds", "minutes", "hours", "days", "weeks", "months", "years"])
    user_id =   fields.Many2one("base.user", required=True)
    code =      fields.Char(required=True)

    # Restart scheduler whenever
    # a job is either created, 
    # modified or deleted
    
    def write(self, *args, **kwargs):
        super().write(*args, **kwargs)
        self._reset_scheduler()
        return

    def create(self, *args, **kwargs):
        result = super().create(*args, **kwargs)
        self._reset_scheduler()
        return result

    def unlink(self, *args, **kwargs):
        result = super().unlink(*args, **kwargs)
        self._reset_scheduler()
        return result

    def _reset_scheduler(self):
        from olaf.cron import Scheduler
        sch = Scheduler()
        sch.reset()
