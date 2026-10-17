# Data Model Specification: `pos_saas_core`

**Feature**: `002-pos-saas-core`  
**Date**: 2026-10-12 (Updated: 2026-10-16)  
**Status**: Implemented & Verified  

---

## 1. Model Extensions

### 1.1. `res.company` (Extended)

Menyimpan konfigurasi identitas tenant dan branding struk default di tingkat perusahaan.

| Field Name | Type | Properties | Description |
| :--- | :--- | :--- | :--- |
| `tenant_uuid` | Char | Index, Copy=False, Default=UUIDv4 | Identifier unik tenant otomatis dibuat via `uuid.uuid4()` |
| `receipt_header` | Text | Translate=True | Default header teks struk (alamat toko, info operasional) |
| `receipt_footer` | Text | Translate=True | Default footer teks struk (slogan, media sosial) |

> **Catatan Logo & NPWP**:
> - Logo struk memanfaatkan field native `company.logo` bawaan Odoo 20 yang otomatis menjadi sumber fallback bagi `pos.config.logo`, menghindari redundansi penyimpanan binary.
> - Template NPWP pada struk diatur tersembunyi (`t-if="False"`) sesuai kebutuhan visual merchant.

### 1.2. `pos.config` (Extended)

Menyimpan konfigurasi tingkat cabang/outlet dan register kasir.

| Field Name | Type | Properties | Description |
| :--- | :--- | :--- | :--- |
| `tenant_uuid` | Char | Related (`company_id.tenant_uuid`), Readonly | Identitas tenant terwarisi dari company |
| `outlet_code` | Char | Required, Default="OUTLET-01", Index | Kode cabang toko (contoh: `ALSUT-01`, `SMG-K1`) |
| `use_custom_receipt` | Boolean | Default=False | Mengaktifkan teks header/footer kustom per outlet |
| `receipt_header_override` | Text | Translate=True | Teks header khusus cabang jika `use_custom_receipt` aktif |
| `receipt_footer_override` | Text | Translate=True | Teks footer khusus cabang jika `use_custom_receipt` aktif |

### 1.3. `res.config.settings` (Extended)

Transient model untuk menghubungkan antarmuka *Point of Sale $\rightarrow$ Settings*.

| Field Name | Type | Related/Config Parameter | Description |
| :--- | :--- | :--- | :--- |
| `saas_tenant_uuid` | Char | `related='company_id.tenant_uuid', readonly=True` | Tampilan status UUID tenant |
| `saas_default_receipt_header` | Text | `related='company_id.receipt_header', readonly=False` | Edit default header struk tenant |
| `saas_default_receipt_footer` | Text | `related='company_id.receipt_footer', readonly=False` | Edit default footer struk tenant |

---

## 2. Odoo 20 Data Loading ke Frontend POS

Di Odoo 20, data POS di-load melalui hook ORM backend:

### 2.1. `pos.config._load_pos_data_read`
Logika fallback header/footer diselesaikan langsung di backend saat sinkronisasi data POS:
```python
@api.model
def _load_pos_data_read(self, records, config):
    read_records = super()._load_pos_data_read(records, config)
    for record in read_records:
        if record.get("use_custom_receipt"):
            if record.get("receipt_header_override"):
                record["receipt_header"] = record["receipt_header_override"]
            if record.get("receipt_footer_override"):
                record["receipt_footer"] = record["receipt_footer_override"]
        else:
            company = config.company_id if config else self.env.company
            if company.receipt_header:
                record["receipt_header"] = company.receipt_header
            if company.receipt_footer:
                record["receipt_footer"] = company.receipt_footer
    return read_records
```

### 2.2. `res.company._load_pos_data_fields`
Mendaftarkan field `tenant_uuid`, `receipt_header`, dan `receipt_footer` ke daftar field company yang dimuat ke POS frontend.

---

## 3. Odoo 20 Constraints & Indexing

```python
# models/pos_config.py
from odoo import models

class PosConfig(models.Model):
    _inherit = "pos.config"

    _indexes = [
        models.Index("(company_id, outlet_code)"),
    ]
```
