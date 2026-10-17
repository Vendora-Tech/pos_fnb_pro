from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    _indexes = [
        models.Index("(company_id, outlet_code)"),
    ]

    tenant_uuid = fields.Char(
        related="company_id.tenant_uuid",
        readonly=True,
        string="Tenant UUID",
    )
    outlet_code = fields.Char(
        string="Outlet Code",
        required=True,
        default="OUTLET-01",
        index=True,
        help="Branch/outlet code identifying this POS register (e.g. ALSUT-01, SMG-K1).",
    )
    use_custom_receipt = fields.Boolean(
        string="Custom Receipt for Outlet",
        default=False,
        help="Enable outlet-specific receipt header and footer overrides.",
    )
    receipt_header_override = fields.Text(
        string="Receipt Header Override",
        translate=True,
        help="Branch-specific header text for POS receipts.",
    )
    receipt_footer_override = fields.Text(
        string="Receipt Footer Override",
        translate=True,
        help="Branch-specific footer text for POS receipts.",
    )

    @api.model
    def _load_pos_data_read(self, records, config):
        read_records = super()._load_pos_data_read(records, config)
        for record in read_records:
            if record.get("use_custom_receipt"):
                if record.get("receipt_header_override"):
                    record["receipt_header"] = record["receipt_header_override"]
                if record.get("receipt_footer_override"):
                    record["receipt_footer"] = record["receipt_footer_override"]
            else:
                company = config.company_id if config else self.env.company
                if company.receipt_header:
                    record["receipt_header"] = company.receipt_header
                if company.receipt_footer:
                    record["receipt_footer"] = company.receipt_footer
        return read_records
