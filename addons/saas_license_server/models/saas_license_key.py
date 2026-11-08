import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SaasLicenseKey(models.Model):
    _name = "saas.license.key"
    _description = "POS License Signing Keypair"
    _order = "is_default desc, id desc"

    name = fields.Char(string="Key Name", required=True)
    key_id = fields.Char(
        string="Key ID (kid)",
        required=True,
        help="Identifier kunci unik (misal: prod2026 atau dev2026)",
    )
    private_key_pem = fields.Text(
        string="Private Key (PEM)",
        groups="base.group_system",
        help="Private key Ed25519 dalam format PKCS8 PEM (Sangat Rahasia - Hanya Super Administrator)",
    )
    public_key_b64 = fields.Char(
        string="Public Key (Base64)",
        readonly=True,
        help="Public key Ed25519 32-byte mentah dalam format Base64 standar untuk didaftarkan ke POS",
    )
    is_default = fields.Boolean(
        string="Default Signing Key",
        default=False,
        help="Kunci default yang otomatis dipilih saat menerbitkan lisensi baru",
    )
    active = fields.Boolean(default=True)
    license_count = fields.Integer(
        string="Total Licenses Issued",
        compute="_compute_license_count",
    )

    _check_key_id_unique = models.Constraint(
        "UNIQUE(key_id)",
        "Key ID (kid) harus unik!",
    )

    @api.depends()
    def _compute_license_count(self):
        license_model = self.env["saas.license.record"]
        for key in self:
            key.license_count = license_model.search_count([("key_id", "=", key.id)])

    @api.constrains("is_default")
    def _check_default_key(self):
        for rec in self:
            if rec.is_default:
                others = self.search([("id", "!=", rec.id), ("is_default", "=", True)])
                if others:
                    others.write({"is_default": False})

    def action_generate_keypair(self):
        """Buat pasangan kunci Ed25519 baru secara otomatis."""
        self.ensure_one()
        private_key = ed25519.Ed25519PrivateKey.generate()
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        public_bytes = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        pub_b64 = base64.b64encode(public_bytes).decode("utf-8")

        self.write(
            {
                "private_key_pem": pem,
                "public_key_b64": pub_b64,
            }
        )
        return True

    def get_private_key_obj(self):
        """Mengurai dan mengembalikan objek private key Ed25519."""
        self.ensure_one()
        if not self.private_key_pem:
            raise UserError("Private Key belum diatur pada kunci ini!")
        try:
            key_obj = serialization.load_pem_private_key(
                self.private_key_pem.encode("utf-8"),
                password=None,
            )
            if not isinstance(key_obj, ed25519.Ed25519PrivateKey):
                raise UserError("Kunci ini bukan Ed25519 Private Key!")
            return key_obj
        except Exception as exc:
            raise UserError(f"Gagal memuat Private Key: {exc}") from exc
