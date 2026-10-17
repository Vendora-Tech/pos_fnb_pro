from odoo import api, fields, models


class SaasAccessRuleField(models.Model):
    _name = "saas.access.rule.field"
    _description = "Field-level Access Restriction"
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
        index=True,
    )
    model_name = fields.Char(
        related="model_id.model",
        string="Technical Model Name",
        store=True,
        index=True,
    )
    field_id = fields.Many2one(
        "ir.model.fields",
        string="Target Field",
        required=True,
        ondelete="cascade",
        domain="[('model_id', '=', model_id)]",
    )
    field_name = fields.Char(
        related="field_id.name",
        string="Technical Field Name",
        store=True,
        index=True,
    )
    is_invisible = fields.Boolean(
        string="Hide Field",
        default=False,
        help="Make this field completely hidden from form, list, and kanban views.",
    )
    is_readonly = fields.Boolean(
        string="Read Only",
        default=False,
        help="Lock this field so users cannot modify its value.",
    )
    is_required = fields.Boolean(
        string="Required",
        default=False,
        help="Make this field mandatory for entry.",
    )
    remove_external_link = fields.Boolean(
        string="Restrict External Link",
        default=False,
        help="Disable opening related records from dropdown.",
    )
    no_create = fields.Boolean(
        string="Restrict Create",
        default=False,
        help="Disable quick create option on relational dropdown.",
    )
    no_create_edit = fields.Boolean(
        string="Restrict Create & Edit",
        default=False,
        help="Disable 'Create and Edit...' option on relational dropdown.",
    )
    hide_export = fields.Boolean(
        string="Restrict Export",
        default=False,
        help="Prevent exporting this field to spreadsheet.",
    )
    conditional_domain = fields.Char(
        string="Conditional Domain",
        default="",
        help="Python condition / domain string for dynamic field visibility, e.g. [('state', '=', 'done')]",
    )

    _check_field_unique = models.Constraint(
        "UNIQUE(rule_id, model_id, field_id)",
        "Aturan field untuk model dan policy ini sudah ada!",
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
