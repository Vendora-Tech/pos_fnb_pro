from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        """Modifikasi session_info web client untuk penegakan batas hak akses."""
        session_info = super().session_info()
        user = self.env.user

        if user.id != 1 and not (user._is_system() or user._is_admin()):
            rule_model = self.env["saas.access.rule"]
            active_rules = rule_model._get_active_rules_for_user(user.id)

            # 1. Nonaktifkan Developer Mode jika diatur
            if any(active_rules.mapped("disable_debug_mode")):
                if request and hasattr(request, "session") and getattr(request.session, "debug", False):
                    request.session.debug = ""
                session_info["debug"] = ""

            # 2. Nonaktifkan Export
            if rule_model._is_export_disabled_for_user(user.id):
                if "groups" in session_info:
                    session_info["groups"]["base.group_allow_export"] = False
                session_info["can_export"] = False

            # 3. Readonly status
            if rule_model._is_readonly_user(user.id):
                session_info["is_readonly"] = True

            # 4. Hide Spreadsheet button
            if any(active_rules.mapped("hide_spreadsheets")):
                session_info["can_insert_in_spreadsheet"] = False

        return session_info
