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
Gunakan algoritma **Ed25519 (EdDSA)**. Public Key di-encode ke Base64 dan disimpan di kode modul (`models/license_verifier.py`) dalam bentuk dict `{kid: public_key_b64}` agar kunci bisa dirotasi. Private Key hanya disimpan di generator (`scripts/license_tools/`) di luar repository. Test membuat keypair sendiri saat runtime dan mem-patch daftar public key.

---

## 2. Token Encoding & Payload Specification

### Format:
Standard Compact JSON Web Signature (JWS) format: `header.payload.signature`
* **Header**: `{"alg": "EdDSA", "typ": "SAAS-LIC", "kid": "k2026a"}`. Token ditolak bila `alg` bukan `EdDSA` atau `kid` tidak dikenal.
* **Encoding**: Setiap bagian base64url tanpa padding. Verifier menambahkan padding sebelum decode.
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
* **Signature**: Ed25519 signature atas byte ASCII `Base64Url(Header) + "." + Base64Url(Payload)`.
* **Validasi Skema**: Payload divalidasi manual sesuai `contracts/license-token-schema.json` (field wajib, tipe, enum `typ`, `max_reg >= 1`, `grace >= 0`, tolak field di luar skema). `until` wajib berupa tanggal untuk `subscription` dan `null` untuk `perpetual`. Tidak menambah dependency `jsonschema`.

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
* Field ini harus ikut dimuat oleh loader data POS saat booting kasir. Catatan 2026-10-16: `_pos_ui_models_to_load` dan `_loader_params_pos_session` adalah API loader versi lama (Odoo 16). Odoo 17+ memakai mekanisme `_load_pos_data*`. Nama method yang tepat wajib diverifikasi di source `point_of_sale` Odoo 20 sebelum implementasi.

### 3.3. Read-Only Setelah Expired
* Guard utama ada di server: method sinkronisasi order dari UI di `pos.order` (nama method diverifikasi di source Odoo 20) menolak order baru saat lisensi `expired`/`invalid`.
* Frontend menonaktifkan tombol Payment sebagai pelengkap UX, bukan sebagai proteksi.

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
* Interval: Setiap 24 jam (sekali sehari pukul 00:05 UTC). Cron hanya memperbarui cache dan log; pengecekan saat buka sesi tetap menghitung ulang status secara langsung sehingga tidak bergantung pada cron.
* Tugas:
  1. Menghitung ulang sisa hari masa aktif (`days_left`).
  2. Transisi status otomatis: `active` $\rightarrow$ `warning` (H-14) $\rightarrow$ `grace` (H+1) $\rightarrow$ `expired` (H+grace+1), dengan tanggal dihitung di zona waktu company (fallback `Asia/Jakarta`). Setiap perubahan status dicatat ke log.
  3. Memperbarui `last_seen_timestamp`.
  4. **Optional Heartbeat Hook**: Jika parameter sistem `saas.license.server_url` dikonfigurasi, cron dapat mengirimkan HTTPS ping status ke server pusat secara *non-blocking*. Jika URL tidak diisi atau server pusat offline/unreachable, cron tetap berhasil dan sistem mengandalkan validasi offline lokal tanpa error.

---

## 6. Hasil Verifikasi Source Odoo 20 (T007, 16-10-2026)

Sumber: `github.com/odoo/odoo` branch `20.0` (default branch, sama dengan image `odoo:20` di docker-compose). Container tidak tersedia di mesin dev, jadi verifikasi dilakukan langsung terhadap source GitHub, bukan isi image.

### 6.1. Pembukaan sesi (`pos.config`, `pos_session`)

- `pos.config.open_ui(self)` — `addons/point_of_sale/models/pos_config.py:1028`. Isi: `ensure_one()`, cek permission test environment, `if not self.current_session_id: _check_before_creating_new_session()`, `_validate_fields`, `_check_company_has_fiscal_country()`, lalu `return self._action_to_open_ui()` (baris 1048). `_action_to_open_ui()` (baris 978) membuat sesi baru bila belum ada, lalu mengembalikan action URL `/pos/ui/<id>`.
- `pos.config.close_ui(self)` (baris 1064) = `return self.open_ui()` (perilaku buka ulang UI, bukan penutupan sesi).
- Penutupan sesi dari UI memakai `pos.session.close_session_from_ui(self, payment_method_closing={})` (`pos_session.py:479`) dan tidak melewati `open_ui`, sehingga guard di `open_ui` tidak menghalangi kasir menutup sesi yang sudah berjalan.
- `pos.session.create(self, vals_list)` — `pos_session.py:388`: loop `vals` untuk `config_id` lalu `create`. Titik guard: sebelum blok `super().create()`.
- `pos.session.open_frontend_cb(self)` — `pos_session.py:661`: `return self.config_id.open_ui()`. Karena memanggil `open_ui`, guard di `open_ui` sudah mencakup jalur ini.

### 6.2. Loader data POS ke frontend

- `pos.session._load_pos_data_fields(self, config)` — `pos_session.py:183`, mengembalikan daftar nama field: `['id', 'name', 'user_id', 'config_id', 'start_at', 'stop_at', 'payment_method_ids', 'state', 'access_token']`.
- `pos.load.mixin._load_pos_data_read()` (`models/pos_load_mixin.py:18,28`) membaca persis field dari daftar tersebut → field compute non-stored cukup didaftarkan di daftar ini agar ikut terkirim.
- `load_data()` selalu memuat record `pos.session` dan `pos.config` lewat `_load_pos_metadata` (`pos_session.py:244-245`) meski keduanya tidak ada di daftar `_load_pos_data_models` (baris 164).
- Di frontend, record sesi diakses lewat plugin: `this.data.models["pos.session"].get(odoo.pos_session_id)` (contoh di `app/plugins/access_right_plugin.js`).

### 6.3. Sinkronisasi order dari kasir

- `pos.order.sync_from_ui(self, orders)` — `pos_order.py:879`. Titik guard read-only.
- `pos.order.remove_from_ui(self, server_ids)` — `pos_order.py:1115`, tanpa guard (hapus order offline tidak relevan untuk lisensi).

### 6.4. Sintaks Constraint & Index

- `odoo/models/__init__.py` melakukan re-export: `from odoo.orm.table_objects import Constraint, Index, UniqueIndex` → boleh ditulis sebagai atribut class: `models.Constraint("CHECK(x >= 1)", "pesan")`, `models.Index("(a, b)")`, `models.UniqueIndex(...)`.
- `odoo/orm/table_objects.py`: `Constraint.__init__(definition, message='')` (definisi SQL pola `CHECK (...)`, `UNIQUE (...)`, `FOREIGN KEY ...`), `Index.__init__(definition)` (contoh `(group_id, active) WHERE active IS TRUE`, `USING btree (...)`). Keduanya punya `__set_name__`, nama objek jadi `{model._table}_{nama_atribut}`.
- Atribut dikumpulkan saat setup model lewat `_table_object_definitions` → `_table_objects` (`odoo/orm/model_classes.py:488-494`).
- Deklarasi lama `_sql_constraints` tidak lagi dikumpulkan (di `odoo/orm/models.py` hanya ada metode internal `_add_sql_constraints`).

### 6.5. Frontend OWL (banner & tombol Payment)

- Navbar: template `point_of_sale.Navbar` di `addons/point_of_sale/static/src/app/components/navbar/navbar.xml` (60 baris, satu root `div.pos-topheader`), komponen `export class Navbar extends Component` di `navbar.js:20`. Patch memakai `patch(Navbar.prototype, {...})` dari `@web/core/patch` + template inherit pada `point_of_sale.Navbar`.
- Tombol Payment: `static/src/app/screens/product_screen/action_pad/action_pad.xml` baris 29: `<button ... class="pay pay-order-button button btn btn-primary ...">` dengan `t-att-disabled="!this.pos.accessRight.disableClickPayment"`.
- Getter `disableClickPayment` ada di `static/src/app/plugins/access_right_plugin.js` (`PosAccessRightPlugin`) dan bernilai default `true` (artinya tombol aktif; nama getter terbalik). Untuk menonaktifkan Payment saat expired, gunakan template inherit pada tombol `button.pay.pay-order-button` (`position="attributes"`) daripada membalik nilai getter.
- Bundle aset kasir: `point_of_sale._assets_pos` (didefinisikan di `addons/point_of_sale/__manifest__.py:183`, di-include oleh `point_of_sale.assets_prod` baris 254).

### 6.6. Settings POS

- View induk: record `point_of_sale.res_config_settings_view_form` (`res_config_settings_views.xml:3`, priority 95, inherit `base.res_config_settings_view_form`).
- Struktur: `<app name="point_of_sale" groups="point_of_sale.group_pos_manager">` → `div.pos_res_config_container` → `div.pos_config_content` → `div[@invisible="not pos_config_id"]` → berisi `<block>` (`restaurant_section`, `pos_payment_section`, ... `pos_preparation_section`).
- XPath untuk block lisensi: `//app[@name='point_of_sale']//div[@invisible="not pos_config_id"]` dengan `position="inside"` (block tambahan ikut tersembunyi saat tidak ada POS dipilih). Catatan: `<app>` ber-`groups="group_pos_manager"`, sehingga hanya manajer POS yang melihat halaman ini.

### 6.7. Terjemahan

- Konvensi utama Odoo 20: `from odoo import ... _, api, fields, models, tools` lalu `_("...")` (di `pos_config.py` dipakai 19 kali vs `self.env._` 2 kali).
- `self.env._("...")` tersedia dan sadar konteks bahasa — dipakai untuk pesan yang dikirim dari model saat bahasa penerima relevan.
- XML view: teks alami langsung di atribut `string`. JS/template OWL: atribut `.translate` (contoh: `placeholder.translate="Search products..."`).
