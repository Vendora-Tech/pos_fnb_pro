# Tasks: SaaS Access Management & Anti-Fraud (`saas_access_management`)

**Feature**: `003-saas-access-management`  
**Plan**: [plan.md](plan.md)  
**Spec**: [spec.md](spec.md)  
**Status**: Ready for Implementation  

---

## Phase 1: Setup & Scaffolding

- [ ] [T001] [P1] [Setup] Buat struktur folder modul `addons/saas_access_management/` (models, views, security, data, tests)
- [ ] [T002] [P1] [Setup] Inisialisasi berkas `addons/saas_access_management/__init__.py` dan `addons/saas_access_management/__manifest__.py` dengan dependensi `base` dan `web`
- [ ] [T003] [P1] [Setup] Konfigurasi hak akses admin di `addons/saas_access_management/security/ir.model.access.csv` untuk model `saas.access.rule`, `saas.access.rule.model`, dan `saas.access.rule.field`

---

## Phase 2: Foundational Data Models

- [ ] [T004] [P1] [Foundation] Implementasikan model induk `saas.access.rule` di `addons/saas_access_management/models/saas_access_rule.py` (`name`, `active`, `user_ids`, `disable_export`, `hide_menu_ids`)
- [ ] [T005] [P1] [Foundation] Implementasikan model pembatasan model `saas.access.rule.model` di `addons/saas_access_management/models/saas_access_rule_model.py` (`hide_create`, `hide_edit`, `hide_delete`)
- [ ] [T006] [P1] [Foundation] Implementasikan model pembatasan field `saas.access.rule.field` di `addons/saas_access_management/models/saas_access_rule_field.py` (`is_invisible`, `is_readonly`)
- [ ] [T007] [P1] [Foundation] Registrasikan seluruh model baru di `addons/saas_access_management/models/__init__.py`

---

## Phase 3: User Story 1 - Proteksi Data Sensitif & Anti-Pencurian Data (Priority: P1)

*Goal: Menyembunyikan harga modal barang (`standard_price`) dan mematikan fitur ekspor data ke Excel/CSV bagi user kasir.*  
*Independent Test: Login sebagai user kasir, periksa kolom `standard_price` di form & list produk tersembunyi; periksa menu Action tidak memuat opsi "Export".*

- [ ] [T008] [P1] [US1] Buat ORM hook `models.BaseModel.get_view` di `addons/saas_access_management/models/base_patch.py` untuk menginjeksi atribut `invisible="1"` pada field yang dibatasi
- [ ] [T009] [P1] [US1] Buat hook web client di `addons/saas_access_management/models/ir_http.py` untuk menginjeksi flag `disable_export` ke dalam `session_info`
- [ ] [T010] [P1] [US1] Buat unit test di `addons/saas_access_management/tests/test_field_and_export_restriction.py` untuk memvalidasi proteksi harga modal dan pemblokiran ekspor

---

## Phase 4: User Story 2 - Proteksi Tombol Berbahaya & Navigasi Menu (Priority: P2)

*Goal: Memblokir tombol Delete pada dokumen pesanan POS (`pos.order`) dan menyembunyikan menu teknis/Apps dari kasir.*  
*Independent Test: Login sebagai kasir, buka pesanan POS, pastikan tombol Delete tidak muncul; pastikan menu Apps dan Settings tersembunyi dari navbar.*

- [ ] [T011] [P2] [US2] Tambahkan logika manipulasi atribut arch `create="false"`, `edit="false"`, `delete="false"` pada hook `get_view` di `addons/saas_access_management/models/base_patch.py`
- [ ] [T012] [P2] [US2] Buat hook penyaringan menu di `addons/saas_access_management/models/ir_ui_menu.py` pada metode `_filter_visible_menus`
- [ ] [T013] [P2] [US2] Buat unit test di `addons/saas_access_management/tests/test_button_and_menu_restriction.py` untuk memvalidasi pemblokiran tombol delete order dan menu filtering

---

## Phase 5: User Story 3 - Visual Role Policy Management (Priority: P3)

*Goal: Menyediakan form visual intuitif bagi pemilik toko untuk mengonfigurasi aturan hak akses tanpa menulis kode XML.*  
*Independent Test: Buat rule baru via form antarmuka, pilih user dan checklist restriction, simpan dan verifikasi langsung aktif.*

- [ ] [T014] [P3] [US3] Buat view form dan list untuk `saas.access.rule` di `addons/saas_access_management/views/saas_access_rule_views.xml` dengan inline editor untuk model dan field restrictions
- [ ] [T015] [P3] [US3] Buat menu navigasi di bawah *Settings $\rightarrow$ Access Management* di `addons/saas_access_management/views/menu_views.xml`
- [ ] [T016] [P3] [US3] Buat data preset role standar bawaan (*Kasir Standar*) di `addons/saas_access_management/data/default_roles_data.xml`

---

## Phase 6: Polish & Integration Verification

- [ ] [T017] [P1] [Polish] Validasi bypass superuser: pastikan System Administrator (UID 1) kebal terhadap seluruh pembatasan policy
- [ ] [T018] [P1] [Polish] Jalankan test suite terpadu via command line runner: `odoo --test-tags=saas_access_management`
- [ ] [T019] [P1] [Polish] Uji kompatibilitas dan instalasi modul di container Docker `odoo20-pos-odoo20-1` pada database `pos`

---

## Dependency & Implementation Strategy

```
Phase 1 (Scaffolding)
       ↓
Phase 2 (Data Models & Security)
       ↓
Phase 3 (US1: Sensitive Fields & No Export) ← MVP Target
       ↓
Phase 4 (US2: Dangerous Buttons & Hidden Menus)
       ↓
Phase 5 (US3: Visual UI & Preset Roles)
       ↓
Phase 6 (Polish & Verification)
```
