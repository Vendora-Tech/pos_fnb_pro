import base64
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "pos_saas_core")
class TestPosSaasCore(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({
            "tenant_uuid": "tenant-test-uuid-9999",
            "receipt_header": "Global Tenant Header",
            "receipt_footer": "Global Tenant Footer",
        })

    def test_company_tenant_fields(self):
        """Verifikasi field tenant res.company."""
        self.assertEqual(self.company.tenant_uuid, "tenant-test-uuid-9999")
        self.assertEqual(self.company.receipt_header, "Global Tenant Header")
        self.assertEqual(self.company.receipt_footer, "Global Tenant Footer")

    def test_tenant_uuid_auto_generated(self):
        """Verifikasi tenant_uuid otomatis terbuat saat membuat company baru."""
        new_company = self.env["res.company"].create({
            "name": "Auto UUID Company",
        })
        self.assertTrue(bool(new_company.tenant_uuid))
        self.assertEqual(len(new_company.tenant_uuid), 36)

    def test_pos_config_outlet_and_fallback(self):
        """Verifikasi outlet_code dan logika fallback receipt di pos.config."""
        pos_config = self.env["pos.config"].create({
            "name": "Main Register ALSUT",
            "company_id": self.company.id,
            "outlet_code": "ALSUT-01",
            "use_custom_receipt": False,
        })
        self.assertEqual(pos_config.outlet_code, "ALSUT-01")
        self.assertEqual(pos_config.tenant_uuid, "tenant-test-uuid-9999")

        # Test fallback ke company receipt header & footer
        loaded = pos_config._load_pos_data_read(pos_config, pos_config)
        self.assertTrue(len(loaded) > 0)
        self.assertEqual(loaded[0]["receipt_header"], "Global Tenant Header")
        self.assertEqual(loaded[0]["receipt_footer"], "Global Tenant Footer")

        # Test override spesifik outlet
        pos_config.write({
            "use_custom_receipt": True,
            "receipt_header_override": "Custom Outlet Header",
            "receipt_footer_override": "Custom Outlet Footer",
        })
        loaded_override = pos_config._load_pos_data_read(pos_config, pos_config)
        self.assertEqual(loaded_override[0]["receipt_header"], "Custom Outlet Header")
        self.assertEqual(loaded_override[0]["receipt_footer"], "Custom Outlet Footer")

    def test_pos_config_logo_fallback_to_company_logo(self):
        """Verifikasi logo pos.config otomatis fallback ke native company.logo."""
        valid_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
        b64_logo = base64.b64encode(valid_png).decode("ascii")
        self.company.logo = b64_logo

        pos_config = self.env["pos.config"].create({
            "name": "Register Company Logo Test",
            "company_id": self.company.id,
            "outlet_code": "TEST-LOGO-01",
            "use_custom_receipt_info": False,
        })
        # Harus terisi dari company.logo
        self.assertTrue(bool(pos_config.logo))
        self.assertEqual(bytes(pos_config.logo), bytes(self.company.logo))

    def test_pos_data_fields_loader(self):
        """Verifikasi penambahan field saas_core ke _load_pos_data_fields res.company."""
        company_fields = self.env["res.company"]._load_pos_data_fields(1)
        expected_company = ["tenant_uuid", "receipt_header", "receipt_footer"]
        for f in expected_company:
            self.assertIn(f, company_fields)
