# Data Model Specification: `saas_access_management`

**Feature**: `003-saas-access-management`  
**Date**: 2026-10-16  
**Status**: Draft  

---

## 1. Core Data Models

### 1.1. `saas.access.rule` (Main Policy Configuration)

Menyimpan konfigurasi kelompok aturan hak akses visual yang diterapkan ke pengguna tertentu.

| Field Name | Type | Properties | Description |
| :--- | :--- | :--- | :--- |
| `name` | Char | Required=True | Nama aturan kebijakan (contoh: `Role: Kasir Toko`) |
| `active` | Boolean | Default=True | Status keaktifan aturan |
| `user_ids` | Many2many | Relation=`res.users` | Daftar user yang terikat kebijakan ini |
| `disable_export` | Boolean | Default=False | Menghilangkan tombol Export to Excel/CSV di list view |
| `hide_menu_ids` | Many2many | Relation=`ir.ui.menu` | Daftar menu navigasi yang disembunyikan |
| `model_access_ids` | One2many | Comodel=`saas.access.rule.model`, Inverse=`rule_id` | Daftar aturan spesifik per model |

---

### 1.2. `saas.access.rule.model` (Model-Level Restriction)

Menyimpan pembatasan aksi (Create, Edit, Delete) pada level model data tertentu.

| Field Name | Type | Properties | Description |
| :--- | :--- | :--- | :--- |
| `rule_id` | Many2one | Comodel=`saas.access.rule`, Required=True, OnDelete=`cascade` | Relasi ke aturan induk |
| `model_id` | Many2one | Comodel=`ir.model`, Required=True, OnDelete=`cascade` | Model Odoo target (contoh: `pos.order`) |
| `model_name` | Char | Related=`model_id.model`, Stored=True, Index=True | Nama teknis model untuk query cepat |
| `hide_create` | Boolean | Default=False | Sembunyikan tombol Buat (*Create*) pada form & list |
| `hide_edit` | Boolean | Default=False | Sembunyikan tombol Edit pada form & inline-editing |
| `hide_delete` | Boolean | Default=False | Sembunyikan tombol Hapus (*Delete*) dan menu Action Delete |
| `field_restriction_ids` | One2many | Comodel=`saas.access.rule.field`, Inverse=`model_access_id` | Daftar pembatasan field di model ini |

---

### 1.3. `saas.access.rule.field` (Field-Level Restriction)

Menyimpan pembatasan akses data spesifik pada kolom tertentu (Invisible atau Readonly).

| Field Name | Type | Properties | Description |
| :--- | :--- | :--- | :--- |
| `model_access_id` | Many2one | Comodel=`saas.access.rule.model`, Required=True, OnDelete=`cascade` | Relasi ke model rule induk |
| `field_id` | Many2one | Comodel=`ir.model.fields`, Required=True, OnDelete=`cascade` | Field target (contoh: `standard_price`) |
| `field_name` | Char | Related=`field_id.name`, Stored=True, Index=True | Nama teknis field |
| `is_invisible` | Boolean | Default=False | Sembunyikan field dari tampilan form dan list |
| `is_readonly` | Boolean | Default=False | Kunci field agar tidak bisa diedit oleh user |

---

## 2. Odoo 20 ORM Hooks & Interception Architecture

### 2.1. Dynamic View Manipulation (`models.BaseModel.get_view`)
Di Odoo 20, modifikasi tampilan view form dan list dipotong pada metode `get_view` di `models.AbstractModel`:
```python
class BaseModel(models.AbstractModel):
    _inherit = "base"

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        res = super().get_view(view_id=view_id, view_type=view_type, **options)
        if self.env.is_superuser():
            return res

        # Terapkan pembatasan model & field dari saas.access.rule aktif
        res["arch"] = self.env["saas.access.rule"]._apply_view_restrictions(
            model=self._name,
            view_type=view_type,
            arch=res["arch"],
            user_id=self.env.uid,
        )
        return res
```

### 2.2. Menu Filtering Hook (`ir.ui.menu`)
Menyaring daftar menu saat frontend web client memuat navigasi:
```python
class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def _filter_visible_menus(self):
        menus = super()._filter_visible_menus()
        if self.env.is_superuser():
            return menus
        hidden_menus = self.env["saas.access.rule"]._get_hidden_menus_for_user(self.env.uid)
        return menus - hidden_menus
```

### 2.3. Anti-Export Interception (`ir.http` & Controller)
Mematikan hak ekspor data ke Excel/CSV:
- Menginjeksikan flag `disable_export: true` ke dalam `session_info` web client sehingga tombol "Export" pada action box otomatis hilang.
- Memvalidasi endpoint controller `/web/export/xlsx` dan `/web/export/csv` agar menolak permintaan (*HTTP 403 Forbidden*) jika user memiliki aturan `disable_export`.

---

## 3. Database Constraints & Indexing

```python
# Unik per user policy kombinasi
_sql_constraints = [
    (
        "model_unique_per_rule",
        "UNIQUE(rule_id, model_id)",
        "Aturan model untuk policy ini sudah ada!",
    ),
    (
        "field_unique_per_model_access",
        "UNIQUE(model_access_id, field_id)",
        "Aturan field untuk model ini sudah ada!",
    ),
]
```
