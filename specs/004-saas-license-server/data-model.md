# Data Model: SaaS License Server (`saas_license_server`)

**Feature Branch**: `004-saas-license-server`  
**Created**: 2026-10-22  
**Status**: Completed  

---

## 1. Model: `saas.license.key`

Menyimpan data pasangan kunci penandatanganan kriptografi Ed25519.

| Field Name | Type | Properties | Description |
|:---|:---|:---|:---|
| `name` | Char | Required | Nama pengenal kunci (contoh: "Production 2026 Key") |
| `key_id` | Char | Required, Index | Key ID (KID) unik untuk header JWS (contoh: "prod2026") |
| `private_key_pem` | Text | Groups: Admin | Private key format PKCS8 PEM terenkripsi/terisolasi |
| `public_key_b64` | Char | Readonly | Public key 32-byte mentah dalam format Base64 |
| `is_default` | Boolean | Default: False | Penanda kunci default aktif untuk penandatanganan baru |
| `active` | Boolean | Default: True | Flag pengarsipan record |
| `license_ids` | One2many | -> `saas.license.record` | Riwayat lisensi yang ditandatangani menggunakan kunci ini |
| `license_count` | Integer | Compute | Jumlah lisensi yang menggunakan kunci ini |

### Constraint & Aturan Bisnis
- `key_id` wajib unik di seluruh database (`models.Constraint('UNIQUE(key_id)', ...)`).
- Jika sebuah kunci ditandai sebagai `is_default=True`, kunci lain yang aktif otomatis diubah menjadi `is_default=False`.
- Method `action_generate_keypair()` membuat keypair baru menggunakan pustaka Python `cryptography.hazmat.primitives.asymmetric.ed25519`.

---

## 2. Model: `saas.license.record`

Master data lisensi merchant/tenant dan penampung token JWS.

| Field Name | Type | Properties | Description |
|:---|:---|:---|:---|
| `license_id` | Char | Required, Readonly, Index | Nomor lisensi berurutan (`LIC-YYYY-XXXX`) |
| `merchant_name` | Char | Required, Index | Nama toko atau badan usaha merchant |
| `license_type` | Selection | Required, Default: `subscription` | Nilai: `subscription` atau `perpetual` |
| `db_uuid` | Char | Required, Index | UUID database Odoo target merchant (`database.uuid`) |
| `tenant_uuid` | Char | Optional | UUID tenant POS core (`company.tenant_uuid`) |
| `max_registers` | Integer | Required, Default: 1 | Batas kuota sesi kasir aktif bersamaan |
| `valid_from` | Date | Required, Default: Today | Tanggal mulai berlakunya lisensi |
| `valid_until` | Date | Optional (Wajib jika Subscription) | Tanggal akhir masa aktif lisensi |
| `grace_period` | Integer | Required, Default: 7 | Masa tenggang kasir setelah expired (hari) |
| `allowed_modules` | Char | Optional | Daftar modul yang diizinkan (format koma) |
| `key_id` | Many2one | -> `saas.license.key`, Required | Kunci Ed25519 yang digunakan untuk menandatangani |
| `state` | Selection | Default: `draft` | Status workflow: `draft`, `issued`, `suspended`, `revoked` |
| `raw_token` | Text | Readonly | String token Compact JWS 3-bagian hasil penandatanganan |
| `issued_at` | Datetime | Readonly | Waktu penandatanganan token dilakukan |
| `issued_by` | Many2one | -> `res.users`, Readonly | User yang mengeksekusi penandatanganan token |
| `notes` | Text | Optional | Catatan internal tim sales/billing |

### Validasi Model (`@api.constrains`)
- `max_registers` harus bernilai lebih dari 0.
- `grace_period` tidak boleh bernilai negatif.
- Pada tipe `subscription`: `valid_until` wajib diisi, dan tanggal `valid_until` harus $\ge$ `valid_from`.
- Pada tipe `perpetual`: `valid_until` harus kosong (`False`).

---

## 3. Transient Model: `saas.license.wizard`

Wizard pop-up untuk membuat lisensi baru dan langsung menghasilkan token dalam satu langkah operasional.

| Field Name | Type | Properties | Description |
|:---|:---|:---|:---|
| `merchant_name` | Char | Required | Nama merchant yang didaftarkan |
| `license_type` | Selection | Required, Default: `subscription` | `subscription` atau `perpetual` |
| `db_uuid` | Char | Required | Database UUID target |
| `tenant_uuid` | Char | Optional | Tenant UUID target |
| `max_registers` | Integer | Required, Default: 1 | Kuota kasir |
| `valid_from` | Date | Required, Default: Today | Tanggal mulai aktif |
| `duration_months` | Integer | Default: 12 | Pilihan durasi cepat (bulan) |
| `valid_until` | Date | Optional | Tanggal akhir (otomatis terhitung dari durasi) |
| `grace_period` | Integer | Required, Default: 7 | Masa tenggang (hari) |
| `key_id` | Many2one | -> `saas.license.key`, Required | Kunci penandatangan default |
| `notes` | Text | Optional | Catatan pendaftaran |

---

## 4. State Machine Workflow

```
[ Draft ] ──( action_issue_token )──> [ Issued ]
   │                                     │
   │                                     ├──( action_suspend )──> [ Suspended ]
   │                                     │                             │
   │                                     │                             └──( action_resume )──> [ Issued ]
   │                                     │
   └──( action_revoke )──────────────────┴──( action_revoke )────> [ Revoked ]
```
