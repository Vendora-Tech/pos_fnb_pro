# Quickstart Guide: Testing & Verifying `pos_saas_license`

**Feature**: `001-pos-saas-license`  
**Date**: 2026-10-06  
**Status**: Completed (Phase 1–Phase 6 Implementation Ready)

---

## 1. Menghasilkan Pasangan Kunci & Token Uji Coba (CLI)

Gunakan tool di `scripts/license_tools/` (lihat `scripts/license_tools/README.md`). Private key disimpan di luar repository atau di path yang di-ignore git.

```bash
# 1. Buat keypair dev. Public key + kid dicetak untuk ditempel ke PUBLIC_KEYS di license_verifier.py
python scripts/license_tools/generate_keypair.py --kid dev2026 --out ~/.pos_saas_keys/dev2026.pem

# 2. Terbitkan token. db_uuid diambil dari halaman License Management (field Database UUID)
python scripts/license_tools/issue_token.py \
  --key ~/.pos_saas_keys/dev2026.pem --kid dev2026 \
  --lid LIC-2026-TEST-001 --mch "Toko Sukses Makmur" \
  --typ subscription --db-uuid <DATABASE_UUID> \
  --max-reg 2 --from 2026-01-01 --until 2026-12-31 --grace 7
```

Format token: `header.payload.signature` (base64url tanpa padding). Header `{"alg":"EdDSA","typ":"SAAS-LIC","kid":"dev2026"}`, signature Ed25519 atas `header_b64 + "." + payload_b64`. Untuk perpetual gunakan `--typ perpetual` tanpa `--until`.

---

## 2. Pemasangan Modul di Odoo 20

1. Kerangka modul ditempatkan di: `addons/pos_saas_license/`.
2. Update list aplikasi dan install modul melalui Makefile:
   ```bash
   make restart-upgrade MODULE=pos_saas_license
   ```

---

## 3. Langkah Pengujian di Antarmuka Odoo 20

### Skenario 1: Input Lisensi Valid
1. Buka menu **Point of Sale $\rightarrow$ Configuration $\rightarrow$ Settings $\rightarrow$ SaaS License**.
2. Salin string token hasil generator dan tempel pada field **License Token**.
3. Klik tombol **Verify & Activate License**.
4. Status berubah menjadi **Active** dengan indikator badge hijau.
5. Masuk ke dashboard POS dan buka kasir $\rightarrow$ Sesi terbuka lancar.

### Skenario 2: Simulasi Token Kedaluwarsa (Expired)
1. Generate token baru dengan `"until": "2026-01-01"` (tanggal lampau melewati grace period).
2. Tempel token ke form Settings dan klik simpan.
3. Status berubah menjadi **Expired** dengan badge merah.
4. Buka kasir $\rightarrow$ Muncul dialog popup: *"Masa aktif lisensi telah berakhir. Silakan hubungi admin untuk perpanjangan."* Sesi ditolak terbuka.

### Skenario 3: Simulasi Banner Peringatan di Kasir (OWL UI)
1. Generate token dengan `"until"` 5 hari dari hari ini.
2. Status lisensi menjadi **Expiring Soon** (Warning).
3. Buka sesi kasir $\rightarrow$ Banner kuning muncul di navbar atas: *"⚠️ Lisensi aktif tersisa 5 hari lagi."*

---

## 4. Eksekusi Unit Test Otomatis Odoo

Jalankan test suite menggunakan container Odoo 20:

```bash
docker compose exec -T odoo20 odoo \
  --test-enable \
  --stop-after-init \
  -d pos \
  -u pos_saas_license \
  --test-tags=/pos_saas_license
```

---

## 5. Eksekusi Otomatisasi Uji Browser E2E (Playwright)

Pengujian end-to-end menyeluruh mencakup otentikasi login, dashboard POS, banner lisensi OWL 3, navigasi server lisensi, transaksi checkout kasir, hingga pengujian mode hard-block saat lisensi kedaluwarsa.

### Menjalankan Seluruh Suite E2E

```bash
# Eksekusi seluruh test suite E2E secara headless dengan reporter list
npx playwright test --reporter=list

# Menjalankan spesifik test flow POS
npx playwright test tests/e2e/pos_flow.spec.ts --reporter=list
```

### Cakupan Skenario E2E yang Diuji

| No | Skenario Uji | Deskripsi Validasi | Bukti Artefak |
|---|---|---|---|
| 1 | **Smoke Health Check** | Ketersediaan server Odoo 20 dan verifikasi title HTML | Lulus (HTTP 200) |
| 2 | **Web Login & Routing** | Form login `e2e_tester` dan redirect ke `/odoo` | Lulus |
| 3 | **Dashboard POS** | Kanban config Point of Sale toko `Bakery Shop` | Lulus |
| 4 | **POS UI & Banner OWL 3** | Kasir `/pos/ui/1`, banner lisensi `.pos-saas-license-banner` | `screenshots/e2e-pos-ui-license-banner.png` |
| 5 | **License Server HQ** | Akses view record lisensi merchant `diva resto` | Lulus |
| 6 | **Access Management RBAC** | Akses view aturan granular `saas_access_management` | Lulus |
| 7 | **Checkout Flow E2E** | Tambah produk ke cart, buka Payment, validasi feedback receipt | `screenshots/e2e-pos-checkout-success.png` |
| 8 | **Hard-Block Expired Mode** | Token kedaluwarsa, pesan banner peringatan, tombol Payment nonaktif | `screenshots/e2e-pos-hardblock-expired.png` |

