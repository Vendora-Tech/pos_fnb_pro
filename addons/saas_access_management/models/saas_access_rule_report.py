from odoo import api, fields, models


class SaasAccessRuleReport(models.Model):
    _name = "saas.access.rule.report"
    _description = "Report / Print Access Restriction"
    _order = "id desc"

    rule_id = fields.Many2one(
        "saas.access.rule",
        string="Access Policy Rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    model_id = fields.Many2one(
        "ir.model",
        string="Target Model",
        required=True,
        ondelete="cascade",
    )
    model_name = fields.Char(
        related="model_id.model",
        string="Technical Model Name",
        store=True,
        index=True,
    )
    report_id = fields.Many2one(
        "ir.actions.report",
        string="Target Report",
        required=True,
        ondelete="cascade",
    )
    report_name = fields.Char(
        related="report_id.name",
        string="Report Name",
        store=True,
    )
    hide = fields.Boolean(
        string="Hide / Restrict Report",
        default=True,
    )

    def _clear_rule_caches(self):
        """Invalidate caches agar perubahan rule langsung efektif."""
        self.env.invalidate_all()
        if hasattr(self.env.transaction, "invalidate_access_cache"):
            self.env.transaction.invalidate_access_cache()
        if hasattr(self.env.transaction, "invalidate_ormcache"):
            self.env.transaction.invalidate_ormcache()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._clear_rule_caches()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._clear_rule_caches()
        return res

    def unlink(self):
        res = super().unlink()
        self._clear_rule_caches()
        return res
