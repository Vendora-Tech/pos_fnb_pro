import base64
from datetime import timedelta
import json
import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

PAYLOAD_KEYS = (
    "lid",
    "mch",
    "typ",
    "db_uuid",
    "tenant_uuid",
    "mods",
    "max_reg",
    "from",
    "until",
    "grace",
)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


class SaasLicenseRecord(models.Model):
    _name = "saas.license.record"
    _description = "POS Store License Record"
    _order = "id desc"

    name = fields.Char(
        string="License ID (lid)",
        required=True,
        copy=False,
        default=lambda self: self.env["ir.sequence"].next_by_code("saas.license.record") or "LIC-NEW",
        help="Nomor ID Lisensi unik (misal: LIC-2026-FNB-001)",
    )
    merchant_name = fields.Char(
        string="Merchant Name (mch)",
        required=True,
        help="Nama merchant atau bisnis pemilik outlet",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer / Partner",
        help="Hubungkan dengan kontak pelanggan di Odoo jika ada",
    )
    license_type = fields.Selection(
        [
            ("subscription", "Subscription (Berlangganan)"),
            ("perpetual", "Perpetual (Beli Putus)"),
        ],
        string="License Type",
        default="subscription",
        required=True,
    )
    db_uuid = fields.Char(
        string="Database UUID",
        required=True,
        help="UUID database Odoo merchant (database.uuid dari ir_config_parameter)",
    )
    tenant_uuid = fields.Char(
        string="Store / Client UUID",
        help="UUID outlet / merchant (opsional)",
    )
    valid_from = fields.Date(
        string="Valid From",
        required=True,
        default=fields.Date.context_today,
    )
    valid_until = fields.Date(
        string="Valid Until",
        help="Tanggal masa aktif berakhir (Wajib untuk tipe subscription, kosongkan untuk perpetual)",
    )
    max_registers = fields.Integer(
        string="Max POS Registers",
        default=1,
        required=True,
        help="Jumlah kuota register kasir aktif yang diizinkan",
    )
    grace_period = fields.Integer(
        string="Grace Period (Days)",
        default=7,
        required=True,
        help="Jumlah hari masa tenggang toleransi setelah tanggal kadaluarsa",
    )
    allowed_modules = fields.Char(
        string="Allowed Modules",
        help="Daftar nama modul yang diizinkan (dipisahkan koma, opsional)",
    )
    key_id = fields.Many2one(
        "saas.license.key",
        string="Signing Key",
        required=True,
        default=lambda self: self._default_key_id(),
        help="Kunci Ed25519 yang digunakan untuk menandatangani token lisensi ini",
    )
    token = fields.Text(
        string="Generated JWS Token",
        readonly=True,
        copy=False,
        help="Token Compact JWS 3-bagian hasil tanda tangan kriptografi",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active / Issued"),
            ("revoked", "Revoked"),
        ],
        string="Status",
        default="draft",
        required=True,
        copy=False,
    )
    issue_date = fields.Datetime(
        string="Issued Date",
        readonly=True,
        copy=False,
    )
    notes = fields.Text(string="Notes")
    days_remaining = fields.Integer(
        string="Days Remaining",
        compute="_compute_days_remaining",
    )

    _check_lid_unique = models.Constraint(
        "UNIQUE(name)",
        "License ID (lid) harus unik!",
    )

    @api.model
    def _default_key_id(self):
        default_key = self.env["saas.license.key"].search([("is_default", "=", True), ("active", "=", True)], limit=1)
        if default_key:
            return default_key.id
        any_key = self.env["saas.license.key"].search([("active", "=", True)], limit=1)
        return any_key.id if any_key else False

    @api.depends("valid_until", "license_type")
    def _compute_days_remaining(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.license_type == "perpetual":
                rec.days_remaining = 9999
            elif rec.valid_until:
                rec.days_remaining = (rec.valid_until - today).days
            else:
                rec.days_remaining = 0

    @api.constrains("license_type", "valid_from", "valid_until", "max_registers", "grace_period")
    def _check_license_rules(self):
        for rec in self:
            if rec.max_registers < 1:
                raise ValidationError("Max POS Registers minimal 1!")
            if rec.grace_period < 0:
                raise ValidationError("Grace Period tidak boleh negatif!")
            if rec.license_type == "subscription":
                if not rec.valid_until:
                    raise ValidationError("Valid Until wajib diisi untuk tipe Subscription!")
                if rec.valid_until < rec.valid_from:
                    raise ValidationError("Valid Until tidak boleh lebih awal dari Valid From!")
            elif rec.license_type == "perpetual" and rec.valid_until:
                raise ValidationError("Tipe Perpetual tidak boleh memiliki Valid Until (harus kosong)!")

    def action_issue_token(self):
        """Menandatangani payload dengan Ed25519 dan menghasilkan Compact JWS."""
        self.ensure_one()
        self._check_license_rules()

        private_key = self.sudo().key_id.get_private_key_obj()

        payload = {
            "lid": self.name.strip(),
            "mch": self.merchant_name.strip(),
            "typ": self.license_type,
            "db_uuid": self.db_uuid.strip(),
            "max_reg": self.max_registers,
            "from": self.valid_from.isoformat(),
            "until": self.valid_until.isoformat() if self.license_type == "subscription" else None,
            "grace": self.grace_period,
        }
        if self.tenant_uuid and self.tenant_uuid.strip():
            payload["tenant_uuid"] = self.tenant_uuid.strip()
        if self.allowed_modules and self.allowed_modules.strip():
            payload["mods"] = [m.strip() for m in self.allowed_modules.split(",") if m.strip()]

        ordered_payload = {k: payload[k] for k in PAYLOAD_KEYS if k in payload}

        header = {
            "alg": "EdDSA",
            "typ": "SAAS-LIC",
            "kid": self.key_id.key_id.strip(),
        }

        header_b64 = b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        payload_b64 = b64url(json.dumps(ordered_payload, separators=(",", ":")).encode("utf-8"))

        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        signature = private_key.sign(signing_input)
        signature_b64 = b64url(signature)

        token = f"{header_b64}.{payload_b64}.{signature_b64}"

        self.write(
            {
                "token": token,
                "state": "active",
                "issue_date": fields.Datetime.now(),
            }
        )
        return True

    def action_revoke(self):
        self.write({"state": "revoked"})

    def action_reset_draft(self):
        self.write({"state": "draft", "token": False})

    def action_renew(self):
        """Memperpanjang lisensi subscription dengan menduplikasi parameter ke record baru."""
        self.ensure_one()
        if self.license_type == "perpetual":
            raise UserError("Lisensi tipe Perpetual tidak memerlukan perpanjangan (berlaku selamanya)!")

        today = fields.Date.context_today(self)
        duration = (
            (self.valid_until - self.valid_from)
            if (self.valid_until and self.valid_from)
            else timedelta(days=365)
        )
        if duration.days <= 0:
            duration = timedelta(days=365)

        if self.valid_until and self.valid_until >= today:
            new_from = self.valid_until + timedelta(days=1)
        else:
            new_from = today
        new_until = new_from + duration

        new_record = self.create({
            "merchant_name": self.merchant_name,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "license_type": "subscription",
            "db_uuid": self.db_uuid,
            "tenant_uuid": self.tenant_uuid,
            "valid_from": new_from,
            "valid_until": new_until,
            "max_registers": self.max_registers,
            "grace_period": self.grace_period,
            "allowed_modules": self.allowed_modules,
            "key_id": self.key_id.id,
            "notes": f"Renewal dari lisensi {self.name}",
        })

        return {
            "name": "Perpanjangan Lisensi POS",
            "type": "ir.actions.act_window",
            "res_model": "saas.license.record",
            "res_id": new_record.id,
            "view_mode": "form",
            "target": "current",
        }
