from odoo import api, fields, models


class SaasAccessRuleModel(models.Model):
    _name = "saas.access.rule.model"
    _description = "Model-level Access Restriction"
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
    hide_create = fields.Boolean(
        string="Hide Create",
        default=False,
        help="Hide Create/New buttons on views for this model.",
    )
    hide_edit = fields.Boolean(
        string="Hide Edit",
        default=False,
        help="Hide Edit/Modify buttons on views for this model.",
    )
    hide_delete = fields.Boolean(
        string="Hide Delete",
        default=False,
        help="Hide Delete action on views for this model.",
    )
    hide_archive = fields.Boolean(
        string="Hide Archive/Unarchive",
        default=False,
        help="Hide Archive and Unarchive actions for this model.",
    )
    hide_duplicate = fields.Boolean(
        string="Hide Duplicate",
        default=False,
        help="Hide Duplicate action for this model.",
    )
    hide_export = fields.Boolean(
        string="Hide Export",
        default=False,
        help="Hide Export feature for this model.",
    )
    hide_import = fields.Boolean(
        string="Hide Import",
        default=False,
        help="Hide Import feature for this model.",
    )
    hide_report = fields.Boolean(
        string="Hide Print / Reports",
        default=False,
        help="Hide report print actions for this model.",
    )
    hide_action = fields.Boolean(
        string="Hide Actions",
        default=False,
        help="Hide contextual actions in the Action menu for this model.",
    )
    hide_search_panel = fields.Boolean(
        string="Hide Search Panel",
        default=False,
        help="Hide search panel on left side of views for this model.",
    )
    hide_filters = fields.Boolean(
        string="Hide Filters",
        default=False,
        help="Hide default search filters for this model.",
    )
    hide_group_by = fields.Boolean(
        string="Hide Group By",
        default=False,
        help="Hide Group By options for this model.",
    )

    _check_model_unique = models.Constraint(
        "UNIQUE(rule_id, model_id)",
        "Aturan model untuk policy ini sudah ada!",
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
