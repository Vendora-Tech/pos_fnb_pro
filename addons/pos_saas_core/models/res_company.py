import uuid
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    tenant_uuid = fields.Char(
        string="Tenant UUID",
        index=True,
        copy=False,
        default=lambda self: str(uuid.uuid4()),
        help="Unique identifier for tenant.",
    )
    receipt_header = fields.Text(
        string="Default Receipt Header",
        translate=True,
        help="Default header text printed on POS receipts across outlets.",
    )
    receipt_footer = fields.Text(
        string="Default Receipt Footer",
        translate=True,
        help="Default footer text printed on POS receipts across outlets.",
    )

    def init(self):
        super().init()
        self.env.cr.execute(
            """
            UPDATE res_company
            SET tenant_uuid = gen_random_uuid()::text
            WHERE tenant_uuid IS NULL OR tenant_uuid = '';
            """
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("tenant_uuid"):
                vals["tenant_uuid"] = str(uuid.uuid4())
        return super().create(vals_list)

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        saas_fields = [
            "tenant_uuid",
            "receipt_header",
            "receipt_footer",
        ]
        for f in saas_fields:
            if f not in fields:
                fields.append(f)
        return fields
