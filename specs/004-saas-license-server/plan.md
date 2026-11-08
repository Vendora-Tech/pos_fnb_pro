# Implementation Plan: SaaS License Server & Token Issuer (`saas_license_server`)

**Feature Branch**: `004-saas-license-server`  
**Created**: 2026-10-22  
**Status**: Completed  
**Target Module**: `addons/saas_license_server`  

---

## 1. Arsitektur Teknis & Modul

Modul ini adalah aplikasi mandiri di instance Odoo pusat (HQ / Billing Portal). Modul tidak bergantung pada modul POS (`point_of_sale`) agar dapat dipasang di instance Odoo server yang ramping.

### Diagram Ketergantungan Modul
```
[ base ]
   ↓
[ web ]
   ↓
[ saas_license_server ] (Pusat / HQ)
   ↓ (menerbitkan token JWS via Ed25519)
[ pos_saas_license ]    (Cabang / Tenant POS, memverifikasi via Public Key)
```

---

## 2. Struktur Direktori File

```
addons/saas_license_server/
├── __init__.py
├── __manifest__.py
├── data/
│   └── saas_license_server_data.xml        # Sequence LIC-YYYY-XXXX
├── models/
│   ├── __init__.py
│   ├── saas_license_key.py                 # Keypair management & Ed25519 generator
│   └── saas_license_record.py              # Tenant license & JWS token issuer
├── wizard/
│   ├── __init__.py
│   └── saas_license_wizard.py              # Modal dialog quick-issue
├── security/
│   ├── saas_license_server_groups.xml      # Viewer, Manager, Admin groups (Odoo 20)
│   └── ir.access.csv                       # CRUD ACL matrix
├── views/
│   ├── saas_license_key_views.xml          # List & form views for signing keys
│   ├── saas_license_record_views.xml       # List, form, search views for licenses
│   ├── saas_license_wizard_views.xml       # Wizard modal form
│   └── saas_license_server_menus.xml       # Menu root & submenus
└── tests/
    ├── __init__.py
    └── test_license_server.py              # Comprehensive unit tests
```

---

## 3. Komponen Kriptografi & Kompatibilitas Token

### Header Format
```json
{
  "alg": "EdDSA",
  "typ": "SAAS-LIC",
  "kid": "<key_id>"
}
```

### Payload Format (Kanonikal / Sesuai Skema Kontrak)
```json
{
  "lid": "LIC-2026-0001",
  "mch": "Nama Merchant",
  "typ": "subscription",
  "db_uuid": "00000000-0000-0000-0000-000000000000",
  "tenant_uuid": "11111111-1111-1111-1111-111111111111",
  "max_reg": 2,
  "from": "2026-01-01",
  "until": "2027-01-01",
  "grace": 7
}
```

### Penandatanganan
1. `header_b64 = base64url(json.dumps(header))`
2. `payload_b64 = base64url(json.dumps(payload))`
3. `signing_input = f"{header_b64}.{payload_b64}".encode("ascii")`
4. `signature_bytes = ed25519_private_key.sign(signing_input)`
5. `signature_b64 = base64url(signature_bytes)`
6. `token = f"{signing_input.decode('ascii')}.{signature_b64}"`

---

## 4. Matriks Hak Akses (Odoo 20 Privileges)

- **`group_saas_license_viewer`**:
  - Akses Read pada `saas.license.record` dan `saas.license.key`.
  - Tidak memiliki akses write/create/delete.
  - Tab Private Key disembunyikan.
- **`group_saas_license_manager`**:
  - Akses Create, Read, Write pada `saas.license.record`.
  - Akses Read pada `saas.license.key` (menandatangani token menggunakan `sudo()` yang terisolasi).
  - Akses penuh ke `saas.license.wizard`.
- **`group_saas_license_admin`**:
  - Akses penuh (CRUD) pada `saas.license.key` dan `saas.license.record`.
  - Dapat melihat dan memperbarui Private Key PEM.
  - Dapat men-generate pasangan kunci Ed25519 baru.
