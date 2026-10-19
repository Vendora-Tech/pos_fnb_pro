"""Ekstensi model pos.session untuk penegakan kuota register, validasi lisensi, dan loader OWL (T023, T033).

Menegakkan aturan lisensi SaaS:
1. `create(vals_list)`:
   - Validasi lisensi aktif (check_pos_access).
   - Penegakan kuota register: jumlah `pos.config` unik yang memiliki sesi aktif
     (`state != 'closed'`) ditambah config yang baru akan dibuka tidak boleh
     melebihi `max_pos_registers` dari lisensi.
2. `open_frontend_cb()`:
   - Memastikan sesi kasir yang di-resume kembali memvalidasi lisensi terkini.
3. Field data loader untuk antarmuka kasir (OWL):
   - `license_state`: Status lisensi (active, warning, grace, expired, invalid)
   - `license_days_left`: Sisa hari masa aktif
   - `license_banner_msg`: Pesan teks banner peringatan
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PosSession(models.Model):
    _inherit = "pos.session"

    license_state = fields.Selection(
        selection=[
            ("active", "Active"),
            ("warning", "Expiring Soon"),
            ("grace", "Grace Period"),
            ("expired", "Expired"),
            ("invalid", "Invalid Token"),
        ],
        string="SaaS License State",
        compute="_compute_license_banner_data",
    )
    license_days_left = fields.Integer(
        string="License Days Remaining",
        compute="_compute_license_banner_data",
    )
    license_banner_msg = fields.Char(
        string="License Banner Message",
        compute="_compute_license_banner_data",
    )

    def _compute_license_banner_data(self):
        """Hitung informasi lisensi untuk banner OWL di layar kasir."""
        for session in self:
            company = session.config_id.company_id or session.env.company
            license_rec = (
                session.env["pos.saas.license"]
                .with_company(company)
                ._get_current()
            )
            result = license_rec._evaluate()
            state = result["state"]
            days_left = result["days_left"] or 0

            session.license_state = state
            session.license_days_left = days_left

            if state == "warning":
                session.license_banner_msg = _(
                    "⚠️ Lisensi aktif tersisa %d hari lagi. Segera lakukan perpanjangan."
                ) % days_left
            elif state == "grace":
                session.license_banner_msg = _(
                    "🚨 Masa aktif telah berakhir. Sistem dalam masa tenggang toleransi %d hari."
                ) % abs(days_left)
            elif state in ("expired", "invalid"):
                session.license_banner_msg = _(
                    "⛔ Masa berlaku lisensi telah habis atau tidak valid. Transaksi kasir dikunci."
                )
            else:
                session.license_banner_msg = False

    def _load_pos_data_fields(self, config):
        """Daftarkan field lisensi ke data loader POS Odoo 20 (T007(c))."""
        params = super()._load_pos_data_fields(config)
        params.extend(["license_state", "license_days_left", "license_banner_msg"])
        return params

    @api.model_create_multi
    def create(self, vals_list):
        """Validasi lisensi dan batas kuota register sebelum membuat sesi baru."""
        for vals in vals_list:
            config_id = vals.get("config_id")
            if not config_id:
                continue

            config = self.env["pos.config"].browse(config_id)
            company = config.company_id or self.env.company

            # 1. Validasi status lisensi SaaS
            license_rec = (
                self.env["pos.saas.license"]
                .with_company(company)
                ._get_current()
            )
            license_rec.check_pos_access(raise_error=True)

            # 2. Penegakan batas kuota register (max_pos_registers)
            max_registers = license_rec.max_pos_registers or 1

            # Ambil semua config_id yang saat ini memiliki sesi aktif (belum closed)
            active_sessions = self.search([
                ("state", "!=", "closed"),
                ("config_id.company_id", "=", company.id),
            ])
            active_config_ids = set(active_sessions.mapped("config_id.id"))

            # Jika config ini belum termasuk dalam config aktif, periksa apakah kuota penuh
            if config.id not in active_config_ids and len(active_config_ids) >= max_registers:
                msg = _(
                    "POS Register quota exceeded: maximum allowed active registers is %d. "
                    "Please close an active session or upgrade your subscription plan."
                ) % max_registers
                raise UserError(msg)

        return super().create(vals_list)

    def open_frontend_cb(self):
        """Validasi lisensi saat kasir melanjutkan (resume) sesi yang sudah ada."""
        for session in self:
            company = session.config_id.company_id or self.env.company
            license_rec = (
                self.env["pos.saas.license"]
                .with_company(company)
                ._get_current()
            )
            license_rec.check_pos_access(raise_error=True)

        return super().open_frontend_cb()
