# Implementation Plan: POS SaaS Licensing Engine (`pos_saas_license`)

**Branch**: `001-pos-saas-license` | **Date**: 2026-10-06 | **Spec**: [spec.md](file:///home/nuralimsyah/Projects/ngulik_odoo/odoo-20/specs/001-pos-saas-license/spec.md)

**Input**: Feature specification from `/specs/001-pos-saas-license/spec.md`

---

## Summary

Membangun modul inti fondasi perizinan **`pos_saas_license`** di folder `addons/` untuk platform SaaS POS Odoo 20. Modul ini memverifikasi token bertanda tangan kriptografis asimetris (**Ed25519**) secara offline, mendukung dual model penjualan (*Subscription* berbatas waktu dengan 7 hari masa toleransi dan *Perpetual* seumur hidup terikat `database.uuid`), mencegat pembukaan sesi kasir jika expired, serta menampilkan banner notifikasi bertingkat pada antarmuka kasir (OWL UI).

---

## Technical Context

**Language/Version**: Python 3.11+ / JavaScript (ECMAScript 2022+ OWL Framework Odoo 20)  
**Primary Dependencies**: `odoo:20`, `point_of_sale`, Python `cryptography.hazmat.primitives.asymmetric.ed25519`  
**Storage**: PostgreSQL 18 (`pos_saas_license`, `pos_saas_license_log`)  
**Testing**: Odoo Test Framework (`odoo.tests.common.TransactionCase`)  
**Target Platform**: Linux Docker Container (`odoo:20` & `postgres:18`)  
**Project Type**: Odoo 20 Modular Addon (`addons/pos_saas_license`)  
**Performance Goals**: Waktu verifikasi tanda tangan token < 1 milidetik, latensi buka sesi kasir < 50 milidetik  
**Constraints**: 100% Offline-capable, zero file upload multipart handling, database instance binding  
**Scale/Scope**: 1 Modul Mandiri (Universal Core Foundation)  

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Prinsip Konstitusi | Status | Catatan Evaluasi Desain |
| :--- | :---: | :--- |
| **I. Library-First (Modular Architecture)** | **PASS** | Modul mandiri di `addons/pos_saas_license`, tidak mengotori modul POS core Odoo. |
| **II. Clean Data Contracts** | **PASS** | Skema payload JSON terdefinisi ketat di `contracts/license-token-schema.json`. |
| **III. Test-First / Automated Testing** | **PASS** | Dilengkapi TransactionCase test (`test_license_crypto.py`, `test_pos_session_license.py`). |
| **IV. Observability & Audit Trail** | **PASS** | Setiap event verifikasi dan insiden keamanan tercatat di `pos.saas.license.log`. |
| **V. Simplicity & YAGNI** | **PASS** | Memilih Ed25519 (string ringkas) dan input copy-paste (tanpa file upload kompleks). |

---

## Project Structure

### Documentation (this feature)

```text
specs/001-pos-saas-license/
├── spec.md              # Feature specification & user stories
├── plan.md              # Implementation plan (this file)
├── research.md          # Cryptography, Odoo 20 hooks, and OWL UI research
├── data-model.md        # Models, fields, constraints, lifecycle state machine
├── quickstart.md        # CLI generator and verification testing guide
├── contracts/
│   └── license-token-schema.json # JSON Schema payload contract
└── checklists/
    └── requirements.md  # 16/16 Quality checklist validation
```

### Source Code Layout (`addons/pos_saas_license/`)

```text
addons/pos_saas_license/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── license_verifier.py       # Ed25519 cryptography signature verification logic
│   ├── pos_saas_license.py       # Core singleton model for tenant license status
│   ├── pos_saas_license_log.py   # Security audit trail log model
│   ├── pos_config.py             # Override open_ui to block cashier UI if expired
│   ├── pos_session.py            # Override create & open_frontend_cb, load data to UI
│   └── res_config_settings.py   # POS settings configuration view glue
├── views/
│   ├── pos_saas_license_views.xml   # Standalone license dashboard view
│   ├── pos_session_views.xml        # Session warning indicators
│   └── res_config_settings_views.xml # POS Configuration tab for license token
├── data/
│   ├── ir_cron_data.xml          # Daily 00:05 UTC expiration check & optional heartbeat
│   └── pos_saas_license_data.xml # Initial default singleton record
├── security/
│   ├── ir.model.access.csv       # ACL permissions for managers and cashiers
│   └── pos_saas_license_security.xml # Security group definitions
├── static/
│   └── src/
│       └── app/
│           └── license_banner/
│               ├── license_banner.js   # OWL Component for cashier warning banner
│               ├── license_banner.xml  # OWL template for Yellow/Orange banner
│               └── license_banner.scss # Custom warning/grace alert styles
└── tests/
    ├── __init__.py
    ├── test_license_crypto.py       # Unit tests for signature verification
    └── test_pos_session_license.py  # Tests for open session blocking & grace period
```

---

## Planned Implementation Phases

1. **Phase 1: Backend Foundation & Kriptografi Ed25519**
   - Implementasi `license_verifier.py` (decode JWS, verifikasi public key, verifikasi `database.uuid`).
   - Implementasi model `pos.saas.license` dan `pos.saas.license.log`.
2. **Phase 2: Intersepsi Kasir & Backend Settings**
   - Override `pos.config` (`open_ui`) dan `pos.session` (`create`, `open_frontend_cb`).
   - Implementasi form *POS $\rightarrow$ Settings* untuk input copy-paste token.
   - Setup cron job `ir.cron` untuk pengecekan status harian (dengan optional non-blocking heartbeat).
3. **Phase 3: Frontend OWL Kasir (POS Banner)**
   - Buat OWL component `LicenseBanner` yang di-inject ke navbar POS.
   - Hubungkan data reaktif status lisensi dari store sesi POS.
4. **Phase 4: Unit Testing & Validasi**
   - Menulis test suite TransactionCase: pengujian token valid, token expired, token rusak, dan kuota register.
