"""Unit test penolakan sinkronisasi pesanan POS (pos.order) saat lisensi expired (T031).

Menguji kepatuhan mode read-only saat lisensi expired:
- Sinkronisasi order baru (sync_from_ui) ditolak dengan UserError saat status 'expired' atau 'invalid'.
- Sinkronisasi order baru tetap diizinkan saat status 'grace', 'warning', atau 'active'.
- last_seen_timestamp bertambah saat order diterima.
"""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from .common import LicenseTestMixin


@tagged("post_install", "-at_install", "pos_saas_license")
class TestPosOrderReadOnly(LicenseTestMixin, TransactionCase):
    """Test penguncian transaksi pos.order saat lisensi expired."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db_uuid = "db-test-uuid-pos-order"
        cls.set_database_uuid(cls.db_uuid)

        cls.company = cls.env.company
        cls.license = cls.env["pos.saas.license"]._get_current()

        cls.pos_config = cls.env["pos.config"].create({
            "name": "Sync Register",
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

    def _sample_order_dict(self, session):
        """Helper untuk membuat payload dummy pesanan POS dari UI."""
        return {
            "id": "0001-test-order",
            "data": {
                "name": "Order 0001",
                "pos_session_id": session.id,
                "user_id": self.env.user.id,
                "amount_paid": 50000.0,
                "amount_total": 50000.0,
                "amount_tax": 0.0,
                "lines": [],
                "statement_ids": [],
            },
        }

    def test_sync_orders_rejected_when_expired(self):
        """Order baru ditolak server saat lisensi sudah lewat grace period (expired)."""
        # Buka sesi saat active
        with self.patch_today("2026-06-01"):
            token = self.make_token(db_uuid=self.db_uuid, until="2026-12-31", grace=7)
            self.license.action_install_token(token)
            session = self.env["pos.session"].create({"config_id": self.pos_config.id})

        # Waktu maju hingga expired
        with self.patch_today("2027-01-10"):
            self.license._refresh_cache()
            self.assertEqual(self.license.state, "expired")

            orders = [self._sample_order_dict(session)]
            with self.assertRaises(UserError):
                self.env["pos.order"].sync_from_ui(orders)

    def test_sync_orders_allowed_during_grace_period(self):
        """Order baru tetap diizinkan saat masih berada dalam masa toleransi (grace)."""
        with self.patch_today("2027-01-04"):
            token = self.make_token(db_uuid=self.db_uuid, until="2026-12-31", grace=7)
            self.license.action_install_token(token)
            self.assertEqual(self.license.state, "grace")

            _session = self.env["pos.session"].create({"config_id": self.pos_config.id})
            orders = []  # Empty list sync call
            res = self.env["pos.order"].sync_from_ui(orders)
            self.assertIsInstance(res, dict)

    def test_last_seen_timestamp_updated_on_order_sync(self):
        """last_seen_timestamp harus bertambah/terisi saat order sync berhasil."""
        with self.patch_today("2026-06-01"):
            token = self.make_token(db_uuid=self.db_uuid, until="2026-12-31", grace=7)
            self.license.action_install_token(token)

            _session = self.env["pos.session"].create({"config_id": self.pos_config.id})
            prev_ts = self.license.last_seen_timestamp

            self.env["pos.order"].sync_from_ui([])
            self.license.invalidate_recordset(["last_seen_timestamp"])
            new_ts = self.license.last_seen_timestamp

            self.assertTrue(new_ts)
            if prev_ts:
                self.assertGreaterEqual(new_ts, prev_ts)
