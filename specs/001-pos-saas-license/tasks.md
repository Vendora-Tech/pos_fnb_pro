---

description: "Task list for POS SaaS Licensing Engine (pos_saas_license)"
---

# Tasks: POS SaaS Licensing Engine (`pos_saas_license`)

**Input**: Design documents from `/specs/001-pos-saas-license/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/license-token-schema.json, quickstart.md

**Tests**: Disertakan, karena plan.md menetapkan test suite `TransactionCase`. Test ditulis lebih dulu dan harus gagal sebelum implementasi.

**Organization**: Task dikelompokkan per user story agar tiap story bisa diimplementasi dan diuji mandiri.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Bisa dikerjakan paralel (file berbeda, tidak bergantung pada task yang belum selesai)
- **[Story]**: User story terkait (US1, US2, US3)
- Semua path relatif terhadap root repository. Modul berada di `addons/pos_saas_license/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Kerangka modul, tooling penerbit token, dan verifikasi API Odoo 20

- [x] T001 Buat kerangka modul: `addons/pos_saas_license/__init__.py` (import `models`), `addons/pos_saas_license/models/__init__.py`, `addons/pos_saas_license/tests/__init__.py`
- [x] T002 Buat `addons/pos_saas_license/__manifest__.py`: `name` "POS SaaS License", `version` "20.0.1.0.0", `author` "Vendora-Tech", `license` "LGPL-3", `category` "Point of Sale", `depends` ["point_of_sale"], `external_dependencies` {"python": ["cryptography"]}, `data` dan `assets` dikosongkan dulu (diisi bertahap per story), `installable` True, `application` False
- [x] T003 [P] Tambahkan pola `*.pem` dan `scripts/license_tools/keys/` ke `.gitignore` agar private key tidak pernah ter-commit (job Gitleaks di `.github/workflows/ci.yml` akan gagal bila bocor)
- [x] T004 [P] Buat `scripts/license_tools/generate_keypair.py`: argumen `--kid`, `--out`; buat Ed25519 private key, simpan PEM ke `--out` (tolak bila file sudah ada), cetak `kid` dan public key raw base64 untuk ditempel ke `PUBLIC_KEYS`
- [x] T005 [P] Buat `scripts/license_tools/issue_token.py`: argumen `--key`, `--kid`, `--lid`, `--mch`, `--typ` (`subscription`|`perpetual`), `--db-uuid`, `--mods` (opsional, dipisah koma), `--max-reg`, `--from`, `--until` (wajib untuk subscription, dilarang untuk perpetual), `--grace` (default 7); hasilkan token `header.payload.signature` base64url tanpa padding, header `{"alg":"EdDSA","typ":"SAAS-LIC","kid":<kid>}`, signature Ed25519 atas `header_b64 + "." + payload_b64`, JSON compact `separators=(",", ":")`
- [x] T006 [P] Buat `scripts/license_tools/README.md`: cara pakai T004/T005, lokasi aman private key, peringatan jangan commit key, dan batasan `pg_dump` (UUID ikut tersalin)
- [x] T007 Verifikasi API Odoo 20 terhadap source `github.com/odoo/odoo` branch `20.0` (branch ini yang dipakai image `odoo:20`; container tidak tersedia di mesin dev) dan catat hasilnya di `specs/001-pos-saas-license/research.md` seksi 6: (a) signature `pos.config.open_ui`, (b) `pos.session.create` dan `open_frontend_cb`, (c) method loader data POS untuk menambah field `pos.session` ke frontend, (d) method sinkronisasi order dari UI di `pos.order`, (e) sintaks `models.Constraint`/`models.Index`, (f) path komponen Navbar dan tombol Payment OWL beserta template-nya, (g) XPath target block settings POS di `res_config_settings_views.xml`, (h) apakah `self.env._` dipakai untuk terjemahan

**Checkpoint**: Modul kosong bisa di-install (`make restart-upgrade MODULE=pos_saas_license`), nama API Odoo 20 sudah pasti

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Verifier kriptografi, perhitungan status, dan model inti yang dipakai semua story

**CRITICAL**: Tidak ada pekerjaan user story sebelum fase ini selesai

### Tests for Foundation

- [x] T008 [P] Buat helper test `addons/pos_saas_license/tests/common.py`: mixin yang membuat keypair Ed25519 saat `setUpClass`, `kid` "test", fungsi `make_token(**overrides)` dan `make_raw_token(header, payload)` untuk token rusak, patch `license_verifier.PUBLIC_KEYS` ke `{"test": <pubkey>}`, helper set `database.uuid` dan patch `pos.saas.license._today()`
- [x] T009 [P] Tulis `addons/pos_saas_license/tests/test_license_crypto.py`: token valid lolos; payload diubah, signature diubah, key lain, `kid` tidak dikenal, `alg` bukan `EdDSA`, jumlah bagian 1/2/4, base64 rusak, JSON rusak semuanya ditolak; validasi skema: field wajib hilang (`lid`, `mch`, `typ`, `db_uuid`, `max_reg`, `from`, `grace`), field asing, `typ` di luar enum, `max_reg` < 1 ("minimum": 1), `grace` < 0 ("minimum": 0), subscription tanpa `until`, perpetual dengan `until` non-null, `from`/`until` bukan format `YYYY-MM-DD`
- [ ] T010 [P] Tulis `addons/pos_saas_license/tests/test_license_state.py` untuk `compute_state` dengan `grace=7`: H-15 `active`, H-14 `warning`, H0 (`until` = today) `warning`, H+1 `grace`, H+7 `grace`, H+8 `expired`; `grace=0` langsung `expired` di H+1; perpetual selalu `active`; `from > today` `invalid`; `db_uuid` tidak cocok `invalid`; `days_left` sesuai

### Implementation for Foundation

- [x] T011 Implementasi `addons/pos_saas_license/models/license_verifier.py` (Python murni, tanpa ORM): konstanta `PUBLIC_KEYS = {kid: public_key_b64}`, `class LicenseError(Exception)` dengan atribut `code` dan `message`, dataclass `LicensePayload`, `_b64url_decode` (tambah padding), `decode_and_verify(token, public_keys=None) -> LicensePayload` (cek 3 bagian, `alg == "EdDSA"`, `typ == "SAAS-LIC"`, `kid` dikenal, verifikasi signature, lalu `_validate_payload` sesuai `contracts/license-token-schema.json` termasuk aturan `allOf` until/typ dan `additionalProperties: false`). Tanpa dependency `jsonschema`
- [ ] T012 Tambahkan `compute_state(payload, today, db_uuid, warning_days=14) -> (state, days_left, reason)` di `addons/pos_saas_license/models/license_verifier.py` sesuai tabel "Aturan Perhitungan Status" di `data-model.md`
- [ ] T013 [P] Implementasi `addons/pos_saas_license/models/pos_saas_license_log.py`: model `pos.saas.license.log`, `_order = "event_date desc"`, field `license_id` Many2one `pos.saas.license` ondelete="cascade", `event_type` Selection required `[('installed', 'Token Installed'), ('verified', 'Signature Verified'), ('warning', 'Warning Triggered'), ('grace_entered', 'Grace Period Entered'), ('expired', 'License Expired'), ('blocked', 'Session Open Blocked'), ('clock_tamper', 'Clock Rollback Detected'), ('invalid_token', 'Invalid Signature')]`, `event_date` Datetime default now index, `user_id` Many2one `res.users`, `details` Text readonly
- [ ] T014 Implementasi `addons/pos_saas_license/models/pos_saas_license.py`: model `pos.saas.license` dengan field sesuai `data-model.md` (`name` Required Default="SaaS License"; `license_type` Selection `[('subscription', 'Subscription'), ('perpetual', 'Perpetual (Beli Putus)')]`; `state` Default='invalid'; `grace_period_days` Default=7; `max_pos_registers` Default=1; `allowed_modules`, `key_id`, `last_verified_at`, `last_seen_timestamp`; computed `days_remaining`, `state_message`), constraint `CHECK(grace_period_days >= 0)` dan `CHECK(max_pos_registers >= 1)` serta index `(license_id, state)` memakai sintaks hasil T007(e). Method: `_get_current()` (ambil atau buat singleton via sudo), `_today()` (tanggal lokal tz company, fallback `Asia/Jakarta`), `_get_database_uuid()` (`ir.config_parameter` `database.uuid`), `_evaluate()` (selalu verifikasi ulang `raw_token`, return dict state/days_left/reason/payload), `_refresh_cache()` (tulis kolom cache, catat log hanya saat state berubah), `action_install_token(token)` (simpan token, catat `installed` atau `invalid_token`), `_log_event(event_type, details)`
- [ ] T015 [P] Buat `addons/pos_saas_license/data/pos_saas_license_data.xml` berisi record singleton awal `noupdate="1"` dengan `name` "SaaS License"
- [ ] T016 [P] Buat `addons/pos_saas_license/security/ir.model.access.csv`: `pos.saas.license` read untuk `point_of_sale.group_pos_user`, read/write/create untuk `point_of_sale.group_pos_manager`; `pos.saas.license.log` read untuk `point_of_sale.group_pos_manager`; tanpa unlink untuk siapa pun kecuali `base.group_system`
- [ ] T017 Daftarkan model di `addons/pos_saas_license/models/__init__.py`, test di `addons/pos_saas_license/tests/__init__.py`, dan file data/security di `addons/pos_saas_license/__manifest__.py`

**Checkpoint**: T009 dan T010 lulus. Token bisa dipasang via shell Odoo dan status terhitung benar

---

## Phase 3: User Story 1 - Validasi Lisensi Langganan & Penguncian Sesi Kasir (Priority: P1) MVP

**Goal**: Kasir tidak bisa membuka atau melanjutkan sesi bila lisensi `expired`/`invalid`, kuota register ditegakkan, merchant bisa memasang token dari Settings, semua offline

**Independent Test**: Pasang token subscription dengan `until` H-9 (lewat grace 7 hari) lalu klik buka sesi: ditolak dengan pesan jelas. Pasang token aktif: sesi terbuka tanpa koneksi internet

### Tests for User Story 1

- [ ] T018 [P] [US1] Tulis `addons/pos_saas_license/tests/test_pos_session_license.py`: `open_ui` sukses untuk `active`, `warning`, `grace`; `UserError` untuk `expired`, `invalid`, dan tanpa token, disertai log `blocked`; `open_frontend_cb` ditolak setelah lisensi menjadi expired; tidak ada panggilan jaringan saat pengecekan (patch `requests`/`urllib` agar raise); clock rollback lebih dari 1 jam memblokir dan mencatat `clock_tamper`, mundur kurang dari 1 jam diizinkan; `last_seen_timestamp` bertambah setelah buka sesi
- [ ] T019 [P] [US1] Tulis `addons/pos_saas_license/tests/test_pos_register_quota.py`: dengan `max_reg=2`, sesi pada config ke-1 dan ke-2 boleh terbuka, config ke-3 ditolak dengan pesan kuota penuh; setelah salah satu sesi `closed`, config ke-3 boleh dibuka; membuat `pos.config` baru tetap diizinkan
- [ ] T020 [P] [US1] Tulis `addons/pos_saas_license/tests/test_license_settings.py`: `action_saas_license_verify` dari `res.config.settings` memasang token valid, menampilkan state, dan menolak token rusak dengan pesan yang jelas tanpa menimpa token lama yang valid

### Implementation for User Story 1

- [ ] T021 [US1] Tambahkan `check_pos_access(raise_error=True)` dan `_check_clock_rollback()` di `addons/pos_saas_license/models/pos_saas_license.py`: evaluasi ulang token, blokir bila `expired`/`invalid` atau waktu sekarang lebih mundur dari `last_seen_timestamp` lebih dari 1 jam, catat log `blocked`/`clock_tamper`, perbarui `last_seen_timestamp` bila lolos. Pesan error memakai terjemahan sesuai hasil T007(h)
- [ ] T022 [P] [US1] Implementasi `addons/pos_saas_license/models/pos_config.py`: override `open_ui()` memanggil `check_pos_access()` sebelum `super()`
- [ ] T023 [P] [US1] Implementasi `addons/pos_saas_license/models/pos_session.py`: override `create(vals_list)` (cek lisensi lalu kuota: jumlah `pos.config` berbeda dengan sesi `state != 'closed'` ditambah config yang akan dibuka tidak boleh melebihi `max_pos_registers`) dan `open_frontend_cb()` (cek lisensi)
- [ ] T024 [US1] Implementasi `addons/pos_saas_license/models/res_config_settings.py`: field `saas_license_token` (Char, bukan config_parameter), field related/compute read-only untuk state, `license_id`, merchant, `license_type`, `valid_until`, sisa hari, `database.uuid`, register terpakai/maksimum, `allowed_modules`; method `action_saas_license_verify()` yang memanggil `action_install_token`
- [ ] T025 [US1] Buat `addons/pos_saas_license/views/res_config_settings_views.xml`: block "SaaS License" di settings POS (XPath dari T007(g)) berisi field token, tombol "Verify & Activate License", badge status (hijau `active`, kuning `warning`, oranye `grace`, merah `expired`/`invalid`), dan detail lisensi read-only
- [ ] T026 [P] [US1] Buat `addons/pos_saas_license/views/pos_saas_license_views.xml`: form read-only `pos.saas.license`, list `pos.saas.license.log`, action dan menu "SaaS License Log" di bawah Point of Sale > Configuration khusus `point_of_sale.group_pos_manager`
- [ ] T027 [US1] Daftarkan `pos_config`, `pos_session`, `res_config_settings` di `addons/pos_saas_license/models/__init__.py` dan kedua view di `data` `addons/pos_saas_license/__manifest__.py`

**Checkpoint**: T018 s.d. T020 lulus. Skenario 1 dan 2 di `quickstart.md` berjalan manual

---

## Phase 4: User Story 2 - Lisensi Beli Putus (Perpetual) dengan Instance Binding (Priority: P2)

**Goal**: Token perpetual aktif tanpa batas waktu dan hanya berlaku di database dengan `database.uuid` yang sama

**Independent Test**: Pasang token perpetual dengan `db_uuid` yang cocok, set tanggal ke 2099: sesi terbuka. Pasang token perpetual dengan `db_uuid` lain: sesi ditolak

### Tests for User Story 2

- [ ] T028 [P] [US2] Tulis `addons/pos_saas_license/tests/test_perpetual_binding.py`: perpetual `active` pada tanggal 2099 dan `days_remaining` tidak dihitung; `db_uuid` tidak cocok menghasilkan `invalid`, `open_ui` ditolak, log `invalid_token` tercatat; mengganti `database.uuid` setelah token terpasang membuat status berubah ke `invalid` pada pengecekan berikutnya

### Implementation for User Story 2

- [ ] T029 [US2] Di `addons/pos_saas_license/models/pos_saas_license.py`, pastikan `_evaluate()` memberi `reason` yang jelas untuk `db_uuid` mismatch (tampilkan `database.uuid` saat ini agar merchant bisa meminta token baru) dan `days_remaining` bernilai 0 serta label "Lifetime" untuk perpetual
- [ ] T030 [US2] Di `addons/pos_saas_license/views/res_config_settings_views.xml`, tampilkan "Valid Until: Lifetime" untuk perpetual dan field `database.uuid` yang mudah disalin

**Checkpoint**: T028 lulus, US1 tetap lulus

---

## Phase 5: User Story 3 - Notifikasi Bertingkat & Grace Period di Antarmuka Kasir (Priority: P3)

**Goal**: Banner kuning (H-14 s.d. H0) dan oranye (grace) di layar kasir, serta mode read-only untuk sesi yang sudah terbuka saat lisensi expired

**Independent Test**: Token dengan `until` H+5 dari hari ini: banner kuning di kasir. Token yang sudah masuk grace: banner oranye, transaksi tetap bisa. Sesi terbuka lalu lisensi lewat grace: order baru ditolak server dan tombol Payment nonaktif

### Tests for User Story 3

- [ ] T031 [P] [US3] Tulis `addons/pos_saas_license/tests/test_pos_order_readonly.py`: sinkronisasi order (method dari T007(d)) ditolak saat `expired`/`invalid`, diterima saat `grace`; `last_seen_timestamp` bertambah saat order diterima
- [ ] T032 [P] [US3] Tulis `addons/pos_saas_license/tests/test_pos_load_data.py`: data yang dimuat loader POS (method dari T007(c)) memuat `license_state`, `license_days_left`, `license_banner_msg` dengan nilai sesuai state

### Implementation for User Story 3

- [ ] T033 [US3] Di `addons/pos_saas_license/models/pos_session.py`, tambahkan field compute `license_state`, `license_days_left`, `license_banner_msg` dan daftarkan ke loader data POS sesuai hasil T007(c)
- [ ] T034 [P] [US3] Implementasi `addons/pos_saas_license/models/pos_order.py`: override method sinkronisasi order dari T007(d) untuk memanggil pengecekan lisensi (tanpa clock rollback block, cukup tolak `expired`/`invalid`) dan memperbarui `last_seen_timestamp`; daftarkan di `addons/pos_saas_license/models/__init__.py`
- [ ] T035 [P] [US3] Buat komponen OWL `addons/pos_saas_license/static/src/app/license_banner/license_banner.js` yang membaca state lisensi dari data sesi POS
- [ ] T036 [P] [US3] Buat template `addons/pos_saas_license/static/src/app/license_banner/license_banner.xml`: `bg-warning text-dark` untuk `warning` dengan teks sisa hari, `bg-danger text-white` untuk `grace` dan `expired`
- [ ] T037 [P] [US3] Buat `addons/pos_saas_license/static/src/app/license_banner/license_banner.scss` untuk posisi banner di atas navbar
- [ ] T038 [US3] Buat `addons/pos_saas_license/static/src/app/license_banner/pos_patch.js` dan template inherit-nya: render `LicenseBanner` di Navbar (path dari T007(f)) dan nonaktifkan tombol Payment saat `license_state` `expired`/`invalid`
- [ ] T039 [US3] Daftarkan aset `static/src/app/license_banner/**/*` ke bundle `point_of_sale._assets_pos` di `addons/pos_saas_license/__manifest__.py`
- [ ] T040 [US3] Verifikasi manual Skenario 3 di `specs/001-pos-saas-license/quickstart.md` untuk H-5, grace H+3, dan expired dengan sesi yang sudah terbuka

**Checkpoint**: T031 dan T032 lulus, banner tampil sesuai state, US1 dan US2 tetap lulus

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Cron harian, heartbeat opsional, dokumentasi, dan validasi CI

- [ ] T041 [P] Tulis `addons/pos_saas_license/tests/test_license_cron.py`: cron mencatat log transisi (`warning`, `grace_entered`, `expired`) sekali per perubahan state, memperbarui `last_seen_timestamp`, tidak memanggil jaringan bila `saas.license.server_url` kosong, dan tetap sukses bila heartbeat gagal (patch HTTP agar raise)
- [ ] T042 Tambahkan `_cron_daily_check()` dan `_send_heartbeat()` di `addons/pos_saas_license/models/pos_saas_license.py`: heartbeat hanya untuk subscription, hanya bila `saas.license.server_url` diisi, timeout 5 detik, semua exception ditangkap dan dicatat ke logger tanpa mengubah state
- [ ] T043 Buat `addons/pos_saas_license/data/ir_cron_data.xml` dengan cron "POS SaaS License: Daily Expiration Check" interval 1 hari pukul 00:05 UTC memanggil `model._cron_daily_check()`, lalu daftarkan di `addons/pos_saas_license/__manifest__.py`
- [ ] T044 [P] Pastikan semua pesan user-facing di `addons/pos_saas_license/models/*.py` dibungkus mekanisme terjemahan Odoo 20 (hasil T007(h))
- [ ] T045 [P] Perbarui `specs/001-pos-saas-license/quickstart.md` bila ada perbedaan nama menu, field, atau perintah setelah implementasi
- [ ] T046 Jalankan `ruff check addons/pos_saas_license scripts/license_tools`, `ruff format --check addons/pos_saas_license scripts/license_tools`, dan `xmllint --noout` untuk semua XML modul; perbaiki temuan
- [ ] T047 Jalankan test modul sesuai `quickstart.md` bagian 4 (`--test-tags=/pos_saas_license`) dan pastikan job "Odoo Module Test" di `.github/workflows/ci.yml` mendeteksi modul ini

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Tanpa dependensi. T007 butuh akses ke source Odoo 20 (container berjalan atau source branch `20.0`)
- **Foundational (Phase 2)**: Bergantung pada Phase 1, memblokir semua story
- **US1 (Phase 3)**: Bergantung pada Phase 2
- **US2 (Phase 4)**: Bergantung pada Phase 2 dan T021/T022 (blokir buka sesi) serta T024/T025 (halaman settings) dari US1
- **US3 (Phase 5)**: Bergantung pada Phase 2. T033 menyentuh `pos_session.py` yang sama dengan T023, jadi dikerjakan setelah T023
- **Polish (Phase 6)**: Setelah story yang diinginkan selesai

### Within Each Story

- Test ditulis dulu dan dipastikan gagal
- Method model inti (`pos_saas_license.py`) sebelum override `pos.config`/`pos.session`/`pos.order`
- Override backend sebelum view dan aset frontend
- Registrasi di `__init__.py`/`__manifest__.py` di akhir story

### File yang Disentuh Banyak Task (kerjakan berurutan)

- `addons/pos_saas_license/models/pos_saas_license.py`: T014, T021, T029, T042
- `addons/pos_saas_license/models/pos_session.py`: T023, T033
- `addons/pos_saas_license/views/res_config_settings_views.xml`: T025, T030
- `addons/pos_saas_license/__manifest__.py`: T002, T017, T027, T039, T043

### Parallel Opportunities

- Phase 1: T003, T004, T005, T006 paralel
- Phase 2: T008, T009, T010 paralel; T013, T015, T016 paralel dengan T011/T012
- US1: T018, T019, T020 paralel; T022 dan T023 paralel setelah T021; T026 paralel dengan T024/T025
- US3: T031, T032 paralel; T034, T035, T036, T037 paralel

---

## Parallel Example: User Story 1

```bash
# Test US1 sekaligus:
Task: "Tulis test_pos_session_license.py"
Task: "Tulis test_pos_register_quota.py"
Task: "Tulis test_license_settings.py"

# Setelah T021 selesai:
Task: "Override open_ui di models/pos_config.py"
Task: "Override create & open_frontend_cb di models/pos_session.py"
```

## Parallel Example: User Story 3

```bash
Task: "Override sinkronisasi order di models/pos_order.py"
Task: "Komponen license_banner.js"
Task: "Template license_banner.xml"
Task: "Style license_banner.scss"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Selesaikan Phase 1 (termasuk T007, verifikasi API Odoo 20)
2. Selesaikan Phase 2
3. Selesaikan Phase 3 (US1)
4. Berhenti dan validasi: test US1 lulus, Skenario 1 dan 2 quickstart berjalan
5. Demo

### Incremental Delivery

1. Setup + Foundational: verifier dan model siap
2. US1: penguncian sesi dan settings (MVP)
3. US2: perpetual dan binding `database.uuid`
4. US3: banner dan read-only di layar kasir
5. Polish: cron, heartbeat opsional, CI

---

## Notes

- Keputusan desain mengacu pada `spec.md` bagian Clarifications sesi 2026-10-16
- Status lisensi tidak pernah dibaca dari kolom cache untuk keputusan izin (FR-013)
- Private key hanya ada di mesin penerbit token, tidak di repository maupun di container merchant
- Commit per task atau per kelompok task yang logis
