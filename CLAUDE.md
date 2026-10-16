# CLAUDE.md

## Wajib dibaca lebih dulu

Baca `AGENTS.md` di root repository ini dan ikuti isinya. Dokumen itu memuat konteks project, stack, perintah, konvensi modul Odoo, alur Spec-Kit, aturan rahasia, dan kebiasaan kerja. File ini hanya menambah hal yang spesifik untuk Claude Code.

Ringkasan yang paling sering relevan:

- Ini ekosistem SaaS POS di atas Odoo 20 dengan PostgreSQL 18 lewat Docker Compose. Modul utama: `addons/pos_saas_license`.
- Semua perintah Odoo dijalankan di dalam container: `make shell-odoo`, `make restart-upgrade MODULE=pos_saas_license`, `make wait-odoo`.
- `.env` dan `*.pem` tidak pernah masuk git. Jangan pernah menampilkan isinya di output atau commit message.
- Requirement hidup di `specs/001-pos-saas-license/`. Spec diperbarui lebih dulu, kode menyusul.

---

## Aturan khusus Claude Code

### Urutan skill Spec-Kit

Fitur di repo ini dikerjakan lewat Spec-Kit dan urutannya penting:

```
speckit-specify → speckit-clarify → speckit-plan → speckit-tasks → speckit-analyze → speckit-implement
```

- Kalau slash command `/speckit-*` tidak tersedia karena `.claude/` tidak ter-commit, baca langsung file skill-nya di `.agents/skills/speckit-<nama>/SKILL.md` dan jalankan langkahnya secara manual.
- Jangan melompat ke `speckit-implement` sebelum `tasks.md` ada dan `speckit-analyze` bersih.
- `speckit-analyze` dan `speckit-clarify` membaca `.specify/memory/constitution.md`. Kalau ada perubahan prinsip proyek, perbarui constitution lewat `speckit-constitution`.
- Setelah menyelesaikan task, tandai `[x]` di `specs/<fitur>/tasks.md`. Jangan menambah pekerjaan tanpa task di sana.
- Fitur aktif dibaca dari `.specify/feature.json`.

### Kapan memakai subagent

- Pakai subagent untuk pencarian kode yang luas dan belum tahu lokasinya ("di mana X didefinisikan", "siapa yang memanggil Y"), atau untuk menelusuri banyak berkas di beberapa addon sekaligus.
- Jangan pakai subagent untuk target yang sudah diketahui. Baca langsung file-nya.
- Jangan mengerjakan ulang hal yang sedang dikerjakan subagent. Kalau pencarian sudah didelegasikan, tunggu hasilnya.
- Setelah subagent melaporkan perubahan kode, periksa sendiri diff-nya sebelum melaporkan pekerjaan sebagai selesai.
- Untuk tugas yang butuh edit kode, kerjakan di konteks utama supaya hasilnya bisa langsung diverifikasi.

### Menjalankan test

Container harus hidup dulu (`make up-d`, lalu `make wait-db` dan `make wait-odoo`).

```bash
# Satu modul, seluruh test
docker compose exec -T odoo20 odoo \
  --db_host=db -d pos_saas_dev \
  -u pos_saas_license --test-enable --test-tags /pos_saas_license \
  --stop-after-init --log-level=test

# Satu class atau method
docker compose exec -T odoo20 odoo \
  --db_host=db -d pos_saas_dev \
  -u pos_saas_license --test-enable \
  --test-tags /pos_saas_license:TestLicenseCrypto \
  --stop-after-init --log-level=test
```

Catatan yang sering bikin test gagal tanpa alasan jelas:

- Jalankan `make wait-odoo` setelah restart, bukan hanya `make ps`. Registry Odoo butuh waktu.
- Setelah menambah file model, view, atau data baru, ingat mendaftarkannya di `models/__init__.py` dan `data` pada manifest, lalu jalankan `make restart-upgrade MODULE=...`. Tanpa itu perubahan tidak terbaca.
- Untuk modul baru yang belum pernah terpasang, pakai `-i` (install) sekali, bukan `-u` (upgrade).
- Perubahan `security/ir.model.access.csv` juga butuh upgrade agar berlaku.
- Test tidak boleh bergantung pada data demo; CI menjalankan `--without-demo=all`.

### Editing dan verifikasi

- Baca file dulu sebelum mengedit. Jangan menebak isi file dari namanya.
- Batasi perubahan pada scope yang diminta. Jangan merapikan hal lain sekaligus.
- Setelah selesai, jalankan `git diff` dan `git status` untuk memastikan tidak ada file yang ikut berubah tanpa sengaja.
- Jangan jalankan `docker compose down -v` atau menghapus `postgresql/` tanpa konfirmasi eksplisit.
- Jangan commit, push, atau mengubah konfigurasi global kecuali diminta.

### Konteks artefak spec

- `specs/` adalah sumber kebenaran. Kalau implementasi perlu menyimpang, perbarui spec atau plan dulu.
- Tulis path relatif di dalam artefak spec, bukan path absolut mesin lokal.
- Kalau project ini dibuka dari mesin atau OS berbeda, periksa apakah `.env` dan `scripts/license_tools/keys/` ada di mesin itu sebelum menjalankan perintah yang membutuhkannya.

### Yang tidak perlu dilakukan

- Jangan menambah `.claude/` ke repo; folder itu di-ignore dan isinya tidak akan tersimpan.
- Jangan mengubah `docs/SAAS_POS_MASTER_BLUEPRINT.md` kecuali diminta; itu dokumen produk, bukan artefak fitur.
- Jangan menambah logika bisnis ke `addons/pos_example/`; modul itu hanya dummy CI di bawah 100 baris.
- Jangan menambah dependensi Python baru ke manifest tanpa alasan tertulis di spec atau plan.
