from odoo.tests.common import TransactionCase


class TestExampleTag(TransactionCase):
    def test_create_tag(self):
        tag = self.env["pos_example.tag"].create({"name": "dummy"})
        self.assertTrue(tag.active)
        self.assertEqual(tag.name, "dummy")
