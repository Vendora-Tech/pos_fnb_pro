/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
import { LicenseBanner } from "./license_banner";

// Daftarkan LicenseBanner ke components Navbar
Navbar.components = {
    ...Navbar.components,
    LicenseBanner,
};

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

patch(ActionpadWidget.prototype, {
    get isPaymentDisabled() {
        const session = this.pos?.session;
        const isLocked = session?.license_state === "expired" || session?.license_state === "invalid";
        return this.pos?.accessRight?.disableClickPayment || isLocked;
    },
});

