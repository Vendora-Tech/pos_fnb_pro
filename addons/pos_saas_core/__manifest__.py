{
    "name": "POS SaaS Core Foundation",
    "summary": "Universal SaaS tenant identity, multi-outlet configuration, and receipt branding for Odoo 20 POS.",
    "version": "20.0.1.0.0",
    "category": "Point of Sale",
    "author": "Vendora-Tech",
    "license": "LGPL-3",
    "depends": [
        "base",
        "point_of_sale",
    ],
    "data": [
        "views/res_company_views.xml",
        "views/pos_config_views.xml",
        "views/res_config_settings_views.xml",
        "views/pos_order_receipt_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
