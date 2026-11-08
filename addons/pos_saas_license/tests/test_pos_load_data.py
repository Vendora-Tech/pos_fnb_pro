"""Unit test loader data POS untuk status lisensi ke UI kasir (T032).

Menguji field compute pos.session yang dikirim ke frontend:
- license_state
- license_days_left
- license_banner_msg
"""

from odoo.tests.common import TransactionCase, tagged

from .common import LicenseTestMixin


@tagged("post_install", "-at_install", "pos_saas_license")
class TestPosLoadData(LicenseTestMixin, TransactionCase):
    """Test loader data lisensi pada pos.session untuk frontend kasir."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db_uuid = "db-test-uuid-pos-load"
        cls.set_database_uuid(cls.db_uuid)

        cls.company = cls.env.company
        cls.license = cls.env["pos.saas.license"]._get_current()

        cls.pos_config = cls.env["pos.config"].create({
            "name": "Frontend Loader Register",
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

    def test_load_pos_data_fields_contains_license_fields(self):
        """Field lisensi wajib terdaftar di _load_pos_data_fields pos.session."""
        fields_loaded = self.env["pos.session"]._load_pos_data_fields(self.pos_config)
        expected = ["license_state", "license_days_left", "license_banner_msg"]
        for f in expected:
            self.assertIn(f, fields_loaded)

    def test_session_computed_banner_warning(self):
        """Field compute session mencerminkan status warning dan pesan banner."""
        with self.patch_today("2026-12-25"):
            token = self.make_token(db_uuid=self.db_uuid, until="2026-12-31", grace=7)
            self.license.action_install_token(token)

            session = self.env["pos.session"].create({"config_id": self.pos_config.id})
            self.assertEqual(session.license_state, "warning")
            self.assertEqual(session.license_days_left, 6)
            self.assertTrue(session.license_banner_msg)
            self.assertIn("6", session.license_banner_msg)

    def test_session_computed_banner_grace(self):
        """Field compute session mencerminkan status grace dan pesan banner."""
        with self.patch_today("2027-01-03"):
            token = self.make_token(db_uuid=self.db_uuid, until="2026-12-31", grace=7)
            self.license.action_install_token(token)

            session = self.env["pos.session"].create({"config_id": self.pos_config.id})
            self.assertEqual(session.license_state, "grace")
            self.assertTrue(session.license_banner_msg)
            self.assertIn("tenggang", session.license_banner_msg.lower())
