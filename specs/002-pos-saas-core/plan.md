# Implementation Plan: POS SaaS Core Foundation (`pos_saas_core`)

**Branch**: `002-pos-saas-core` | **Date**: 2026-10-12 (Updated: 2026-10-16) | **Status**: Completed & Verified | **Spec**: [spec.md](file:///home/nuralimsyah/Projects/ngulik_odoo/odoo-20/specs/002-pos-saas-core/spec.md)

---

## Summary

Membangun modul fondasi `pos_saas_core` di `addons/pos_saas_core/` untuk Odoo 20. Modul ini menyediakan identitas tenant multi-outlet, standarisasi branding struk thermal (logo company native, header, footer), pengaturan terpadu di POS Settings dan Form Companies, serta patch template struk POS.

---

## Technical Context

- **Platform**: Odoo 20.0 LTS (Python 3.12+ / JavaScript OWL)
- **Primary Dependencies**: `base`, `point_of_sale`
- **Downstream Modules**: `pos_saas_license`, `saas_access_management`
- **Storage**: PostgreSQL (`res_company`, `pos_config`)
- **Testing**: `odoo.tests.common.TransactionCase` (`addons/pos_saas_core/tests/test_pos_saas_core.py`)
- **Location**: `addons/pos_saas_core/`
- **Principles**: YAGNI, lazy, zero external python libraries, shortest clean diff.

---

## Constitution & Principle Check

| Prinsip | Status | Catatan Evaluasi |
| :--- | :---: | :--- |
| **I. Library-First & Modular** | **PASS** | Terisolasi di `addons/pos_saas_core`, mewarisi `point_of_sale` secara standar. |
| **II. Clean Data Contracts** | **PASS** | Skema receipt branding terdefinisi di `contracts/tenant-receipt-schema.json`. |
| **III. Simplicity & YAGNI** | **PASS** | Meng-extend `res.company` dan `pos.config` tanpa tabel redundan; memakai native `company.logo`. |
| **IV. Performance & Offline** | **PASS** | Data branding termuat via `_load_pos_data_read` dan `_load_pos_data_fields`, 100% offline-ready. |

---

## Project Structure (`addons/pos_saas_core/`)

```text
addons/pos_saas_core/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── pos_config.py            # Ekstensi outlet_code, tenant_uuid, hook _load_pos_data_read
│   ├── res_company.py           # Ekstensi tenant_uuid, receipt_header, receipt_footer, hook _load_pos_data_fields
│   └── res_config_settings.py   # Glue view POS Settings
├── views/
│   ├── pos_config_views.xml     # Form POS config (outlet code & overrides)
│   ├── res_company_views.xml    # Tab Point of Sale di Form Companies
│   ├── res_config_settings_views.xml # Section Store Identity & Receipt Branding di POS Settings
│   └── pos_order_receipt_views.xml   # QWeb template hook struk
└── tests/
    ├── __init__.py
    └── test_pos_saas_core.py    # Unit tests (4 passed)
```

---

## Implementation Status

1. **Phase 1: Backend Foundation & Data Models** - [x] **DONE**
   - File `__manifest__.py` dan `__init__.py` terkonfigurasi.
   - Ekstensi model `res.company`, `pos.config`, dan `res_config_settings` aktif.
2. **Phase 2: Views & Konfigurasi** - [x] **DONE**
   - View form POS config, tab Companies, dan blok POS Settings aktif dengan layout rapi.
   - Seluruh teks "SaaS" dihilangkan dari antarmuka visual pengguna.
3. **Phase 3: Frontend POS Receipt Integration** - [x] **DONE**
   - Hook ORM Odoo 20 `_load_pos_data_read` dan `_load_pos_data_fields` menangani fallback header/footer.
   - Template struk QWeb terpasang.
4. **Phase 4: Unit Testing & Verification** - [x] **DONE**
   - Seluruh 4 pengujian unit `test_pos_saas_core.py` lulus 100% tanpa error.
