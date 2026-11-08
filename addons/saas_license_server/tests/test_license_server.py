import base64
import json
from datetime import date, timedelta
from unittest import mock

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestSaasLicenseServer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Buat keypair awal untuk pengujian
        cls.signing_key = cls.env["saas.license.key"].create(
            {
                "name": "Test Key 2026",
                "key_id": "test2026",
                "is_default": True,
            }
        )
        cls.signing_key.action_generate_keypair()

        # Buat user dengan role berbeda
        cls.group_viewer = cls.env.ref("saas_license_server.group_saas_license_viewer")
        cls.group_manager = cls.env.ref("saas_license_server.group_saas_license_manager")
        cls.group_admin = cls.env.ref("saas_license_server.group_saas_license_admin")

        cls.user_viewer = cls.env["res.users"].create(
            {
                "name": "License Viewer User",
                "login": "license_viewer",
                "email": "viewer@example.com",
                "group_ids": [(6, 0, [cls.group_viewer.id])],
            }
        )
        cls.user_manager = cls.env["res.users"].create(
            {
                "name": "License Manager User",
                "login": "license_manager",
                "email": "manager@example.com",
                "group_ids": [(6, 0, [cls.group_manager.id])],
            }
        )

    def test_01_keypair_generation(self):
        """Memastikan pasangan kunci Ed25519 berhasil di-generate secara valid."""
        key = self.env["saas.license.key"].create(
            {
                "name": "Secondary Key",
                "key_id": "sec2026",
            }
        )
        self.assertFalse(key.private_key_pem)
        self.assertFalse(key.public_key_b64)

        key.action_generate_keypair()
        self.assertTrue(key.private_key_pem.startswith("-----BEGIN PRIVATE KEY-----"))
        self.assertTrue(bool(key.public_key_b64))
        # 32 bytes base64 = 44 chars
        raw_pub = base64.b64decode(key.public_key_b64)
        self.assertEqual(len(raw_pub), 32)

    def test_02_issue_subscription_license(self):
        """Memastikan penerbitan lisensi subscription menghasilkan token JWS yang valid."""
        today = fields.Date.today()
        valid_until = today + timedelta(days=365)
        db_uuid = "4c650da3-befc-11f1-8534-971c6e3cbd00"

        license_rec = self.env["saas.license.record"].create(
            {
                "merchant_name": "Toko Berkah Sejahtera",
                "license_type": "subscription",
                "db_uuid": db_uuid,
                "valid_from": today,
                "valid_until": valid_until,
                "max_registers": 2,
                "grace_period": 7,
                "key_id": self.signing_key.id,
            }
        )
        self.assertEqual(license_rec.state, "draft")
        self.assertFalse(license_rec.token)

        license_rec.action_issue_token()
        self.assertEqual(license_rec.state, "active")
        self.assertTrue(bool(license_rec.token))

        # Urai token JWS (header.payload.signature)
        parts = license_rec.token.split(".")
        self.assertEqual(len(parts), 3)

        header_json = base64.urlsafe_b64decode(parts[0] + "==").decode("utf-8")
        header = json.loads(header_json)
        self.assertEqual(header["alg"], "EdDSA")
        self.assertEqual(header["typ"], "SAAS-LIC")
        self.assertEqual(header["kid"], "test2026")

        payload_json = base64.urlsafe_b64decode(parts[1] + "==").decode("utf-8")
        payload = json.loads(payload_json)
        self.assertEqual(payload["lid"], license_rec.name)
        self.assertEqual(payload["mch"], "Toko Berkah Sejahtera")
        self.assertEqual(payload["typ"], "subscription")
        self.assertEqual(payload["db_uuid"], db_uuid)
        self.assertEqual(payload["max_reg"], 2)
        self.assertEqual(payload["grace"], 7)
        self.assertEqual(payload["until"], valid_until.isoformat())

        # Verifikasi end-to-end langsung menggunakan verifier pos_saas_license jika tersedia
        try:
            from odoo.addons.pos_saas_license.models import license_verifier

            verified = license_verifier.decode_and_verify(
                license_rec.token,
                public_keys={"test2026": self.signing_key.public_key_b64},
            )
            self.assertEqual(verified.lid, license_rec.name)
            self.assertEqual(verified.mch, "Toko Berkah Sejahtera")
            self.assertEqual(verified.db_uuid, db_uuid)
            state, days_left, banner_msg = license_verifier.compute_state(verified, today, db_uuid)
            self.assertEqual(state, "active")
            self.assertEqual(days_left, 365)
        except ImportError:
            pass

    def test_03_issue_perpetual_license(self):
        """Memastikan lisensi perpetual tidak memiliki valid_until dan token valid."""
        today = fields.Date.today()
        db_uuid = "5d761eb4-cefd-22e2-9645-082d7f4dce11"

        license_rec = self.env["saas.license.record"].create(
            {
                "merchant_name": "Resto Abadi Jaya",
                "license_type": "perpetual",
                "db_uuid": db_uuid,
                "valid_from": today,
                "max_registers": 5,
                "grace_period": 0,
                "key_id": self.signing_key.id,
            }
        )
        license_rec.action_issue_token()
        self.assertEqual(license_rec.state, "active")

        parts = license_rec.token.split(".")
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "==").decode("utf-8"))
        self.assertEqual(payload["typ"], "perpetual")
        self.assertIsNone(payload.get("until"))

    def test_04_validation_constraints(self):
        """Memastikan validasi input model mencegah aturan yang keliru."""
        today = fields.Date.today()

        # Subscription tanpa valid_until harus ditolak
        with self.assertRaises(ValidationError):
            self.env["saas.license.record"].create(
                {
                    "merchant_name": "Test Invalid",
                    "license_type": "subscription",
                    "db_uuid": "dummy-uuid",
                    "valid_from": today,
                    "valid_until": False,
                    "key_id": self.signing_key.id,
                }
            )

        # Perpetual dengan valid_until harus ditolak
        with self.assertRaises(ValidationError):
            self.env["saas.license.record"].create(
                {
                    "merchant_name": "Test Invalid Perp",
                    "license_type": "perpetual",
                    "db_uuid": "dummy-uuid",
                    "valid_from": today,
                    "valid_until": today + timedelta(days=30),
                    "key_id": self.signing_key.id,
                }
            )

        # Max registers < 1 harus ditolak
        with self.assertRaises(ValidationError):
            self.env["saas.license.record"].create(
                {
                    "merchant_name": "Test Invalid Reg",
                    "license_type": "subscription",
                    "db_uuid": "dummy-uuid",
                    "valid_from": today,
                    "valid_until": today + timedelta(days=30),
                    "max_registers": 0,
                    "key_id": self.signing_key.id,
                }
            )

    def test_05_wizard_issuance(self):
        """Memastikan Wizard penerbitan cepat dapat membuat dan mengaktifkan lisensi."""
        today = fields.Date.today()
        wizard = self.env["saas.license.wizard"].create(
            {
                "merchant_name": "Kafe Kopi Kenangan",
                "db_uuid": "6e872fc5-df0e-33f3-0756-193e8a5edf22",
                "license_type": "subscription",
                "valid_from": today,
                "valid_until": today + timedelta(days=180),
                "max_registers": 3,
                "key_id": self.signing_key.id,
            }
        )
        action = wizard.action_issue_license()
        self.assertEqual(action["res_model"], "saas.license.record")

        created_record = self.env["saas.license.record"].browse(action["res_id"])
        self.assertEqual(created_record.merchant_name, "Kafe Kopi Kenangan")
        self.assertEqual(created_record.state, "active")
        self.assertTrue(bool(created_record.token))

    def test_06_role_access_rights(self):
        """Memastikan pembatasan hak akses role Viewer vs Manager."""
        today = fields.Date.today()

        # Manager BISA membuat lisensi
        rec_mgr = self.env["saas.license.record"].with_user(self.user_manager).create(
            {
                "merchant_name": "Outlet Manager Test",
                "db_uuid": "7f983ad6-ef1f-4404-1867-204f9b6fee33",
                "license_type": "subscription",
                "valid_from": today,
                "valid_until": today + timedelta(days=90),
                "key_id": self.signing_key.id,
            }
        )
        self.assertTrue(rec_mgr.id)
        # Manager BISA menerbitkan token
        rec_mgr.action_issue_token()
        self.assertEqual(rec_mgr.state, "active")

        # Viewer TIDAK BISA membuat lisensi
        with self.assertRaises(AccessError):
            self.env["saas.license.record"].with_user(self.user_viewer).create(
                {
                    "merchant_name": "Outlet Viewer Test",
                    "db_uuid": "8a094be7-f020-5515-2978-31500c7fff44",
                    "license_type": "subscription",
                    "valid_from": today,
                    "valid_until": today + timedelta(days=90),
                    "key_id": self.signing_key.id,
                }
            )
