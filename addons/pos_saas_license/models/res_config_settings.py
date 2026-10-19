"""Konfigurasi lisensi SaaS pada Settings POS (res.config.settings) (T024).

Menyediakan antarmuka Settings POS untuk memasang token lisensi,
melihat status lisensi terkini, sisa hari aktif, kuota register, dan detail lisensi.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Input token dari manajer POS (tidak disimpan di ir.config_parameter)
    saas_license_token = fields.Char(
        string="License Token",
        help="Input token lisensi JWT/JWS Ed25519 yang diterima dari portal merchant.",
    )

    # Field representasi status dan informasi lisensi aktif
    saas_license_state = fields.Selection(
        selection=[
            ("active", "Active"),
            ("warning", "Expiring Soon"),
            ("grace", "Grace Period"),
            ("expired", "Expired"),
            ("invalid", "Invalid Token"),
        ],
        string="License Status",
        compute="_compute_saas_license_info",
        readonly=True,
    )
    saas_license_id = fields.Char(
        string="License ID",
        compute="_compute_saas_license_info",
        readonly=True,
    )
    saas_merchant_name = fields.Char(
        string="Merchant Name",
        compute="_compute_saas_license_info",
        readonly=True,
    )
    saas_license_type = fields.Selection(
        selection=[
            ("subscription", "Subscription"),
            ("perpetual", "Perpetual (Beli Putus)"),
        ],
        string="License Type",
        compute="_compute_saas_license_info",
        readonly=True,
    )
    saas_valid_until = fields.Date(
        string="Valid Until",
        compute="_compute_saas_license_info",
        readonly=True,
    )
    saas_days_remaining = fields.Integer(
        string="Days Remaining",
        compute="_compute_saas_license_info",
        readonly=True,
    )
    saas_database_uuid = fields.Char(
        string="Database UUID",
        compute="_compute_saas_license_info",
        readonly=True,
    )
    saas_allowed_modules = fields.Char(
        string="Allowed Modules",
        compute="_compute_saas_license_info",
        readonly=True,
    )
    saas_state_message = fields.Char(
        string="Status Message",
        compute="_compute_saas_license_info",
        readonly=True,
    )
    saas_max_registers = fields.Integer(
        string="Max Registers",
        compute="_compute_saas_license_info",
        readonly=True,
    )
    saas_active_registers = fields.Integer(
        string="Active Registers",
        compute="_compute_saas_license_info",
        readonly=True,
    )

    def _get_saas_license(self):
        """Ambil record lisensi untuk company saat ini."""
        company = self.company_id or self.env.company
        return (
            self.env["pos.saas.license"]
            .with_company(company)
            ._get_current()
        )

    @api.depends("company_id")
    def _compute_saas_license_info(self):
        """Hitung seluruh informasi lisensi untuk tampilan Settings POS."""
        for record in self:
            company = record.company_id or record.env.company
            license_rec = (
                record.env["pos.saas.license"]
                .with_company(company)
                ._get_current()
            )

            # Hitung jumlah register unik yang sedang memiliki sesi aktif
            active_sessions = record.env["pos.session"].search([
                ("state", "!=", "closed"),
                ("config_id.company_id", "=", company.id),
            ])
            active_count = len(set(active_sessions.mapped("config_id.id")))

            record.saas_license_state = license_rec.state
            record.saas_license_id = license_rec.license_id
            record.saas_merchant_name = license_rec.merchant_name
            record.saas_license_type = license_rec.license_type
            record.saas_valid_until = license_rec.valid_until
            record.saas_days_remaining = license_rec.days_remaining
            record.saas_database_uuid = license_rec._get_database_uuid()
            record.saas_allowed_modules = license_rec.allowed_modules
            record.saas_state_message = license_rec.state_message
            record.saas_max_registers = license_rec.max_pos_registers
            record.saas_active_registers = active_count

    def action_saas_license_verify(self):
        """Aksi tombol 'Verify & Activate License' di Settings POS.

        Memvalidasi token baru yang dimasukkan:
        - Jika valid: memperbarui raw_token, memverifikasi ulang, dan me-refresh cache.
        - Jika tidak valid: membatalkan proses dengan UserError dan TIDAK merusak token lama.
        """
        self.ensure_one()
        raw_token = (self.saas_license_token or "").strip()
        if not raw_token:
            raise UserError(_("Please enter a license token before verifying."))

        license_rec = self._get_saas_license()

        # Uji coba verifikasi token terlebih dahulu tanpa menimpa raw_token aktif
        from .license_verifier import LicenseError, compute_state, decode_and_verify

        try:
            payload = decode_and_verify(raw_token)
        except LicenseError as exc:
            raise UserError(_("Invalid license token: %s (%s)") % (exc.code, exc.message)) from exc

        # Periksa kesesuaian database_uuid dan validitas state
        db_uuid = license_rec._get_database_uuid()
        today = license_rec._today()
        state, _days_left, reason = compute_state(payload, today, db_uuid)

        if state == "invalid":
            raise UserError(_("License token cannot be activated: %s") % reason)

        # Token valid dan dapat diaktivasi -> pasang ke model lisensi
        license_rec.action_install_token(raw_token)

        # Reset field input transient
        self.saas_license_token = False

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("License Activated"),
                "message": _("License %s for %s has been successfully activated (Status: %s).")
                % (payload.lid, payload.mch, state.upper()),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
