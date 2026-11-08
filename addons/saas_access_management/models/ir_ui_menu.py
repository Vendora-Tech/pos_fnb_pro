from odoo import models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    def _load_menus_blacklist(self):
        """Tambahkan menu yang diblokir oleh access rule ke dalam blacklist menu."""
        blacklist = super()._load_menus_blacklist()
        user_id = self.env.user.id

        if user_id != 1:
            hidden_menus = self.env["saas.access.rule"]._get_hidden_menus_for_user(
                user_id
            )
            if hidden_menus:
                all_hidden = self.search([("id", "child_of", hidden_menus.ids)])
                blacklist = list(set(blacklist) | set(all_hidden.ids))

        return blacklist

    def _filter_visible_menus(self):
        """Saring menu yang tampil agar tidak menyertakan menu terlarang."""
        visible_menus = super()._filter_visible_menus()
        user_id = self.env.user.id

        if user_id != 1:
            hidden_menus = self.env["saas.access.rule"]._get_hidden_menus_for_user(
                user_id
            )
            if hidden_menus:
                all_hidden = self.search([("id", "child_of", hidden_menus.ids)])
                visible_menus = visible_menus - all_hidden

        return visible_menus
