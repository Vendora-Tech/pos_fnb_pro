# AGENTS.md — pos_fnb_pro

Panduan kerja untuk agent coding di repository ini. Isinya berlaku untuk semua lapisan repo: modul Odoo di `addons/`, tooling di `scripts/`, infra Docker/CI, dan artefak spec-driven di `specs/` serta `.specify/`.

Dokumen ini adalah arahan kerja, bukan kontrak yang menuntut kepatuhan mutlak. Kalau konteks nyata bertentangan dengan isi di sini, utamakan isi repository dan laporkan selisihnya.

---

## 1. Apa project ini

Ekosistem SaaS POS di atas Odoo 20 untuk pasar Indonesia (F&B dan Retail). Model bisnisnya database-per-tenant: satu instance Odoo per merchant, dengan modul lisensi yang mengunci sesi kasir ketika langganan berakhir.

Komponen yang sudah ada di repo:

- `pos_saas_license` — engine lisensi offline-first: token Ed25519, grace period, kuota register, banner peringatan di kasir. Ini jalur kritis.
- `pos_example` — modul dummy khusus CI, bukan untuk produksi.

Dokumen sumber kebenaran:

| Dokumen | Isi |
| :--- | :--- |
| `docs/SAAS_POS_MASTER_BLUEPRINT.md` | Blueprint produk: kategori toko, tiering fitur, roadmap, arsitektur SaaS |
| `specs/001-pos-saas-license/spec.md` | Requirement fungsional dan user story yang disetujui |
| `specs/001-pos-saas-license/plan.md` | Rancangan teknis dan struktur file yang ditargetkan |
| `specs/001-pos-saas-license/research.md` | Hasil verifikasi API Odoo 20 dari source, keputusan kripto |
| `specs/001-pos-saas-license/data-model.md` | Definisi field, aturan perhitungan status, state machine |
| `specs/001-pos-saas-license/tasks.md` | Daftar task T001–T045 beserta status |
| `specs/001-pos-saas-license/quickstart.md` | Skenario pengujian manual |
| `specs/001-pos-saas-license/contracts/license-token-schema.json` | Skema payload token |

---

## 2. Stack dan runtime

- Odoo 20 (`odoo:20`) dengan PostgreSQL 18 (`postgres:18`), dijalankan lewat Docker Compose.
- Compose project: `odoo20-pos`. Service: `odoo20` dan `db`.
- Port host: `ODOO_WEB_PORT` (default 10020) → 8069, `ODOO_CHAT_PORT` (default 20020) → 8072.
- Mount: `./addons` → `/mnt/extra-addons`, `./etc` → `/etc/odoo`, `./entrypoint.sh` → `/entrypoint.sh`, `./postgresql` → PGDATA.
- Nama database dev default: `pos_saas_dev` (variabel `DB_NAME` di Makefile).
- Konfigurasi lingkungan dibaca dari `.env`, yang dibuat dengan menyalin `.env.example`. `.env` tidak pernah masuk repo.
- Addons pihak ketiga yang masuk lewat `addons/` tetap di-track git, karena job CI `module-test` memindai `addons/*/__manifest__.py`.

Untuk bekerja di mesin dev, container harus hidup (`make up-d`) karena hampir semua perintah Odoo dijalankan di dalam container.

---

## 3. Peta direktori

| Path | Isi | Catatan |
| :--- | :--- | :--- |
| `addons/pos_saas_license/` | Modul lisensi (target utama) | Masih scaffold; hanya `__manifest__.py`, `__init__.py`, `models/__init__.py`, `tests/__init__.py` |
| `addons/pos_example/` | Modul dummy CI | `depends: base`, dipakai untuk memastikan pipeline install/test berfungsi |
| `scripts/license_tools/` | Penerbit token di luar Odoo | `generate_keypair.py`, `issue_token.py`, `README.md`; `keys/` berisi private key lokal dan di-ignore git |
| `specs/001-pos-saas-license/` | Artefak spec-driven fitur aktif | Sumber kebenaran requirement |
| `.specify/` | Konfigurasi dan template Spec-Kit | `feature.json` menunjuk fitur aktif; `memory/constitution.md` berisi prinsip proyek |
| `.agents/skills/` | Skill Spec-Kit yang tersedia | `speckit-specify`, `speckit-clarify`, `speckit-plan`, `speckit-tasks`, `speckit-analyze`, `speckit-implement`, `speckit-checklist`, `speckit-converge`, `speckit-taskstoissues`, `speckit-constitution` |
| `docs/` | Blueprint produk | Bukan artefak fitur, jangan diubah tanpa alasan |
| `etc/` | Konfigurasi Odoo (`odoo.conf`, `requirements.txt`, `logrotate`) | `etc/odoo.conf` adalah template default Odoo, hampir seluruhnya komentar |
| `.github/workflows/ci.yml` | Pipeline CI | 4 job: `lint-validate`, `security`, `smoke-test`, `module-test` |

---

## 4. Perintah kerja

Semua lewat Makefile. Jalankan `make help` untuk daftar lengkap.

```bash
# Siklus harian
make up-d                 # jalankan container di background
make ps                   # status container
make logs-odoo            # ikuti log Odoo
make shell-odoo           # bash di dalam container Odoo
make psql                 # shell psql ke DB_NAME
make down                 # hentikan container (volume postgresql/ tetap ada)

# Sinkronisasi modul
make wait-db              # tunggu PostgreSQL siap
make wait-odoo            # tunggu registry Odoo selesai load
make upgrade MODULE=pos_saas_license
make restart-upgrade MODULE=pos_saas_license   # wait-db + up + wait-odoo + upgrade + restart
make upgrade-all
make scaffold MODULE=nama_modul                # buat kerangka modul baru

# Utilitas
make perms                # perbaiki permission addons/, etc/, postgresql/
make logs-odoo-file       # tail etc/odoo-server.log
```

`make upgrade` dan `make restart-upgrade` juga menerima nama modul sebagai argumen posisi: `make restart-upgrade pos_saas_license`.

Menjalankan test satu modul, langsung di dalam container:

```bash
docker compose exec -T odoo20 odoo \
  --db_host=db -d pos_saas_dev \
  -u pos_saas_license --test-enable --test-tags /pos_saas_license \
  --stop-after-init --log-level=test
```

Untuk memfilter per class atau method, pakai `--test-tags /pos_saas_license:TestLicenseCrypto` atau `/pos_saas_license:TestLicenseCrypto.test_valid_token`.

Menerbitkan token uji coba (dijalankan di host, di luar Odoo):

```bash
python scripts/license_tools/generate_keypair.py --kid dev2026 --out ~/.pos_saas_keys/dev2026.pem

python scripts/license_tools/issue_token.py \
  --key ~/.pos_saas_keys/dev2026.pem --kid dev2026 \
  --lid LIC-2026-TEST-001 --mch "Toko Sukses Makmur" \
  --typ subscription --db-uuid <DATABASE_UUID> \
  --max-reg 2 --from 2026-01-01 --until 2026-12-31 --grace 7
```

`database.uuid` diambil dari `ir.config_parameter` dan ditampilkan di halaman Settings POS.

---

## 5. Konvensi kode modul Odoo

**Manifest.** Format `20.0.<major>.<minor>.<patch>`, `author` "Vendora-Tech", `license` "LGPL-3", `category` "Point of Sale", `installable` True, `application` False untuk modul pendukung. Daftar `depends` dijaga seminimal mungkin; jangan menambah dependensi tanpa alasan yang tertulis di spec atau plan.

**Struktur modul.** Ikuti layout yang sudah dipakai `pos_saas_license`: `models/` dengan `__init__.py` yang mengimpor tiap file model, `views/`, `data/`, `security/ir.model.access.csv`, `tests/` dengan `tests/__init__.py`. Setiap file model baru harus didaftarkan di `models/__init__.py`, dan setiap file data/view didaftarkan di `data` pada manifest.

**Python di dalam Odoo.** Import dari `odoo` (`api`, `fields`, `models`, `_`), bukan import internal framework. Pemisahan kode yang tidak butuh ORM (misalnya verifier kripto) ke file terpisah supaya bisa diuji tanpa setup database.

**Constraint dan index.** Odoo 20 memakai atribut class `models.Constraint("CHECK (...)", "pesan")` dan `models.Index("(...)")` dari `odoo.orm.table_objects`. Sintaks lama `_sql_constraints` tidak lagi dikumpulkan, jadi jangan dipakai.

**Terjemahan.** Konvensi utama di Odoo 20 adalah `_("...")` dari `odoo`. `self.env._("...")` dipakai untuk pesan yang bahasa penerimanya relevan. Teks di XML view ditulis langsung di atribut `string`; di template OWL pakai `.translate`.

**Aset POS.** Komponen OWL kasir didaftarkan ke bundle `point_of_sale._assets_pos` di manifest, bukan bundle web biasa.

**Keamanan akses.** Setiap model baru perlu baris di `security/ir.model.access.csv`. Model konfigurasi lisensi: read untuk `point_of_sale.group_pos_user`, read/write/create untuk `point_of_sale.group_pos_manager`, tanpa unlink kecuali `base.group_system`.

**Bahasa kode.** Nama model, field, method, variabel, dan pesan commit dalam bahasa Inggris. Komentar, docstring, dan dokumentasi internal boleh bahasa Indonesia. Jangan mencampur keduanya dalam satu identifier.

**Dependensi Python.** Yang sudah dipakai: `cryptography` (Ed25519), tersedia di image `odoo:20`. Validasi skema payload ditulis manual mengikuti `contracts/license-token-schema.json`, tanpa menambah `jsonschema`.

---

## 6. Test

- Test memakai `odoo.tests.common.TransactionCase`, disimpan di `addons/<modul>/tests/`, dan didaftarkan di `tests/__init__.py`.
- Test ditulis sebelum implementasi dan diharapkan gagal dulu. Ini sudah menjadi pola di `tasks.md`, jadi pertahankan urutannya: tulis test, jalankan sampai merah, baru implementasi.
- Helper yang dipakai bersama (pembuatan keypair, patching `PUBLIC_KEYS`, helper `make_token`) diletakkan di `tests/common.py` sebagai mixin, bukan diduplikasi di tiap file test.
- Untuk hal yang bergantung waktu, jangan pakai tanggal nyata. Patch method `_today()` atau lewati tanggal sebagai parameter supaya hasilnya deterministik.
- Untuk memastikan modul benar-benar offline, patch `requests`/`urllib` agar melempar exception selama test dan pastikan tidak ada panggilan jaringan.
- Dummy CI (`pos_example`) dijaga di bawah 100 baris. Jangan menambah logika bisnis ke sana.

---

## 7. Konteks teknis yang sudah terverifikasi

Bagian ini merangkum temuan dari `specs/001-pos-saas-license/research.md` agar tidak perlu diulang setiap sesi. Kalau butuh detail baris dan file, buka dokumen itu.

**Titik intervensi sesi kasir (Odoo 20).** `action_pos_session_open` tidak ada di Odoo 20. Gerbang yang benar:

- `pos.config.open_ui()` — pintu masuk saat kasir menekan "New Session", "Continue Selling", atau membuka POS dari dashboard.
- `pos.session.create(vals_list)` — tempat validasi kuota register.
- `pos.session.open_frontend_cb()` — memanggil `self.config_id.open_ui()`, jadi guard di `open_ui` sudah mencakupnya.
- `pos.config.close_ui()` justru memanggil `open_ui()`, dan penutupan sesi dari UI lewat `close_session_from_ui()` tidak melewati `open_ui`.

**Loader data POS.** `_pos_ui_models_to_load` dan `_loader_params_pos_session` adalah API Odoo 16. Odoo 20 memakai `_load_pos_data*`. Field yang harus sampai ke frontend cukup didaftarkan di `pos.session._load_pos_data_fields()`; record sesi diakses di frontend lewat `this.data.models["pos.session"].get(odoo.pos_session_id)`.

**Sinkronisasi order.** Guard read-only ada di `pos.order.sync_from_ui()`. `remove_from_ui()` tidak perlu dijaga karena hanya menghapus order offline.

**Frontend OWL.** Patch Navbar lewat `patch(Navbar.prototype, ...)` dari `@web/core/patch` plus template inherit `point_of_sale.Navbar`. Untuk menonaktifkan tombol Payment, inherit `button.pay.pay-order-button` dengan `position="attributes"`. Jangan membalik getter `disableClickPayment` di `access_right_plugin.js` — namanya terbalik dan nilainya `true` berarti tombol aktif.

**Settings POS.** Block lisensi disisipkan dengan XPath `//app[@name='point_of_sale']//div[@invisible="not pos_config_id"]` dan `position="inside"`. `<app>` tersebut bergrup `group_pos_manager`, jadi hanya manajer POS yang melihatnya.

**Kontrak token.** Compact JWS tiga bagian base64url tanpa padding: `header.payload.signature`. Header `{"alg": "EdDSA", "typ": "SAAS-LIC", "kid": "<kid>"}`. Signature Ed25519 di atas byte ASCII `header_b64 + "." + payload_b64`. Payload wajib `lid, mch, typ, db_uuid, max_reg, from, grace`; `mods` opsional; `until` wajib untuk `subscription` dan harus kosong untuk `perpetual`. Field di luar skema ditolak.

**Perhitungan status.** `today` memakai tanggal lokal zona waktu company dengan fallback `Asia/Jakarta`, dan `days_left = until - today`. `invalid` bila token kosong, signature gagal, skema tidak valid, `kid` tidak dikenal, `db_uuid` tidak cocok, atau `from` di masa depan. `active` untuk perpetual atau `days_left > 14`; `warning` untuk `0 <= days_left <= 14`; `grace` untuk `-grace <= days_left < 0`; `expired` untuk `days_left < -grace`.

**Keputusan selalu dari verifikasi ulang.** Kolom hasil turunan token di database (`license_id`, `state`, `valid_until`, dan sejenisnya) hanya cache tampilan. Setiap keputusan izin harus memverifikasi ulang `raw_token`. Ini yang membuat sistem tahan terhadap manipulasi record langsung di database.

**Server sebagai penentu.** Proteksi utama ada di server Odoo. Menonaktifkan tombol Payment di frontend hanya pelengkap UX dan tidak dianggap sebagai kontrol keamanan.

**Clock rollback.** Toleransi 1 jam. Mundur lebih dari itu memblokir akses dan mencatat event `clock_tamper`. `last_seen_timestamp` menyimpan waktu server terbesar yang pernah terlihat.

**Batasan yang diketahui, bukan bug.** `pg_dump` ikut menyalin `database.uuid`, jadi kloning database juga mengkloning binding lisensi. Untuk perpetual, binding ini bersifat pertahanan kasual. Heartbeat ke server pusat hanya dijalankan bila `saas.license.server_url` diisi, dengan timeout 5 detik, dan seluruh exception ditangkap tanpa mengubah state.

**Fitur bawaan Odoo 20 yang relevan.** `pos_self_order`, `l10n_id_pos_self_order_qris`, dan `pos_restaurant` dipakai dari core Odoo, tanpa fork.

---

## 8. Alur kerja spec-driven

Fitur di repo ini dikerjakan lewat Spec-Kit. Urutan yang dipakai:

1. `speckit-specify` — tulis atau perbarui `specs/<fitur>/spec.md` dari deskripsi kebutuhan.
2. `speckit-clarify` — tutup area yang masih ambigu sebelum masuk perancangan.
3. `speckit-plan` — hasilkan `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`.
4. `speckit-tasks` — hasilkan `tasks.md` dengan ID `T001`, `T002`, dan penanda `[P]` serta `[US1]`.
5. `speckit-analyze` — periksa konsistensi antar artefak sebelum implementasi.
6. `speckit-implement` — kerjakan task berurutan sesuai fase di `tasks.md`.

Fitur aktif ditentukan oleh `.specify/feature.json`. Prinsip proyeknya ada di `.specify/memory/constitution.md` dan dibaca oleh `speckit-analyze` serta `speckit-clarify`.

Cara memperlakukan artefak spec:

- `specs/` adalah sumber kebenaran kebutuhan. Kalau implementasi perlu menyimpang, perbarui spec atau plan dulu, jangan langsung mengubah kode dengan asumsi baru.
- Tandai task `[x]` di `tasks.md` hanya setelah kodenya ada dan test terkait lulus.
- Kalau menemukan pekerjaan yang belum tercakup, tambahkan task baru dengan ID lanjutan; jangan menumpuk pekerjaan tanpa jejak di `tasks.md`. Skill `speckit-converge` dipakai untuk memindai selisih antara kode dan spec.
- `tasks.md` menetapkan test lebih dulu. Pertahankan urutan itu saat menambah task baru.
- `checklists/requirements.md` mencatat status validasi spec. Perbarui bila ada item yang berubah statusnya.
- Tulis path relatif di dalam artefak spec. Path absolut mesin lokal akan rusak begitu repo dipindah atau dibuka agent lain.

---

## 9. Rahasia dan data sensitif

- `.env` tidak masuk repo. `.env.example` adalah template, dan nilainya tidak berisi kredensial nyata.
- Private key penerbit token (`*.pem`) dan folder `scripts/license_tools/keys/` sudah di-ignore. Job `security` di CI menjalankan Gitleaks, jadi key yang bocor akan langsung menggagalkan pipeline.
- Private key hanya berada di mesin penerbit. Public key ditempel sebagai base64 ke `PUBLIC_KEYS` di `models/license_verifier.py`, dan key itu memang untuk dibagikan.
- Ada satu key dev di `scripts/license_tools/keys/dev2026.pem` di working tree lokal. Key itu hanya untuk uji coba lokal dan tidak pernah masuk commit.
- Jangan menampilkan isi `.env`, private key, atau token lisensi asli ke output terminal, ringkasan sesi, pesan commit, atau dokumentasi. Tampilkan potongan yang di-mask bila perlu referensi.
- `database.uuid` bukan rahasia, tapi identitas tenant. Jangan menyalinnya ke issue publik, log, atau commit message.
- Data merchant di dalam database tenant tidak boleh diekspor ke luar repo atau ke layanan pihak ketiga tanpa permintaan eksplisit.

---

## 10. Git dan CI

Branch yang ada: `main`, `dev`, dan branch fitur (misalnya `pos_saas_license`). Pekerjaan modul lisensi berlangsung di branch fitur, lalu masuk lewat `dev` sebelum `main`.

Commit message memakai prefix tipe: `feat:`, `fix:`, `test:`, `ci:`, `build:`, `docs:`, `chore:`. Satu commit sebaiknya fokus pada satu perubahan.

Job CI di `.github/workflows/ci.yml`:

| Job | Isi | Kapan jalan |
| :--- | :--- | :--- |
| `lint-validate` | `actionlint`, lint YAML, `docker compose config`, ShellCheck pada `entrypoint.sh` dan `scripts/`, syntax Python + Ruff untuk `addons/`, validasi XML view, validasi `__manifest__.py` | Push dan PR ke `dev`/`main` |
| `security` | Gitleaks, penjagaan file sensitif dan password hardcoded, Trivy config scan, Trivy image scan `odoo:20` dan `postgres:18` | Push dan PR ke `dev`/`main` |
| `smoke-test` | Boot stack, tunggu PostgreSQL dan registry Odoo, HTTP health check ke `/web/login` | PR dan push ke `main`, nightly, manual |
| `module-test` | Auto-discover `addons/*/__manifest__.py`, install dengan `--test-enable --without-demo=all`, lanjut `-u all` untuk regresi, lalu pylint-odoo (non-blocking) | PR dan push ke `main`, nightly, manual |

Catatan: job `lint-validate` sengaja tidak memakai Docker dan targetnya selesai di bawah 3 menit, karena mayoritas kesalahan modul Odoo berasal dari XML tidak valid, manifest rusak, atau salah konfigurasi compose. Job `smoke-test` dan `module-test` tidak jalan saat push ke `dev`.

Konsekuensi praktis:

- Modul baru tidak perlu didaftarkan manual di CI. Yang perlu benar adalah `addons/*/__manifest__.py` dan test yang ikut terpasang.
- Test harus lulus di database bersih dengan `--without-demo=all` pada percobaan pertama. Pastikan test tidak bergantung pada data demo.
- pylint-odoo bersifat informatif. Temuannya tetap layak ditindaklanjuti, terutama `odoolint`.
- Jangan menambah file biner besar, arsip database, atau artefak runtime ke git.

Artefak runtime yang tidak masuk git: `postgresql/`, `etc/filestore/`, `etc/sessions/`, `etc/odoo-server.log*`, `screenshots/`, `__pycache__/`, `.ruff_cache/`, `.pytest_cache/`, `.claude/`.

---

## 11. Catatan operasional Docker dan CI

- Panggil container lewat nama service Compose: `docker compose exec -T odoo20 ...`, bukan nama container literal. Nama container bergantung pada compose project dan bisa berubah.
- Makefile menyediakan `CONTAINER` dan `DB_CONTAINER` sebagai variabel yang bisa di-override lewat `.env` atau command line bila nama container berbeda di mesin kamu.
- Makefile membaca `.env` otomatis. Tanpa `.env`, `DB_USER` dan `DB_PASSWORD` kosong dan target `upgrade` akan gagal.
- Setelah mengubah mount atau menambah folder baru, jalankan `make perms` supaya permission tidak menghalangi container.
- `make wait-odoo` melakukan polling HTTP ke `/web/login`, jadi siap dipakai sebelum upgrade. Container Odoo tidak dianggap siap hanya karena prosesnya hidup.
- Jangan menjalankan `docker compose down -v` atau menghapus isi `postgresql/` tanpa konfirmasi eksplisit, karena itu menghapus seluruh data tenant.
- `docker compose` tidak selalu tersedia di mesin dev. Verifikasi API Odoo dilakukan dengan membaca source `github.com/odoo/odoo` branch `20.0`, yang sama dengan image `odoo:20` di compose. Catat hasil verifikasi ke `research.md`, jangan simpan di memori sesi saja.

---

## 12. Kebiasaan kerja

- Pahami requirement dulu. Baca spec, plan, dan task terkait sebelum mengubah kode.
- Baca file target dan konteks sekitarnya sebelum mengedit. Jangan mengubah kode yang belum dibaca.
- Buat perubahan sekecil yang menyelesaikan masalah. Refactor besar di luar scope sebaiknya diusulkan dulu.
- Jalankan test dan validasi hanya pada scope yang berubah. Test suite penuh hanya bila diminta.
- Setelah validasi, periksa `git diff` dan status repo, lalu laporkan file yang berubah.
- Jangan menyatakan sesuatu sudah selesai tanpa verifikasi nyata. Bedakan dengan jelas antara yang sudah dijalankan, yang diperkirakan, dan yang belum diketahui.
- Bila menemui blocker, hentikan pekerjaan, tulis apa yang memblokir dan apa yang sudah dicoba, lalu minta arahan.
- Bila menemukan ketidaksesuaian antara kode dan spec, catat dan perbarui spec-nya, jangan diam-diam menyimpang.
- Untuk operasi destruktif atau sulit dibalik (hapus data, hapus file, `down -v`, force push), minta konfirmasi dulu.

---

## 13. Gap yang masih terbuka

Daftar ini diperbarui 16-10-2026 dan sudah diperiksa terhadap isi repo.

**Sudah dibereskan pada sesi ini:**

- `.ruff_cache/` dan `__pycache__/` di luar `addons/` kini di-ignore lewat `.gitignore` root; sebelumnya hanya `addons/.gitignore` yang menutupnya.
- Path absolut mesin lain di `specs/001-pos-saas-license/checklists/requirements.md` diganti menjadi relatif.
- Job `module-test` tidak lagi mengandalkan nama container literal; sekarang memakai `docker compose exec -T odoo20`.
- `.specify/memory/constitution.md` sudah diisi dengan prinsip proyek, sebelumnya masih template kosong.

**Masih terbuka:**

- Implementasi `pos_saas_license` baru sebatas scaffold. Phase 1 selesai, T008–T045 belum dikerjakan.
- Integrasi Spec-Kit di `.specify/integration.json` diset ke `claude`, sementara `.claude/` di-ignore git. Artefak command claude tidak akan pernah masuk repo. Perlu diputuskan apakah integrasi dipindah atau folder itu dikecualikan dari ignore.
- Ruff dijalankan CI pada `addons/`, tapi tidak ada `pyproject.toml` atau `ruff.toml` di root. Aturan yang berlaku karena itu bergantung pada default versi Ruff di runner, sehingga hasil lint lokal bisa berbeda dari CI.
- `etc/odoo.conf` masih template default Odoo dengan seluruh opsi terkomentar, sehingga konfigurasi efektif sepenuhnya bergantung pada argumen CLI dan environment.
- Fitur di luar modul lisensi (blueprint kategori toko, tiering) belum punya spec tersendiri.
