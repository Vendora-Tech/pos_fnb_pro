"""Audit trail lisensi SaaS (T013)."""

from odoo import fields, models


class PosSaasLicenseLog(models.Model):
    """Satu baris per kejadian: instalasi, verifikasi, peringatan, insiden."""

    _name = "pos.saas.license.log"
    _description = "SaaS License Audit Log"
    _order = "event_date desc"

    license_id = fields.Many2one(
        "pos.saas.license",
        string="License",
        ondelete="cascade",
        index=True,
    )
    event_type = fields.Selection(
        [
            ("installed", "Token Installed"),
            ("verified", "Signature Verified"),
            ("warning", "Warning Triggered"),
            ("grace_entered", "Grace Period Entered"),
            ("expired", "License Expired"),
            ("blocked", "Session Open Blocked"),
            ("clock_tamper", "Clock Rollback Detected"),
            ("invalid_token", "Invalid Signature"),
        ],
        string="Event Type",
        required=True,
    )
    event_date = fields.Datetime(
        string="Event Date",
        default=fields.Datetime.now,
        required=True,
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        ondelete="set null",
    )
    details = fields.Text(string="Details", readonly=True)
