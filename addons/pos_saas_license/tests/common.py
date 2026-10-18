"""Helper bersama untuk test `pos_saas_license` (T008).

Mixin ini dipakai bersama `odoo.tests.common.TransactionCase`:

    class TestLicenseCrypto(LicenseTestMixin, TransactionCase):
        ...

`setUpClass` membuat keypair Ed25519 sekali per test class, mengisi
`kid`/`private_key`/`public_key_b64`, lalu mem-patch
`license_verifier.PUBLIC_KEYS` sehingga token yang dibuat helper ini lolos
verifikasi. Private key hanya hidup di memori test dan tidak pernah ditulis ke
disk.

Modul `license_verifier` belum ada sampai T011. Import-nya karena itu dilakukan
malas (lazy) di dalam method, bukan di level modul, supaya paket test tetap
bisa dimuat.
"""

import base64
import contextlib
import datetime
import json
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

TOKEN_HEADER_ALG = "EdDSA"
TOKEN_HEADER_TYP = "SAAS-LIC"


class LicenseTestMixin:
    """Mixin pembuat keypair, token JWS, dan patch konteks lisensi."""

    kid = "test"
    private_key = None
    public_key_b64 = None
    _public_keys_patcher = None

    # ---------------------------------------------------------------- setup

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kid = "test"
        cls.private_key = ed25519.Ed25519PrivateKey.generate()
        cls.public_key_b64 = base64.b64encode(
            cls.private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        ).decode()
        verifier = cls._get_verifier_module()
        cls._public_keys_patcher = mock.patch.object(
            verifier, "PUBLIC_KEYS", {cls.kid: cls.public_key_b64}
        )
        cls._public_keys_patcher.start()

    @classmethod
    def tearDownClass(cls):
        if cls._public_keys_patcher is not None:
            cls._public_keys_patcher.stop()
            cls._public_keys_patcher = None
        super().tearDownClass()

    @staticmethod
    def _get_verifier_module():
        # Import malas: modul verifier baru ada mulai T011.
        from odoo.addons.pos_saas_license.models import license_verifier

        return license_verifier

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _b64url(raw):
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    @classmethod
    def _json_b64url(cls, value):
        """Encode dict/list sebagai JSON compact, atau str sebagai byte apa adanya."""
        if isinstance(value, str):
            raw = value.encode()
        else:
            raw = json.dumps(value, separators=(",", ":")).encode()
        return cls._b64url(raw)

    # --------------------------------------------------------------- tokens

    def default_header(self):
        return {
            "alg": TOKEN_HEADER_ALG,
            "typ": TOKEN_HEADER_TYP,
            "kid": self.kid,
        }

    def default_payload(self):
        return {
            "lid": "LIC-TEST-001",
            "mch": "Test Merchant",
            "typ": "subscription",
            "db_uuid": "test-db-uuid",
            "max_reg": 2,
            "from": "2026-01-01",
            "until": "2026-12-31",
            "grace": 7,
        }

    def make_payload(self, **overrides):
        """Payload valid dengan override; nilai None menghapus field."""
        payload = self.default_payload()
        for key, value in overrides.items():
            if value is None:
                payload.pop(key, None)
            else:
                payload[key] = value
        return payload

    def make_token(self, **overrides):
        """Token JWS valid yang ditandatangani `cls.private_key`."""
        return self.make_raw_token(
            self.default_header(), self.make_payload(**overrides)
        )

    def make_raw_token(self, header, payload, sign=True, key=None):
        """Token mentah untuk kasus rusak atau header/payload custom.

        `header` dan `payload` boleh dict (di-JSON-kan compact) atau str (dipakai
        apa adanya). Bila `sign` False, segmen signature dibiarkan kosong dan
        bentuk token yang lain (1/2/4 bagian) disusun langsung di test.
        `key` dipakai untuk menandatangani dengan key lain; default key test.
        """
        header_b64 = self._json_b64url(header)
        payload_b64 = self._json_b64url(payload)
        signing_input = f"{header_b64}.{payload_b64}".encode()
        if not sign:
            signature_b64 = ""
        else:
            signature_b64 = self._b64url((key or self.private_key).sign(signing_input))
        return f"{header_b64}.{payload_b64}.{signature_b64}"

    # ------------------------------------------------------------- konteks

    def set_database_uuid(self, value):
        """Tulis `database.uuid` di ir.config_parameter dan kembalikan nilainya."""
        self.env["ir.config_parameter"].sudo().set_param("database.uuid", value)
        return value

    @contextlib.contextmanager
    def patch_today(self, date_str):
        """Patch `pos.saas.license._today()` ke tanggal tetap."""
        if isinstance(date_str, str):
            today = datetime.date.fromisoformat(date_str)
        elif isinstance(date_str, datetime.datetime):
            today = date_str.date()
        else:
            today = date_str
        license_model = self.env["pos.saas.license"]
        with mock.patch.object(
            type(license_model), "_today", lambda *args, **kwargs: today
        ):
            yield today
