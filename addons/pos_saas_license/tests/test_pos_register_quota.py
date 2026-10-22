"""Unit test penegakan kuota register POS (max_pos_registers) (T019).

Menguji aturan pembatasan kuota kasir aktif:
- Dengan `max_reg=2`, sesi pada config ke-1 dan ke-2 boleh dibuka bersamaan.
- Sesi pada config ke-3 ditolak dengan UserError kuota penuh.
- Setelah salah satu sesi ditutup (`state='closed'`), config ke-3 dapat membuka sesi.
- Pembuatan record `pos.config` baru tidak dibatasi kuota (hanya sesi kasir aktif yang dihitung).
"""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from .common import LicenseTestMixin


@tagged("post_install", "-at_install", "pos_saas_license")
class TestPosRegisterQuota(LicenseTestMixin, TransactionCase):
    """Test penegakan batas max_pos_registers pada pos.session."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db_uuid = "db-test-uuid-pos-quota"
        cls.set_database_uuid(cls.db_uuid)

        cls.company = cls.env.company
        cls.license = cls.env["pos.saas.license"]._get_current()

        # Buat 3 pos.config untuk pengujian kuota
        cls.config1 = cls.env["pos.config"].create({
            "name": "Register 1",
            "company_id": cls.company.id,
        })
        cls.config2 = cls.env["pos.config"].create({
            "name": "Register 2",
            "company_id": cls.company.id,
        })
        cls.config3 = cls.env["pos.config"].create({
            "name": "Register 3",
            "company_id": cls.company.id,
        })

    def setUp(self):
        super().setUp()
        self.set_database_uuid(self.db_uuid)
        # Pasang token aktif dengan max_reg=2
        token = self.make_token(
            db_uuid=self.db_uuid,
            max_reg=2,
            until="2026-12-31",
            grace=7,
        )
        self.license.action_install_token(token)
        self.assertEqual(self.license.max_pos_registers, 2)

    def test_pos_config_creation_unlimited(self):
        """Membuat record pos.config baru selalu diizinkan tanpa batas kuota."""
        config_extra = self.env["pos.config"].create({
            "name": "Register Unlimited Config Record",
            "company_id": self.company.id,
        })
        self.assertTrue(config_extra.id, "Record pos.config harus bebas dibuat")

    def test_quota_enforcement_on_active_sessions(self):
        """Membuka sesi melebihi max_reg wajib ditolak, dan dibuka kembali setelah ada sesi ditutup."""
        with self.patch_today("2026-06-01"):
            # Sesi 1 buka: OK (kuota terpakai 1/2)
            session1 = self.env["pos.session"].create({"config_id": self.config1.id})
            self.assertTrue(session1.id)

            # Sesi 2 buka: OK (kuota terpakai 2/2)
            session2 = self.env["pos.session"].create({"config_id": self.config2.id})
            self.assertTrue(session2.id)

            # Sesi 3 buka: GAGAL karena kuota sudah 2
            with self.assertRaises(UserError):
                self.env["pos.session"].create({"config_id": self.config3.id})

            # Tutup sesi 1
            session1.write({"state": "closed"})

            # Sesi 3 sekarang harus bisa dibuka (kuota terpakai kembali 2: session2 + session3)
            session3 = self.env["pos.session"].create({"config_id": self.config3.id})
            self.assertTrue(session3.id, "Sesi config ke-3 harus berhasil dibuka setelah sesi 1 closed")
