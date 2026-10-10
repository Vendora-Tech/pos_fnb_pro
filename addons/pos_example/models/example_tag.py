from odoo import fields, models


class ExampleTag(models.Model):
    _name = "pos_example.tag"
    _description = "CI Dummy Tag"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
