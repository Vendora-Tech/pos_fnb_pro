# Feature Specification: POS SaaS Core Foundation (`pos_saas_core`)

**Feature Branch**: `002-pos-saas-core`  
**Created**: 2026-10-12 (Updated: 2026-10-16)  
**Status**: Implemented & Verified  
**Target Module**: `addons/pos_saas_core`  

**Input**: Spesifikasi modul fondasi `pos_saas_core` untuk identitas tenant SaaS, standarisasi branding struk POS (logo thermal monokrom via native company logo, header alamat outlet, footer promosi/sosmed), konfigurasi terpadu di POS Settings dan form Companies, serta dukungan multi-outlet/cabang per tenant tanpa label visual "SaaS".

---

## Clarifications

### Session 2026-10-12 & 2026-10-16
- Q: Di mana metadata global tenant disimpan dan bagaimana hubungannya dengan multi-outlet?  
  A: Metadata tenant global disimpan dengan meng-extend model native `res.company` (`tenant_uuid`, default `receipt_header`, `receipt_footer`) dan ditampilkan di tab "Point of Sale" pada form Companies. Setiap outlet/register kasir (`pos.config`) dapat mewarisi nilai global atau melakukan override spesifik cabang (`outlet_code`, `receipt_header_override`, `receipt_footer_override`).
- Q: Bagaimana logo struk ditangani?  
  A: Menggunakan field native `company.logo` bawaan Odoo 20 yang otomatis menjadi fallback bagi `pos.config.logo`, menghindari redundansi binary field terpisah.
- Q: Bagaimana teks visual pada antarmuka pengguna?  
  A: Seluruh string "SaaS" dihilangkan dari antarmuka pengguna (view forms, settings block, page tabs) agar tetap bersih, profesional, dan netral bagi merchant ("Store Identity & Receipt Branding", "Outlet Settings", "Point of Sale").
- Q: Apakah modul ini memperkenalkan dependensi eksternal?  
  A: Tidak. 100% mengandalkan framework bawaan Odoo 20 (`base`, `point_of_sale`) dan native Python standard library.

---

## User Scenarios & Testing

### User Story 1 - Identitas Bisnis & Multi-Outlet Konfigurasi (Priority: P1)

Sebagai Pemilik Toko (Tenant), saya ingin mengonfigurasi identitas bisnis saya sekali di tingkat Company dan memberikan kode cabang/outlet khusus pada tiap register kasir, sehingga seluruh laporan dan struk transaksi teridentifikasi sesuai outlet asalnya.

**Independent Test**: Mengubah identitas perusahaan dan kode outlet pada konfigurasi POS, membuka sesi kasir, lalu memverifikasi data outlet terbaca secara akurat pada order dan backend.

**Acceptance Scenarios**:
1. **Given** Pengaturan Company memiliki `tenant_uuid` dan nama merchant terisi, **When** Konfigurasi POS baru dibuat, **Then** `outlet_code` dapat ditentukan secara unik dan mereferensikan Company tersebut.
2. **Given** POS Config memiliki `outlet_code` (misal `ALSUT-01`), **When** Transaksi penjualan dibuat dari POS tersebut, **Then** Nomor referensi dan data order mengikat kode outlet tersebut.

---

### User Story 2 - Standarisasi Branding Struk Thermal ESC/POS (Priority: P2)

Sebagai Kasir dan Pemilik Toko, saya ingin struk belanja yang dicetak menampilkan logo usaha yang tajam, nama dan alamat cabang yang jelas, serta ucapan terima kasih/sosial media di bagian bawah struk.

**Acceptance Scenarios**:
1. **Given** Logo diatur pada Company Settings, **When** Kasir menyelesaikan pesanan dan mencetak struk, **Then** Template struk otomatis memuat logo dari company.
2. **Given** Outlet memiliki `receipt_header_override` (misal: "Cabang Alam Sutera, Ruko Broadway No. 12"), **When** Struk dicetak di outlet tersebut, **Then** Header kustom outlet yang muncul menggantikan header default company.
3. **Given** Outlet tidak mengisi header override, **When** Struk dicetak, **Then** Template struk otomatis menggunakan default header dari `res.company`.

---

### User Story 3 - Integrasi Satu Pintu di POS Settings & Form Company (Priority: P3)

Sebagai Administrator Toko, saya ingin mengatur identitas tenant dan preferensi struk langsung melalui menu *Point of Sale $\rightarrow$ Settings* atau tab *Point of Sale* pada *Settings $\rightarrow$ Companies*.

**Acceptance Scenarios**:
1. **Given** Admin membuka POS Settings atau form Companies, **When** Mengedit field branding struk dan menekan "Save", **Then** Perubahan langsung tersimpan ke `res.company` dan sinkron secara real-time.

---

## Key Entities & Data Dictionary

1. **`res.company` (Extended)**:
   - `tenant_uuid` (Char, Readonly): UUID unik tenant.
   - `receipt_header` (Text): Header default struk perusahaan.
   - `receipt_footer` (Text): Footer default struk perusahaan.

2. **`pos.config` (Extended)**:
   - `tenant_uuid` (Char, Related): UUID tenant dari company.
   - `outlet_code` (Char): Kode unik cabang (misal `SMG-K1`, `BDG-02`).
   - `use_custom_receipt` (Boolean): Flag untuk mengaktifkan override spesifik cabang.
   - `receipt_header_override` (Text): Header khusus outlet.
   - `receipt_footer_override` (Text): Footer khusus outlet.

---

## Success Criteria

- **SC-001**: Data branding (logo, header, footer) sukses dimuat ke frontend kasir via hook `_load_pos_data_read` dan `_load_pos_data_fields`.
- **SC-002**: 100% struk kasir yang dicetak menampilkan identitas outlet dan branding secara konsisten baik online maupun offline.
- **SC-003**: Zero dependency eksternal, kompatibel penuh dengan Odoo 20 LTS.
