"""Model lisensi SaaS: kolom cache untuk tampilan, keputusan selalu diverifikasi ulang.

Kolom turunan token di sini hanya cache. Setiap keputusan izin memanggil
`_evaluate()`, yang memverifikasi ulang `raw_token` lewat `license_verifier`
(FR-013). Karena itu manipulasi langsung di database tidak mengubah keputusan.
"""

import json
import logging
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import license_verifier
from .license_verifier import (
    LicenseError,
    compute_state,
    decode_and_verify,
)

_logger = logging.getLogger(__name__)

FALLBACK_TIMEZONE = "Asia/Jakarta"

# Jenis event audit yang dicatat saat status berubah.
STATE_EVENT_TYPES = {
    "active": "verified",
    "warning": "warning",
    "grace": "grace_entered",
    "expired": "expired",
    "invalid": "invalid_token",
}


class PosSaasLicense(models.Model):
    """Lisensi aktif satu database tenant."""

    _name = "pos.saas.license"
    _description = "POS License"

    name = fields.Char(default="POS License", required=True)
    license_id = fields.Char(string="License ID", readonly=True, index=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        ondelete="cascade",
    )
    tenant_uuid = fields.Char(
        string="Tenant UUID",
        related="company_id.tenant_uuid",
        readonly=True,
    )
    merchant_name = fields.Char(string="Merchant", readonly=True)
    license_type = fields.Selection(
        [
            ("subscription", "Subscription"),
            ("perpetual", "Perpetual (Beli Putus)"),
        ],
        string="License Type",
        required=True,
        default="subscription",
    )
    database_uuid = fields.Char(string="Database UUID", readonly=True)
    raw_token = fields.Text(
        string="License Token",
        help="Token mentah dari penerbit. Biarkan kosong sampai token dipasang.",
    )
    valid_from = fields.Date(string="Valid From", readonly=True)
    valid_until = fields.Date(string="Valid Until", readonly=True)
    grace_period_days = fields.Integer(
        string="Grace Period (Days)",
        default=7,
    )
    max_pos_registers = fields.Integer(
        string="Max POS Registers",
        default=1,
    )
    allowed_modules = fields.Char(string="Allowed Modules", readonly=True)
    key_id = fields.Char(string="Key ID", readonly=True)
    state = fields.Selection(
        [
            ("active", "Active"),
            ("warning", "Expiring Soon"),
            ("grace", "Grace Period"),
            ("expired", "Expired"),
            ("invalid", "Invalid Token"),
        ],
        string="Status",
        default="invalid",
    )
    state_message = fields.Char(
        string="Status Message",
        compute="_compute_state_display",
    )
    days_remaining = fields.Integer(
        string="Days Remaining",
        compute="_compute_state_display",
    )
    last_verified_at = fields.Datetime(string="Last Verified", readonly=True)
    last_seen_timestamp = fields.Datetime(
        string="Last Seen Timestamp",
        help="Waktu server terbesar yang pernah terlihat. Dipakai mendeteksi "
        "clock rollback saat buka sesi, sync order, atau cron.",
    )

    _check_grace_period_positive = models.Constraint(
        "CHECK(grace_period_days >= 0)",
        "Grace period days must be non-negative.",
    )
    _check_max_pos_registers_positive = models.Constraint(
        "CHECK(max_pos_registers >= 1)",
        "Maximum POS registers quota must be at least 1.",
    )
    _license_state_idx = models.Index("(license_id, state)")

    # ------------------------------------------------------------- display

    @api.depends("raw_token", "company_id")
    def _compute_state_display(self):
        for record in self:
            result = record._evaluate()
            record.days_remaining = result["days_left"] or 0
            record.state_message = result["reason"]

    # ------------------------------------------------------------- helpers

    @api.model
    def _get_current(self):
        """Ambil lisensi company aktif, buat singleton-nya bila belum ada."""
        company = self.env.company
        if not company or not company.id:
            return self
        license_rec = self.sudo().search(
            [("company_id", "=", company.id)], limit=1
        )
        if not license_rec:
            license_rec = self.sudo().create(
                {"company_id": company.id, "name": "POS License"}
            )
        return license_rec

    @api.model
    def _get_database_uuid(self):
        """`database.uuid` tenant; dibandingkan dengan `db_uuid` di payload."""
        Param = self.env["ir.config_parameter"].sudo()
        if hasattr(Param, "get_str"):
            return Param.get_str("database.uuid") or ""
        return Param.get_param("database.uuid") or ""

    def _company_timezone(self):
        """Zona waktu company, fallback `Asia/Jakarta`."""
        self.ensure_one()
        tz_name = self.company_id.partner_id.tz or FALLBACK_TIMEZONE
        try:
            return ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, ValueError):
            _logger.warning(
                "Unknown timezone %r, falling back to %s",
                tz_name,
                FALLBACK_TIMEZONE,
            )
            return ZoneInfo(FALLBACK_TIMEZONE)

    def _today(self):
        """Tanggal lokal zona waktu company, bukan tanggal UTC."""
        self.ensure_one()
        return datetime.now(UTC).astimezone(self._company_timezone()).date()

    def _evaluate(self):
        """Verifikasi ulang `raw_token` dan kembalikan status terkini.

        Hasilnya dict `state`, `days_left`, `reason`, dan `payload`; `payload`
        bernilai `None` bila token kosong, signature gagal, atau skemanya tidak
        valid.
        """
        self.ensure_one()
        token = (self.raw_token or "").strip()
        if not token:
            return {
                "state": "invalid",
                "days_left": None,
                "reason": "no license token installed",
                "payload": None,
            }
        public_keys = None
        if "saas.license.key" in self.env:
            extra_keys = {
                k.key_id: k.public_key_b64
                for k in self.env["saas.license.key"].sudo().search([("active", "=", True)])
                if k.key_id and k.public_key_b64
            }
            if extra_keys:
                public_keys = dict(license_verifier.PUBLIC_KEYS)
                public_keys.update(extra_keys)

        try:
            payload = decode_and_verify(token, public_keys=public_keys)
        except LicenseError as exc:
            return {
                "state": "invalid",
                "days_left": None,
                "reason": f"{exc.code}: {exc.message}",
                "payload": None,
            }

        current_db_uuid = self._get_database_uuid()
        company_tenant_uuid = getattr(self.company_id, "tenant_uuid", False) or getattr(self.env.company, "tenant_uuid", False)
        if payload and payload.db_uuid == company_tenant_uuid:
            expected_db_uuid = company_tenant_uuid
        else:
            expected_db_uuid = current_db_uuid

        state, days_left, reason = compute_state(
            payload,
            self._today(),
            expected_db_uuid,
        )
        return {
            "state": state,
            "days_left": days_left,
            "reason": reason,
            "payload": payload,
        }

    # ------------------------------------------------------------- actions

    def _log_event(self, event_type, details=None):
        """Catat satu baris audit trail milik lisensi ini."""
        self.ensure_one()
        return (
            self.env["pos.saas.license.log"]
            .sudo()
            .create(
                {
                    "license_id": self.id,
                    "event_type": event_type,
                    "details": details,
                    "user_id": self.env.user.id,
                }
            )
        )

    def _refresh_cache(self):
        """Tulis kolom cache, dan catat log hanya saat status berubah."""
        self.ensure_one()
        result = self._evaluate()
        payload = result["payload"]
        previous_state = self.state

        vals = {
            "state": result["state"],
            "last_verified_at": fields.Datetime.now(),
            "database_uuid": self._get_database_uuid(),
        }
        if payload is not None:
            vals.update(
                {
                    "license_id": payload.lid,
                    "merchant_name": payload.mch,
                    "license_type": payload.typ,
                    "valid_from": payload.from_,
                    "valid_until": payload.until or False,
                    "grace_period_days": payload.grace,
                    "max_pos_registers": payload.max_reg,
                    "allowed_modules": ",".join(payload.mods) or False,
                    "key_id": payload.kid,
                }
            )
        self.sudo().write(vals)

        if previous_state != result["state"]:
            self._log_event(
                STATE_EVENT_TYPES[result["state"]],
                f"{previous_state} -> {result['state']}: {result['reason']}",
            )
        return result

    def action_install_token(self, token):
        """Pasang token baru: simpan, verifikasi, catat, lalu perbarui cache."""
        self.ensure_one()
        token = (token or "").strip()
        self.write({"raw_token": token})

        result = self._evaluate()
        payload = result["payload"]
        if payload is None or result["state"] == "invalid":
            self._log_event("invalid_token", result["reason"])
        else:
            self._log_event(
                "installed",
                f"license {payload.lid} for {payload.mch}",
            )
        self._refresh_cache()
        return result

    # -------------------------------------------------------- POS gatekeeper

    def _check_clock_rollback(self):
        """Deteksi manipulasi jam server.

        Mundur hingga 1 jam ditoleransi (misal sinkronisasi NTP).
        Mundur lebih dari 1 jam memblokir akses dan mencatat event `clock_tamper`.
        """
        self.ensure_one()
        if not self.last_seen_timestamp:
            return True

        now_naive = datetime.now(UTC).replace(tzinfo=None)
        last_seen = self.last_seen_timestamp
        if hasattr(last_seen, "tzinfo") and last_seen.tzinfo is not None:
            last_seen = last_seen.astimezone(UTC).replace(tzinfo=None)

        if now_naive < (last_seen - timedelta(hours=1)):
            msg = _(
                "Clock rollback detected: server time %s is more than 1 hour behind last recorded time %s."
            ) % (now_naive.isoformat(), last_seen.isoformat())
            _logger.error(msg)
            self._log_event("clock_tamper", msg)
            return False

        return True

    @api.model
    def _format_humanized_license_error(self, state, reason=""):
        """Menyusun pesan error lisensi yang ramah pengguna, mudah dipahami kasir/pemilik toko,
        dan membedakan antara mode debug (developer) vs non-debug (user biasa).
        """
        is_debug = bool(self.env.context.get("debug"))
        reason_str = str(reason or "").lower()

        # Mode Debug: Kembalikan pesan teknis presisi untuk developer
        if is_debug:
            return _("POS access blocked: license is %s (%s).") % (state, reason)

        # Mode Non-Debug (Kasir / Merchant): Format pesan humanized, solutif, dan jelas
        if not reason or "malformed_token" in reason_str or "not_found" in reason_str:
            return _(
                "Aplikasi Kasir Belum Diaktifkan\n\n"
                "Sistem belum mendeteksi lisensi aktif untuk toko ini.\n\n"
                "Petunjuk untuk Pengelola / Kasir:\n"
                "1. Masuk ke menu: Point of Sale > Configuration > Settings\n"
                "2. Temukan bagian 'Store / Merchant Identity'\n"
                "3. Masukkan token lisensi Anda pada kolom 'License Token' lalu klik 'Verify & Activate Token'\n\n"
                "Silakan hubungi administrator atau penyedia sistem apabila Anda membutuhkan bantuan."
            )

        if "expired" in state or "expired" in reason_str:
            return _(
                "Masa Berlaku Lisensi Telah Habis\n\n"
                "Masa aktif lisensi toko Anda telah selesai dan masa tenggang toleransi (grace period) telah berakhir, sehingga transaksi kasir ditangguhkan sementara.\n\n"
                "Solusi:\n"
                "1. Lakukan perpanjangan lisensi toko Anda.\n"
                "2. Buka menu Point of Sale > Configuration > Settings lalu masukkan token lisensi perpanjangan yang baru.\n\n"
                "Hubungi administrator sistem untuk mengaktifkan kembali akses kasir Anda."
            )

        if "db_mismatch" in reason_str:
            return _(
                "Token Lisensi Tidak Cocok dengan Database Toko\n\n"
                "Token lisensi yang terpasang terdaftar untuk database toko yang berbeda.\n\n"
                "Solusi:\n"
                "1. Pastikan Anda memasukkan token lisensi resmi yang diterbitkan khusus untuk database toko ini.\n"
                "2. Periksa kembali Database UUID Anda di menu Settings."
            )

        if "invalid_signature" in reason_str or "unknown_kid" in reason_str:
            return _(
                "Verifikasi Keaslian Lisensi Gagal\n\n"
                "Tanda tangan digital pada token lisensi tidak dapat diverifikasi atau kunci penerbit tidak dikenali.\n\n"
                "Solusi:\n"
                "Pastikan Anda menyalin seluruh teks token lisensi secara utuh tanpa ada karakter yang terpotong."
            )

        if "clock_tamper" in reason_str or "rollback" in reason_str:
            return _(
                "Waktu Sistem Perangkat Kasir Tidak Sesuai\n\n"
                "Sistem mendeteksi tanggal atau jam pada komputer/server kasir mundur dari waktu transaksi sebelumnya.\n\n"
                "Solusi:\n"
                "1. Sesuaikan tanggal dan jam perangkat ke waktu saat ini secara otomatis (sinkronkan waktu internet / NTP).\n"
                "2. Setelah jam komputer benar, silakan buka kembali sesi kasir."
            )

        # Fallback umum
        return _(
            "Akses Kasir Terkendala Lisensi\n\n"
            "Status lisensi saat ini tidak valid (%s).\n\n"
            "Solusi:\n"
            "Silakan periksa pengaturan lisensi di menu Point of Sale > Configuration > Settings atau hubungi administrator sistem."
        ) % state

    def check_pos_access(self, raise_error=True):
        """Gerbang validasi pembukaan dan kelanjutan sesi kasir.

        Mengevaluasi ulang lisensi secara offline. Memblokir akses bila lisensi
        `expired`, `invalid`, atau terjadi pemunduran jam (clock rollback).
        Memperbarui `last_seen_timestamp` saat akses berhasil diizinkan.
        """
        record = self._get_current() if not self else self[0]

        # 1. Periksa pemunduran waktu server (clock rollback)
        if not record._check_clock_rollback():
            if self.env.context.get("debug"):
                msg = _("System clock rollback detected. POS access is temporarily blocked for security.")
            else:
                msg = record._format_humanized_license_error("invalid", "clock_tampered")
            record._log_event("blocked", msg)
            if raise_error:
                raise UserError(msg)
            return False

        # 2. Evaluasi ulang token lisensi saat ini
        result = record._evaluate()
        state = result["state"]
        reason = result["reason"]

        if state in ("expired", "invalid"):
            msg = record._format_humanized_license_error(state, reason)
            record._log_event("blocked", msg)
            if raise_error:
                raise UserError(msg)
            return False

        # 3. Akses diizinkan (active, warning, grace) -> perbarui last_seen_timestamp
        now_naive = datetime.now(UTC).replace(tzinfo=None)
        if not record.last_seen_timestamp or now_naive > record.last_seen_timestamp:
            record.sudo().write({"last_seen_timestamp": now_naive})

        return True

    # -------------------------------------------------------- Cron & Heartbeat

    @api.model
    def _cron_daily_check(self):
        """Pemeriksaan status berkala harian (ir.cron).

        Menyegarkan cache status lisensi untuk seluruh company, mencatat
        transisi status ke audit log, memperbarui `last_seen_timestamp`,
        dan secara opsional mengirimkan heartbeat ke licensing server.
        """
        licenses = self.search([])
        for license_rec in licenses:
            license_rec._refresh_cache()

            # Perbarui last_seen_timestamp jika server berjalan maju
            now_naive = datetime.now(UTC).replace(tzinfo=None)
            if not license_rec.last_seen_timestamp or now_naive > license_rec.last_seen_timestamp:
                license_rec.sudo().write({"last_seen_timestamp": now_naive})

            # Heartbeat opsional (hanya model subscription)
            if license_rec.license_type == "subscription":
                license_rec._send_heartbeat()

    def _send_heartbeat(self):
        """Mengirim ping status lisensi ke central licensing server secara non-blocking."""
        self.ensure_one()
        Param = self.env["ir.config_parameter"].sudo()
        if hasattr(Param, "get_str"):
            server_url = (Param.get_str("saas.license.server_url") or "").strip()
        else:
            server_url = (Param.get_param("saas.license.server_url") or "").strip()
        if not server_url:
            return

        payload_data = {
            "license_id": self.license_id,
            "database_uuid": self.database_uuid,
            "tenant_uuid": self.tenant_uuid,
            "state": self.state,
            "days_remaining": self.days_remaining,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        try:
            req = urllib.request.Request(
                server_url,
                data=json.dumps(payload_data).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "Odoo-POS-SaaS-Client/20.0"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                _logger.info(
                    "SaaS License heartbeat sent successfully to %s: HTTP %s",
                    server_url,
                    getattr(response, "status", 200),
                )
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                "SaaS License optional heartbeat to %s failed (non-blocking): %s",
                server_url,
                exc,
            )


