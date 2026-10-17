from odoo import models
from odoo.exceptions import UserError


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        user = self.env.user
        if user.id != 1 and not (user._is_system() or user._is_admin()):
            report_sudo = self._get_report(report_ref)
            rule_model = self.env["saas.access.rule"].sudo().with_context(saas_access_bypass=True)
            if rule_model._is_report_restricted(user.id, report_sudo.id, report_sudo.model):
                raise UserError("Anda tidak memiliki izin untuk mencetak dokumen/laporan ini!")
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
