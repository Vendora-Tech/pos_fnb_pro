"""Verifikasi token lisensi SaaS (T011).

Modul ini sengaja tidak mengimpor apa pun dari `odoo` supaya bisa diuji tanpa
setup database. Isinya hanya verifikasi kripto dan validasi skema.

Kontrak token mengikuti
`specs/001-pos-saas-license/contracts/license-token-schema.json`: compact JWS
tiga bagian base64url tanpa padding, header
`{"alg": "EdDSA", "typ": "SAAS-LIC", "kid": "<kid>"}`, dan signature Ed25519
atas byte ASCII `header_b64 + "." + payload_b64`.

`PUBLIC_KEYS` berisi public key yang memang untuk dibagikan; private key hanya
ada di mesin penerbit (`scripts/license_tools/keys/` di-ignore git). Kolom cache
di database tidak pernah dipakai sebagai sumber keputusan; setiap keputusan izin
memverifikasi ulang token lewat modul ini.
"""

import base64
import binascii
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

TOKEN_ALG = "EdDSA"
TOKEN_TYP = "SAAS-LIC"

# kid -> public key Ed25519 (base64 standar dari 32 byte mentah).
PUBLIC_KEYS = {
    # Key dev untuk uji coba lokal. Ganti dengan key produksi sebelum rilis.
    "dev2026": "Ye1zwvJX+MnRnE+Xc0vRzNnYsCVU7XSCbIZrFWsFvV4=",
}

CODE_MALFORMED_TOKEN = "malformed_token"
CODE_INVALID_HEADER = "invalid_header"
CODE_UNKNOWN_KID = "unknown_kid"
CODE_INVALID_SIGNATURE = "invalid_signature"
CODE_INVALID_PAYLOAD = "invalid_payload"

LICENSE_TYPES = ("subscription", "perpetual")

LICENSE_STATES = ("active", "warning", "grace", "expired", "invalid")

PAYLOAD_FIELDS = (
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

REQUIRED_PAYLOAD_FIELDS = ("lid", "mch", "typ", "db_uuid", "max_reg", "from", "grace")

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class LicenseError(Exception):
    """Token ditolak. `code` dipakai untuk log, `message` untuk manusia."""

    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class LicensePayload:
    """Isi token yang sudah lolos verifikasi signature dan skema.

    Tanggal disimpan sebagai string ISO apa adanya dari token; konversi ke
    `datetime.date` dilakukan saat perhitungan status.
    """

    lid: str
    mch: str
    typ: str
    db_uuid: str
    max_reg: int
    from_: str
    grace: int
    tenant_uuid: str | None = None
    mods: list = field(default_factory=list)
    until: str | None = None
    # `kid` diambil dari header token, dipakai model untuk kolom cache `key_id`.
    kid: str | None = None

    @property
    def is_perpetual(self):
        return self.typ == "perpetual"


# --------------------------------------------------------------- decoding


def _b64url_decode(segment):
    """Decode base64url tanpa padding; tolak karakter di luar alfabet."""
    if not isinstance(segment, str):
        raise LicenseError(
            CODE_MALFORMED_TOKEN, "token segment must be a string"
        )
    padded = segment + "=" * (-len(segment) % 4)
    try:
        return base64.b64decode(padded, altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise LicenseError(
            CODE_MALFORMED_TOKEN, "token segment is not valid base64url"
        ) from exc


def _json_object(raw, label):
    """Parse byte menjadi dict JSON; tolak JSON rusak atau bukan object."""
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise LicenseError(
            CODE_MALFORMED_TOKEN, f"{label} is not valid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise LicenseError(
            CODE_MALFORMED_TOKEN, f"{label} must be a JSON object"
        )
    return value


def _validate_header(header, public_keys):
    """Pastikan header berkontrak SAAS-LIC dan kembalikan `kid`-nya."""
    if header.get("alg") != TOKEN_ALG:
        raise LicenseError(CODE_INVALID_HEADER, "header alg must be EdDSA")
    if header.get("typ") != TOKEN_TYP:
        raise LicenseError(CODE_INVALID_HEADER, "header typ must be SAAS-LIC")
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid:
        raise LicenseError(CODE_INVALID_HEADER, "header kid is missing")
    if kid not in public_keys:
        raise LicenseError(CODE_UNKNOWN_KID, f"kid {kid!r} is not registered")
    return kid


def _verify_signature(signing_input, signature, public_key_b64):
    """Verifikasi signature Ed25519 atas `header_b64.payload_b64`."""
    try:
        raw_key = base64.b64decode(public_key_b64, validate=True)
        public_key = Ed25519PublicKey.from_public_bytes(raw_key)
    except (binascii.Error, TypeError, ValueError) as exc:
        raise LicenseError(
            CODE_INVALID_SIGNATURE, "registered public key is not usable"
        ) from exc
    try:
        public_key.verify(signature, signing_input)
    except (InvalidSignature, ValueError) as exc:
        raise LicenseError(
            CODE_INVALID_SIGNATURE, "token signature does not match"
        ) from exc


# ----------------------------------------------------------- schema rules


def _reject(code, message):
    raise LicenseError(code, message)


def _require_string(data, name):
    if name not in data:
        _reject(CODE_INVALID_PAYLOAD, f"payload field {name!r} is required")
    value = data[name]
    # Skema hanya menuntut tipe string, tanpa minLength.
    if not isinstance(value, str):
        _reject(CODE_INVALID_PAYLOAD, f"payload field {name!r} must be a string")
    return value


def _require_integer(data, name, minimum):
    if name not in data:
        _reject(CODE_INVALID_PAYLOAD, f"payload field {name!r} is required")
    value = data[name]
    # bool adalah subclass int di Python, tapi bukan integer di JSON Schema.
    if isinstance(value, bool) or not isinstance(value, int):
        _reject(CODE_INVALID_PAYLOAD, f"payload field {name!r} must be an integer")
    if value < minimum:
        _reject(
            CODE_INVALID_PAYLOAD,
            f"payload field {name!r} must be >= {minimum}",
        )
    return value


def _require_date(data, name):
    value = _require_string(data, name)
    if not _DATE_PATTERN.match(value):
        _reject(
            CODE_INVALID_PAYLOAD,
            f"payload field {name!r} must use the YYYY-MM-DD format",
        )
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise LicenseError(
            CODE_INVALID_PAYLOAD, f"payload field {name!r} is not a real date"
        ) from exc
    return value


def _validate_payload(data, kid=None):
    """Validasi payload tanpa `jsonschema`, mengikuti kontrak JSON schema."""
    unknown = sorted(set(data) - set(PAYLOAD_FIELDS))
    if unknown:
        _reject(
            CODE_INVALID_PAYLOAD,
            f"payload has fields outside the schema: {', '.join(unknown)}",
        )
    for name in REQUIRED_PAYLOAD_FIELDS:
        if name not in data:
            _reject(CODE_INVALID_PAYLOAD, f"payload field {name!r} is required")

    lid = _require_string(data, "lid")
    mch = _require_string(data, "mch")
    typ = _require_string(data, "typ")
    if typ not in LICENSE_TYPES:
        _reject(
            CODE_INVALID_PAYLOAD,
            f"payload field 'typ' must be one of {', '.join(LICENSE_TYPES)}",
        )
    db_uuid = _require_string(data, "db_uuid")
    max_reg = _require_integer(data, "max_reg", 1)
    grace = _require_integer(data, "grace", 0)
    from_ = _require_date(data, "from")

    tenant_uuid = data.get("tenant_uuid")
    if tenant_uuid is not None and not isinstance(tenant_uuid, str):
        _reject(CODE_INVALID_PAYLOAD, "payload field 'tenant_uuid' must be a string")

    mods = data.get("mods", [])
    if not isinstance(mods, list) or any(not isinstance(item, str) for item in mods):
        _reject(
            CODE_INVALID_PAYLOAD, "payload field 'mods' must be a list of strings"
        )

    until = data.get("until")
    if until is None:
        if typ == "subscription":
            _reject(
                CODE_INVALID_PAYLOAD,
                "a subscription token must carry an 'until' date",
            )
    else:
        until = _require_date(data, "until")
        if typ == "perpetual":
            _reject(
                CODE_INVALID_PAYLOAD,
                "a perpetual token must not carry an 'until' date",
            )

    return LicensePayload(
        lid=lid,
        mch=mch,
        typ=typ,
        db_uuid=db_uuid,
        max_reg=max_reg,
        from_=from_,
        grace=grace,
        tenant_uuid=tenant_uuid,
        mods=list(mods),
        until=until,
        kid=kid,
    )


# ------------------------------------------------------------------ public


def decode_and_verify(token, public_keys=None):
    """Verifikasi `token` dan kembalikan `LicensePayload`.

    `public_keys` menggantikan `PUBLIC_KEYS` bila diberikan. Signature
    diverifikasi sebelum payload di-parse, jadi isi token tidak pernah dipakai
    sebelum keasliannya terbukti.
    """
    keys = PUBLIC_KEYS if public_keys is None else public_keys
    if not isinstance(token, str):
        raise LicenseError(CODE_MALFORMED_TOKEN, "token must be a string")
    segments = token.split(".")
    if len(segments) != 3:
        raise LicenseError(
            CODE_MALFORMED_TOKEN, "token must have three dot separated segments"
        )
    header_b64, payload_b64, signature_b64 = segments

    header = _json_object(_b64url_decode(header_b64), "token header")
    kid = _validate_header(header, keys)

    signature = _b64url_decode(signature_b64)
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    _verify_signature(signing_input, signature, keys[kid])

    payload = _json_object(_b64url_decode(payload_b64), "token payload")
    return _validate_payload(payload, kid=kid)


def _coerce_date(value):
    """Terima `datetime.date`, `datetime.datetime`, atau string ISO."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _days_phrase(count):
    """Jumlah hari untuk pesan alasan: `1 day` atau `2 days`."""
    unit = "day" if abs(count) == 1 else "days"
    return f"{abs(count)} {unit}"


def compute_state(payload, today, db_uuid, warning_days=14):
    """Hitung `(state, days_left, reason)` dari payload yang sudah terverifikasi.

    `today` adalah tanggal lokal zona waktu company (fallback `Asia/Jakarta`),
    dan `db_uuid` adalah `database.uuid` tenant. Aturan mengikuti tabel
    "Aturan Perhitungan Status" di `specs/001-pos-saas-license/data-model.md`:
    `days_left > warning_days` active, `0 <= days_left <= warning_days` warning,
    `-grace <= days_left < 0` grace, dan di bawahnya expired. `days_left`
    bernilai `None` bila status tidak dihitung dari tanggal jatuh tempo.
    """
    today = _coerce_date(today)
    if payload.db_uuid != db_uuid:
        return (
            "invalid",
            None,
            f"database uuid does not match this database (current: {db_uuid}, token: {payload.db_uuid})",
        )
    if _coerce_date(payload.from_) > today:
        return "invalid", None, "license is not effective yet"
    if payload.is_perpetual:
        return "active", None, "Lifetime (perpetual license never expires)"
    if not payload.until:
        return "invalid", None, "subscription without an expiration date"

    days_left = (_coerce_date(payload.until) - today).days
    if days_left > warning_days:
        return "active", days_left, f"expires in {_days_phrase(days_left)}"
    if days_left >= 0:
        return "warning", days_left, f"expires in {_days_phrase(days_left)}"
    if days_left >= -payload.grace:
        return (
            "grace",
            days_left,
            f"grace period, {_days_phrase(days_left)} past expiry",
        )
    return "expired", days_left, f"expired {_days_phrase(days_left)} ago"
