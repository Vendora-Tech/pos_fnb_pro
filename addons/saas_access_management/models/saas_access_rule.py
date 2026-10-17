import json
import logging
from lxml import etree

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SaasAccessRule(models.Model):
    _name = "saas.access.rule"
    _description = "Access Management Policy Rule"
    _order = "id desc"

    name = fields.Char(
        string="Policy Name",
        required=True,
        help="Descriptive name of this role policy (e.g. Kasir Toko, Warehouse Staff).",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Toggle to activate or deactivate this policy.",
    )
    user_ids = fields.Many2many(
        "res.users",
        "saas_access_rule_users_rel",
        "rule_id",
        "user_id",
        string="Users",
        help="Users affected by these access restrictions.",
    )
    company_ids = fields.Many2many(
        "res.company",
        "saas_access_rule_companies_rel",
        "rule_id",
        "company_id",
        string="Companies",
        help="Companies where this rule is enforced (multi-company support).",
    )
    readonly = fields.Boolean(
        string="Read-Only User",
        default=False,
        help="Make assigned users completely read-only across the entire system.",
    )
    disable_debug_mode = fields.Boolean(
        string="Disable Developer Mode",
        default=False,
        help="Prevent assigned users from activating developer/debug mode (?debug=1).",
    )
    disable_login = fields.Boolean(
        string="Disable Login",
        default=False,
        help="Prevent assigned users from logging in to the system.",
    )
    apply_hierarchy = fields.Boolean(
        string="Manage Hierarchy Access",
        default=False,
        help="Allow managers to see and manage records created by their subordinates.",
    )
    hide_chatter = fields.Boolean(
        string="Hide Chatter",
        default=False,
        help="Hide chatter section (messages, notes, activities) globally across all models.",
    )
    hide_send_message = fields.Boolean(
        string="Hide Send Message",
        default=False,
        help="Hide Send Message button in chatter globally.",
    )
    hide_log_note = fields.Boolean(
        string="Hide Log Note",
        default=False,
        help="Hide Log Note button in chatter globally.",
    )
    hide_activity = fields.Boolean(
        string="Hide Schedule Activity",
        default=False,
        help="Hide Schedule Activity button in chatter globally.",
    )
    hide_export = fields.Boolean(
        string="Hide Export",
        default=False,
        help="Prevent assigned users from exporting data to Excel/CSV.",
    )
    hide_import = fields.Boolean(
        string="Hide Import",
        default=False,
        help="Prevent assigned users from importing records.",
    )
    hide_spreadsheets = fields.Boolean(
        string="Hide Spreadsheet",
        default=False,
        help="Hide Insert in Spreadsheet button globally.",
    )
    hide_duplicate = fields.Boolean(
        string="Hide Duplicate Globally",
        default=False,
        help="Hide duplicate action across all models.",
    )
    hide_archive = fields.Boolean(
        string="Hide Archive Globally",
        default=False,
        help="Hide archive and unarchive actions across all models.",
    )
    hide_filters = fields.Boolean(
        string="Hide Filters Globally",
        default=False,
        help="Hide default filters across all search views.",
    )
    hide_group_by = fields.Boolean(
        string="Hide Group By Globally",
        default=False,
        help="Hide group by options across all search views.",
    )
    hide_search_panel = fields.Boolean(
        string="Hide Search Panel Globally",
        default=False,
        help="Hide search panels across all views.",
    )

    # Tabs (One2many relations)
    hide_menu_ids = fields.Many2many(
        "ir.ui.menu",
        "saas_access_rule_menu_rel",
        "rule_id",
        "menu_id",
        string="Hidden Menus",
        help="Menus completely hidden from navigation for assigned users.",
    )
    model_access_ids = fields.One2many(
        "saas.access.rule.model",
        "rule_id",
        string="Model Restrictions",
        copy=True,
    )
    field_access_ids = fields.One2many(
        "saas.access.rule.field",
        "rule_id",
        string="Field Restrictions",
        copy=True,
    )
    button_tab_access_ids = fields.One2many(
        "saas.access.rule.button.tab",
        "rule_id",
        string="Button & Tab Restrictions",
        copy=True,
    )
    domain_access_ids = fields.One2many(
        "saas.access.rule.domain",
        "rule_id",
        string="Domain Restrictions",
        copy=True,
    )
    chatter_access_ids = fields.One2many(
        "saas.access.rule.chatter",
        "rule_id",
        string="Model Chatter Restrictions",
        copy=True,
    )
    hide_filters_groups_ids = fields.One2many(
        "saas.access.rule.filter",
        "rule_id",
        string="Filter & Group Restrictions",
        copy=True,
    )
    report_access_ids = fields.One2many(
        "saas.access.rule.report",
        "rule_id",
        string="Report / Print Restrictions",
        copy=True,
    )

    def _clear_rule_caches(self):
        """Invalidate caches agar perubahan rule langsung efektif."""
        self.env.invalidate_all()
        if hasattr(self.env.transaction, "invalidate_access_cache"):
            self.env.transaction.invalidate_access_cache()
        if hasattr(self.env.transaction, "invalidate_ormcache"):
            self.env.transaction.invalidate_ormcache()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._clear_rule_caches()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._clear_rule_caches()
        return res

    def unlink(self):
        res = super().unlink()
        self._clear_rule_caches()
        return res

    @api.model
    def _get_active_rules_for_user(self, user_id):
        """Ambil seluruh rules aktif untuk user tertentu dan company aktif."""
        if not user_id or user_id == 1:
            return self.browse()
        user = self.env["res.users"].sudo().with_context(saas_access_bypass=True).browse(user_id)
        if user._is_system() or user._is_admin():
            return self.browse()

        company_id = self.env.company.id
        return self.sudo().with_context(saas_access_bypass=True).search([
            ("active", "=", True),
            ("user_ids", "in", [user_id]),
            "|",
            ("company_ids", "=", False),
            ("company_ids", "in", [company_id]),
        ])

    @api.model
    def _is_export_disabled_for_user(self, user_id, model=None):
        """Cek apakah export dinonaktifkan secara global atau per-model."""
        if not user_id or user_id == 1:
            return False
        rules = self._get_active_rules_for_user(user_id)
        if not rules:
            return False
        if any(rules.mapped("readonly")) or any(rules.mapped("hide_export")):
            return True
        if model:
            model_rules = rules.mapped("model_access_ids").filtered(
                lambda m: m.model_name == model
            )
            if any(model_rules.mapped("hide_export")):
                return True
        return False

    @api.model
    def _is_import_disabled_for_user(self, user_id, model=None):
        """Cek apakah import dinonaktifkan secara global atau per-model."""
        if not user_id or user_id == 1:
            return False
        rules = self._get_active_rules_for_user(user_id)
        if not rules:
            return False
        if any(rules.mapped("readonly")) or any(rules.mapped("hide_import")):
            return True
        if model:
            model_rules = rules.mapped("model_access_ids").filtered(
                lambda m: m.model_name == model
            )
            if any(model_rules.mapped("hide_import")):
                return True
        return False

    @api.model
    def _is_readonly_user(self, user_id):
        """Cek apakah user read-only."""
        if not user_id or user_id == 1:
            return False
        rules = self._get_active_rules_for_user(user_id)
        return any(rules.mapped("readonly"))

    @api.model
    def _is_debug_mode_disabled(self, user_id):
        """Cek apakah developer mode dinonaktifkan untuk user ini."""
        if not user_id or user_id == 1:
            return False
        rules = self._get_active_rules_for_user(user_id)
        return any(rules.mapped("disable_debug_mode"))

    @api.model
    def _is_login_disabled(self, user_id):
        """Cek apakah user dilarang masuk sistem."""
        if not user_id or user_id == 1:
            return False
        rules = self._get_active_rules_for_user(user_id)
        return any(rules.mapped("disable_login"))

    @api.model
    def _is_report_restricted(self, user_id, report_id, model=None):
        """Cek apakah pencetakan laporan tertentu diblokir untuk user ini."""
        if not user_id or user_id == 1:
            return False
        rules = self._get_active_rules_for_user(user_id)
        if not rules:
            return False
        if model:
            model_rules = rules.mapped("model_access_ids").filtered(
                lambda m: m.model_name == model
            )
            if any(model_rules.mapped("hide_report")):
                return True
        report_rules = rules.mapped("report_access_ids").filtered(
            lambda r: r.report_id.id == report_id and r.hide
        )
        return bool(report_rules)

    @api.model
    def _is_field_export_restricted(self, user_id, model, field_name):
        """Cek apakah field tertentu dilarang untuk diekspor ke spreadsheet."""
        if not user_id or user_id == 1:
            return False
        rules = self._get_active_rules_for_user(user_id)
        if not rules:
            return False
        field_rules = rules.mapped("field_access_ids").filtered(
            lambda f: f.model_name == model and f.field_name == field_name and f.hide_export
        )
        return bool(field_rules)

    @api.model
    def _get_hidden_menus_for_user(self, user_id):
        """Ambil seluruh menu yang disembunyikan untuk user ini."""
        if not user_id or user_id == 1:
            return self.env["ir.ui.menu"].browse()
        rules = self._get_active_rules_for_user(user_id)
        return rules.mapped("hide_menu_ids")

    @api.model
    def _apply_view_restrictions(self, model, view_type, arch, user_id):
        """Modifikasi arsitektur XML arch secara dinamis sesuai aturan user."""
        if not user_id or user_id == 1:
            return arch

        rules = self._get_active_rules_for_user(user_id)
        if not rules:
            return arch

        try:
            doc = etree.fromstring(arch.encode("utf-8"))
        except Exception as e:
            _logger.warning("Gagal mem-parse XML arch untuk model %s: %s", model, e)
            return arch

        is_readonly = any(rules.mapped("readonly"))
        model_rules = rules.mapped("model_access_ids").filtered(
            lambda m: m.model_name == model
        )

        # 1. Aturan Readonly Global & Model Action Buttons (create, edit, delete, duplicate, import, export)
        hide_create = is_readonly or any(model_rules.mapped("hide_create"))
        hide_edit = is_readonly or any(model_rules.mapped("hide_edit"))
        hide_delete = is_readonly or any(model_rules.mapped("hide_delete"))
        hide_duplicate = is_readonly or any(rules.mapped("hide_duplicate")) or any(model_rules.mapped("hide_duplicate"))
        hide_archive = is_readonly or any(rules.mapped("hide_archive")) or any(model_rules.mapped("hide_archive"))
        hide_import = is_readonly or any(rules.mapped("hide_import")) or any(model_rules.mapped("hide_import"))
        hide_export = is_readonly or any(rules.mapped("hide_export")) or any(model_rules.mapped("hide_export"))

        if hide_create:
            doc.attrib["create"] = "false"
        if hide_edit:
            doc.attrib["edit"] = "false"
        if hide_delete:
            doc.attrib["delete"] = "false"
        if hide_duplicate:
            doc.attrib["duplicate"] = "false"
        if hide_archive:
            doc.attrib["archive"] = "false"
        if hide_import:
            doc.attrib["import"] = "false"
        if hide_export:
            doc.attrib["export_xlsx"] = "false"

        # 2. Aturan Search View (Filters, Group By, Search Panel)
        if view_type == "search":
            hide_all_filters = any(rules.mapped("hide_filters")) or any(model_rules.mapped("hide_filters"))
            hide_all_group_by = any(rules.mapped("hide_group_by")) or any(model_rules.mapped("hide_group_by"))
            hide_sp = any(rules.mapped("hide_search_panel")) or any(model_rules.mapped("hide_search_panel"))

            if hide_all_filters:
                for node in doc.xpath("//filter[not(@context) or not(contains(@context, 'group_by'))]"):
                    node.attrib["invisible"] = "True"
            if hide_all_group_by:
                for node in doc.xpath("//filter[contains(@context, 'group_by')] | //group"):
                    node.attrib["invisible"] = "True"
            if hide_sp:
                for node in doc.xpath("//searchpanel"):
                    node.attrib["invisible"] = "True"

            # Filter spesifik per baris
            filter_rules = rules.mapped("hide_filters_groups_ids").filtered(
                lambda f: f.model_name == model and f.hide
            )
            for fr in filter_rules:
                fname = fr.name.strip()
                for node in doc.xpath(f"//filter[@name='{fname}'] | //filter[@string='{fname}']"):
                    node.attrib["invisible"] = "True"

        # 3. Aturan Field (Invisible, Readonly, Required, Remove External Link, Conditional)
        field_rules = rules.mapped("field_access_ids").filtered(
            lambda f: f.model_name == model
        )
        for field_rule in field_rules:
            fname = field_rule.field_name
            # Cari di form, list/tree, dan kanban
            for node in doc.xpath(f"//field[@name='{fname}']"):
                if field_rule.is_invisible:
                    node.attrib["invisible"] = "True"
                    node.attrib["column_invisible"] = "True"
                elif field_rule.conditional_domain:
                    node.attrib["invisible"] = field_rule.conditional_domain

                if field_rule.is_readonly or is_readonly:
                    node.attrib["readonly"] = "True"
                if field_rule.is_required:
                    node.attrib["required"] = "True"

                # Relational Dropdown Restrictions
                rel_opts = {}
                if field_rule.remove_external_link:
                    rel_opts["no_open"] = True
                if field_rule.no_create:
                    rel_opts["no_create"] = True
                if field_rule.no_create_edit:
                    rel_opts["no_create_edit"] = True
                    rel_opts["no_quick_create"] = True
                if rel_opts:
                    cur_opts = node.attrib.get("options", "{}")
                    try:
                        # parse options safely if json-like
                        parsed = eval(cur_opts) if cur_opts.startswith("{") else {}
                        parsed.update(rel_opts)
                        node.attrib["options"] = str(parsed)
                    except Exception:
                        node.attrib["options"] = str(rel_opts)

        # 4. Aturan Button & Tab (Sembunyikan tombol spesifik atau page/tab form)
        button_tab_rules = rules.mapped("button_tab_access_ids").filtered(
            lambda b: b.model_name == model and b.hide
        )
        for bt in button_tab_rules:
            target_name = bt.name.strip()
            cond_val = bt.conditional_domain if bt.conditional_domain else "True"
            if bt.button_tab_type == "button":
                for node in doc.xpath(f"//button[@name='{target_name}'] | //button[@string='{target_name}']"):
                    node.attrib["invisible"] = cond_val
            elif bt.button_tab_type == "tab":
                for node in doc.xpath(f"//page[@name='{target_name}'] | //page[@string='{target_name}']"):
                    node.attrib["invisible"] = cond_val

        # 5. Aturan Chatter (Global & Model-wise)
        chatter_rules = rules.mapped("chatter_access_ids").filtered(
            lambda c: c.model_name == model
        )
        hide_full_chatter = (
            any(rules.mapped("hide_chatter"))
            or any(chatter_rules.mapped("hide_chatter"))
        )
        if hide_full_chatter:
            for node in doc.xpath("//div[contains(@class, 'oe_chatter')] | //chatter"):
                node.attrib["invisible"] = "True"

        return etree.tostring(doc, encoding="utf-8").decode("utf-8")
