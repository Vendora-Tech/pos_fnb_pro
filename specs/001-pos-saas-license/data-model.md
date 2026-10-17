# Data Model Specification: `pos_saas_license`

**Feature**: `001-pos-saas-license`  
**Date**: 2026-10-06  
**Status**: Completed (Phase 1)

---

## 1. Entity: `pos.saas.license`

Model data utama yang menyimpan status lisensi aktif sistem per database tenant.

### Fields Definition

| Field Name | Type | Properties | Description |
| :--- | :--- | :--- | :--- |
| `name` | Char | Required, Default="SaaS License" | Label representasi rekaman |
| `license_id` | Char | Readonly, Index | ID lisensi unik dari SaaS Provider (misal: `LIC-2026-001`) |
| `company_id` | Many2one | `res.company`, Required, Default=current | Entitas tenant pemilik lisensi (dari `pos_saas_core`) |
| `tenant_uuid` | Char | Related='company_id.tenant_uuid', Readonly | UUID unik tenant yang terikat dengan lisensi |
| `merchant_name` | Char | Readonly | Nama penyewa/merchant yang tertera pada lisensi |
| `license_type` | Selection | Required, `[('subscription', 'Subscription'), ('perpetual', 'Perpetual (Beli Putus)')]` | Jenis model lisensi |
| `database_uuid` | Char | Readonly | Database UUID Odoo yang terikat |
| `raw_token` | Text | Required | String token mentah (Base64/JWT) yang dimasukkan pengguna |
| `valid_from` | Date | Readonly | Tanggal awal mulai berlaku |
| `valid_until` | Date | Readonly | Tanggal jatuh tempo kedaluwarsa (False/Null untuk perpetual) |
| `grace_period_days` | Integer | Default=7 | Jumlah hari masa tenggang toleransi |
| `max_pos_registers` | Integer | Default=1 | Kuota jumlah `pos.config` berbeda dengan sesi belum `closed` |
| `allowed_modules` | Char | Readonly | Isi `mods` dari payload, dipisah koma. Hanya informasi, belum dipakai untuk gating |
| `key_id` | Char | Readonly | `kid` dari header token |
| `state_message` | Char | Computed | Penjelasan status untuk UI (alasan `invalid`, sisa hari, dsb.) |
| `state` | Selection | Default='invalid', `[('active', 'Active'), ('warning', 'Expiring Soon'), ('grace', 'Grace Period'), ('expired', 'Expired'), ('invalid', 'Invalid Token')]` | Status siklus hidup lisensi |
| `days_remaining` | Integer | Computed | Sisa hari aktif sebelum jatuh tempo |
| `last_verified_at` | Datetime | Readonly | Timestamp verifikasi kriptografis terakhir |
| `last_seen_timestamp` | Datetime | Stored | Waktu server terbesar yang pernah terlihat saat buka sesi, sync order, atau cron (deteksi clock rollback, toleransi 1 jam) |

> Semua kolom turunan token (`license_id` s.d. `max_pos_registers`, `state`) adalah cache tampilan. Keputusan izin selalu memakai hasil verifikasi ulang `raw_token` (FR-013).

### Aturan Perhitungan Status

`today` = tanggal lokal zona waktu company (fallback `Asia/Jakarta`). `days_left = until - today`.

| Kondisi | State |
| :--- | :--- |
| Token kosong, signature gagal, skema tidak valid, `kid` tidak dikenal, `db_uuid` tidak cocok, atau `from > today` | `invalid` |
| `typ = perpetual` | `active` |
| `days_left > 14` | `active` |
| `0 <= days_left <= 14` | `warning` |
| `-grace <= days_left < 0` | `grace` |
| `days_left < -grace` | `expired` |

Contoh dengan `grace = 7`: H-15 `active`, H-14 s.d. H0 `warning`, H+1 s.d. H+7 `grace`, H+8 `expired`.

### State Machine Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Invalid : Modul Terpasang Tanpa Token
    Invalid --> Active : Input Valid Token (H > 14 atau perpetual)
    Invalid --> Warning : Input Valid Token (0 <= H <= 14)
    Active --> Warning : H <= 14 hari sebelum valid_until
    Warning --> Grace : valid_until < Hari Ini <= valid_until + grace
    Grace --> Expired : Lewat valid_until + grace
    Expired --> Active : Input Token Baru Perpanjangan
    Active --> Invalid : Tanda Tangan Gagal / Tamper / db_uuid Tidak Cocok
```

---

## 2. Entity: `pos.saas.license.log`

Model audit trail untuk mencatat seluruh riwayat aktivitas, verifikasi, dan insiden keamanan terkait lisensi.

### Fields Definition

| Field Name | Type | Properties | Description |
| :--- | :--- | :--- | :--- |
| `license_id` | Many2one | `pos.saas.license`, Ondelete='cascade' | Relasi ke entitas lisensi |
| `event_type` | Selection | Required, `[('installed', 'Token Installed'), ('verified', 'Signature Verified'), ('warning', 'Warning Triggered'), ('grace_entered', 'Grace Period Entered'), ('expired', 'License Expired'), ('blocked', 'Session Open Blocked'), ('clock_tamper', 'Clock Rollback Detected'), ('invalid_token', 'Invalid Signature')]` | Kategori kejadian |
| `event_date` | Datetime | Default=now, Index | Waktu kejadian |
| `user_id` | Many2one | `res.users` | User yang memicu aksi |
| `details` | Text | Readonly | Catatan teknis & pesan error |

---

## 3. Odoo 20 Model Extensions: `pos.config` & `pos.session`

### 3.1. `pos.config` (Intersepsi Pembukaan UI Kasir)
* **Override Method `open_ui()`**:
  - Memanggil `self.env['pos.saas.license'].verify_active_session()`.
  - Jika lisensi `expired` atau `invalid`, melempar `UserError` informatif yang mencegah kasir membuka UI.

### 3.2. `pos.session` (Kontrol Kuota & Passing Data ke OWL)
* **Override Method `create(vals_list)`**:
  - Memeriksa lisensi dan kuota: jumlah `pos.config` berbeda dengan sesi `state != 'closed'` (termasuk config yang akan dibuka) tidak boleh melebihi `max_pos_registers`.
* **Override Method `open_frontend_cb()`**:
  - Memastikan sesi kasir yang di-resume memvalidasi lisensi terkini.
* **Fields untuk OWL UI**:

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `license_state` | Selection | Computed dari `pos.saas.license.state` |
| `license_days_left` | Integer | Sisa hari aktif |
| `license_banner_msg` | Char | Teks pesan banner yang ditampilkan di layar kasir |

> Mekanisme pengiriman field ini ke frontend POS (loader data POS Odoo 20) wajib diverifikasi langsung ke source `point_of_sale` Odoo 20 sebelum implementasi. API `_pos_ui_models_to_load` / `_loader_params_*` adalah API versi lama.

### 3.3. `pos.order` (Read-Only setelah Expired)
* Override method sinkronisasi order dari UI (nama method diverifikasi di source Odoo 20) untuk menolak order baru saat lisensi `expired` atau `invalid`, serta memperbarui `last_seen_timestamp`.

---

## 4. Odoo 20 SQL Constraints & Indexing

Sesuai standar modern Odoo 19+ (`models.Constraint` dan `models.Index` dideklarasikan sebagai atribut class, menggantikan `_sql_constraints`). Sintaks final diverifikasi terhadap source Odoo 20:

```python
# models/pos_saas_license.py
_check_grace_period_positive = models.Constraint(
    "CHECK(grace_period_days >= 0)",
    "Grace period days must be non-negative.",
)
_check_max_pos_registers_positive = models.Constraint(
    "CHECK(max_pos_registers >= 1)",
    "Maximum POS registers quota must be at least 1.",
)
_license_state_idx = models.Index("(license_id, state)")
```
