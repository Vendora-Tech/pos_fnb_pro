"""Unit test lisensi beli putus (perpetual) dengan instance binding (T028).

Menguji aturan lisensi perpetual:
- Token perpetual aktif pada tahun 2099 dan sisa hari tidak dihitung (days_remaining = 0).
- db_uuid tidak cocok menghasilkan invalid, open_ui ditolak, log invalid_token tercatat.
- Mengganti database.uuid setelah token terpasang membuat status berubah ke invalid
  pada pengecekan berikutnya.
"""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from .common import LicenseTestMixin


@tagged("post_install", "-at_install", "pos_saas_license")
class TestPerpetualBinding(LicenseTestMixin, TransactionCase):
    """Test lisensi perpetual dan binding hardware/database UUID."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db_uuid = "db-test-uuid-perpetual"
        cls.set_database_uuid(cls.db_uuid)

        cls.company = cls.env.company
        cls.license = cls.env["pos.saas.license"]._get_current()

        cls.pos_config = cls.env["pos.config"].create({
            "name": "Perpetual Register",
            "company_id": cls.company.id,
        })

    def setUp(self):
        super().setUp()
        self.set_database_uuid(self.db_uuid)
        self.license.write({
            "raw_token": False,
            "last_seen_timestamp": False,
        })
        self.license._refresh_cache()

    def test_perpetual_active_far_future(self):
        """Lisensi perpetual aktif tanpa batas waktu (misal tahun 2099) dan days_remaining = 0."""
        token = self.make_token(
            typ="perpetual",
            db_uuid=self.db_uuid,
            until=None,
        )
        self.license.action_install_token(token)

        # Diuji pada tahun 2099
        with self.patch_today("2099-01-01"):
            eval_res = self.license._evaluate()
            self.assertEqual(eval_res["state"], "active")
            self.assertIsNone(eval_res["days_left"])

            self.license._refresh_cache()
            self.assertEqual(self.license.state, "active")
            self.assertEqual(self.license.days_remaining, 0)

            # Buka UI harus berhasil
            action = self.pos_config.open_ui()
            self.assertTrue(action)

    def test_perpetual_db_uuid_mismatch_rejected(self):
        """Token dengan db_uuid tidak cocok wajib ditolak invalid dan mencatat log."""
        token = self.make_token(
            typ="perpetual",
            db_uuid="wrong-instance-db-uuid",
            until=None,
        )
        self.license.action_install_token(token)

        self.assertEqual(self.license.state, "invalid")
        self.assertIn(self.db_uuid, self.license.state_message or "")

        with self.assertRaises(UserError):
            self.pos_config.open_ui()

        log = self.env["pos.saas.license.log"].search([
            ("license_id", "=", self.license.id),
            ("event_type", "=", "invalid_token"),
        ], limit=1)
        self.assertTrue(log)

    def test_db_uuid_changed_after_installation(self):
        """Mengubah database.uuid setelah token terpasang otomatis mengubah state ke invalid."""
        token = self.make_token(
            typ="perpetual",
            db_uuid=self.db_uuid,
            until=None,
        )
        self.license.action_install_token(token)
        self.assertEqual(self.license.state, "active")

        # Simulasi database di-clone / database.uuid diganti
        self.set_database_uuid("cloned-different-uuid")

        # Pengecekan berikutnya wajib mendeteksi mismatch
        eval_res = self.license._evaluate()
        self.assertEqual(eval_res["state"], "invalid")

        with self.assertRaises(UserError):
            self.pos_config.open_ui()
