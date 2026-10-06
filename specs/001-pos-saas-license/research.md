# Technical Research & Architecture: POS SaaS Licensing Engine (`pos_saas_license`)

**Feature**: `001-pos-saas-license`  
**Date**: 2026-10-06  
**Status**: Completed (Phase 0)

---

## 1. Cryptographic Signature Standard (Ed25519 vs RSA-2048)

### Research & Analysis:
* **RSA-2048**: Menghasilkan tanda tangan 256 byte dan string token panjang (~800 - 1200 karakter base64), verifikasi membutuhkan waktu ~2-3 ms.
* **Ed25519 (EdDSA)**:
  - Tanda tangan hanya **64 bytes** dan Public Key hanya **32 bytes**.
  - Total panjang string token JWT/Base64 sangat kompak (~250 - 350 karakter).
  - Waktu verifikasi **< 0.5 ms** (sangat cepat, jauh di bawah batas target SC-002: 50 ms).
  - Menggunakan modul standar Python `cryptography.hazmat.primitives.asymmetric.ed25519` yang selalu tersedia di Python 3.11/3.12 pada image Docker `odoo:20`.

### Decision:
Gunakan algoritma **Ed25519 (EdDSA)**. Public Key di-encode ke Base64 dan disimpan di kode modul (`models/license_verifier.py`), sedangkan Private Key hanya disimpan di generator SaaS Controller.

---

## 2. Token Encoding & Payload Specification

### Format:
Standard Compact JSON Web Signature (JWS) format: `header.payload.signature`
* **Header**: `{"alg": "EdDSA", "typ": "SAAS-LIC"}`
* **Payload**:
  ```json
  {
    "lid": "LIC-2026-FNB-0089",
    "mch": "Kopi Senja Nusantara",
    "typ": "subscription",
    "db_uuid": "7a3b4c12-3456-7890-abcd-ef1234567890",
    "mods": ["pos_base", "pos_id_qris", "pos_id_thermal"],
    "max_reg": 3,
    "from": "2026-01-01",
    "until": "2026-12-31",
    "grace": 7
  }
  ```
* **Signature**: Ed25519 signature di-hash dari `Base64Url(Header) + "." + Base64Url(Payload)`.

---

## 3. Odoo 20 Model Extension & Interception Points

### 3.1. Interception Sesi Kasir (`pos.config` & `pos.session`)
Berdasarkan verifikasi langsung terhadap source code Odoo 20 (`odoo/addons/point_of_sale/models`):
* `action_pos_session_open` tidak ada di Odoo 20.
* Gerbang utama pembukaan sesi kasir di Odoo 20 adalah:
  1. `pos.config.open_ui()`: Pintu masuk utama yang dipanggil saat kasir menekan tombol "New Session", "Continue Selling", atau membuka UI kasir dari dashboard POS.
  2. `pos.session.create()`: Pintu masuk pembuatan record sesi di database (tempat validasi kuota `max_pos_registers` dan status lisensi).
  3. `pos.session.open_frontend_cb()`: Pintu masuk saat me-resume sesi yang sudah ada (memanggil `self.config_id.open_ui()`).

**Metode Intervensi Terverifikasi**:
1. Override `pos.config.open_ui()`: Sebelum membuka UI, panggil `self.env['pos.saas.license'].verify_active_session()`. Jika lisensi berstatus `expired` (lewat masa grace) atau `invalid`, lemparkan `UserError` informatif yang mencegah UI terbuka.
2. Override `pos.session.create()`: Sebelum membuat record sesi baru di database, validasi kuota register aktif agar tidak melebihi `max_pos_registers`.
3. Override `pos.session.open_frontend_cb()`: Memastikan sesi yang dilanjutkan memvalidasi status lisensi terkini.

### 3.2. Passing Data Lisensi ke OWL POS Frontend
Di Odoo 20, data POS di-load ke browser melalui model loader:
* Model `pos.session` menambahkan computed/stored field:
  - `license_state`: `'active'` | `'warning'` | `'grace'` | `'expired'` | `'invalid'`
  - `license_days_left`: Integer (sisa hari sebelum expired)
  - `license_message`: String penjelasan banner
* Field ini didaftarkan ke `_pos_ui_models_to_load` atau di-inject via `_loader_params_pos_session` sehingga store POS frontend langsung memuat status lisensi saat booting kasir.

---

## 4. Komponen Frontend OWL (POS Warning Banner)

### UI Component:
* Lokasi: `static/src/app/license_banner/license_banner.js` & `license_banner.xml`.
* Mount point: Di-inject di atas area `Navbar` atau `Chrome` POS kasir.
* Reaktivitas OWL:
  - Jika `license_state === 'warning'`: Menampilkan banner **Kuning/Amber** (`bg-warning text-dark`) dengan teks: *"⚠️ Lisensi aktif tersisa X hari lagi. Segera lakukan perpanjangan."*
  - Jika `license_state === 'grace'`: Menampilkan banner **Oranye/Merah Muda** (`bg-danger text-white`) dengan teks: *"🚨 Masa aktif telah berakhir. Sistem dalam masa tenggang toleransi X hari."*
  - Jika `license_state === 'expired'`: Tombol "Payment" dan "Orderline Edit" di-disable / read-only modal.

---

## 5. Sinkronisasi & Cron Job Background

### Batasan Scope (Decoupled Central Server):
* **Central Licensing Server** (Server pusat pembuat token & pengelola perpanjangan) berada **di luar scope modul client `pos_saas_license`** dan dijadwalkan sebagai project/layanan terpisah.
* Modul client `pos_saas_license` beroperasi **100% mandiri secara offline (*offline-first*)** menggunakan tanda tangan Ed25519 dan perhitungan tanggal lokal `valid_until + grace_period_days`.

### Scheduled Action (`ir.cron`):
* Nama: `POS SaaS License: Daily Expiration Check`
* Interval: Setiap 24 jam (sekali sehari pukul 00:05 UTC).
* Tugas:
  1. Menghitung ulang sisa hari masa aktif (`days_left`).
  2. Transisi status otomatis: `active` $\rightarrow$ `warning` (H-14) $\rightarrow$ `grace` (H+1) $\rightarrow$ `expired` (H+8).
  3. **Optional Heartbeat Hook**: Jika parameter sistem `saas.license.server_url` dikonfigurasi, cron dapat mengirimkan HTTPS ping status ke server pusat secara *non-blocking*. Jika URL tidak diisi atau server pusat offline/unreachable, cron tetap berhasil dan sistem mengandalkan validasi offline lokal tanpa error.
