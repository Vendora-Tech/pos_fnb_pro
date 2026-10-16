#!/usr/bin/env python3
"""Issue a POS SaaS license token (compact JWS, Ed25519).

Token format: header.payload.signature (base64url, no padding).

    header  {"alg": "EdDSA", "typ": "SAAS-LIC", "kid": <kid>}
    payload see contracts/license-token-schema.json
    sig     Ed25519 over ASCII "<header_b64>.<payload_b64>"

Usage:
    python scripts/license_tools/issue_token.py \
        --key ./keys/dev2026.pem --kid dev2026 \
        --lid LIC-2026-TEST-001 --mch "Toko Sukses Makmur" \
        --typ subscription --db-uuid <DATABASE_UUID> \
        --max-reg 2 --from 2026-01-01 --until 2026-12-31 --grace 7

    # perpetual: no --until allowed
    python scripts/license_tools/issue_token.py ... --typ perpetual --from 2026-01-01
"""

import argparse
import base64
import datetime
import json
import pathlib
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

PAYLOAD_KEYS = (
    "lid",
    "mch",
    "typ",
    "db_uuid",
    "mods",
    "max_reg",
    "from",
    "until",
    "grace",
)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def date_arg(value: str) -> str:
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"{value!r} is not a YYYY-MM-DD date"
        ) from None
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--key", required=True, help="Path to the Ed25519 private key PEM"
    )
    parser.add_argument(
        "--kid",
        required=True,
        help="Key id, must match a key registered in PUBLIC_KEYS",
    )
    parser.add_argument(
        "--lid", required=True, help="License id, e.g. LIC-2026-FNB-0089"
    )
    parser.add_argument("--mch", required=True, help="Merchant name")
    parser.add_argument(
        "--typ",
        required=True,
        choices=["subscription", "perpetual"],
        help="License model",
    )
    parser.add_argument(
        "--db-uuid", required=True, help="Target database.uuid of the Odoo tenant"
    )
    parser.add_argument(
        "--mods",
        default="",
        help="Comma separated allowed modules (stored for display only)",
    )
    parser.add_argument(
        "--max-reg", required=True, type=int, help="Maximum POS registers (>= 1)"
    )
    parser.add_argument(
        "--from",
        dest="valid_from",
        required=True,
        type=date_arg,
        help="First valid date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--until",
        type=date_arg,
        default=None,
        help="Expiration date (YYYY-MM-DD); subscription only",
    )
    parser.add_argument(
        "--grace",
        default=7,
        type=int,
        help="Grace period days after expiration (default: 7)",
    )
    return parser.parse_args()


def validate(args: argparse.Namespace) -> str | None:
    if args.max_reg < 1:
        return "--max-reg must be >= 1"
    if args.grace < 0:
        return "--grace must be >= 0"
    if args.typ == "subscription" and args.until is None:
        return "--until is required for subscription licenses"
    if args.typ == "perpetual" and args.until is not None:
        return "--until is not allowed for perpetual licenses (it must be null)"
    if args.until is not None and args.until < args.valid_from:
        return "--until must not be earlier than --from"
    if args.mods and not all(m.strip() for m in args.mods.split(",")):
        return "--mods contains an empty module name"
    return None


def main() -> int:
    args = parse_args()
    error = validate(args)
    if error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    key_path = pathlib.Path(args.key).expanduser()
    if not key_path.exists():
        print(f"ERROR: private key not found: {key_path}", file=sys.stderr)
        return 1

    try:
        private_key = serialization.load_pem_private_key(
            key_path.read_bytes(), password=None
        )
    except (TypeError, ValueError) as exc:
        print(
            f"ERROR: cannot load private key {key_path}: {exc}. "
            "Encrypted keys are not supported by this tool.",
            file=sys.stderr,
        )
        return 1
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        print("ERROR: --key is not an Ed25519 private key", file=sys.stderr)
        return 1

    payload = {
        "lid": args.lid,
        "mch": args.mch,
        "typ": args.typ,
        "db_uuid": args.db_uuid,
        "max_reg": args.max_reg,
        "from": args.valid_from,
        "until": args.until,  # null for perpetual, required date for subscription
        "grace": args.grace,
    }
    if args.mods:
        payload["mods"] = [m.strip() for m in args.mods.split(",")]
    # JSON contract order: lid, mch, typ, db_uuid, mods, max_reg, from, until, grace
    payload = {k: payload[k] for k in PAYLOAD_KEYS if k in payload}

    header = {"alg": "EdDSA", "typ": "SAAS-LIC", "kid": args.kid}
    header_b64 = b64url(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = b64url(json.dumps(payload, separators=(",", ":")).encode())

    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature_b64 = b64url(private_key.sign(signing_input))

    token = f"{header_b64}.{payload_b64}.{signature_b64}"
    print(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
