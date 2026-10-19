"""Unit test aktivasi lisensi dari Settings POS (res.config.settings) (T020).

Menguji integrasi view settings dengan engine lisensi:
- `action_saas_license_verify()` pada `res.config.settings` memasang token valid,
  memperbarui status lisensi, dan menampilkan detail lisensi.
- Memasukkan token yang tidak valid/rusak menolak dengan UserError dan
  TIDAK menimpa token lama yang valid.
"""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from .common import LicenseTestMixin


@tagged("post_install", "-at_install", "pos_saas_license")
class TestLicenseSettings(LicenseTestMixin, TransactionCase):
    """Test pengaturan lisensi pada res.config.settings."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db_uuid = "db-test-uuid-settings"
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

    def test_verify_valid_token_from_settings(self):
        """Memasang token valid lewat res.config.settings memperbarui data lisensi."""
        valid_token = self.make_token(
            lid="LIC-SETTINGS-001",
            mch="Warung Kopi Modern",
            db_uuid=self.db_uuid,
            until="2026-12-31",
            max_reg=3,
        )

        settings = self.env["res.config.settings"].create({
            "saas_license_token": valid_token,
        })
        settings.action_saas_license_verify()

        self.license.refresh()
        self.assertEqual(self.license.license_id, "LIC-SETTINGS-001")
        self.assertEqual(self.license.merchant_name, "Warung Kopi Modern")
        self.assertEqual(self.license.max_pos_registers, 3)
        self.assertEqual(self.license.raw_token, valid_token)

    def test_verify_invalid_token_does_not_overwrite_existing_valid_token(self):
        """Token invalid wajib ditolak UserError tanpa merusak token valid yang sedang aktif."""
        # 1. Pasang token valid pertama
        initial_token = self.make_token(
            lid="LIC-INITIAL-VALID",
            mch="Merchant Pertama",
            db_uuid=self.db_uuid,
            until="2026-12-31",
        )
        self.license.action_install_token(initial_token)
        self.assertEqual(self.license.license_id, "LIC-INITIAL-VALID")

        # 2. Coba pasang token rusak lewat settings
        corrupt_token = initial_token[:-5] + "XXXXX"
        settings = self.env["res.config.settings"].create({
            "saas_license_token": corrupt_token,
        })

        with self.assertRaises(UserError):
            settings.action_saas_license_verify()

        # 3. Token lama harus tetap utuh
        self.license.refresh()
        self.assertEqual(self.license.raw_token, initial_token, "Token lama tidak boleh tertimpa jika verifikasi gagal")
        self.assertEqual(self.license.license_id, "LIC-INITIAL-VALID")
