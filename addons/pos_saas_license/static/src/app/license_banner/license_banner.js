/** @odoo-module **/

import { Component, useProps, t } from "@odoo/owl";

export class LicenseBanner extends Component {
    static template = "pos_saas_license.LicenseBanner";
    props = useProps({
        state: t.string().optional("active"),
        message: t.string().optional(""),
        daysLeft: t.number().optional(0),
    });

    get isWarning() {
        return this.props.state === "warning";
    }

    get isGrace() {
        return this.props.state === "grace";
    }

    get isExpired() {
        return this.props.state === "expired" || this.props.state === "invalid";
    }

    get alertClass() {
        if (this.isWarning) {
            return "alert-warning text-dark";
        }
        if (this.isGrace) {
            return "alert-danger text-white";
        }
        if (this.isExpired) {
            return "alert-danger text-white fw-bold";
        }
        return "d-none";
    }
}
