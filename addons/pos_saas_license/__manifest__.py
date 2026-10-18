{
    "name": "POS SaaS License",
    "summary": "Offline-first SaaS licensing engine for POS: Ed25519 token, grace period, register quota, cashier banner.",
    "version": "20.0.1.0.0",
    "author": "Vendora-Tech",
    "license": "LGPL-3",
    "category": "Point of Sale",
    "depends": [
        "point_of_sale",
        "pos_saas_core",
    ],
    "external_dependencies": {
        "python": ["cryptography"],
    },
    "data": [
        "security/ir.access.csv",
        "data/pos_saas_license_data.xml",
    ],
    "assets": {},
    "installable": True,
    "application": False,
    "auto_install": False,
}
