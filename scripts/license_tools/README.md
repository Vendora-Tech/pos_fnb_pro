# POS SaaS License Tools

Toolkit penerbit token lisensi untuk modul `addons/pos_saas_license`.

Perhatian utama: **private key hanya boleh ada di mesin penerbit token.** Jangan pernah commit
file `.pem` atau menaruhnya di repository/container merchant (`.gitignore` sudah mengabaikan
`*.pem` dan `scripts/license_tools/keys/`; job Gitleaks di CI akan menghentikan commit yang
berisi kunci privat).

## 1. Buat pasangan kunci

```bash
python scripts/license_tools/generate_keypair.py --kid dev2026 --out ~/.pos_saas_keys/dev2026.pem
```

Output yang dicetak:

- path private key (rahasia, jangan di-commit)
- public key Base64 beserta `kid`, tempelkan ke `PUBLIC_KEYS` di
  `addons/pos_saas_license/models/license_verifier.py`

Script menolak menimpa private key yang sudah ada. Regenerasi kunci artinya kunci lama harus
tetap terdaftar di `PUBLIC_KEYS` agar token lama tidak langsung mati.

## 2. Terbitkan token

```bash
python scripts/license_tools/issue_token.py \
  --key ~/.pos_saas_keys/dev2026.pem --kid dev2026 \
  --lid LIC-2026-TEST-001 --mch "Toko Sukses Makmur" \
  --typ subscription --db-uuid <DATABASE_UUID> \
  --mods pos_base,pos_qris --max-reg 2 \
  --from 2026-01-01 --until 2026-12-31 --grace 7
```

Lisensi beli putus (tanpa `--until`):

```bash
python scripts/license_tools/issue_token.py \
  --key ~/.pos_saas_keys/dev2026.pem --kid dev2026 \
  --lid LIC-2026-0001 --mch "Toko Sejahtera" \
  --typ perpetual --db-uuid <DATABASE_UUID> --max-reg 3 \
  --from 2026-01-01
```

Aturan yang dipakai script:

- `--until` wajib untuk `subscription`, dilarang untuk `perpetual` (payload `until` menjadi `null`)
- `--max-reg >= 1`, `--grace >= 0`
- `--from` dan `--until` harus format `YYYY-MM-DD`
- `--db-uuid` diambil dari field **Database UUID** di halaman Point of Sale → Settings → SaaS License

Isi `--db-uuid` harus sama dengan `database.uuid` database target. Jika berbeda, modul akan
menolak token tersebut.

## 3. Format token

`header.payload.signature`, masing-masing bagian base64url tanpa padding:

- header: `{"alg":"EdDSA","typ":"SAAS-LIC","kid":"<kid>"}`
- payload: JSON compact sesuai `specs/001-pos-saas-license/contracts/license-token-schema.json`
- signature: Ed25519 atas byte ASCII `header_b64 + "." + payload_b64`

## 4. Batasan yang diketahui

- Restore `pg_dump` mentah memindahkan `database.uuid` yang sama, sehingga token tetap diterima
  di mesin lain. Ini batasan yang diterima sesuai threat model (perlindungan pelanggaran kasual).
- Clawing waktu mundur (jam OS dimundurkan) terdeteksi lewat `last_seen_timestamp` dengan
  toleransi 1 jam, bukan lewat token.
- Tool ini adalah penerbit internal. Tidak ada licensing server pusat di scope modul klien.
