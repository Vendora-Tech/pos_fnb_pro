from odoo import api, fields, models


class SaasAccessRuleChatter(models.Model):
    _name = "saas.access.rule.chatter"
    _description = "Model-wise Chatter Access Restriction"
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
    hide_chatter = fields.Boolean(
        string="Hide Entire Chatter",
        default=False,
        help="Completely hide chatter widget for this model.",
    )
    hide_send_message = fields.Boolean(
        string="Hide Send Message",
        default=False,
        help="Hide Send Message button in chatter.",
    )
    hide_log_note = fields.Boolean(
        string="Hide Log Notes",
        default=False,
        help="Hide Log Note button in chatter.",
    )
    hide_activity = fields.Boolean(
        string="Hide Schedule Activity",
        default=False,
        help="Hide Activities button in chatter.",
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
