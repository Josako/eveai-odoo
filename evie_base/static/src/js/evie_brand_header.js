/** @odoo-module */

/**
 * evie_brand_header view widget (odoo-evie-form-branding).
 *
 * Renders the Evie icon plus a section title above the Evie section of a
 * form. Use this on forms that have no core notebook: Odoo's Notebook
 * component hides the tab bar when only one page is visible, so the
 * branded-tab CSS hook (`.o_notebook .nav-link[name="evie"]`) is
 * unavailable there. On forms with a core multi-page notebook, prefer the
 * branded tab instead (page `name="evie"`).
 *
 * Usage in a form view:
 *     <widget name="evie_brand_header" title="EVIE"
 *             invisible="not x_evie_capsule_id"/>
 *
 * Attributes:
 *     title (string, optional): the header text. Defaults to 'EVIE'.
 */

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class EvieBrandHeader extends Component {
    static template = "evie_base.EvieBrandHeader";
    static props = {
        record: { type: Object, optional: true },
        title: { type: String, optional: true },
    };

    get title() {
        return this.props.title || "EVIE";
    }
}

export const evieBrandHeader = {
    component: EvieBrandHeader,
    extractProps: ({ attrs }) => ({
        title: attrs.title,
    }),
};

registry.category("view_widgets").add("evie_brand_header", evieBrandHeader);
