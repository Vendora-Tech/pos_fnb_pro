# Feature Specification: SaaS Access Management & Anti-Fraud (`saas_access_management`)

**Feature Branch**: `003-saas-access-management`  
**Created**: 2026-10-16  
**Status**: Draft  
**Target Module**: `addons/saas_access_management`  

**Input**: Spesifikasi modul visual access management dan anti-fraud untuk ekosistem SaaS POS Odoo 20. Modul ini menyederhanakan kontrol hak akses rumit Odoo menjadi antarmuka visual sederhana bagi pemilik toko, melindungi infrastruktur SaaS (Provider Shield), serta mengamankan bisnis merchant dari kecurangan internal (Merchant Fraud Shield).

---

## Clarifications

### Session 2026-10-16
- Q: Bagaimana arsitektur teknis pembatasan hak akses di Odoo 20 diterapkan tanpa merusak view inheritance standar?  
  A: Menggunakan hook ORM pada `get_views` / `get_view` di backend untuk memodifikasi view architecture secara dinamis berdasarkan user/role yang sedang login (injeksi atribut `invisible="1"`, `readonly="1"`, penghapusan tombol aksi, dan penonaktifan aksi ekspor di controller/RPC).
- Q: Apakah modul ini menggantikan sistem security group dan ACL bawaan Odoo?  
  A: Tidak. Modul ini bekerja di atas layer security Odoo sebagai *visual presentation and action filter*, sehingga hak akses database tetap aman dan pemilik toko tidak perlu memahami teknis XML atau Record Rules.
- Q: Siapa yang kebal terhadap aturan pembatasan ini?  
  A: User System Administrator (ID 1 / Superuser / SaaS Master Admin) otomatis bebas dari pembatasan untuk kebutuhan pemeliharaan teknis sistem.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Proteksi Data Sensitif & Anti-Pencurian Data (Priority: P1)

Sebagai Pemilik Toko (Store Owner), saya ingin menyembunyikan harga modal barang (`standard_price`) dan mematikan fitur ekspor data ke Excel/CSV bagi user Kasir, sehingga karyawan tidak mengetahui margin laba toko dan tidak dapat mencuri basis data pelanggan.

**Why this priority**: Kebocoran margin harga modal dan pencurian basis data pelanggan/omset adalah risiko finansial paling nyata bagi pemilik bisnis retail dan F&B.

**Independent Test**: Login sebagai user kasir, buka daftar produk, periksa bahwa kolom harga modal tidak terlihat. Buka menu pelanggan, pilih baris data, lalu periksa bahwa opsi "Export" pada menu Action telah dinonaktifkan.

**Acceptance Scenarios**:
1. **Given** User kasir memiliki role "Kasir" dengan pembatasan field `standard_price` aktif, **When** Kasir membuka form atau list produk, **Then** Kolom harga modal tidak ditampilkan pada layar.
2. **Given** User kasir memiliki aturan "No Export" aktif, **When** Kasir memilih satu atau banyak record pada tampilan list, **Then** Menu Action tidak menyediakan pilihan "Export" ke Excel/CSV.

---

### User Story 2 - Proteksi Tombol Berbahaya & Navigasi Menu (Priority: P2)

Sebagai Pemilik Toko dan Penyedia SaaS, saya ingin memblokir tombol Delete pada dokumen pesanan POS (`pos.order`) dan menyembunyikan menu teknis/Apps dari staf kasir, sehingga transaksi tidak bisa dihapus diam-diam dan sistem tidak dirusak.

**Why this priority**: Menghilangkan celah manipulasi transaksi (*void liar/hapus nota*) dan mencegah merchant mengutak-atik modul teknis backend.

**Independent Test**: Login sebagai kasir, buka riwayat order kasir, pastikan tombol Delete tidak muncul. Periksa navigasi navbar atas, pastikan menu *Apps*, *Settings*, dan *Technical* tersembunyi sepenuhnya.

**Acceptance Scenarios**:
1. **Given** Role Kasir memiliki pembatasan tombol Delete pada model `pos.order`, **When** Kasir membuka detail transaksi penjualan, **Then** Tombol Delete / Action Delete tidak tersedia.
2. **Given** Role Kasir dibatasi dari menu backend sensitif, **When** Kasir membuka halaman utama backend, **Then** Hanya menu yang diizinkan (Point of Sale) yang terlihat.

---

### User Story 3 - Visual Role Policy Management (Priority: P3)

Sebagai Administrator Toko, saya ingin mengatur kebijakan hak akses melalui antarmuka visual yang mudah dipahami (memilih checkbox sembunyikan menu, tombol, atau field), tanpa harus menulis kode XML atau membuat Record Rules teknis.

**Why this priority**: Menjaga kemudahan operasional (*UX friendly*) bagi merchant non-teknis.

**Independent Test**: Buka menu *Settings $\rightarrow$ Access Management*, buat aturan baru bernama "Staff Kasir", pilih model `product.template`, pilih field `standard_price` menjadi invisible, simpan dan terapkan ke user kasir.

**Acceptance Scenarios**:
1. **Given** Admin membuat aturan pembatasan baru pada model tertentu, **When** Kebijakan disimpan dan diaktifkan, **Then** Aturan langsung berlaku seketika saat user terkait me-refresh peramban.

---

## Edge Cases

- **Akses Langsung via URL / Action Window**: Jika user mencoba mengetikkan URL action langsung (contoh: action Apps), controller backend menolak request dan mengembalikan pesan akses ditolak (*Access Denied*).
- **Multiple Role Conflict**: Jika satu user terdaftar dalam dua role yang berbeda, sistem menerapkan prinsip hak akses paling ketat (*strictest restriction wins*).
- **Superuser Override**: User dengan hak akses Superuser / Admin Master selalu dapat mengakses seluruh menu dan tombol tanpa terkena filter policy.

---

## Key Entities & Data Dictionary

1. **`saas.access.rule` (Model Utama)**:
   - `name` (Char, Required): Nama kebijakan hak akses (contoh: "Kasir Standar", "Supervisor").
   - `user_ids` (Many2many `res.users`): Daftar pengguna yang terkena kebijakan.
   - `active` (Boolean): Status aktif aturan.
   - `disable_export` (Boolean): Nonaktifkan ekspor data Excel/CSV untuk user terkait.
   - `hide_menu_ids` (Many2many `ir.ui.menu`): Daftar menu yang disembunyikan.
   - `model_access_ids` (One2many `saas.access.rule.model`): Rincian pembatasan per model.

2. **`saas.access.rule.model` (Pembatasan Per Model)**:
   - `rule_id` (Many2one `saas.access.rule`, Cascade): Relasi ke aturan induk.
   - `model_id` (Many2one `ir.model`, Required): Model target (contoh: `pos.order`, `product.template`).
   - `hide_create` (Boolean): Sembunyikan tombol Buat (*Create*).
   - `hide_edit` (Boolean): Sembunyikan tombol Ubah (*Edit*).
   - `hide_delete` (Boolean): Sembunyikan tombol Hapus (*Delete*).
   - `field_restriction_ids` (One2many `saas.access.rule.field`): Rincian pembatasan field.

3. **`saas.access.rule.field` (Pembatasan Per Field)**:
   - `model_access_id` (Many2one `saas.access.rule.model`, Cascade): Relasi ke model rule.
   - `field_id` (Many2one `ir.model.fields`, Required): Field target (contoh: `standard_price`).
   - `is_invisible` (Boolean): Sembunyikan field dari tampilan.
   - `is_readonly` (Boolean): Kunci field menjadi hanya baca.

---

## Success Criteria

- **SC-001**: Fitur No Export 100% memblokir tombol ekspor data pada seluruh list view bagi user yang dibatasi.
- **SC-002**: Field sensitif (`standard_price`) 100% tidak ter-render di antarmuka kasir.
- **SC-003**: Overhead pemrosesan view pada hook `get_views` < 15ms per request.
- **SC-004**: Zero dependensi eksternal, kompatibel penuh dengan Odoo 20 LTS.
