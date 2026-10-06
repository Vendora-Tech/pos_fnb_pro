# 🚀 Master Blueprint & Architecture: SaaS POS Ecosystem (Odoo 20)

Dokumen ini merupakan rangkuman komprehensif dari seluruh hasil riset, arsitektur teknis, konfigurasi infrastruktur, dan analisis kebutuhan fitur untuk pembangunan platform **SaaS Point of Sale (POS)** berbasis **Odoo 20.0 (LTS 2026)**.

---

## 📑 Daftar Isi
1. [Visi & Strategi Produk](#1-visi--strategi-produk)
2. [Status Infrastruktur & Environment Odoo 20](#2-status-infrastruktur--environment-odoo-20)
3. [Universal Core Foundation (Fondasi Wajib SaaS)](#3-universal-core-foundation-fondasi-wajib-saas)
4. [Analisis & Pemetaan 6 Kategori Toko](#4-analisis--pemetaan-6-kategori-toko)
5. [Arsitektur Self-Order & Kiosk Ecosystem](#5-arsitektur-self-order--kiosk-ecosystem)
6. [Struktur Packaging & Tiering Bisnis](#6-struktur-packaging--tiering-bisnis)
7. [Roadmap Eksekusi Teknis (Spec-Kit Workflow)](#7-roadmap-eksekusi-teknis-spec-kit-workflow)
8. [Arsitektur Lisensi & Monetisasi (Token Expire vs Beli Putus)](#8-arsitektur-lisensi--monetisasi-token-expire-vs-beli-putus)
9. [Arsitektur Visual Access Management & Anti-Fraud](#9-arsitektur-visual-access-management--anti-fraud)

---

## 1. Visi & Strategi Produk

Membangun platform **SaaS Point of Sale (POS)** siap jual dengan target utama pasar Indonesia, mengombinasikan keunggulan antarmuka modern Odoo 20 (OWL Framework, Offline-first IndexedDB, WebSerial hardware integration) dengan kebutuhan lokal (QRIS dinamis, direct thermal print, kontrol anti-fraud, dan self-ordering).

### Prinsip Utama:
* **Multi-Tenant Isolation:** Menggunakan model *Database-per-tenant* untuk keamanan maksimal dan kebebasan backup/restore per merchant.
* **Modular Add-On Architecture:** Modul dikemas terpisah di folder `addons/` sehingga merchant hanya mengaktifkan modul sesuai industrinya (F&B vs Retail).
* **Zero Browser Print Dialog:** Integrasi pencetakan struk kasir dan tiket dapur langsung ke hardware printer (ESC/POS).

---

## 2. Status Infrastruktur & Environment Odoo 20

Environment pengembangan telah dikonfigurasi penuh dan berjalan aktif:

```
┌───────────────────────────────────────────────────────────────┐
│                    DOCKER COMPOSE TOPOLOGY                    │
├───────────────────────────────┬───────────────────────────────┤
│ Container: odoo20-pos-odoo20-1│ Container: odoo20-pos-db-1    │
│ Image: odoo:20 (v20.0-2026)   │ Image: postgres:18            │
│ Port Web: 10020 -> 8069       │ Internal Network: 5432        │
│ Port Chat: 20020 -> 8072      │ (Isolasi total dari host)     │
└───────────────────────────────┴───────────────────────────────┘
```

### Konfigurasi Keamanan yang Diterapkan:
1. **Hardening Kredensial Default:** Menghapus default bawaan open-source (`minhng.info` dan `odoo20@2026`).
2. **Isolasi Lingkungan via `.env`:** Master password, user database, dan port diisolasi di file `.env` yang dilindungi `.gitignore`.
3. **Automasi Manajemen via `Makefile`:**
   - `make up-d` : Menjalankan container di background.
   - `make scaffold MODULE=<name>` : Kerangka otomatis modul Odoo baru di `addons/`.
   - `make restart-upgrade MODULE=<name>` : Upgrade modul instan dengan validasi HTTP registry.
4. **Git Repository Sync:**
   - Folder `addons/` terhubung langsung ke repositori GitHub: **`Pendora-nikki/pos-20`** (Branch: `main`).
5. **Antigravity Skill `odoo-20.0`:**
   - Terpasang di `~/.gemini/config/skills/odoo-20.0/` dengan 18 panduan referensi resmi yang tervalidasi langsung terhadap source code Odoo 20.

---

## 3. Universal Core Foundation (Fondasi Wajib SaaS)

Setiap toko (tanpa memandang jenis industrinya) wajib dibekali modul-modul fondasi berikut:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   UNIVERSAL CORE MODULES (SAAS BASE)                   │
├────────────────────────┬───────────────────────────────────────────────┤
│ Modul Teknis           │ Fungsi Kritis                                 │
├────────────────────────┼───────────────────────────────────────────────┤
│ pos_saas_core          │ Identitas toko, branding logo struk, tenant   │
│ pos_saas_license       │ Kontrol lisensi kriptografis (Token/Putus)    │
│ saas_access_management │ Visual Role Policy (Hide Field/Btn/Menu/Export│
│ pos_id_qris            │ Integrasi QRIS Dinamis (Midtrans/Xendit)      │
│ pos_id_thermal         │ Direct Raw ESC/POS print (USB/BT/LAN 58/80mm) │
│ pos_cashier_lock       │ Anti-fraud (PIN supervisor untuk void/diskon) │
│ pos_cash_shift         │ Pencatatan modal awal kasir & closing shift   │
│ pos_customer_screen    │ Layar display pelanggan (rincian belanja/QRIS)│
└────────────────────────┴───────────────────────────────────────────────┘
```

---

## 4. Analisis & Pemetaan 6 Kategori Toko

Berdasarkan layar inisialisasi Odoo **"Choose your store"**, berikut adalah peta kebutuhan modul hasil riset Odoo Apps Store:

### 1. 👕 Clothes (Fashion, Apparel & Butik) — *"Multi colors and sizes"*
* **Tantangan:** 1 produk memiliki puluhan SKU varian (Warna x Ukuran).
* **Modul Solusi:**
  - `pos_product_variant_matrix` : Pop-up grid matriks ukuran (S/M/L) x warna dalam satu klik.
  - `product_barcode_labels` : Cetak stiker barcode SKU per varian untuk hangtag baju.
  - `pos_order_return` / `pos_exchange` : Validasi retur barang dan tukar ukuran via scan struk lama.
  - `pos_loyalty` : Program reward poin member dan diskon khusus langganan.

### 2. 🛋️ Furniture (Mebel & Perkakas Rumah) — *"Stock, configurator, replenishment"*
* **Tantangan:** Barang besar (*bulky*), pengiriman terjadwal, dan sistem DP (*Down Payment*).
* **Modul Solusi:**
  - `pos_partial_payment` : Terima pembayaran DP 30%, pencatatan sisa saldo tagihan, dan pelunasan saat kirim.
  - `pos_delivery_order` : Input alamat kirim langsung di kasir yang memicu Surat Jalan (*Picking*) di gudang.
  - `pos_product_configurator` : Pilihan opsi rakitan (jenis kayu, kain jok sofa, finishing pelitur).
  - `pos_lot_serial` & `pos_warranty` : Input nomor seri barang untuk pelacakan garansi resmi.

### 3. 🥐 Bakery (Toko Roti & Pastry) — *"Food, but over the counter"*
* **Tantangan:** Transaksi konter kilat, pemotongan stok bahan resep, dan pesanan kue custom.
* **Modul Solusi:**
  - `create_manufacturing_order_from_pos` / `pos_product_bom` : Pemotongan otomatis bahan baku (tepung, telur, mentega) saat roti terjual.
  - `pos_preorder_cake` : Form pesanan kue ulang tahun di kasir (catatan tulisan lilin/cokelat, tanggal/jam ambil, DP).
  - `pos_scale` / `iot_webserial` : Integrasi timbangan digital USB untuk kue kiloan / cookies curah.
  - `stock_lot_expiry` : Kontrol kedaluwarsa batch roti untuk mencegah display produk basi.

### 4. 🍔 Restaurant (Resto Dine-In & Kafe) — *"Tables, menus, kitchen display"*
* **Tantangan:** Denah meja, pesanan dapur tanpa kertas, split tagihan, dan menu paket.
* **Modul Solusi:**
  - `pos_restaurant` *(Native)* : Denah visual meja, pindah meja, dan gabung meja.
  - `pos_kitchen_screen` (KDS) : Layar tablet dapur (Station Kitchen, Bar, Grill) dengan indikator waktu masak.
  - `aspl_pos_combo` : Menu paket bundling hemat (Nasi + Ayam + Minum) dengan opsi rasa.
  - `pos_product_modifier` : Opsi catatan menu (level pedas, es dipisah, tanpa seledri).
  - `pos_takeaway_charge` : Pemisahan pesanan makan di tempat vs bungkus dengan biaya kemasan otomatis.

### 5. 🍸 Bar (Pub, Lounge, Coffee Bar) — *"Floor plan, tips, self order"*
* **Tantangan:** Open tab (pesan berkali-kali bayar akhir), happy hour, dan tips bartender.
* **Modul Solusi:**
  - `pos_open_tab` / `pos_customer_tab` : Membuka tagihan di awal, tamu bebas order ronde minuman berikutnya.
  - `pos_timed_pricelist` (Happy Hour) : Diskon minuman otomatis pada rentang jam tertentu (misal: 17:00 - 20:00).
  - `pos_tip_management` : Input tip untuk bartender dan persentase service charge otomatis.
  - `pos_self_order` *(Native)* : Scan QR meja bar untuk memesan langsung dari smartphone tamu.

### 6. 🛒 Retail (Minimarket, Toko Kelontong, Supermarket) — *"Any shop"*
* **Tantangan:** Kecepatan kasir tinggi (*antrean panjang*), puluhan ribu SKU, barcode scanner kilat.
* **Modul Solusi:**
  - `pos_fast_scan` : Scan barcode beruntun otomatis tanpa delay jeda kursor.
  - `sh_pos_realtime_stock_update` : Tampilan sisa stok real-time di tombol produk dan peringatan anti-minus.
  - `pos_multi_uom` (Grosir) : Otomatisasi harga bertingkat beli eceran (Pcs) vs karton (Dus).
  - `pos_promotions` : Skema diskon retail modern (Beli 1 Gratis 1 / Buy X Get Y).

---

## 5. Arsitektur Self-Order & Kiosk Ecosystem

Salah satu keunggulan terbesar Odoo 20 adalah dukungan native terhadap **`pos_self_order`** dan modul pembayaran lokal **`l10n_id_pos_self_order_qris`**.

```
                           ┌─────────────────────────┐
                           │    METODE SELF-ORDER    │
                           └────────────┬────────────┘
                                        │
                 ┌──────────────────────┴──────────────────────┐
                 ▼                                             ▼
     ┌───────────────────────┐                     ┌───────────────────────┐
     │   TABLE QR (BYOD)     │                     │    KIOSK TERMINAL     │
     │  (Scan QR di Meja HP) │                     │ (Layar Sentuh Mesin)  │
     └───────────┬───────────┘                     └───────────┬───────────┘
                 │                                             │
                 │   [ Pesan & Bayar QRIS Instan di HP / Kasir] │
                 │   [ Cetak Tiket Nomor Antrean di Kiosk ]    │
                 ▼                                             ▼
     ┌─────────────────────────────────────────────────────────────────────┐
     │             KITCHEN DISPLAY SYSTEM (KDS) & ROUTING                  │
     │     Pesanan masuk otomatis ke Station Dapur (Kitchen / Bar)         │
     └──────────────────────────────────┬──────────────────────────────────┘
                                        ▼
     ┌─────────────────────────────────────────────────────────────────────┐
     │              QUEUE CALLING SCREEN (TV DISPLAY CONTER)               │
     │       "Nomor Antrean 105 Silakan Mengambil Pesanan di Konter"       │
     └─────────────────────────────────────────────────────────────────────┘
```

---

## 6. Struktur Packaging & Tiering Bisnis

Untuk kemudahan penjualan SaaS dan pemeliharaan kode, seluruh modul dikemas ke dalam **2 Vertikal Utama**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SAAS POS UNIVERSAL CORE                         │
│       (QRIS Dinamis, Direct ESC/POS, Anti-Fraud Kasir, Shift Kas)      │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │                                │
                    ▼                                ▼
       ┌────────────────────────┐       ┌────────────────────────┐
       │     PAKET F&B PRO      │       │   PAKET RETAIL PRO     │
       │ (Resto, Bakery, Bar)   │       │(Minimarket, Baju, Mebel│
       ├────────────────────────┤       ├────────────────────────┤
       │ • Kitchen Display (KDS)│       │ • Matriks Ukuran/Warna │
       │ • Denah Meja & Split   │       │ • Multi-UOM / Grosir   │
       │ • Resep BoM Bahan Baku │       │ • Fast Barcode Scan    │
       │ • Combo & Modifiers    │       │ • DP & Delivery Order  │
       │ • Table QR Self-Order  │       │ • Stok Fisik Realtime  │
       └────────────────────────┘       └────────────────────────┘
```

---

## 7. Roadmap Eksekusi Teknis (Spec-Kit Workflow)

Langkah terstruktur berikutnya menggunakan skill **Spec-Kit** yang sudah terpasang:

1. **Phase 1 (Specification - `speckit-specify`):**
   - Mengunci dokumen spesifikasi `spec.md` untuk MVP (fokus: Core Kasir, QRIS Dinamis, Thermal Print, dan Anti-Fraud).
2. **Phase 2 (Clarification - `speckit-clarify`):**
   - Mengonfirmasi parameter teknis kritis (gateway provider, model multi-tenancy, batasan hak akses).
3. **Phase 3 (Technical Planning - `speckit-plan`):**
   - Merancang struktur arsitektur modul di `addons/` (Python model, OWL component, QWeb layout).
4. **Phase 4 (Task Breakdown & Implementation - `speckit-tasks` & `speckit-implement`):**
   - Memecah tugas koding secara terurut dan mengeksekusi penulisan modul langsung di repository `addons/`.

---

## 8. Arsitektur Lisensi & Monetisasi (Token Expire vs Beli Putus)

Untuk mendukung model bisnis fleksibel bagi merchant skala UMKM hingga korporat, sistem SaaS POS mengimplementasikan modul lisensi khusus: **`pos_saas_license`**.

### 8.1. Prinsip Keamanan Kriptografis (Asymmetric Cryptography)

Untuk mencegah merchant memanipulasi database secara manual (misal mengubah tanggal expired langsung di tabel PostgreSQL), validasi lisensi mengadopsi skema tanda tangan digital asimetris (**RSA / Ed25519**):

```
 ┌────────────────────────────────────────────────────────┐
 │       CENTRAL SAAS / LICENSING SERVER (Penyedia SaaS)  │
 │  - Memegang PRIVATE KEY (Rahasia Utama)                │
 │  - Generate License Token / Key terenkripsi untuk merchant│
 └───────────────────────────┬────────────────────────────┘
                             │
            Mengirim Token Lisensi (JWT / Base64 Encrypted)
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │        ODOO MERCHANT (Container odoo20 Client)         │
 │  - Memegang PUBLIC KEY (Hanya untuk verifikasi)        │
 │  - Memvalidasi masa berlaku & hardware fingerprint     │
 └────────────────────────────────────────────────────────┘
```

> [!IMPORTANT]
> **Realitas Batasan Keamanan (*Threat Model & Anti-Tamper*):**
> * **Keamanan Token Kriptografis:** Tanda tangan asimetris memastikan token tidak dapat dipalsukan atau diubah isinya (*tamper-proof payload*) tanpa memegang Private Key.
> * **Model Cloud-Hosted SaaS (Database-per-tenant di server penyedia):** Proteksi ini **sangat kuat dan efektif**, karena merchant tidak memiliki akses root ke server, container, maupun source code Odoo.
> * **Model On-Premise / Self-Hosted (Server milik merchant):** Bersifat menghalangi pelanggaran kasual (*casual / non-technical infringement*). Merchant yang memiliki akses `root` ke server fisik masih memiliki celah untuk mengedit file Python modul (misal menghapus blok pengecekan lisensi) atau memanipulasi jam sistem (*system clock rollback*).

---

### 8.2. Perbandingan Dua Model Penjualan

| Parameter | 🔄 Model Langganan (*Subscription / Token Expire*) | 🏷️ Model Beli Putus (*Perpetual / Non-Expire*) |
| :--- | :--- | :--- |
| **Masa Aktif (`valid_until`)** | Berbatas waktu (Bulanan / Tahunan). | **Permanen / Lifetime** (`null` atau tahun `9999`). |
| **Proteksi Duplikasi** | Otomatis terkunci saat tanggal jatuh tempo habis. | **Hardware/Instance Binding** (Identitas unik server). |
| **Ketergantungan Internet** | Boleh offline hingga tanggal expired tercapai (Heartbeat berkala). | **100% Offline** setelah token diinput di awal. |
| **Batasan Kapasitas** | Fleksibel upgrade kuota kasir sesuai paket langganan. | Terkunci pada jumlah register kasir/cabang yang dibeli di awal. |
| **Sistem Grace Period** | 7 hari toleransi dengan banner peringatan di kasir sebelum lock total. | Tidak berlaku (lisensi aktif selamanya). |

---

### 8.3. Struktur Payload Data Lisensi (Token JSON)

Token lisensi ditandatangani secara digital dengan struktur muatan sebagai berikut:

```json
{
  "license_id": "LIC-2026-FNB-0089",
  "merchant_name": "Kopi Senja Nusantara",
  "license_type": "subscription",     // Pilihan: "subscription" ATAU "perpetual"
  "hardware_id": "a4f8c9b2-uuid-...", // Kunci unik identitas server client
  "modules_allowed": [
    "pos_base",
    "pos_id_qris",
    "pos_restaurant",
    "pos_kitchen_screen"
  ],
  "max_pos_registers": 3,             // Kuota maksimum register kasir aktif
  "valid_from": "2026-01-01",
  "valid_until": "2026-12-31",        // Tanggal expired (null jika tipe perpetual)
  "grace_period_days": 7              // Toleransi keterlambatan bayar (hari)
}
```

---

### 8.4. Proteksi Model "Beli Putus" & Catatan Kritis Fingerprinting

Pada skema beli putus (*perpetual*), tantangannya adalah mencegah merchant menduplikasi sistem ke cabang lain tanpa izin. Namun terdapat batasan teknis lingkungan container yang harus diantisipasi:

> [!WARNING]
> **Catatan Kritis Docker & Database Dump:**
> 1. File `/etc/machine-id` di dalam container Docker seringkali tidak unik atau dapat berubah saat container di-*recreate* / di-*rebuild*.
> 2. Nilai `database.uuid` Odoo akan ikut tersalin secara identik jika database di-backup (`pg_dump`) lalu di-restore ke server cabang lain.
> 3. Oleh karena itu, strategi definitif untuk hardware/instance binding (misalnya memanfaatkan host-mounted volume ID, file lisensi statis terenkripsi, CPU serial host, atau verifikasi jaringan) **wajib difinalisasi dan diputuskan secara mendalam pada tahap `speckit-clarify`**.

---

### 8.5. Siklus & UX Kasir di Frontend OWL

1. **Validasi Buka Sesi Kasir (`pos.session.open_session`):**
   - Sebelum register kasir dibuka, backend Python memverifikasi integritas tanda tangan token dan masa berlaku tanggal server.
   - Jika valid $\rightarrow$ Kasir terbuka normal.
   - Jika expired $\rightarrow$ Muncul dialog peringatan keras dan tombol buka kasir diblokir.
2. **Peringatan Bertingkat di Layar Kasir (OWL UI):**
   - **H-14 s/d H-1 sebelum expired:** Banner kuning lembut di pojok atas: *"Masa aktif tersisa X hari. Segera lakukan perpanjangan."*
   - **Grace Period (H+1 s/d H+7 setelah expired):** Banner oranye mencolok dengan peringatan jatuh tempo; kasir tetap diizinkan transaksi sementara.
   - **Expired Total (Lewat Masa Grace):** Kasir masuk ke mode *Read-Only* (hanya bisa melihat rekonsiliasi dan mencetak ulang laporan riwayat, tidak bisa input transaksi baru).

---

## 9. Arsitektur Visual Access Management & Anti-Fraud

Modul **`saas_access_management`** dirancang untuk menyederhanakan kontrol hak akses Odoo yang rumit menjadi tampilan antarmuka visual yang mudah dikonfigurasi langsung oleh pemilik toko, sekaligus melindungi infrastruktur SaaS dari konfigurasi fatal merchant.

### 9.1. Peran Ganda Access Management

```
                    ┌──────────────────────────────────────────────┐
                    │           SAAS ACCESS MANAGEMENT             │
                    └──────────────────────┬───────────────────────┘
                                           │
             ┌─────────────────────────────┴─────────────────────────────┐
             ▼                                                           ▼
┌───────────────────────────────┐                       ┌───────────────────────────────┐
│     SAAS PROVIDER SHIELD      │                       │     MERCHANT FRAUD SHIELD     │
│ (Proteksi Infrastruktur SaaS) │                       │  (Proteksi Bisnis Pemilik)    │
├───────────────────────────────┤                       ├───────────────────────────────┤
│ • Sembunyikan menu Apps       │                       │ • Sembunyikan harga modal/lab │
│ • Kunci menu Technical Config │                       │ • Blokir tombol Delete Order  │
│ • Sembunyikan Database Mgr    │                       │ • Matikan fitur Export Excel  │
│ • Cegah instalasi modul liar  │                       │ • Batasi hak diskon / void    │
└───────────────────────────────┘                       └───────────────────────────────┘
```

---

### 9.2. Matriks 5 Dimensi Pembatasan Hak Akses

Modul ini mengontrol 5 titik rawan secara visual tanpa perlu menulis kode XML atau Record Rules:

1. **Hide Menus (Navigasi):** Sembunyikan menu/submenu tertentu dari user (misal: menu *Settings*, *Accounting*, atau *Technical*).
2. **Hide Buttons (Aksi):** Sembunyikan tombol spesifik seperti *Create*, *Edit*, *Delete*, *Action*, *Duplicate*, atau *Refund*.
3. **Field-Level Restriction (Data Sensitif):**
   - Atur field menjadi **Invisible** (misal: `standard_price` / harga modal produk disembunyikan total dari kasir).
   - Atur field menjadi **Read-Only** (misal: kasir tidak bisa mengubah harga jual `list_price`).
4. **No Export (Anti Pencurian Data):** Mematikan fitur bawaan Odoo *"Export all to Excel/CSV"* untuk mencegah karyawan mencuri basis data pelanggan atau riwayat omset toko.
5. **Report Restriction:** Membatasi akses cetak laporan keuangan atau laba rugi hanya untuk user bertingkat Manager/Owner.

---

### 9.3. Preset Role Bawaan (*Out-of-the-Box*)

Sistem langsung menyediakan 3 tingkatan peran standar yang siap digunakan merchant sejak hari pertama:

```
┌─────────────────┬───────────────────────────────────────────────────────────────┐
│ Role Preset     │ Cakupan Hak Akses                                             │
├─────────────────┼───────────────────────────────────────────────────────────────┤
│ 👑 Store Owner  │ Akses penuh seluruh modul bisnis (POS, Stok, Penjualan, Laba).│
│ 👔 Supervisor   │ Bisa pantau stok & setujui void/diskon, dilarang hapus order. │
│ 💵 Kasir        │ Hanya buka layar POS, harga modal & menu backend tersembunyi. │
└─────────────────┴───────────────────────────────────────────────────────────────┘
```

---

### 9.4. Implementasi Teknis Odoo 20

* **Model Backend (`saas.access.rule`):** Menyimpan aturan per role/user terhadap model, field, button, dan menu yang dibatasi.
* **View Interceptor (`get_views` override):** Memodifikasi arch view XML secara dinamis sebelum dikirim ke browser client (menghapus tombol atau node field terlarang).
* **OWL Web Client Patch:** Mematikan action dropdown *Export* dan validasi tombol di antarmuka web client Odoo 20.


