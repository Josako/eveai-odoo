/** @odoo-module */

/**
 * evie_personal_link field widget (dual-personal-link-surfaces).
 *
 * Fetches the record's short personal outreach links from Evie on demand —
 * both pinned variants at once (website and chat-direct, no target
 * pre-selection) — and offers each for copying on its own full-width row
 * with its click count, for use in ad-hoc messages (mail, LinkedIn, …)
 * written by the rep. The links are never stored in Odoo: every fetch goes
 * to the Evie copy-surface endpoint. When Evie is unreachable the widget
 * shows a clear, non-blocking message; the form always keeps working.
 *
 * Usage in a form view (bound to the capsule anchor field):
 *     <field name="x_evie_capsule_id" widget="evie_personal_link"
 *            options="{'kind': 'lead'}"/>
 *
 * Options:
 *     kind (string, required): 'lead' or 'activity' — selects the Evie
 *         endpoint variant (lead-only links vs. (lead, activity) links).
 */

import { Component, useState } from "@odoo/owl";
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
        // variants: null until fetched; afterwards per-variant dicts
        // ({url, target_url, resolved_target, clicks}) or null when that
        // variant could not be composed.
        this.state = useState({ loading: false, error: "", variants: null });
    }

    get rows() {
        // Both variants side by side, each on its own full-width row. A
        // variant the endpoint returned as null is skipped.
        if (!this.state.variants) {
            return [];
        }
        const { website, chat } = this.state.variants;
        const rows = [];
        if (website) {
            rows.push({
                key: "website", icon: "fa fa-globe",
                label: _t("Website (chat widget)"), ...website,
            });
        }
        if (chat) {
            rows.push({
                key: "chat", icon: "fa fa-comments",
                label: _t("Chat client (direct)"), ...chat,
            });
        }
        return rows;
    }

    get capsuleId() {
        return this.props.record.data[this.props.name];
    }

    async onFetch() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const result = await this.orm.call(
                "evie.personal.link", "get_personal_link",
                [this.props.kind, this.capsuleId]);
            if (result.ok) {
                this.state.variants = {
                    website: result.website, chat: result.chat,
                };
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

    async onCopy(url) {
        try {
            await navigator.clipboard.writeText(url);
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
