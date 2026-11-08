# Requirements Checklist: SaaS License Server (`saas_license_server`)

**Status**: Verified  
**Date**: 2026-10-22  

---

## 1. Requirement Kriptografi & Format Token
- [x] **REQ-CRYPTO-01**: Menghasilkan keypair Ed25519 standar (RFC 8032) dengan pustaka `cryptography`.
- [x] **REQ-CRYPTO-02**: Private Key disimpan dalam format PKCS8 PEM terenkripsi/terisolasi.
- [x] **REQ-CRYPTO-03**: Public Key diekstrak dalam format Base64 mentah 32-byte (kompatibel langsung dengan `PUBLIC_KEYS` di `license_verifier.py`).
- [x] **REQ-CRYPTO-04**: Format token adalah Compact JWS 3-bagian (`header.payload.signature`) base64url tanpa padding `=`.
- [x] **REQ-CRYPTO-05**: Header memuat `alg: EdDSA`, `typ: SAAS-LIC`, dan `kid: <key_id>`.
- [x] **REQ-CRYPTO-06**: Payload kanonikal memuat `lid`, `mch`, `typ`, `db_uuid`, `max_reg`, `from`, `grace`, dan `until` (khusus subscription).

## 2. Requirement Fungsional & Model
- [x] **REQ-FUNC-01**: Model `saas.license.key` mendukung pembuatan keypair otomatis lewat satu klik tombol.
- [x] **REQ-FUNC-02**: Master record `saas.license.record` mendukung tipe lisensi `subscription` dan `perpetual`.
- [x] **REQ-FUNC-03**: Constraint memvalidasi `valid_until` wajib ada di tipe subscription dan wajib kosong di tipe perpetual.
- [x] **REQ-FUNC-04**: Tombol *Issue & Sign Token* mengeksekusi penandatanganan dan menyimpan raw token.
- [x] **REQ-FUNC-05**: Wizard `saas.license.wizard` memfasilitasi penerbitan cepat satu klik.
- [x] **REQ-FUNC-06**: Sequence penomoran otomatis `LIC-YYYY-XXXX` aktif saat record lisensi dibuat.

## 3. Requirement Keamanan & Hak Akses
- [x] **REQ-SEC-01**: Role Viewer hanya memiliki akses baca (`read-only`) ke master lisensi.
- [x] **REQ-SEC-02**: Role Manager dapat membuat lisensi dan menerbitkan token tanpa perlu melihat teks Private Key PEM.
- [x] **REQ-SEC-03**: Role Administrator memiliki akses penuh ke Private Key PEM dan pembuatan keypair baru.
- [x] **REQ-SEC-04**: Tab Private Key tersembunyi dari user non-administrator di level form view XML.

## 4. Requirement Pengujian
- [x] **REQ-TEST-01**: Unit test mencakup pembuatan keypair, penandatanganan subscription, dan penandatanganan perpetual.
- [x] **REQ-TEST-02**: Unit test memvalidasi token hasil penerbitan menggunakan verifier resmi `pos_saas_license.license_verifier`.
- [x] **REQ-TEST-03**: Unit test memvalidasi penegakan hak akses role Manager vs Viewer.
- [x] **REQ-TEST-04**: Seluruh pengujian lulus 100% di dalam kontainer Odoo 20 tanpa error.
