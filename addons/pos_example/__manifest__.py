{
    "name": "POS Example (CI Dummy)",
    "summary": "Minimal CI smoke-test module. NOT for production.",
    "version": "20.0.1.0.0",
    "author": "Vendora-Tech",
    "license": "LGPL-3",
    "category": "Point of Sale",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/example_tag_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
