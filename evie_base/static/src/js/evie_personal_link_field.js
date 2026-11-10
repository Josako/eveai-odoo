/** @odoo-module */

/**
 * evie_personal_link field widget (landing-page-improvement).
 *
 * Loads every active named outreach destination and direct chat on form
 * open and refreshes on window focus, with preferred/Make labels and
 * independent click counts. Links are never stored in Odoo. Failures are
 * non-blocking and the form keeps working.
 *
 * Usage in a form view (bound to the capsule anchor field):
 *     <field name="x_evie_capsule_id" widget="evie_personal_link"
 *            options="{'kind': 'lead'}"/>
 *
 * Options:
 *     kind (string, required): 'lead' or 'activity' — selects the Evie
 *         endpoint variant (lead-only links vs. (lead, activity) links).
 */

import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

export class EviePersonalLinkField extends Component {
    static template = "evie_base.EviePersonalLinkField";
    static props = {
        ...standardFieldProps,
        kind: String,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        // destinations: null until fetched; afterwards the API's ordered
        // destination collection with short/long URLs and click counts.
        this.state = useState({ loading: false, error: "", destinations: null, copied: null });
        this.onFocus = this.onFocus.bind(this);
        onWillStart(() => this.onFetch());
        window.addEventListener("focus", this.onFocus);
        onWillUnmount(() => {
            window.removeEventListener("focus", this.onFocus);
            clearTimeout(this.copiedTimer);
        });
    }

    onFocus() {
        if (!this.state.loading) {
            this.onFetch();
        }
    }

    get rows() {
        if (!this.state.destinations) {
            return [];
        }
        return this.state.destinations.map((destination) => {
            const clicks = Number(destination.clicks) || 0;
            return {
                ...destination,
                key: destination.key || "default",
                icon: destination.kind === "CHAT_DIRECT" ? "fa fa-comments" : "fa fa-globe",
                clicksLabel: clicks === 1 ? _t("1 click") : _t("%s clicks", clicks),
                clicksClass: this.clicksClass(clicks),
            };
        });
    }

    /** Grey when unopened, orange for a first look (1–2), green once engaged (3+). */
    clicksClass(clicks) {
        if (clicks >= 3) {
            return "o_evie_personal_link__clicks--high";
        }
        if (clicks >= 1) {
            return "o_evie_personal_link__clicks--low";
        }
        return "o_evie_personal_link__clicks--none";
    }

    get capsuleId() {
        return this.props.record.data[this.props.name];
    }

    async onFetch() {
        if (this.state.loading) {
            return;
        }
        this.state.loading = true;
        this.state.error = "";
        try {
            const result = await this.orm.call(
                "evie.personal.link", "get_personal_link",
                [this.props.kind, this.capsuleId]);
            if (result.ok) {
                this.state.destinations = result.destinations;
            } else {
                this.state.error = result.message
                    || _t("No personal link could be resolved.");
            }
        } catch {
            this.state.error = _t("Evie is unreachable — try again later.");
        } finally {
            this.state.loading = false;
        }
    }

    async onCopy(row) {
        try {
            await navigator.clipboard.writeText(row.url);
            this.state.copied = row.key;
            clearTimeout(this.copiedTimer);
            this.copiedTimer = setTimeout(() => {
                this.state.copied = null;
            }, 2000);
            this.notification.add(_t("Personal link copied to the clipboard."),
                { type: "success" });
        } catch {
            this.notification.add(
                _t("Could not access the clipboard — select and copy the link manually."),
                { type: "warning" });
        }
    }
}

export const eviePersonalLinkField = {
    component: EviePersonalLinkField,
    supportedOptions: [
        {
            label: "Record kind ('lead' or 'activity')",
            name: "kind",
            type: "string",
        },
    ],
    extractProps: ({ options }) => ({
        kind: options.kind || "lead",
    }),
};

registry.category("fields").add("evie_personal_link", eviePersonalLinkField);
