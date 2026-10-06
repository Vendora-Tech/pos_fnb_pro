# Quickstart Guide: Testing & Verifying `pos_saas_license`

**Feature**: `001-pos-saas-license`  
**Date**: 2026-10-06  
**Status**: Completed (Phase 1)

---

## 1. Menghasilkan Pasangan Kunci & Token Uji Coba (CLI)

Gunakan utilitas CLI generator berbasis Python untuk membuat Ed25519 keypair dan token simulasi:

```python
# scripts/generate_test_token.py
import json
import base64
from cryptography.hazmat.primitives.asymmetric import ed25519

# 1. Generate Keypair
private_key = ed25519.Ed25519PrivateKey.generate()
public_key = private_key.public_key()

pub_bytes = public_key.public_bytes_raw()
print("PUBLIC KEY (Paste ke models/verifier.py):", base64.b64encode(pub_bytes).decode())

# 2. Buat Payload Token Simulasi
payload = {
    "lid": "LIC-2026-TEST-001",
    "mch": "Toko Sukses Makmur",
    "typ": "subscription",
    "db_uuid": "TARGET_DB_UUID_HERE",
    "mods": ["pos_base"],
    "max_reg": 2,
    "from": "2026-01-01",
    "until": "2026-12-31",
    "grace": 7
}

payload_json = json.dumps(payload, separators=(',', ':')).encode()
payload_b64 = base64.urlsafe_b64encode(payload_json).rstrip(b'=').decode()

# 3. Tanda Tangani Payload
sig = private_key.sign(payload_b64.encode())
sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b'=').decode()

# Token Lengkap JWS format: payload.signature
token_string = f"{payload_b64}.{sig_b64}"
print("\nTOKEN LISENSI SIAP PAKAI:\n", token_string)
```

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
docker exec -it odoo20-pos-odoo20-1 odoo \
  --test-enable \
  --stop-after-init \
  -d odoo20_pos \
  -i pos_saas_license \
  --test-tags=/pos_saas_license
```
