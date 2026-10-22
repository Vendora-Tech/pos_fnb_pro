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
        "data/ir_cron_data.xml",
        "views/pos_saas_license_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_saas_license/static/src/app/license_banner/license_banner.scss",
            "pos_saas_license/static/src/app/license_banner/license_banner.js",
            "pos_saas_license/static/src/app/license_banner/license_banner.xml",
            "pos_saas_license/static/src/app/license_banner/pos_patch.js",
            "pos_saas_license/static/src/app/license_banner/pos_patch.xml",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
