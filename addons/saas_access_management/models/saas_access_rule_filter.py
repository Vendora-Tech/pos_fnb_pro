from odoo import api, fields, models


class SaasAccessRuleFilter(models.Model):
    _name = "saas.access.rule.filter"
    _description = "Filter and Group By Access Restriction"
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
    filter_type = fields.Selection(
        [
            ("filter", "Filter"),
            ("group_by", "Group By"),
        ],
        string="Type",
        default="filter",
        required=True,
    )
    name = fields.Char(
        string="Filter / Group Name or String",
        required=True,
        help="Name attribute or label of the filter / group in search view.",
    )
    hide = fields.Boolean(
        string="Hide Element",
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
