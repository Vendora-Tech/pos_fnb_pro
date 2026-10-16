#!/usr/bin/env python3
"""Generate an Ed25519 keypair for the POS SaaS license issuer.

The private key (PEM) is written to a local path ONLY. It must never be
committed to the repository (see .gitignore: *.pem, scripts/license_tools/keys/).
The public key printed here gets pasted into PUBLIC_KEYS in
addons/pos_saas_license/models/license_verifier.py.

Usage:
    python scripts/license_tools/generate_keypair.py --kid dev2026 --out ./keys/dev2026.pem
"""

import argparse
import base64
import pathlib
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--kid", required=True, help="Key id, stored in the token header (e.g. dev2026)"
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Path to write the private key PEM (must be git-ignored)",
    )
    args = parser.parse_args()

    out_path = pathlib.Path(args.out).expanduser()
    if out_path.exists():
        print(
            f"ERROR: {out_path} already exists. Refusing to overwrite an existing private key.",
            file=sys.stderr,
        )
        return 1
    out_path.parent.mkdir(parents=True, exist_ok=True)

    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    out_path.write_bytes(private_pem)
    try:
        out_path.chmod(0o600)
    except OSError:
        pass  # e.g. on Windows; the .gitignore rule is the real protection

    public_b64 = base64.b64encode(
        public_key.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    ).decode()

    print("PRIVATE KEY written to (do NOT commit this):")
    print(f"  {out_path}")
    print()
    print(
        "Paste this into PUBLIC_KEYS in addons/pos_saas_license/models/license_verifier.py:"
    )
    print(f'    "{args.kid}": "{public_b64}",')
    return 0


if __name__ == "__main__":
    sys.exit(main())
