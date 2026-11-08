from odoo import fields, models
from odoo.exceptions import AccessDenied


class ResUsers(models.Model):
    _inherit = "res.users"

    access_management_rule_ids = fields.Many2many(
        "saas.access.rule",
        "saas_access_rule_users_rel",
        "user_id",
        "rule_id",
        string="Access Management Policies",
        help="Kebijakan Access Management yang diterapkan pada pengguna ini.",
    )

    def write(self, vals):
        res = super().write(vals)
        if "access_management_rule_ids" in vals:
            self.env["saas.access.rule"]._clear_rule_caches()
        return res

    def _check_credentials(self, credential, env):
        if self.id != 1:
            rule_model = self.env["saas.access.rule"].sudo().with_context(saas_access_bypass=True)
            if rule_model._is_login_disabled(self.id):
                raise AccessDenied(
                    "Akses masuk Anda telah dinonaktifkan oleh kebijakan Access Management!"
                )
        return super()._check_credentials(credential, env)
