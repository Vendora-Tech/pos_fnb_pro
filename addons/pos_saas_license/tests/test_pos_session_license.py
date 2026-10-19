"""Unit test intersepsi pembukaan sesi kasir berdasarkan status lisensi (T018).

Menguji pembukaan UI dan sesi POS terhadap siklus hidup lisensi:
- `open_ui()` diizinkan pada status `active`, `warning`, dan `grace`.
- `open_ui()` melempar `UserError` dan mencatat log `blocked` pada status `expired`,
  `invalid`, atau saat belum ada token.
- `open_frontend_cb()` ditolak saat lisensi kedaluwarsa.
- Seluruh pengecekan berjalan offline (tanpa panggilan jaringan).
- Deteksi manipulasi jam (clock rollback): toleransi mundur hingga 1 jam diizinkan;
  mundur lebih dari 1 jam memblokir akses dan mencatat log `clock_tamper`.
- `last_seen_timestamp` diperbarui setelah sesi berhasil diakses.
"""

from datetime import UTC, datetime, timedelta
from unittest import mock

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from .common import LicenseTestMixin


@tagged("post_install", "-at_install", "pos_saas_license")
class TestPosSessionLicense(LicenseTestMixin, TransactionCase):
    """Test penguncian sesi kasir pos.config dan pos.session berdasarkan lisensi."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db_uuid = "db-test-uuid-pos-session"
        cls.set_database_uuid(cls.db_uuid)

        cls.company = cls.env.company
        cls.license = cls.env["pos.saas.license"]._get_current()

        # Buat konfigurasi POS untuk pengujian
        cls.pos_config = cls.env["pos.config"].create({
            "name": "Register 1 Test",
            "company_id": cls.company.id,
        })

    def setUp(self):
        super().setUp()
        self.set_database_uuid(self.db_uuid)
        # Reset token ke keadaan kosong
        self.license.write({
            "raw_token": False,
            "last_seen_timestamp": False,
        })
        self.license._refresh_cache()

    def _install_token(self, **payload_overrides):
        """Helper untuk menerbitkan dan memasang token lisensi uji."""
        overrides = {
            "db_uuid": self.db_uuid,
            **payload_overrides,
        }
        token = self.make_token(**overrides)
        self.license.action_install_token(token)
        return token

    # -------------------------------------------------------------------------
    # 1. Validasi Status Lisensi Saat Buka UI
    # -------------------------------------------------------------------------

    def test_open_ui_blocked_without_token(self):
        """open_ui() wajib memblokir dengan UserError bila belum ada token."""
        with self.assertRaises(UserError):
            self.pos_config.open_ui()

        # Harus ada audit log 'blocked'
        log = self.env["pos.saas.license.log"].search([
            ("license_id", "=", self.license.id),
            ("event_type", "=", "blocked"),
        ], limit=1)
        self.assertTrue(log, "Log blocked harus tercatat saat akses ditolak tanpa token")

    def test_open_ui_allowed_when_active(self):
        """open_ui() diizinkan saat status lisensi active."""
        with self.patch_today("2026-06-01"):
            self._install_token(until="2026-12-31")
            self.assertEqual(self.license.state, "active")

            # Tidak boleh melempar UserError
            action = self.pos_config.open_ui()
            self.assertTrue(action, "open_ui harus mengembalikan aksi saat active")

    def test_open_ui_allowed_when_warning(self):
        """open_ui() tetap diizinkan saat status lisensi warning (H-14 s.d. H0)."""
        with self.patch_today("2026-12-20"):
            self._install_token(until="2026-12-31")
            self.assertEqual(self.license.state, "warning")

            action = self.pos_config.open_ui()
            self.assertTrue(action, "open_ui harus diizinkan pada status warning")

    def test_open_ui_allowed_when_grace(self):
        """open_ui() tetap diizinkan saat dalam grace period (grace=7)."""
        with self.patch_today("2027-01-04"):
            self._install_token(until="2026-12-31", grace=7)
            self.assertEqual(self.license.state, "grace")

            action = self.pos_config.open_ui()
            self.assertTrue(action, "open_ui harus diizinkan pada masa grace")

    def test_open_ui_blocked_when_expired(self):
        """open_ui() wajib melempar UserError saat lisensi expired (lewat grace)."""
        with self.patch_today("2027-01-10"):
            self._install_token(until="2026-12-31", grace=7)
            self.assertEqual(self.license.state, "expired")

            with self.assertRaises(UserError):
                self.pos_config.open_ui()

            log = self.env["pos.saas.license.log"].search([
                ("license_id", "=", self.license.id),
                ("event_type", "=", "blocked"),
            ], limit=1)
            self.assertTrue(log, "Log blocked harus tercatat saat status expired")

    def test_open_ui_blocked_when_invalid(self):
        """open_ui() wajib memblokir jika token corrupt atau db_uuid mismatch."""
        with self.patch_today("2026-06-01"):
            self._install_token(db_uuid="wrong-database-uuid", until="2026-12-31")
            self.assertEqual(self.license.state, "invalid")

            with self.assertRaises(UserError):
                self.pos_config.open_ui()

            log = self.env["pos.saas.license.log"].search([
                ("license_id", "=", self.license.id),
                ("event_type", "=", "blocked"),
            ], limit=1)
            self.assertTrue(log, "Log blocked harus tercatat saat status invalid")

    def test_open_frontend_cb_blocked_when_expired(self):
        """open_frontend_cb pada sesi yang di-resume wajib ditolak jika expired."""
        with self.patch_today("2026-06-01"):
            self._install_token(until="2026-12-31", grace=7)
            session = self.env["pos.session"].create({"config_id": self.pos_config.id})

        # Waktu maju hingga expired
        with self.patch_today("2027-01-10"):
            self.license._refresh_cache()
            self.assertEqual(self.license.state, "expired")

            with self.assertRaises(UserError):
                session.open_frontend_cb()

    # -------------------------------------------------------------------------
    # 2. Offline Enforcement (Tidak Ada Panggilan Jaringan)
    # -------------------------------------------------------------------------

    def test_offline_enforcement_no_network_calls(self):
        """Pemeriksaan lisensi tidak boleh melakukan koneksi internet/HTTP eksternal."""
        with self.patch_today("2026-06-01"):
            self._install_token(until="2026-12-31")

            with mock.patch("urllib.request.urlopen", side_effect=RuntimeError("Network call forbidden")), \
                 mock.patch("urllib.request.Request", side_effect=RuntimeError("Network call forbidden")):
                action = self.pos_config.open_ui()
                self.assertTrue(action, "Verifikasi lisensi lokal offline harus berhasil tanpa jaringan")

    # -------------------------------------------------------------------------
    # 3. Deteksi Clock Rollback & Pembaruan last_seen_timestamp
    # -------------------------------------------------------------------------

    def test_clock_rollback_detection(self):
        """Mundur jam > 1 jam memblokir akses dan mencatat clock_tamper."""
        with self.patch_today("2026-06-01"):
            self._install_token(until="2026-12-31")

            # Simulasi waktu berjalan normal, simpan timestamp acuan
            base_time = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
            self.license.write({"last_seen_timestamp": base_time.replace(tzinfo=None)})

            # 1. Mundur 30 menit (toleransi <= 1 jam) -> diizinkan
            slight_drift = base_time - timedelta(minutes=30)
            with mock.patch("addons.pos_saas_license.models.pos_saas_license.datetime") as mock_dt:
                mock_dt.now.return_value = slight_drift
                action = self.pos_config.open_ui()
                self.assertTrue(action, "Drift <= 1 jam harus ditoleransi")

            # 2. Mundur 70 menit (> 1 jam) -> diblokir dengan clock_tamper
            tampered_time = base_time - timedelta(minutes=70)
            with mock.patch("addons.pos_saas_license.models.pos_saas_license.datetime") as mock_dt:
                mock_dt.now.return_value = tampered_time
                with self.assertRaises(UserError):
                    self.pos_config.open_ui()

            log = self.env["pos.saas.license.log"].search([
                ("license_id", "=", self.license.id),
                ("event_type", "=", "clock_tamper"),
            ], limit=1)
            self.assertTrue(log, "Event clock_tamper wajib tercatat saat clock rollback > 1 jam")

    def test_last_seen_timestamp_updated_on_successful_access(self):
        """last_seen_timestamp harus diperbarui bertambah saat akses sesi berhasil."""
        with self.patch_today("2026-06-01"):
            self._install_token(until="2026-12-31")
            prev_ts = self.license.last_seen_timestamp

            self.pos_config.open_ui()
            self.license.invalidate_recordset(["last_seen_timestamp"])
            new_ts = self.license.last_seen_timestamp

            self.assertTrue(new_ts, "last_seen_timestamp harus terisi setelah sesi dibuka")
            if prev_ts:
                self.assertGreaterEqual(new_ts, prev_ts)
