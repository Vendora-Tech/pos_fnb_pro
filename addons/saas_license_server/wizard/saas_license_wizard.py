from odoo import api, fields, models


class SaasLicenseWizard(models.TransientModel):
    _name = "saas.license.wizard"
    _description = "Quick Issue License Wizard"

    merchant_name = fields.Char(string="Merchant Name", required=True)
    partner_id = fields.Many2one("res.partner", string="Customer / Partner")
    db_uuid = fields.Char(string="Tenant Database UUID", required=True)
    tenant_uuid = fields.Char(string="Tenant UUID")
    license_type = fields.Selection(
        [
            ("subscription", "Subscription (Berlangganan)"),
            ("perpetual", "Perpetual (Beli Putus)"),
        ],
        string="License Type",
        default="subscription",
        required=True,
    )
    valid_from = fields.Date(string="Valid From", required=True, default=fields.Date.context_today)
    valid_until = fields.Date(string="Valid Until")
    max_registers = fields.Integer(string="Max POS Registers", default=1, required=True)
    grace_period = fields.Integer(string="Grace Period (Days)", default=7, required=True)
    key_id = fields.Many2one(
        "saas.license.key",
        string="Signing Key",
        required=True,
        default=lambda self: self._default_key_id(),
    )
    license_id_custom = fields.Char(string="Custom License ID (Optional)")

    @api.model
    def _default_key_id(self):
        default_key = self.env["saas.license.key"].search([("is_default", "=", True), ("active", "=", True)], limit=1)
        if default_key:
            return default_key.id
        any_key = self.env["saas.license.key"].search([("active", "=", True)], limit=1)
        return any_key.id if any_key else False

    def action_issue_license(self):
        self.ensure_one()
        vals = {
            "merchant_name": self.merchant_name,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "db_uuid": self.db_uuid,
            "tenant_uuid": self.tenant_uuid,
            "license_type": self.license_type,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until if self.license_type == "subscription" else False,
            "max_registers": self.max_registers,
            "grace_period": self.grace_period,
            "key_id": self.key_id.id,
        }
        if self.license_id_custom:
            vals["name"] = self.license_id_custom

        record = self.env["saas.license.record"].create(vals)
        record.action_issue_token()

        return {
            "name": f"License {record.name}",
            "type": "ir.actions.act_window",
            "res_model": "saas.license.record",
            "res_id": record.id,
            "view_mode": "form",
            "target": "current",
        }
