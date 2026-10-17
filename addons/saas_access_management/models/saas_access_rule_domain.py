from odoo import api, fields, models


class SaasAccessRuleDomain(models.Model):
    _name = "saas.access.rule.domain"
    _description = "Domain-based Record Restriction"
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
    domain = fields.Char(
        string="Domain Filter",
        required=True,
        default="[]",
        help="Odoo domain filter expression, e.g. [('create_uid', '=', user.id)]",
    )
    restrict_read = fields.Boolean(
        string="Apply on Read",
        default=True,
        help="Filter visible records according to this domain.",
    )
    restrict_write = fields.Boolean(
        string="Restrict Edit",
        default=False,
        help="Prevent editing records that do not match the domain.",
    )
    restrict_create = fields.Boolean(
        string="Restrict Create",
        default=False,
        help="Prevent creating records outside this domain condition.",
    )
    restrict_delete = fields.Boolean(
        string="Restrict Delete",
        default=False,
        help="Prevent deleting records that match this domain.",
    )
    is_soft_restriction = fields.Boolean(
        string="Soft Restriction",
        default=False,
        help="If enabled, record visibility is not blocked but logged/warned.",
    )
    warning_message = fields.Char(
        string="Warning Message",
        default="Peringatan: Data ini berada di luar batas otoritas standar Anda.",
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
