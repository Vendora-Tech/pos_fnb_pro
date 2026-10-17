from odoo import api, fields, models


class SaasAccessRuleButtonTab(models.Model):
    _name = "saas.access.rule.button.tab"
    _description = "Button and Tab Access Restriction"
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
    button_tab_type = fields.Selection(
        [
            ("button", "Button / Action Link"),
            ("tab", "Tab / Page"),
        ],
        string="Type",
        default="button",
        required=True,
    )
    name = fields.Char(
        string="Element Name / String",
        required=True,
        help="Technical name or display string of the button/tab (e.g. action_post, order_lines).",
    )
    hide = fields.Boolean(
        string="Hide Element",
        default=True,
        help="Hide this button or tab from views.",
    )
    conditional_domain = fields.Char(
        string="Conditional Domain",
        default="",
        help="Condition when this button/tab should be hidden/disabled.",
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
