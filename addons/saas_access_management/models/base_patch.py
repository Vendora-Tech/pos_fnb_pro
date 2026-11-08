import logging
from odoo import api, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

SYSTEM_PREFIXES = (
    "saas.access.",
    "ir.",
    "bus.",
    "res.users",
    "res.company",
    "res.groups",
    "web.",
)


class Base(models.AbstractModel):
    _inherit = "base"

    def _is_exempt_from_access_policy(self):
        """Cek apakah model atau user dikecualikan dari pembatasan SaaS."""
        if not self._name or self.is_transient():
            return True
        if self.env.context.get("saas_access_bypass"):
            return True
        for prefix in SYSTEM_PREFIXES:
            if self._name.startswith(prefix):
                return True
        user = self.env.user
        if user.id == 1:
            return True
        return False

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """Intercept get_view untuk memodifikasi arch UI secara dinamis."""
        result = super().get_view(view_id=view_id, view_type=view_type, **options)
        user_id = self.env.user.id

        if user_id != 1 and "arch" in result and self._name:
            if not self._is_exempt_from_access_policy():
                rule_model = self.env["saas.access.rule"].sudo().with_context(saas_access_bypass=True)
                result["arch"] = rule_model._apply_view_restrictions(
                    self._name, view_type, result["arch"], user_id
                )
        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Blokir pembuatan data jika user read-only atau hide_create aktif, dan validasi required."""
        if not self._is_exempt_from_access_policy():
            user_id = self.env.user.id
            rule_model = self.env["saas.access.rule"].sudo().with_context(saas_access_bypass=True)
            if rule_model._is_readonly_user(user_id):
                raise UserError("Pengguna dengan status Read-Only tidak diizinkan membuat data baru!")
            rules = rule_model._get_active_rules_for_user(user_id)
            if rules:
                model_rules = rules.mapped("model_access_ids").filtered(
                    lambda m: m.model_name == self._name
                )
                if any(model_rules.mapped("hide_create")):
                    raise UserError(
                        "Kebijakan keamanan sistem melarang Anda menambah data baru pada modul ini!"
                    )
                # Validasi field yang dipaksa Required
                required_fields = rules.mapped("field_access_ids").filtered(
                    lambda f: f.model_name == self._name and f.is_required
                )
                for rf in required_fields:
                    fname = rf.field_name
                    for vals in vals_list:
                        if fname not in vals or not vals.get(fname):
                            raise UserError(
                                f"Field '{fname}' wajib diisi sesuai kebijakan sistem!"
                            )
        return super().create(vals_list)

    def write(self, vals):
        """Blokir pembaruan data jika user read-only atau hide_edit aktif."""
        if not self._is_exempt_from_access_policy():
            user_id = self.env.user.id
            rule_model = self.env["saas.access.rule"].sudo().with_context(saas_access_bypass=True)
            if rule_model._is_readonly_user(user_id):
                raise UserError("Pengguna dengan status Read-Only tidak diizinkan mengubah data!")
            rules = rule_model._get_active_rules_for_user(user_id)
            if rules:
                model_rules = rules.mapped("model_access_ids").filtered(
                    lambda m: m.model_name == self._name
                )
                if any(model_rules.mapped("hide_edit")):
                    raise UserError(
                        "Kebijakan keamanan sistem melarang Anda mengubah data pada modul ini!"
                    )
                # Validasi field required saat dikosongkan
                required_fields = rules.mapped("field_access_ids").filtered(
                    lambda f: f.model_name == self._name and f.is_required
                )
                for rf in required_fields:
                    fname = rf.field_name
                    if fname in vals and not vals.get(fname):
                        raise UserError(
                            f"Field '{fname}' wajib diisi dan tidak boleh dikosongkan!"
                        )
        return super().write(vals)

    def unlink(self):
        """Blokir eksekusi unlink via ORM/RPC jika user read-only atau hide_delete aktif."""
        if not self._is_exempt_from_access_policy():
            user_id = self.env.user.id
            rule_model = self.env["saas.access.rule"].sudo().with_context(saas_access_bypass=True)
            if rule_model._is_readonly_user(user_id):
                raise UserError("Pengguna dengan status Read-Only tidak diizinkan menghapus data!")
            rules = rule_model._get_active_rules_for_user(user_id)
            if rules:
                model_rules = rules.mapped("model_access_ids").filtered(
                    lambda m: m.model_name == self._name
                )
                if any(model_rules.mapped("hide_delete")):
                    raise UserError(
                        "Kebijakan keamanan sistem melarang Anda menghapus data pada modul ini!"
                    )
        return super().unlink()

    def copy(self, default=None):
        """Blokir duplikasi data jika hide_duplicate aktif."""
        if not self._is_exempt_from_access_policy():
            user_id = self.env.user.id
            rule_model = self.env["saas.access.rule"].sudo().with_context(saas_access_bypass=True)
            if rule_model._is_readonly_user(user_id):
                raise UserError("Pengguna dengan status Read-Only tidak diizinkan menduplikasi data!")
            rules = rule_model._get_active_rules_for_user(user_id)
            if rules:
                if any(rules.mapped("hide_duplicate")):
                    raise UserError("Kebijakan sistem melarang duplikasi data!")
                model_rules = rules.mapped("model_access_ids").filtered(
                    lambda m: m.model_name == self._name
                )
                if any(model_rules.mapped("hide_duplicate")):
                    raise UserError("Kebijakan sistem melarang duplikasi data pada modul ini!")
        return super().copy(default=default)

    def export_data(self, fields_to_export):
        """Blokir pemanggilan export_data jika fitur export dinonaktifkan untuk user atau field."""
        user = self.env.user
        if user.id != 1 and not (user._is_system() or user._is_admin()):
            rule_model = self.env["saas.access.rule"].sudo().with_context(saas_access_bypass=True)
            if rule_model._is_export_disabled_for_user(user.id, self._name):
                raise AccessError(
                    "Kebijakan keamanan sistem melarang Anda mengekspor data ke file spreadsheet!"
                )
            for f in fields_to_export:
                base_fname = f.split("/")[0]
                if rule_model._is_field_export_restricted(user.id, self._name, base_fname):
                    raise AccessError(
                        f"Field '{base_fname}' dilarang untuk diekspor ke spreadsheet!"
                    )
        return super().export_data(fields_to_export)

    @api.model
    def load(self, fields, data):
        """Blokir impor data jika fitur import dinonaktifkan untuk user."""
        user = self.env.user
        if user.id != 1 and not (user._is_system() or user._is_admin()):
            if self.env["saas.access.rule"].sudo().with_context(saas_access_bypass=True)._is_import_disabled_for_user(user.id, self._name):
                raise AccessError(
                    "Kebijakan keamanan sistem melarang Anda mengimpor data!"
                )
        return super().load(fields, data)

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        """Terapkan domain record restriction dinamis per user."""
        if not self._is_exempt_from_access_policy():
            user = self.env.user
            rule_model = self.env["saas.access.rule"].sudo().with_context(saas_access_bypass=True)
            rules = rule_model._get_active_rules_for_user(user.id)
            if rules:
                domain_rules = rules.mapped("domain_access_ids").filtered(
                    lambda d: d.model_name == self._name and d.restrict_read and not d.is_soft_restriction
                )
                for dr in domain_rules:
                    if dr.domain and dr.domain.strip():
                        try:
                            eval_domain = safe_eval(
                                dr.domain,
                                {"user": user, "company": self.env.company},
                            )
                            if eval_domain and isinstance(eval_domain, (list, tuple)):
                                domain = list(Domain(domain) & Domain(eval_domain))
                        except Exception as e:
                            _logger.warning("Gagal mengevaluasi domain rule: %s", e)
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)
