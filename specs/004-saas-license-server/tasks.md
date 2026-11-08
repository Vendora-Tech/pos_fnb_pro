# Tasks: SaaS License Server & Token Issuer (`saas_license_server`)

**Feature Branch**: `004-saas-license-server`  
**Target Module**: `addons/saas_license_server`  
**Status**: Completed  

---

## Phase 1: Arsitektur & Scaffolding
- [x] **T001**: Buat direktori modul dan manifest Odoo 20 (`addons/saas_license_server/__manifest__.py`, `__init__.py`).
- [x] **T002**: Definisikan grup hak akses `res.groups.privilege` untuk Viewer, Manager, dan Admin (`security/saas_license_server_groups.xml`).
- [x] **T003**: Konfigurasikan tabel perizinan CRUD model (`security/ir.access.csv`).
- [x] **T004**: Siapkan sequence otomatis ID lisensi `LIC-YYYY-XXXX` (`data/saas_license_server_data.xml`).

## Phase 2: Engine Kriptografi & Data Model
- [x] **T005**: Implementasi model `saas.license.key` dengan generator Ed25519 PKCS8 PEM & Public Key Base64 (`models/saas_license_key.py`).
- [x] **T006**: Implementasi model `saas.license.record` dengan penyusun payload kanonikal dan engine penandatanganan Compact JWS 3-bagian (`models/saas_license_record.py`).
- [x] **T007**: Implementasi validasi ketat tanggal dan kuota register via `@api.constrains`.
- [x] **T008**: Implementasi transient model `saas.license.wizard` untuk penerbitan instan (`wizard/saas_license_wizard.py`).

## Phase 3: Antarmuka Pengguna & Navigasi
- [x] **T009**: Buat tampilan Form, List, dan Search untuk `saas.license.key` (`views/saas_license_key_views.xml`).
- [x] **T010**: Buat tampilan Form, List, dan Search untuk `saas.license.record` lengkap dengan widget CopyClipboardText (`views/saas_license_record_views.xml`).
- [x] **T011**: Buat tampilan dialog form untuk `saas.license.wizard` (`views/saas_license_wizard_views.xml`).
- [x] **T012**: Susun menu utama *SaaS Licenses* dan sub-menunya (`views/saas_license_server_menus.xml`).

## Phase 4: Pengujian & Validasi
- [x] **T013**: Buat unit test komprehensif (`tests/test_license_server.py`) mencakup:
  - Pembuatan pasangan kunci Ed25519 otomatis.
  - Penerbitan token Subscription dan validasi silang dengan `pos_saas_license.license_verifier`.
  - Penerbitan token Perpetual tanpa `until`.
  - Penegakan batasan data (`ValidationError`).
  - Eksekusi alur penerbitan via Wizard.
  - Penegakan izin hak akses (Manager vs Viewer).
- [x] **T014**: Jalankan test runner di dalam kontainer Odoo 20 dan verifikasi 100% lulus (6/6 tests passed).
