"""Test verifikasi kriptografi dan validasi skema token lisensi (T009).

Test ini memanggil `decode_and_verify` dari
`odoo.addons.pos_saas_license.models.license_verifier` secara murni: tanpa
akses database dan tanpa jaringan. Keypair Ed25519 serta patch `PUBLIC_KEYS`
disediakan oleh `LicenseTestMixin` di `tests/common.py`.

Kontrak token mengikuti
`specs/001-pos-saas-license/contracts/license-token-schema.json`: compact JWS
tiga bagian base64url tanpa padding, header
`{"alg": "EdDSA", "typ": "SAAS-LIC", "kid": "<kid>"}`, dan signature Ed25519
atas byte ASCII `header_b64 + "." + payload_b64`.
"""

import base64
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from odoo.addons.pos_saas_license.models.license_verifier import (
    LicenseError,
    decode_and_verify,
)
from odoo.tests.common import TransactionCase

from .common import LicenseTestMixin

# `from` adalah keyword Python, jadi atribut LicensePayload untuk field
# `from`/`until` boleh memakai suffix atau nama panjang.
_PAYLOAD_ATTR_ALIASES = {
    "from": ("from", "from_", "valid_from"),
    "until": ("until", "valid_until"),
}


class TestLicenseCrypto(LicenseTestMixin, TransactionCase):
    """Unit test `decode_and_verify`: signature, bentuk token, dan skema."""

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def b64url_encode(self, raw):
        """Encode byte menjadi base64url tanpa padding."""
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    def payload_field(self, payload, name):
        """Baca field payload secara toleran terhadap nama atribut alternatif."""
        for attr in _PAYLOAD_ATTR_ALIASES.get(name, (name,)):
            if hasattr(payload, attr):
                return getattr(payload, attr)
        if hasattr(payload, "get"):
            return payload.get(name)
        self.fail(f"LicensePayload tidak punya field {name!r}")

    def assert_token_rejected(self, token, message):
        """Token wajib ditolak dengan LicenseError yang punya kode terisi."""
        with self.assertRaises(LicenseError, msg=message) as caught:
            decode_and_verify(token)
        error = caught.exception
        self.assertIsInstance(
            getattr(error, "code", None), str, "LicenseError.code must be a string"
        )
        self.assertTrue(error.code, "LicenseError.code must not be empty")
        return error

    def json_segment(self, value):
        """Buat satu bagian token dari objek Python (JSON compact)."""
        raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
        return self.b64url_encode(raw)

    # ------------------------------------------------------------------
    # Token valid
    # ------------------------------------------------------------------

    def test_valid_subscription_token_accepted(self):
        """Token subscription yang ditandatangani benar lolos verifikasi."""
        payload = decode_and_verify(self.make_token())
        expected = self.default_payload()
        for name in ("lid", "mch", "typ", "db_uuid", "max_reg", "from", "until"):
            self.assertEqual(
                self.payload_field(payload, name),
                expected[name],
                f"Payload field {name!r} must be carried over from the token",
            )
        self.assertFalse(
            self.payload_field(payload, "mods"),
            "mods must be empty when the token does not send it",
        )

    def test_valid_perpetual_token_accepted(self):
        """Perpetual tanpa `until` valid dan tidak memuat tanggal jatuh tempo."""
        payload = decode_and_verify(self.make_token(typ="perpetual", until=None))
        self.assertEqual(self.payload_field(payload, "typ"), "perpetual")
        self.assertFalse(self.payload_field(payload, "until"))

    def test_optional_tenant_uuid_accepted(self):
        """`tenant_uuid` dari pos_saas_core boleh ada dan tidak diwajibkan."""
        with_tenant = decode_and_verify(self.make_token(tenant_uuid="tenant-test-uuid"))
        self.assertEqual(
            self.payload_field(with_tenant, "tenant_uuid"), "tenant-test-uuid"
        )
        decode_and_verify(self.make_token())

    def test_missing_grace_defaults_to_seven(self):
        """`grace` tidak wajib; bila hilang, nilai default skema adalah 7 hari."""
        payload = decode_and_verify(self.make_token(grace=None))
        self.assertEqual(self.payload_field(payload, "grace"), 7)

    def test_optional_fields_accepted(self):
        """`mods` tidak diwajibkan skema."""
        payload = decode_and_verify(self.make_token(mods=["pos_base", "pos_id_qris"]))
        self.assertEqual(
            self.payload_field(payload, "mods"), ["pos_base", "pos_id_qris"]
        )

    def test_minimum_values_accepted(self):
        """Batas minimum skema (max_reg=1, grace=0) tetap valid."""
        payload = decode_and_verify(self.make_token(max_reg=1, grace=0))
        self.assertEqual(self.payload_field(payload, "max_reg"), 1)
        self.assertEqual(self.payload_field(payload, "grace"), 0)

    def test_public_keys_argument_overrides_module_keys(self):
        """Argumen `public_keys` dipakai bila diberikan."""
        token = self.make_token()
        payload = decode_and_verify(token, public_keys={"test": self.public_key_b64})
        self.assertEqual(self.payload_field(payload, "lid"), "LIC-TEST-001")
        with self.assertRaises(LicenseError, msg="Only the 'other' kid is registered"):
            decode_and_verify(token, public_keys={"other": self.public_key_b64})

    # ------------------------------------------------------------------
    # Token rusak
    # ------------------------------------------------------------------

    def test_tampered_payload_rejected(self):
        """Payload diubah setelah ditandatangani wajib ditolak."""
        header_b64, _, signature_b64 = self.make_token().split(".")
        payload = self.default_payload()
        payload["max_reg"] = 99
        tampered = ".".join([header_b64, self.json_segment(payload), signature_b64])
        self.assert_token_rejected(
            tampered, "Payload tampering must fail signature verification"
        )

    def test_tampered_signature_rejected(self):
        """Signature yang diubah wajib ditolak."""
        header_b64, payload_b64, signature_b64 = self.make_token().split(".")
        flipped = ("A" if signature_b64[0] != "A" else "B") + signature_b64[1:]
        tampered = f"{header_b64}.{payload_b64}.{flipped}"
        self.assert_token_rejected(tampered, "A modified signature must be rejected")

    def test_token_signed_with_other_key_rejected(self):
        """Signature dari keypair lain wajib ditolak."""
        other_key = Ed25519PrivateKey.generate()
        token = self.make_raw_token(
            {"alg": "EdDSA", "typ": "SAAS-LIC", "kid": self.kid},
            self.default_payload(),
            key=other_key,
        )
        self.assert_token_rejected(
            token, "A token signed by a foreign key must be rejected"
        )

    def test_unknown_kid_rejected(self):
        """Header dengan `kid` yang tidak terdaftar wajib ditolak."""
        token = self.make_raw_token(
            {"alg": "EdDSA", "typ": "SAAS-LIC", "kid": "unknown-kid"},
            self.default_payload(),
        )
        self.assert_token_rejected(
            token, "An unknown kid must be rejected even with a valid signature"
        )

    def test_unknown_algorithm_rejected(self):
        """`alg` selain EdDSA wajib ditolak."""
        token = self.make_raw_token(
            {"alg": "HS256", "typ": "SAAS-LIC", "kid": self.kid},
            self.default_payload(),
        )
        self.assert_token_rejected(token, "alg must be EdDSA")

    def test_wrong_header_type_rejected(self):
        """Header dengan `typ` selain SAAS-LIC wajib ditolak."""
        token = self.make_raw_token(
            {"alg": "EdDSA", "typ": "JWT", "kid": self.kid},
            self.default_payload(),
        )
        self.assert_token_rejected(token, "Header typ must be SAAS-LIC")

    def test_malformed_segment_count_rejected(self):
        """Token yang bukan 3 bagian wajib ditolak."""
        header_b64, payload_b64, signature_b64 = self.make_token().split(".")
        cases = {
            "empty": "",
            "one_part": header_b64,
            "two_parts": f"{header_b64}.{payload_b64}",
            "four_parts": f"{header_b64}.{payload_b64}.{signature_b64}.extra",
        }
        for label, token in cases.items():
            with self.subTest(label=label):
                self.assert_token_rejected(
                    token, f"Token with {label} must be rejected"
                )

    def test_broken_base64_rejected(self):
        """Bagian base64 yang tidak bisa didecode wajib ditolak."""
        header_b64, payload_b64, signature_b64 = self.make_token().split(".")
        cases = {
            "header": f"@@@.{payload_b64}.{signature_b64}",
            "payload": f"{header_b64}.@@@.{signature_b64}",
            "signature": f"{header_b64}.{payload_b64}.@@@",
        }
        for label, token in cases.items():
            with self.subTest(label=label):
                self.assert_token_rejected(
                    token, f"Invalid base64 in the {label} segment must be rejected"
                )

    def test_broken_json_rejected(self):
        """JSON yang rusak atau bukan object wajib ditolak."""
        header_b64, payload_b64, signature_b64 = self.make_token().split(".")
        broken_json = self.b64url_encode(b"{not-json")
        not_an_object = self.b64url_encode(b"[]")
        cases = {
            "header_json": f"{broken_json}.{payload_b64}.{signature_b64}",
            "payload_json": f"{header_b64}.{broken_json}.{signature_b64}",
            "payload_not_object": f"{header_b64}.{not_an_object}.{signature_b64}",
        }
        for label, token in cases.items():
            with self.subTest(label=label):
                self.assert_token_rejected(
                    token, f"{label} must be rejected as malformed JSON"
                )

    # ------------------------------------------------------------------
    # Validasi skema payload
    # ------------------------------------------------------------------

    def test_missing_required_field_rejected(self):
        """Field wajib yang hilang wajib ditolak."""
        for field in ("lid", "mch", "typ", "db_uuid", "max_reg", "from"):
            with self.subTest(field=field):
                token = self.make_token(**{field: None})
                self.assert_token_rejected(
                    token, f"Missing required field {field!r} must be rejected"
                )

    def test_unknown_payload_field_rejected(self):
        """Field di luar skema wajib ditolak (additionalProperties: false)."""
        token = self.make_token(unexpected_field="unexpected")
        self.assert_token_rejected(token, "Unknown payload fields must be rejected")

    def test_license_type_outside_enum_rejected(self):
        """`typ` di luar enum wajib ditolak."""
        for value in ("trial", "SUBSCRIPTION", ""):
            with self.subTest(typ=value):
                token = self.make_token(
                    typ=value, until=self.default_payload()["until"]
                )
                self.assert_token_rejected(
                    token, f"typ {value!r} must be rejected as out of enum"
                )

    def test_max_reg_below_minimum_rejected(self):
        """`max_reg` kurang dari 1 wajib ditolak (minimum: 1)."""
        for value in (0, -1):
            with self.subTest(max_reg=value):
                token = self.make_token(max_reg=value)
                self.assert_token_rejected(
                    token, f"max_reg {value!r} must be rejected as below minimum"
                )

    def test_max_reg_wrong_type_rejected(self):
        """`max_reg` bukan integer wajib ditolak."""
        for value in ("2", 1.5):
            with self.subTest(max_reg=value):
                token = self.make_token(max_reg=value)
                self.assert_token_rejected(
                    token, f"max_reg {value!r} must be rejected as not an integer"
                )

    def test_negative_grace_rejected(self):
        """`grace` kurang dari 0 wajib ditolak (minimum: 0)."""
        token = self.make_token(grace=-1)
        self.assert_token_rejected(token, "A negative grace must be rejected")

    def test_subscription_without_until_rejected(self):
        """Subscription tanpa `until` wajib ditolak."""
        token = self.make_token(until=None)
        self.assert_token_rejected(
            token, "Subscription tokens must carry an until date"
        )

    def test_perpetual_with_until_rejected(self):
        """Perpetual dengan `until` non-null wajib ditolak."""
        token = self.make_token(typ="perpetual", until="2026-12-31")
        self.assert_token_rejected(
            token, "Perpetual tokens must not carry an until date"
        )

    def test_invalid_date_format_rejected(self):
        """`from`/`until` di luar format YYYY-MM-DD wajib ditolak."""
        cases = {
            "from_slashes": {"from": "01/01/2026"},
            "from_unpadded": {"from": "2026-1-1"},
            "until_slashes": {"until": "31/12/2026"},
            "until_reversed": {"until": "12-31-2026"},
        }
        for label, overrides in cases.items():
            with self.subTest(case=label):
                token = self.make_token(**overrides)
                self.assert_token_rejected(
                    token, f"Invalid date format in {label} must be rejected"
                )
