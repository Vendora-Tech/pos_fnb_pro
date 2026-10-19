/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { LicenseBanner } from "./license_banner";

patch(Navbar, {
    components: {
        ...Navbar.components,
        LicenseBanner,
    },
});

patch(Navbar.prototype, {
    get saasLicenseState() {
        const session = this.pos?.session;
        return session?.license_state || "active";
    },

    get saasLicenseMessage() {
        const session = this.pos?.session;
        return session?.license_banner_msg || "";
    },

    get saasLicenseDaysLeft() {
        const session = this.pos?.session;
        return session?.license_days_left || 0;
    },
});
