{
    "name": "POS License Server",
    "version": "20.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Penerbit dan Pengelola Lisensi POS (Ed25519 Token Issuer)",
    "description": """
Modul Server Penerbit Lisensi POS
=================================
Fitur:
- Manajemen Keypair Kriptografi Ed25519 (Private & Public Key).
- Penerbitan Token Lisensi Compact JWS (3-bagian) untuk klien Odoo POS.
- Kontrol role hak akses bertingkat: Viewer, Manager, dan Administrator.
- Manajemen masa aktif, tipe subscription/perpetual, kuota register, dan grace period.
- Terintegrasi penuh dengan verifier offline modul pos_saas_license.
    """,
    "author": "Vendora-Tech",
    "website": "https://github.com/nuralimsyah/odoo-20",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "data": [
        "security/saas_license_server_groups.xml",
        "security/ir.access.csv",
        "data/saas_license_server_data.xml",
        "views/saas_license_key_views.xml",
        "views/saas_license_record_views.xml",
        "views/saas_license_wizard_views.xml",
        "views/saas_license_server_menus.xml",
    ],
    "application": True,
    "installable": True,
    "module_type": "official",
}
