"""Unit test scheduled action (cron harian) dan heartbeat opsional (T041).

Menguji fungsi ir.cron 'POS SaaS License: Daily Expiration Check':
- Cron mengevaluasi dan mencatat log transisi (warning, grace_entered, expired)
  hanya saat terjadi perubahan state.
- last_seen_timestamp diperbarui.
- Tidak ada panggilan HTTP/jaringan keluar jika saas.license.server_url kosong.
- Tetap berhasil (tanpa melempar exception) meski koneksi heartbeat gagal/error.
"""

from unittest import mock

from odoo.tests.common import TransactionCase, tagged

from .common import LicenseTestMixin


@tagged("post_install", "-at_install", "pos_saas_license")
class TestLicenseCron(LicenseTestMixin, TransactionCase):
    """Test cron harian pos.saas.license dan heartbeat opsional."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db_uuid = "db-test-uuid-pos-cron"
        cls.set_database_uuid(cls.db_uuid)

        cls.company = cls.env.company
        cls.license = cls.env["pos.saas.license"]._get_current()

    def setUp(self):
        super().setUp()
        self.set_database_uuid(self.db_uuid)
        self.license.write({
            "raw_token": False,
            "last_seen_timestamp": False,
        })
        self.license._refresh_cache()

    def test_cron_updates_state_and_last_seen_timestamp(self):
        """Cron memperbarui status ke warning saat mendekati masa kedaluwarsa."""
        with self.patch_today("2026-06-01"):
            token = self.make_token(db_uuid=self.db_uuid, until="2026-12-31", grace=7)
            self.license.action_install_token(token)
            self.assertEqual(self.license.state, "active")

        # Masuk ke H-10 (warning)
        with self.patch_today("2026-12-21"):
            self.env["pos.saas.license"]._cron_daily_check()

            self.license.refresh()
            self.assertEqual(self.license.state, "warning")
            self.assertTrue(self.license.last_seen_timestamp)

            # Periksa log audit transisi ke warning tercatat
            log = self.env["pos.saas.license.log"].search([
                ("license_id", "=", self.license.id),
                ("event_type", "=", "warning"),
            ], limit=1)
            self.assertTrue(log)

    def test_cron_no_network_calls_when_server_url_empty(self):
        """Cron tidak boleh mencoba koneksi jaringan keluar jika server_url tidak diisi."""
        self.env["ir.config_parameter"].sudo().set_param("saas.license.server_url", False)

        with self.patch_today("2026-06-01"):
            token = self.make_token(db_uuid=self.db_uuid, until="2026-12-31")
            self.license.action_install_token(token)

            with mock.patch("urllib.request.urlopen") as mock_url:
                self.env["pos.saas.license"]._cron_daily_check()
                mock_url.assert_not_called()

    def test_cron_graceful_heartbeat_failure(self):
        """Jika heartbeat ke central server gagal/timeout, cron tidak boleh gagal."""
        self.env["ir.config_parameter"].sudo().set_param(
            "saas.license.server_url", "https://licensing.example.com/api/heartbeat"
        )

        with self.patch_today("2026-06-01"):
            token = self.make_token(db_uuid=self.db_uuid, until="2026-12-31")
            self.license.action_install_token(token)

            with mock.patch("urllib.request.urlopen", side_effect=RuntimeError("Connection timed out")):
                # Tidak boleh melempar exception
                self.env["pos.saas.license"]._cron_daily_check()
                self.license.refresh()
                self.assertEqual(self.license.state, "active")
