# Feature Specification: SaaS License Server & Ed25519 Token Issuer (`saas_license_server`)

**Feature Branch**: `004-saas-license-server`  
**Created**: 2026-10-22  
**Status**: Completed & Verified  
**Target Module**: `addons/saas_license_server`  

**Input**: Spesifikasi modul server penerbit lisensi terpusat (License Issuer & Key Management) untuk ekosistem SaaS Odoo 20 POS. Modul ini berjalan di instance Odoo pusat (HQ/Billing Portal) dan menggantikan ketergantungan pada script CLI lokal (`issue_token.py` dan `generate_keypair.py`), menyediakan antarmuka visual terproteksi untuk tim billing/admin dalam mengelola keypair Ed25519, menerbitkan token Compact JWS (3 bagian), mengontrol kuota register, masa aktif, serta hak akses role bertingkat.

---

## Clarifications

### Session 2026-10-22
- Q: Apakah modul `saas_license_server` dipasang di database merchant (tenant)?  
  A: **Tidak.** Modul ini hanya dipasang di instance Odoo pusat (HQ / Billing Portal). Sisi merchant hanya memasang `pos_saas_license` (verifier) dan hanya menyimpan Public Key agar merchant tidak dapat memalsukan token lisensi sendiri.
- Q: Bagaimana format token yang dihasilkan?  
  A: Menggunakan format Compact JWS tiga bagian base64url tanpa padding (`header.payload.signature`) dengan algoritma `EdDSA` (Ed25519) yang 100% kompatibel dengan verifier offline `pos_saas_license`.
- Q: Bagaimana pembagian role user di Odoo Pusat?  
  A: Terdapat 3 role berbasis `res.groups.privilege` Odoo 20:
  1. **Viewer**: Read-only daftar lisensi dan masa aktif.
  2. **Manager**: Dapat membuat data tenant, mengatur kuota, dan menandatangani token lisensi.
  3. **Administrator**: Mengelola Private Key Ed25519 (membuat keypair baru, mengganti kunci penandatanganan).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Penerbitan Token Lisensi Tenant (Priority: P1)

Sebagai Staf Billing / Manager SaaS, saya ingin menerbitkan token lisensi untuk merchant baru dengan memasukkan data toko, database UUID, tipe lisensi (Subscription atau Perpetual), kuota register kasir, dan masa berlaku, sehingga merchant menerima token lisensi siap pakai untuk mengaktifkan sistem POS mereka.

**Why this priority**: Penerbitan token adalah fungsi inti bisnis SaaS untuk monetisasi dan aktivasi merchant.

**Independent Test**: Buat record lisensi baru di menu *SaaS Licenses $\rightarrow$ Tenant Licenses*, masukkan database UUID valid, atur tipe Subscription (1 tahun) dan kuota 2 kasir, klik *Issue & Sign Token*. Pastikan token JWS 3-bagian terbentuk dan dapat disalin via clipboard.

**Acceptance Scenarios**:
1. **Given** User memiliki role Manager, **When** Mengisi form tenant dan mengklik "Issue & Sign Token", **Then** Sistem menghasilkan string token JWS valid dan status lisensi berubah menjadi "Active / Issued".
2. **Given** Token diterbitkan untuk target `database.uuid`, **When** Token diverifikasi menggunakan library `license_verifier`, **Then** Token lolos verifikasi kriptografi Ed25519 dengan status `active`.

---

### User Story 2 - Manajemen Keypair & Isolasi Private Key (Priority: P2)

Sebagai Administrator SaaS, saya ingin membuat pasangan kunci kriptografi Ed25519 secara otomatis melalui antarmuka web dan memastikan Private Key hanya dapat diakses oleh Administrator, sedangkan Public Key dapat disalin untuk didaftarkan ke verifier POS.

**Why this priority**: Private Key adalah rahasia terpenting sistem SaaS; kebocoran private key memungkinkan pihak luar memalsukan lisensi tanpa batas.

**Independent Test**: Buka menu *SaaS Licenses $\rightarrow$ Configuration $\rightarrow$ Signing Keys*, klik "Generate Keypair (Auto)", pastikan string Private Key PEM terbentuk dan tersembunyi dari user non-admin.

**Acceptance Scenarios**:
1. **Given** User adalah Administrator, **When** Mengklik tombol "Generate Keypair (Auto)", **Then** Sistem membuat kunci privat Ed25519 format PKCS8 PEM dan public key Base64 mentah 32-byte.
2. **Given** User login dengan role Manager atau Viewer, **When** Membuka detail Signing Key, **Then** Tab Private Key tidak ditampilkan dan akses read level ORM ditolak.

---

### User Story 3 - Wizard Penerbitan Cepat Instan (Priority: P3)

Sebagai Staf Operasional, saya ingin menerbitkan lisensi baru melalui dialog modal cepat (*Quick Issue Wizard*) tanpa harus berpindah-pindah form, sehingga proses aktivasi merchant saat pendaftaran dapat selesai dalam hitungan detik.

**Why this priority**: Meningkatkan kecepatan operasional tim onboarding merchant.

**Independent Test**: Klik menu *SaaS Licenses $\rightarrow$ Quick Issue Wizard*, isi nama merchant dan database UUID, klik tombol "Issue & Generate Token". Pastikan sistem langsung membuka form detail lisensi dengan token yang sudah aktif dan siap disalin.

**Acceptance Scenarios**:
1. **Given** Staf membuka Quick Issue Wizard, **When** Menekan tombol "Issue & Generate Token", **Then** Record lisensi dibuat, ditandatangani, dan layar dialihkan ke halaman lisensi aktif.

---

### User Story 4 - Penegakan Aturan Kontrak Lisensi (Priority: P4)

Sebagai Penyedia SaaS, saya ingin sistem memvalidasi integritas data lisensi sebelum penandatanganan (misalnya: lisensi Subscription wajib memiliki tanggal berakhir, Perpetual dilarang memiliki tanggal berakhir, dan kuota register minimal 1).

**Why this priority**: Menghindari penerbitan token rusak yang akan ditolak oleh verifier merchant di lapangan.

**Independent Test**: Buat lisensi tipe Subscription tanpa mengisi field Valid Until, klik simpan, pastikan sistem melempar `ValidationError`.

**Acceptance Scenarios**:
1. **Given** Lisensi bertipe Subscription, **When** Valid Until kosong atau lebih kecil dari Valid From, **Then** Sistem menolak penyimpanan data dengan pesan kesalahan yang jelas.
2. **Given** Lisensi bertipe Perpetual, **When** Valid Until diisi tanggal, **Then** Sistem menolak penyimpanan data.

---

## Edge Cases

- **Signing Key Tidak Ditemukan / Tidak Memiliki Private Key**: Sistem memvalidasi keberadaan private key sebelum proses penandatanganan dan melempar `UserError` jika kunci kosong.
- **Sudo Execution pada Penandatanganan**: User role Manager diizinkan menerbitkan token via method backend dengan elevasi hak akses signing, tanpa memberikan akses baca langsung terhadap isi teks private key.
- **Multiple Default Keys**: Sistem secara otomatis menonaktifkan flag `is_default` pada kunci lama jika ada kunci baru yang ditandai sebagai default.

---

## Functional Requirements

- **FR-001**: Model `saas.license.key` untuk menyimpan identifier kunci (`key_id`), nama, private key PEM, public key Base64, status aktif, dan default signing key.
- **FR-002**: Method `action_generate_keypair` pada `saas.license.key` yang menghasilkan pasangan kunci Ed25519 secara deterministik via pustaka murni `cryptography`.
- **FR-003**: Model `saas.license.record` untuk master data lisensi tenant (`lid`, `mch`, `typ`, `db_uuid`, `tenant_uuid`, `max_reg`, `from`, `until`, `grace`, `mods`).
- **FR-004**: Method `action_issue_token` pada `saas.license.record` yang merangkai header JWS, payload terurut, menandatangani string dengan Ed25519, dan menyimpan token 3 bagian.
- **FR-005**: Transient model `saas.license.wizard` untuk antarmuka penerbitan instan satu langkah.
- **FR-006**: Grup hak akses Odoo 20 `res.groups.privilege` untuk Viewer, Manager, dan Administrator beserta matriks `ir.access.csv`.
- **FR-007**: Widget salin ke clipboard pada tampilan form untuk kemudahan transfer token.
- **FR-008**: Sequence otomatis untuk ID lisensi tenant (`LIC-YYYY-XXXX`).

---

## Non-Functional Requirements

- **NFR-001 (Kriptografi Murni)**: Menggunakan algoritma Ed25519 standar (RFC 8032) tanpa modifikasi.
- **NFR-002 (Kompatibilitas Odoo 20)**: Tidak bergantung pada modul POS di sisi server pusat; hanya bergantung pada modul inti `base` dan `web`.
- **NFR-003 (Keamanan Rahasia)**: Private Key dilindungi di level view XML dan level ORM field access control.
