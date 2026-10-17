{
    "name": "Access Management",
    "summary": "All In One Access Management app for fields, models, menus, buttons, tabs, domains, and chatter",
    "version": "20.0.1.0.0",
    "category": "Administration",
    "author": "Vendora-Tech",
    "license": "LGPL-3",
    "depends": [
        "base",
        "web",
        "product",
        "point_of_sale",
    ],
    "data": [
        "security/ir.access.csv",
        "views/saas_access_rule_views.xml",
        "views/menu_views.xml",
        "views/res_users_views.xml",
        "data/default_roles_data.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
