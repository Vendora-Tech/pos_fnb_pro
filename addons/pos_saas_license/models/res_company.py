from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = "res.company"

    saas_license_id = fields.Many2one(
        "pos.saas.license",
        string="Active License",
        compute="_compute_saas_license_info",
    )
    saas_license_state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("warning", "Warning"),
            ("grace", "Grace Period"),
            ("expired", "Expired"),
            ("invalid", "Invalid"),
        ],
        string="License Status",
        compute="_compute_saas_license_info",
    )
    saas_license_code = fields.Char(
        string="License ID",
        compute="_compute_saas_license_info",
    )
    saas_license_merchant = fields.Char(
        string="Licensed Merchant",
        compute="_compute_saas_license_info",
    )
    saas_valid_until = fields.Date(
        string="Valid Until",
        compute="_compute_saas_license_info",
    )
    saas_days_remaining = fields.Integer(
        string="Days Remaining",
        compute="_compute_saas_license_info",
    )
    saas_max_registers = fields.Integer(
        string="Max POS Registers",
        compute="_compute_saas_license_info",
    )
    saas_license_token = fields.Text(
        string="License Token",
        inverse="_inverse_saas_license_token",
        compute="_compute_saas_license_token",
    )

    def _get_active_saas_license(self):
        self.ensure_one()
        if not self.id or not isinstance(self.id, int):
            return self.env["pos.saas.license"]
        license_rec = self.env["pos.saas.license"].sudo().search([("company_id", "=", self.id)], limit=1)
        if not license_rec:
            license_rec = self.env["pos.saas.license"].sudo().create({
                "company_id": self.id,
                "name": "POS License",
            })
        return license_rec

    def _compute_saas_license_info(self):
        for company in self:
            license_rec = company._get_active_saas_license()
            if not license_rec:
                company.saas_license_id = False
                company.saas_license_state = "draft"
                company.saas_license_code = False
                company.saas_license_merchant = False
                company.saas_valid_until = False
                company.saas_days_remaining = 0
                company.saas_max_registers = 1
            else:
                company.saas_license_id = license_rec
                company.saas_license_state = license_rec.state
                company.saas_license_code = license_rec.license_id
                company.saas_license_merchant = license_rec.merchant_name
                company.saas_valid_until = license_rec.valid_until
                company.saas_days_remaining = license_rec.days_remaining
                company.saas_max_registers = license_rec.max_pos_registers

    def _compute_saas_license_token(self):
        for company in self:
            license_rec = company._get_active_saas_license()
            company.saas_license_token = license_rec.raw_token if license_rec else False

    def _inverse_saas_license_token(self):
        for company in self:
            if not company.id or not isinstance(company.id, int):
                continue
            license_rec = company._get_active_saas_license()
            if license_rec and company.saas_license_token != license_rec.raw_token:
                license_rec.action_install_token(company.saas_license_token)

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            company._get_active_saas_license()
        return companies

    def action_redeem_saas_license(self):
        self.ensure_one()
        token = (self.saas_license_token or "").strip()
        if not token:
            raise UserError(_("Silakan tempelkan token lisensi pada kolom License Token terlebih dahulu!"))

        license_rec = self._get_active_saas_license()
        result = license_rec.action_install_token(token)

        if result.get("state") == "invalid":
            reason = result.get("reason") or _("Format token tidak valid atau terpotong.")
            raise UserError(
                _("Aktivasi Lisensi Gagal:\n%s\n\nPastikan seluruh teks token disalin lengkap mulai dari 'eyJ...' sampai selesai.")
                % reason
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Aktivasi Lisensi Berhasil!"),
                "message": _("Lisensi %s untuk %s berhasil diaktifkan dengan status %s.")
                % (
                    license_rec.license_id,
                    license_rec.merchant_name,
                    license_rec.state.upper(),
                ),
                "sticky": False,
                "type": "success",
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
