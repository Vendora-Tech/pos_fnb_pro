# Feature Specification: POS SaaS Licensing Engine (`pos_saas_license`)

**Feature Branch**: `001-pos-saas-license`

**Created**: 2026-10-06

**Status**: Draft

**Input**: User description: "Modul pos_saas_license dengan token ditandatangani asimetris (RSA/Ed25519), model jual langganan (valid_until, grace period 7 hari) dan beli putus (lifetime, instance binding), payload lengkap, UX kasir bertingkat, dengan batasan threat model anti-tamper realistis dan mitigasi fingerprint Docker."

## Clarifications

### Session 2026-10-06
- Q: Bagaimana metode definitif binding instance di lingkungan Docker untuk lisensi perpetual dan subscription? → A: Token ditandatangani dan memuat `database.uuid`. Untuk model langganan (subscription), validasi lokal dilengkapi mekanisme check-in / heartbeat berkala ke licensing server saat online. Untuk model beli putus (perpetual), beroperasi 100% offline dan mengandalkan `database.uuid` + cryptographic signature untuk menahan pelanggaran kasual (*casual violation defense*), selaras dengan threat model.
- Q: Bagaimana format delivery dan input token lisensi ke sistem Odoo merchant? → A: Menggunakan mekanisme copy-paste string token teks (Base64/JWT) langsung ke input field di halaman Point of Sale Settings (sederhana, tanpa penanganan file upload multipart di server).

### Session 2026-10-16
- Q: Format token yang final? → A: Compact JWS 3 bagian `header.payload.signature` (base64url tanpa padding). Header `{"alg": "EdDSA", "typ": "SAAS-LIC", "kid": "<id kunci>"}`. Signature Ed25519 atas `header_b64 + "." + payload_b64`. Modul menyimpan daftar public key per `kid` agar kunci bisa dirotasi.
- Q: Nama field payload mana yang menjadi acuan? → A: `contracts/license-token-schema.json` (`lid`, `mch`, `typ`, `db_uuid`, `mods`, `max_reg`, `from`, `until`, `grace`). Istilah `hardware_id` di dokumen lama berarti `db_uuid`.
- Q: Apakah check-in ke licensing server wajib untuk subscription? → A: Tidak. Licensing server pusat di luar scope. Modul hanya menyediakan hook heartbeat opsional dan non-blocking yang aktif bila parameter `saas.license.server_url` diisi.
- Q: Bagaimana kuota `max_reg` dihitung? → A: Jumlah `pos.config` berbeda yang memiliki sesi berstatus belum `closed`. Membuka sesi untuk register baru ditolak bila jumlah itu sudah mencapai `max_reg`. Membuat `pos.config` baru tetap diizinkan.
- Q: Apa perilaku setelah lewat grace period? → A: Pembukaan dan resume sesi diblokir. Sesi yang sudah terbuka tidak bisa menyinkronkan order baru (ditolak di server, tombol Payment di UI dinonaktifkan). Laporan dan riwayat di backend tetap bisa diakses.
- Q: Apakah `mods` dipakai untuk membatasi modul? → A: Belum. Nilainya disimpan dan ditampilkan saja.
- Q: Zona waktu acuan tanggal? → A: Tanggal hari ini dihitung dengan zona waktu company (fallback `Asia/Jakarta`). `until` bersifat inklusif (hari `until` masih `warning`/`active`).
- Q: Bagaimana deteksi clock rollback? → A: `last_seen_timestamp` diperbarui saat pembukaan sesi, sinkronisasi order, dan cron. Bila waktu server lebih mundur dari `last_seen_timestamp` lebih dari 1 jam, pembukaan sesi diblokir dan event `clock_tamper` dicatat.
- Q: Bagaimana jika `from` masih di masa depan? → A: Status `invalid` dengan pesan bahwa lisensi belum berlaku.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Validasi Lisensi Langganan & Penguncian Sesi Kasir (Priority: P1)

Sebagai Pemilik Platform SaaS POS, saya ingin sistem memverifikasi masa aktif token lisensi saat kasir hendak membuka sesi transaksi, sehingga merchant yang masa berlangganannya telah habis tidak dapat membuat transaksi baru tanpa memperpanjang langganan.

**Why this priority**: Ini adalah *core MVP value* dari sistem SaaS. Tanpa penegakan lisensi yang memblokir transaksi setelah jatuh tempo, monetisasi langganan SaaS tidak dapat berjalan.

**Independent Test**: Dapat diuji secara independen dengan menginstal modul, memasukkan token langganan bertanggal kedaluwarsa hari kemarin, lalu mencoba membuka sesi kasir (`pos.session`). Sistem harus menolak pembukaan sesi dan menampilkan pesan peringatan yang jelas.

**Acceptance Scenarios**:

1. **Given** Toko memiliki token lisensi aktif dengan `valid_until` masih di masa depan, **When** Kasir menekan tombol "Buka Sesi Kasir" (*Open Session*), **Then** Sesi kasir berhasil terbuka dan kasir dapat memproses transaksi normal.
2. **Given** Token lisensi telah melewati `valid_until` dan melewati masa toleransi (*grace period*), **When** Kasir menekan tombol "Buka Sesi Kasir", **Then** Sistem menolak pembukaan sesi dan menampilkan dialog error informatif untuk menghubungi penyedia SaaS.
3. **Given** Sistem kasir sedang tidak terhubung ke jaringan internet (*offline*), **When** Kasir membuka sesi sebelum tanggal `valid_until`, **Then** Sistem tetap mengizinkan pembukaan sesi secara mandiri (*offline-first*).

---

### User Story 2 - Lisensi Beli Putus (Perpetual) dengan Instance Binding (Priority: P2)

Sebagai Pemilik Platform SaaS, saya ingin menjual lisensi beli putus (*lifetime*) yang terikat pada identitas server/instance merchant, sehingga merchant dapat menggunakan sistem selamanya secara *offline*, namun lisensi tersebut tidak dapat disalin dan digunakan bebas di cabang/server lain.

**Why this priority**: Mendukung model bisnis kedua (*one-time purchase / perpetual*) bagi merchant yang menolak sistem sewa bulanan, sekaligus meminimalkan penyalahgunaan duplikasi sistem.

**Independent Test**: Dapat diuji secara mandiri dengan menerbitkan token berjenis `perpetual` yang mengunci `database.uuid` A. Saat sistem dijalankan pada database A, kasir aktif selamanya tanpa batas waktu. Saat token dipasang pada database dengan `database.uuid` berbeda, sistem mengunci sesi kasir.

**Acceptance Scenarios**:

1. **Given** Token lisensi bertipe `perpetual` diinput ke server dengan `db_uuid` yang cocok, **When** Kasir membuka sesi kasir kapan pun, **Then** Sistem selalu mengizinkan transaksi tanpa pernah mengalami kedaluwarsa waktu.
2. **Given** Token dipasang pada database dengan `database.uuid` yang berbeda dari `db_uuid` di token, **When** Kasir mencoba membuka sesi kasir, **Then** Sistem mendeteksi ketidakcocokan identitas instance dan memblokir sesi transaksi.

---

### User Story 3 - Notifikasi Bertingkat & Grace Period di Antarmuka Kasir (Priority: P3)

Sebagai Kasir dan Pemilik Toko, saya ingin melihat indikator sisa masa aktif lisensi secara bertahap di antarmuka kasir, serta tetap diberikan toleransi masa tenggang (*grace period*) 7 hari saat telat membayar, sehingga operasional toko tidak tiba-tiba lumpuh mendadak di tengah jam sibuk.

**Why this priority**: Menjaga retensi dan kepuasan pengguna (*merchant experience*) agar proses penagihan berjalan manusiawi tanpa mengorbankan transaksi yang sedang antre.

**Independent Test**: Dapat diuji secara visual di UI POS dengan memanipulasi tanggal sisa lisensi (H-10, H-2, H+3 masa grace), dan memverifikasi kemunculan banner warna serta status fungsionalitas tombol kasir.

**Acceptance Scenarios**:

1. **Given** Masa aktif lisensi tersisa antara 14 hari hingga 1 hari (H-14 s/d H-1), **When** Kasir berada di layar transaksi POS, **Then** Muncul banner informasi berwarna kuning lembut di bagian atas layar kasir yang mengingatkan waktu perpanjangan.
2. **Given** Tanggal `valid_until` telah terlewat namun masih dalam rentang 7 hari *grace period* (H+1 s/d H+7), **When** Kasir melakukan transaksi, **Then** Kasir tetap bisa menyelesaikan pembayaran, namun muncul banner oranye tegas bahwa lisensi dalam masa tenggang.
3. **Given** Lisensi telah melewati masa *grace period*, **When** Pengguna membuka riwayat laporan atau sesi POS lama, **Then** Sistem beroperasi dalam mode *Read-Only* (bisa melihat riwayat dan mencetak ulang laporan, tetapi dilarang membuat transaksi penjualan baru).
4. **Given** Sesi kasir sudah terbuka saat lisensi melewati masa *grace period*, **When** Kasir mencoba menyelesaikan order baru, **Then** Server menolak sinkronisasi order dan tombol Payment di UI dinonaktifkan.

---

### Edge Cases

- **System Clock Rollback**: Bagaimana jika merchant memundurkan jam sistem operasi server agar tampak belum kedaluwarsa?
  * *Penanganan*: Sistem menyimpan `last_seen_timestamp` yang diperbarui saat pembukaan sesi, sinkronisasi order, dan cron. Jika waktu sistem saat ini lebih mundur dari nilai tersebut lebih dari 1 jam, sistem mencatat event `clock_tamper` dan mengunci pembukaan sesi.
- **Corrupt / Tampered Token String**: Bagaimana jika seseorang mencoba mengedit isi teks token atau mengubah tanggal di database?
  * *Penanganan*: Verifikasi tanda tangan kriptografis (*signature verification*) dengan Public Key akan otomatis gagal, dan status lisensi langsung berubah menjadi `invalid`.
- **Database Backup & Restore**: Bagaimana jika database tenant di-dump dan di-restore ke mesin baru?
  * *Penanganan*: Token terikat ke `database.uuid`. Batasan yang diketahui: restore `pg_dump` mentah membawa `database.uuid` yang sama sehingga tidak terdeteksi. Hal ini diterima sesuai threat model (perlindungan pelanggaran kasual).
- **Batasan Kuota Register Kasir**: Bagaimana jika merchant mencoba membuat 5 titik kasir padahal token hanya mengizinkan `max_pos_registers: 2`?
  * *Penanganan*: Sistem menghitung jumlah `pos.config` berbeda yang memiliki sesi belum `closed`; pembukaan sesi untuk register ke-3 ditolak dengan pesan kuota penuh. Pembuatan `pos.config` baru tetap diizinkan.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Sistem MUST memverifikasi integritas dan keaslian token lisensi menggunakan tanda tangan kriptografi asimetris (RSA / Ed25519) dengan Public Key yang tersemat pada modul.
- **FR-002**: Sistem MUST menolak token jika tanda tangan digital tidak cocok dengan isi muatan (*payload*) data.
- **FR-003**: Sistem MUST mendukung model lisensi `subscription` dengan pembatasan tanggal kedaluwarsa `valid_until` dan masa tenggang `grace_period_days`.
- **FR-004**: Sistem MUST mendukung model lisensi `perpetual` tanpa batas waktu kedaluwarsa yang terikat pada identitas server/instance merchant.
- **FR-005**: Sistem MUST memvalidasi lisensi secara lokal di server Odoo tenant tanpa mewajibkan koneksi internet aktif setiap kali sesi kasir dibuka (*offline-ready*).
- **FR-006**: Sistem MUST memvalidasi batas maksimum register kasir aktif berdasarkan atribut `max_reg` di dalam token, dihitung sebagai jumlah `pos.config` berbeda yang memiliki sesi belum `closed`.
- **FR-007**: Sistem MUST mencegat pembukaan dan resume sesi kasir (`pos.config.open_ui`, `pos.session.create`, `pos.session.open_frontend_cb`) dan membatalkan aksi jika lisensi `invalid` atau `expired`.
- **FR-008**: Antarmuka kasir (OWL UI) MUST menampilkan banner peringatan bertingkat (Kuning untuk H-14 s/d H-1, Oranye untuk masa *grace period*).
- **FR-009**: Sistem MUST mengalihkan antarmuka ke mode *Read-Only* ketika lisensi telah kedaluwarsa penuh melewati masa tenggang: server menolak sinkronisasi order baru dan tombol Payment di UI kasir dinonaktifkan.
- **FR-010**: Sistem MUST menyediakan halaman konfigurasi di menu *Point of Sale $\rightarrow$ Settings $\rightarrow$ License Management* untuk melihat status, masa aktif, identitas mesin, dan input token baru.
- **FR-011**: Identitas instance server MUST menggunakan `database.uuid` Odoo yang termuat di dalam payload token bertanda tangan. Validasi kedua model lisensi berjalan 100% offline. Untuk model `subscription`, sistem MAY mengirim heartbeat non-blocking ke licensing server bila `saas.license.server_url` dikonfigurasi; kegagalan heartbeat tidak memengaruhi status lisensi.
- **FR-012**: Mekanisme input token lisensi MUST menggunakan copy-paste string token teks (Base64/JWT) langsung ke form pengaturan *Point of Sale → Settings → License Management* tanpa memerlukan penanganan file upload.
- **FR-013**: Status lisensi MUST dihitung ulang dari `raw_token` yang diverifikasi setiap kali pengecekan dilakukan. Kolom turunan (`valid_until`, `state`, dsb.) hanya cache tampilan dan tidak dipakai sebagai dasar keputusan.
- **FR-014**: Sistem MUST mendeteksi clock rollback lebih dari 1 jam terhadap `last_seen_timestamp` dan memblokir pembukaan sesi.
- **FR-015**: Daftar `mods` di payload disimpan dan ditampilkan, tetapi belum dipakai untuk membatasi instalasi atau akses modul.

---

### Key Entities *(include if feature involves data)*

- **`pos.saas.license`**: Entitas tunggal (singleton per tenant) yang menyimpan status lisensi aktif:
  - `license_id`: Kode unik lisensi dari penyedia SaaS.
  - `merchant_name`: Nama entitas toko / penyewa.
  - `license_type`: Tipe lisensi (`subscription` vs `perpetual`).
  - `database_uuid`: `database.uuid` Odoo yang terikat (dari `db_uuid` di payload).
  - `raw_token`: Teks tanda tangan digital lengkap.
  - `valid_from`: Tanggal awal berlaku.
  - `valid_until`: Tanggal akhir berlaku (null untuk perpetual).
  - `grace_period_days`: Jumlah hari toleransi setelah kedaluwarsa.
  - `max_pos_registers`: Batas maksimum titik kasir yang diizinkan.
  - `state`: Status lisensi saat ini (`active`, `warning`, `grace`, `expired`, `invalid`).
  - `last_verified_at`: Waktu pengecekan validitas terakhir.
- **`pos.saas.license.log`**: Catatan riwayat audit event lisensi:
  - `event_type`: Jenis kejadian (`installed`, `verified`, `warning`, `grace_entered`, `expired`, `blocked`, `clock_tamper`, `invalid_token`).
  - `event_date`: Waktu pencatatan kejadian.
  - `user_id`: Pengguna yang memicu event.
  - `details`: Rincian deskripsi teknis kejadian.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% upaya pembukaan sesi kasir pada sistem dengan token kedaluwarsa (lewat masa grace) berhasil diblokir secara konsisten.
- **SC-002**: Waktu eksekusi verifikasi token saat membuka sesi kasir tidak menambah latensi lebih dari 50 milidetik (tidak mengganggu kecepatan kasir).
- **SC-003**: Sistem dapat memvalidasi dan mengizinkan transaksi kasir 100% secara *offline* tanpa membutuhkan koneksi internet selama token masih dalam masa berlaku.
- **SC-004**: Tingkat kegagalan verifikasi akibat modifikasi manual isi database mencapai 100% deteksi (token otomatis ditolak saat isi diubah tanpa private key).

---

## Assumptions

- **Target Deployment Utama**: Sistem ditargetkan untuk lingkungan *Cloud-Hosted Database-per-Tenant* yang dikelola oleh tim penyedia SaaS, di mana merchant tidak memiliki akses `root` ke container atau kode sumber Python.
- **Batas Kemampuan Anti-Tamper pada On-Premise**: Pada deployment *self-hosted/on-premise* milik merchant, mekanisme ini melindungi dari pelanggaran kasual/non-teknis. Merchant dengan hak akses `root` penuh secara teori tetap dapat memodifikasi file Python atau merekayasa jam OS.
- **Ketersediaan Modul Kriptografi**: Environment Python Odoo 20 memiliki pustaka kriptografi standar (`cryptography` atau `pycryptodome`) yang sudah terpasang di container Docker.
- **Zona Waktu Konsisten**: Validasi tanggal kedaluwarsa mengacu pada tanggal lokal zona waktu company (fallback `Asia/Jakarta`) dari jam server yang tersinkronisasi via NTP.
- **Licensing Server di Luar Scope**: Penerbitan token untuk sementara dilakukan dengan script CLI internal; private key tidak pernah disimpan di repository.
