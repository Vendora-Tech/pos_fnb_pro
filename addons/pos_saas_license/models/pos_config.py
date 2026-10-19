"""Ekstensi model pos.config untuk intervensi pembukaan UI kasir (T022).

Memvalidasi status lisensi SaaS sebelum kasir membuka antarmuka POS.
"""

from odoo import models


class PosConfig(models.Model):
    _inherit = "pos.config"

    def open_ui(self):
        """Gerbang intersepsi saat kasir membuka atau melanjutkan sesi POS."""
        self.ensure_one()
        # Evaluasi lisensi untuk company pemilik konfigurasi POS ini
        license_rec = (
            self.env["pos.saas.license"]
            .with_company(self.company_id)
            ._get_current()
        )
        license_rec.check_pos_access(raise_error=True)
        return super().open_ui()
