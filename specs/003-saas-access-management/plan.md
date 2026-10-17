# Implementation Plan: SaaS Access Management & Anti-Fraud (`saas_access_management`)

**Branch**: `003-saas-access-management` | **Date**: 2026-10-16 | **Spec**: [spec.md](file:///home/nuralimsyah/Projects/ngulik_odoo/odoo-20/specs/003-saas-access-management/spec.md)

---

## Summary

Membangun modul fondasi `saas_access_management` di `addons/saas_access_management/` untuk Odoo 20. Modul ini menyediakan kontrol hak akses visual untuk memproteksi data bisnis sensitif (sembunyikan harga modal `standard_price`), blokir aksi berbahaya (hapus order `pos.order`), matikan fitur ekspor Excel/CSV, dan sembunyikan menu teknis/Apps bagi staf kasir.

---

## Technical Context

- **Platform**: Odoo 20.0 LTS (Python 3.12+ / OWL Web Client)
- **Primary Dependencies**: `base`, `web`
- **Downstream Modules**: `pos_saas_core`, `point_of_sale`
- **Storage**: PostgreSQL (`saas_access_rule`, `saas_access_rule_model`, `saas_access_rule_field`)
- **Testing**: `odoo.tests.common.TransactionCase` (`addons/saas_access_management/tests/test_access_management.py`)
- **Location**: `addons/saas_access_management/`
- **Principles**: YAGNI, shortest clean diff, zero monkey-patching di luar standard ORM hooks (`get_view`, `_filter_visible_menus`, `session_info`).

---

## Constitution & Principle Check

| Prinsip | Status | Catatan Evaluasi |
| :--- | :---: | :--- |
| **I. Library-First & Modular** | **PASS** | Terisolasi di `addons/saas_access_management`, siap dipasang mandiri di atas `base` & `web`. |
| **II. Clean Data Contracts** | **PASS** | Kontrak skema terdefinisi di `contracts/access-policy-schema.json`. |
| **III. Simplicity & YAGNI** | **PASS** | Menggunakan 3 tabel relasi murni tanpa XML builder rumit. |
| **IV. Performance** | **PASS** | Evaluasi policy di-cache pada user session dengan query terindeks; overhead < 15ms. |

---

## Project Structure (`addons/saas_access_management/`)

```text
addons/saas_access_management/
├── __init__.py
├── __manifest__.py
├── security/
│   └── ir.model.access.csv      # Hak akses admin untuk mengelola policy
├── models/
│   ├── __init__.py
│   ├── saas_access_rule.py       # Model induk policy & evaluasi restriction
│   ├── saas_access_rule_model.py # Aturan level model (hide create, edit, delete)
│   ├── saas_access_rule_field.py # Aturan level field (invisible, readonly)
│   ├── base_patch.py             # ORM hook get_view untuk modifikasi arch XML
│   ├── ir_ui_menu.py             # Filter menu navigasi
│   └── ir_http.py                # Injeksi disable_export ke session_info
├── views/
│   ├── saas_access_rule_views.xml # Form & list view konfigurasi visual policy
│   └── menu_views.xml            # Menu di bawah Settings / Technical
├── data/
│   └── default_roles_data.xml    # Preset role bawaan (Kasir, Supervisor)
└── tests/
    ├── __init__.py
    └── test_access_management.py # Unit test evaluasi view, no export, dan menu
```

---

## Implementation Phases

1. **Phase 1: Backend Foundation & Data Models**
   - Buat `__manifest__.py`, `__init__.py`, dan hak akses `ir.model.access.csv`.
   - Implementasikan model `saas.access.rule`, `saas.access.rule.model`, dan `saas.access.rule.field`.
2. **Phase 2: ORM Hooks & View Manipulation**
   - Implementasikan hook `get_view` di `models/base_patch.py` untuk injeksi dinamis `create="false"`, `edit="false"`, `delete="false"`, dan `invisible="1"`.
   - Implementasikan penyaringan menu di `models/ir_ui_menu.py`.
3. **Phase 3: Anti-Export & Web Client Integration**
   - Implementasikan flag `disable_export` di `models/ir_http.py`.
   - Blokir endpoint controller ekspor untuk user terlarang.
4. **Phase 4: Views & Preset Data**
   - Rancang antarmuka form policy yang intuitif dengan inline one2many fields.
   - Sediakan preset dasar (Kasir) di `data/default_roles_data.xml`.
5. **Phase 5: Automated Unit Testing**
   - Buat skenario pengujian `TransactionCase` untuk memvalidasi:
     - Field `standard_price` menjadi invisible untuk kasir.
     - Aksi delete pada `pos.order` tersembunyi.
     - Menu yang dibatasi tidak muncul.
     - Superuser tetap bebas mengakses seluruh elemen.
