import odoo.http
from unittest.mock import MagicMock
from lxml import etree

from odoo.exceptions import AccessDenied, AccessError, UserError
from odoo.tests.common import TransactionCase


class TestSaasAccessManagement(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Buat user kasir uji coba
        cls.cashier_user = cls.env["res.users"].create(
            {
                "name": "Test Cashier Staff",
                "login": "test_cashier_staff",
                "email": "cashier@vendora.test",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("base.group_partner_manager").id,
                        ],
                    )
                ],
            }
        )

        # Ambil model & field produk
        cls.product_model = cls.env.ref("product.model_product_template")
        cls.cost_field = cls.env.ref(
            "product.field_product_template__standard_price"
        )
        cls.barcode_field = cls.env.ref(
            "product.field_product_template__barcode"
        )

        # Buat Access Rule untuk kasir
        cls.cashier_rule = cls.env["saas.access.rule"].create(
            {
                "name": "Kebijakan Kasir Toko",
                "active": True,
                "hide_export": True,
                "user_ids": [(6, 0, [cls.cashier_user.id])],
                "model_access_ids": [
                    (
                        0,
                        0,
                        {
                            "model_id": cls.product_model.id,
                            "hide_delete": True,
                            "hide_duplicate": True,
                            "hide_search_panel": True,
                        },
                    )
                ],
                "field_access_ids": [
                    (
                        0,
                        0,
                        {
                            "model_id": cls.product_model.id,
                            "field_id": cls.cost_field.id,
                            "is_invisible": True,
                            "is_readonly": True,
                            "hide_export": True,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "model_id": cls.product_model.id,
                            "field_id": cls.barcode_field.id,
                            "is_required": True,
                            "remove_external_link": True,
                            "no_create": True,
                            "no_create_edit": True,
                        },
                    ),
                ],
            }
        )

    def test_view_cost_price_invisible_for_cashier(self):
        """Pastikan field harga modal (standard_price) disembunyikan untuk kasir."""
        ProductTemplate = self.env["product.template"]

        cashier_view = ProductTemplate.with_user(self.cashier_user).get_view(
            view_type="form"
        )
        arch = cashier_view.get("arch", "")
        self.assertTrue(bool(arch), "XML arch harus tersedia")

        doc = etree.fromstring(arch.encode("utf-8"))
        nodes = doc.xpath("//field[@name='standard_price']")
        for node in nodes:
            self.assertEqual(
                node.attrib.get("invisible"),
                "True",
                "Field standard_price harus invisible=True untuk kasir",
            )
            self.assertEqual(
                node.attrib.get("column_invisible"),
                "True",
                "Field standard_price harus column_invisible=True untuk kasir",
            )

        admin_view = ProductTemplate.with_user(self.env.ref("base.user_admin")).get_view(
            view_type="form"
        )
        self.assertTrue(bool(admin_view.get("arch")))

    def test_block_delete_product_for_cashier(self):
        """Pastikan kasir dilarang menghapus produk (UserError), sedangkan admin diizinkan."""
        product = self.env["product.template"].create(
            {
                "name": "Nasi Goreng Spesial Test",
                "list_price": 25000.0,
                "barcode": "BARCODE-001",
            }
        )

        with self.assertRaises(UserError):
            product.with_user(self.cashier_user).unlink()

        res = product.unlink()
        self.assertTrue(res, "Admin harus tetap dapat menghapus data")

    def test_disable_export_for_cashier(self):
        """Pastikan kasir tidak dapat mengekspor data (AccessError) dan can_export False."""
        product = self.env["product.template"].create(
            {
                "name": "Es Teh Manis Test",
                "list_price": 5000.0,
                "barcode": "BARCODE-002",
            }
        )

        with self.assertRaises(AccessError):
            product.with_user(self.cashier_user).export_data(["name", "list_price"])

        is_disabled = self.env["saas.access.rule"]._is_export_disabled_for_user(
            self.cashier_user.id
        )
        self.assertTrue(is_disabled, "Flag disable export harus True untuk kasir")

        mock_request = MagicMock()
        mock_request.session.uid = self.cashier_user.id
        mock_request.session.context = {}
        mock_request.session.debug = False
        mock_request.cookies = {}
        mock_request.httprequest.headers = {}
        token = odoo.http.request_var.set(mock_request)
        try:
            session_info = self.env["ir.http"].with_user(self.cashier_user).session_info()
            self.assertFalse(session_info.get("can_export"), "can_export harus False")
            if "groups" in session_info:
                self.assertFalse(
                    session_info["groups"].get("base.group_allow_export"),
                    "base.group_allow_export harus False",
                )
        finally:
            odoo.http.request_var.reset(token)

        export_result = product.export_data(["name", "list_price"])
        self.assertIn("datas", export_result)

    def test_hidden_menu_filter(self):
        """Pastikan menu yang ditandai hidden dimasukkan ke dalam blacklist kasir."""
        test_menu = self.env["ir.ui.menu"].create(
            {
                "name": "Menu Rahasia Toko",
                "parent_id": False,
            }
        )
        self.cashier_rule.write(
            {
                "hide_menu_ids": [(4, test_menu.id)],
            }
        )

        blacklist = self.env["ir.ui.menu"].with_user(self.cashier_user)._load_menus_blacklist()
        self.assertIn(
            test_menu.id,
            blacklist,
            "Menu yang diblokir harus ada di dalam blacklist kasir",
        )

        admin_blacklist = self.env["ir.ui.menu"]._load_menus_blacklist()
        self.assertNotIn(
            test_menu.id,
            admin_blacklist,
            "Menu tidak boleh diblacklist untuk superuser",
        )

    def test_readonly_user_mode(self):
        """Pastikan opsi readonly user memblokir create, write, dan unlink."""
        ro_user = self.env["res.users"].create(
            {
                "name": "Read Only Staff",
                "login": "readonly_staff",
                "email": "ro@vendora.test",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        self.env["saas.access.rule"].create(
            {
                "name": "Kebijakan Read Only",
                "active": True,
                "readonly": True,
                "user_ids": [(6, 0, [ro_user.id])],
            }
        )

        product = self.env["product.template"].create(
            {
                "name": "Produk Readonly Test",
                "list_price": 10000.0,
            }
        )

        with self.assertRaises(UserError):
            self.env["product.template"].with_user(ro_user).create({"name": "Produk Baru"})

        with self.assertRaises(UserError):
            product.with_user(ro_user).write({"list_price": 12000.0})

        with self.assertRaises(UserError):
            product.with_user(ro_user).unlink()

    def test_hide_button_and_tab(self):
        """Pastikan pembatasan button dan tab berhasil disuntikkan ke arch XML."""
        self.cashier_rule.write(
            {
                "button_tab_access_ids": [
                    (
                        0,
                        0,
                        {
                            "model_id": self.product_model.id,
                            "button_tab_type": "button",
                            "name": "action_open_label_layout",
                            "hide": True,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "model_id": self.product_model.id,
                            "button_tab_type": "tab",
                            "name": "sales",
                            "hide": True,
                        },
                    ),
                ],
            }
        )

        sample_arch = """
        <form string="Product">
            <header>
                <button name="action_open_label_layout" string="Print Labels"/>
            </header>
            <sheet>
                <notebook>
                    <page name="general_information" string="General Information"/>
                    <page name="sales" string="Sales"/>
                </notebook>
            </sheet>
        </form>
        """
        modified_arch = self.env["saas.access.rule"]._apply_view_restrictions(
            "product.template", "form", sample_arch, self.cashier_user.id
        )
        doc = etree.fromstring(modified_arch.encode("utf-8"))

        btn = doc.xpath("//button[@name='action_open_label_layout']")
        self.assertTrue(btn)
        self.assertEqual(btn[0].attrib.get("invisible"), "True")

        tab = doc.xpath("//page[@name='sales']")
        self.assertTrue(tab)
        self.assertEqual(tab[0].attrib.get("invisible"), "True")

    def test_hide_chatter(self):
        """Pastikan widget chatter disembunyikan jika rule hide_chatter aktif."""
        self.cashier_rule.write({"hide_chatter": True})

        sample_arch = """
        <form string="Test Form">
            <sheet>
                <field name="name"/>
            </sheet>
            <div class="oe_chatter">
                <chatter/>
            </div>
        </form>
        """
        modified_arch = self.env["saas.access.rule"]._apply_view_restrictions(
            "product.template", "form", sample_arch, self.cashier_user.id
        )
        doc = etree.fromstring(modified_arch.encode("utf-8"))
        chatter_div = doc.xpath("//div[contains(@class, 'oe_chatter')]")
        self.assertTrue(chatter_div)
        self.assertEqual(chatter_div[0].attrib.get("invisible"), "True")

    def test_disable_debug_mode(self):
        """Pastikan mode pengembang dinonaktifkan di session_info."""
        self.cashier_rule.write({"disable_debug_mode": True})

        mock_request = MagicMock()
        mock_request.session.uid = self.cashier_user.id
        mock_request.session.context = {}
        mock_request.session.debug = "assets"
        mock_request.cookies = {}
        mock_request.httprequest.headers = {}
        token = odoo.http.request_var.set(mock_request)
        try:
            session_info = self.env["ir.http"].with_user(self.cashier_user).session_info()
            self.assertEqual(session_info.get("debug"), "")
            self.assertEqual(mock_request.session.debug, "")
        finally:
            odoo.http.request_var.reset(token)

    def test_dynamic_domain_search_restriction(self):
        """Pastikan domain restriction menyaring data produk pada _search."""
        prod_a = self.env["product.template"].create({"name": "ABC Item", "barcode": "A1"})
        prod_b = self.env["product.template"].create({"name": "XYZ Item", "barcode": "B1"})

        self.cashier_rule.write(
            {
                "domain_access_ids": [
                    (
                        0,
                        0,
                        {
                            "model_id": self.product_model.id,
                            "domain": "[('name', 'like', 'ABC')]",
                            "restrict_read": True,
                        },
                    )
                ]
            }
        )

        res = self.env["product.template"].with_user(self.cashier_user).search([("id", "in", [prod_a.id, prod_b.id])])
        self.assertIn(prod_a, res)
        self.assertNotIn(prod_b, res)

    def test_disable_login(self):
        """Pastikan login user diblokir jika disable_login aktif."""
        self.cashier_rule.write({"disable_login": True})
        with self.assertRaises(AccessDenied):
            self.cashier_user._check_credentials(
                {"type": "password", "password": "dummy_pass"}, self.env
            )

    def test_make_field_required(self):
        """Pastikan field yang di-set required wajib diisi saat create."""
        partner_model = self.env.ref("base.model_res_partner")
        email_field = self.env.ref("base.field_res_partner__email")
        self.cashier_rule.write(
            {
                "field_access_ids": [
                    (
                        0,
                        0,
                        {
                            "model_id": partner_model.id,
                            "field_id": email_field.id,
                            "is_required": True,
                        },
                    )
                ]
            }
        )

        # Create tanpa email -> Harus UserError
        with self.assertRaises(UserError):
            self.env["res.partner"].with_user(self.cashier_user).create(
                {"name": "Partner Tanpa Email"}
            )

        # Create dengan email -> Berhasil
        partner = self.env["res.partner"].with_user(self.cashier_user).create(
            {"name": "Partner Beremail", "email": "valid@test.com"}
        )
        self.assertTrue(partner)

    def test_hide_duplicate(self):
        """Pastikan opsi duplikasi diblokir jika hide_duplicate aktif."""
        prod = self.env["product.template"].create({"name": "Produk Asli", "barcode": "BC-ORIG"})
        with self.assertRaises(UserError):
            prod.with_user(self.cashier_user).copy()

    def test_search_view_restrictions(self):
        """Pastikan search panel dan filter disembunyikan pada search view."""
        sample_search_arch = """
        <search string="Search Products">
            <field name="name"/>
            <filter string="Available" name="available" domain="[('list_price', '>', 0)]"/>
            <searchpanel>
                <field name="categ_id" icon="fa-cutlery"/>
            </searchpanel>
        </search>
        """
        self.cashier_rule.write(
            {
                "hide_filters_groups_ids": [
                    (
                        0,
                        0,
                        {
                            "model_id": self.product_model.id,
                            "filter_type": "filter",
                            "name": "available",
                            "hide": True,
                        },
                    )
                ]
            }
        )
        modified_arch = self.env["saas.access.rule"]._apply_view_restrictions(
            "product.template", "search", sample_search_arch, self.cashier_user.id
        )
        doc = etree.fromstring(modified_arch.encode("utf-8"))

        sp = doc.xpath("//searchpanel")
        self.assertEqual(sp[0].attrib.get("invisible"), "True")

        filter_node = doc.xpath("//filter[@name='available']")
        self.assertEqual(filter_node[0].attrib.get("invisible"), "True")

    def test_res_users_access_management_tab_and_sync(self):
        """Pastikan tab Access Management di res.users berfungsi dan tersinkron dua arah."""
        # 1. Pastikan rule yang ada tersinkron ke field access_management_rule_ids di user
        self.assertIn(self.cashier_rule, self.cashier_user.access_management_rule_ids)

        # 2. Buat rule baru dan assign langsung dari res.users
        new_rule = self.env["saas.access.rule"].create({"name": "Kebijakan Tambahan User"})
        self.cashier_user.write({"access_management_rule_ids": [(4, new_rule.id)]})

        # Cek sinkronisasi dua arah ke saas.access.rule.user_ids
        self.assertIn(self.cashier_user, new_rule.user_ids)

        # 3. Pastikan view form res.users memuat tab access_management
        user_form_view = self.env["res.users"].get_view(view_id=self.env.ref("base.view_users_form").id, view_type="form")
        self.assertIn('name="access_management"', user_form_view["arch"])
