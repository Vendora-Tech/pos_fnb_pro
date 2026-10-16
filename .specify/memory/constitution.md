# POS FnB Pro Constitution

## Core Principles

### I. Lisensi adalah Jalur Kritis

Modul lisensi menentukan apakah merchant boleh berjualan. Karena itu:

- Keputusan izin selalu dihitung dari hasil verifikasi ulang `raw_token` pada saat dibutuhkan. Kolom turunan token di database (`license_id`, `state`, `valid_until`, `max_pos_registers`, dan sejenisnya) hanya cache tampilan dan bukan dasar keputusan.
- Verifikasi signature memakai Ed25519 (EdDSA) dengan format compact JWS `header.payload.signature`, base64url tanpa padding. Signature dihitung atas `header_b64 + "." + payload_b64`.
- Payload divalidasi manual terhadap `specs/001-pos-saas-license/contracts/license-token-schema.json`: field wajib, tipe, enum `typ`, batas nilai, dan penolakan field di luar skema. Validasi tidak menarik dependensi tambahan.
- Public key disimpan sebagai base64 di `PUBLIC_KEYS` dengan kunci `kid` agar rotasi kunci tidak memutus token yang sudah terbit. Private key hanya ada di mesin penerbit.
- Setiap kegagalan verifikasi menghasilkan `code` dan `message` yang bisa dibaca manusia, bukan exception generik.

### II. Offline-First, Server sebagai Penentu

- Sistem bekerja penuh tanpa internet. Perpanjangan lisensi dilakukan dengan memasang token baru, bukan dengan koneksi ke server pusat.
- Proteksi utama ada di server Odoo pada titik `pos.config.open_ui()`, `pos.session.create()`, dan `pos.order.sync_from_ui()`. Penonaktifan tombol di frontend hanya pelengkap UX dan tidak dihitung sebagai kontrol keamanan.
- Heartbeat ke server pusat bersifat opsional. Ia hanya berjalan bila `saas.license.server_url` diisi, memakai timeout pendek, dan tidak pernah mengubah state lisensi ketika gagal.
- Kalau jaringan bermasalah, transaksi kasir tetap berjalan sesuai status lisensi lokal.

### III. Test-First pada Modul

- Test ditulis sebelum implementasi. Test dijalankan sampai gagal, lalu implementasi menyusul sampai lulus.
- Test modul memakai `odoo.tests.common.TransactionCase` dan disimpan di `addons/<modul>/tests/`.
- Helper bersama (pembuatan keypair, patching `PUBLIC_KEYS`, penyusunan token) diletakkan di `tests/common.py` sebagai mixin, tidak diduplikasi.
- Test tidak bergantung pada data demo, karena CI menjalankan `--without-demo=all`.
- Hal yang bergantung waktu diuji dengan cara melompati tanggal sebagai parameter atau mem-patch method tanggal, supaya hasilnya deterministik.
- Sifat offline diuji dengan memastikan tidak ada panggilan jaringan selama pengecekan lisensi.

### IV. Modul Terisolasi, Dependensi Minimal

- Satu modul satu tanggung jawab. Modul lisensi berdiri sendiri di `addons/pos_saas_license/` dan tidak menambah `depends` tanpa alasan yang tertulis di spec atau plan.
- Fitur Odoo 20 yang sudah ada dipakai langsung dari core (`pos_self_order`, `l10n_id_pos_self_order_qris`, `pos_restaurant`). Core Odoo tidak difork.
- Logika yang tidak membutuhkan ORM dipisahkan ke file sendiri agar bisa diuji tanpa setup database.
- Modul dummy `pos_example` dijaga murni sebagai sarana CI di bawah 100 baris; logika bisnis tidak masuk ke sana.
- Setiap model baru punya entri di `security/ir.model.access.csv`.

### V. Rahasia Penerbit dan Isolasi Tenant

- `.env`, `*.pem`, dan `scripts/license_tools/keys/` tidak pernah masuk repository. Job `security` di CI menjalankan Gitleaks dan akan menggagalkan pipeline bila terjadi kebocoran.
- Isi rahasia tidak ditampilkan ke output terminal, ringkasan sesi, pesan commit, atau dokumentasi. Bila perlu dirujuk, tampilkan dalam bentuk ter-mask.
- Arsitektur tenancy adalah database-per-tenant. Satu instance melayani satu merchant, dan tidak ada akses lintas tenant.
- Data merchant tidak diekspor ke luar lingkungannya tanpa permintaan eksplisit.
- `database.uuid` berfungsi sebagai identitas tenant dan binding lisensi. Nilainya bukan rahasia, tapi juga tidak disebarkan.

### VI. Konfigurasi Eksplisit, Tanpa Nilai Tertanam

- Kredensial dan port dibaca dari `.env`. Nilai nyata tidak ditanam di kode, Makefile, compose, atau workflow.
- Perintah yang menyentuh container memakai nama service Compose, bukan nama container literal, agar tidak bergantung pada nama project.
- Locale waktu dihitung dari zona waktu company dengan fallback `Asia/Jakarta`, dan tidak diasumsikan UTC.

## Batasan Teknis dan Lingkungan

**Stack.** Odoo 20 di atas image `odoo:20`, PostgreSQL 18, dijalankan lewat Docker Compose dengan project `odoo20-pos`. Port host default 10020 (web) dan 20020 (chat). Database dev default `pos_saas_dev`.

**Addons.** `./addons` dimount ke `/mnt/extra-addons`. Modul di dalamnya di-track git karena job CI `module-test` memindai `addons/*/__manifest__.py`.

**Manifest modul.** Versi `20.0.<major>.<minor>.<patch>`, `license` "LGPL-3", `author` "Vendora-Tech", `category` "Point of Sale", `installable` True, `application` False untuk modul pendukung.

**Sintaks Odoo 20.** Constraint dan index ditulis sebagai atribut class `models.Constraint(...)` dan `models.Index(...)`. `_sql_constraints` tidak lagi dikumpulkan oleh ORM dan tidak dipakai. Fungsi loader data POS memakai keluarga `_load_pos_data*`, bukan `_pos_ui_models_to_load` yang berasal dari Odoo 16.

**Kontrak token.** Payload wajib memuat `lid`, `mch`, `typ`, `db_uuid`, `max_reg`, `from`, `grace`; `mods` opsional. `until` wajib untuk `subscription` dan kosong untuk `perpetual`. Field di luar skema ditolak.

**Status lisensi.** Berdasarkan `days_left = until - today` dengan toleransi grace: `invalid` bila verifikasi atau binding gagal, `active` untuk perpetual atau `days_left > 14`, `warning` untuk `0 <= days_left <= 14`, `grace` untuk `-grace <= days_left < 0`, `expired` untuk `days_left < -grace`.

**Batasan yang diterima.** `pg_dump` ikut menyalin `database.uuid`, sehingga kloning database mengkloning binding lisensi. Untuk lisensi perpetual, binding ini bersifat pertahanan kasual. Deteksi clock rollback memakai toleransi 1 jam dan dicatat sebagai event `clock_tamper`.

**Verifikasi API.** Karena container tidak selalu tersedia, verifikasi API Odoo dilakukan terhadap source `github.com/odoo/odoo` branch `20.0`. Hasilnya wajib dicatat di `specs/<fitur>/research.md`, bukan hanya diingat dalam sesi.

## Alur Kerja Pengembangan

**Spec-driven.** Fitur dikerjakan berurutan: `speckit-specify`, `speckit-clarify`, `speckit-plan`, `speckit-tasks`, `speckit-analyze`, lalu `speckit-implement`. Fitur aktif ditentukan `.specify/feature.json`. Implementasi tidak dimulai sebelum `tasks.md` tersedia dan analisis konsistensi bersih.

**Spec sebagai sumber kebenaran.** `specs/` memuat kebutuhan yang disetujui. Kalau implementasi perlu menyimpang, spec atau plan diperbarui lebih dulu. Pekerjaan yang belum tercakup ditambahkan sebagai task baru dengan ID lanjutan, bukan dikerjakan tanpa jejak.

**Status task.** Task ditandai `[x]` di `tasks.md` hanya setelah kodenya ada dan test terkait lulus.

**Path.** Artefak spec memakai path relatif. Path absolut mesin lokal tidak ditulis di dokumentasi repo.

**Quality gate.** Sebelum perubahan dianggap selesai:

- Test modul yang tersentuh lulus di database bersih.
- `-u all` lulus untuk memastikan tidak ada regresi.
- Tidak ada rahasia baru di diff, dan Gitleaks bersih.
- Perubahan pada manifest, view, data, atau security diverifikasi lewat `--test-enable` atau upgrade manual, bukan hanya dengan membaca kode.

**Lingkup perubahan.** Perubahan dibuat sekecil yang menyelesaikan masalah. Refactor di luar lingkup diminta diusulkan lebih dulu. Validasi dijalankan hanya pada scope yang berubah, kecuali diminta sebaliknya.

**Pelaporan.** Setiap penyelesaian melaporkan file yang diubah, validasi yang dijalankan, asumsi yang dipakai, dan blocker yang tersisa. Hasil yang diperkirakan tidak dilaporkan sebagai hasil yang sudah diamati.

## Governance

- Dokumen ini menggantikan praktik lain yang bertentangan untuk keputusan rancangan. `AGENTS.md` dan `CLAUDE.md` memuat panduan operasional harian dan dirujuk dari sini.
- Amandemen dilakukan lewat `speckit-constitution`, disertai alasan dan dampaknya terhadap fitur yang sedang berjalan.
- Prinsip ditambah hanya bila ada kebutuhan nyata yang belum tercakup. Jumlah prinsip dijaga tetap ringkas.
- Setiap pekerjaan yang lewat `speckit-analyze` diperiksa terhadap prinsip di dokumen ini. Pelanggaran dilaporkan sebagai temuan, bukan diabaikan.
- Konflik antara dokumen ini dan `AGENTS.md` diselesaikan dengan memperbarui `AGENTS.md`; dokumen ini yang menjadi acuan.

**Version**: 1.0.0 | **Ratified**: 16-10-2026 | **Last Amended**: 16-10-2026
