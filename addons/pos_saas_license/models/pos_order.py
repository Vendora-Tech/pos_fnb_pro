"""Ekstensi model pos.order untuk proteksi read-only saat lisensi expired (T034).

Menolak sinkronisasi transaksi penjualan baru dari antarmuka kasir saat lisensi
berstatus `expired` atau `invalid`.
"""

from datetime import UTC, datetime

from odoo import _, api, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def sync_from_ui(self, orders):
        """Validasi lisensi sebelum menyimpan sinkronisasi pesanan dari frontend kasir."""
        # 1. Evaluasi status lisensi SaaS company aktif
        license_rec = self.env["pos.saas.license"]._get_current()
        result = license_rec._evaluate()
        state = result["state"]
        reason = result["reason"]

        # Tolak order baru hanya jika expired atau invalid (grace, warning, active diizinkan)
        if state in ("expired", "invalid"):
            msg = _("Cannot sync POS orders: license is %s (%s). System is in read-only mode.") % (
                state,
                reason,
            )
            license_rec._log_event("blocked", msg)
            raise UserError(msg)

        # 2. Perbarui last_seen_timestamp untuk deteksi rollback
        now_naive = datetime.now(UTC).replace(tzinfo=None)
        if not license_rec.last_seen_timestamp or now_naive > license_rec.last_seen_timestamp:
            license_rec.sudo().write({"last_seen_timestamp": now_naive})

        return super().sync_from_ui(orders)
