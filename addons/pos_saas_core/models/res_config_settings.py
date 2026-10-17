from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    saas_tenant_uuid = fields.Char(
        related="company_id.tenant_uuid",
        readonly=True,
        string="Tenant UUID",
        help="Global unique tenant identifier for this store.",
    )
    saas_default_receipt_header = fields.Text(
        related="company_id.receipt_header",
        readonly=False,
        string="Tenant Default Receipt Header",
        help="Fallback header if outlet does not specify an override.",
    )
    saas_default_receipt_footer = fields.Text(
        related="company_id.receipt_footer",
        readonly=False,
        string="Tenant Default Receipt Footer",
        help="Fallback footer if outlet does not specify an override.",
    )
