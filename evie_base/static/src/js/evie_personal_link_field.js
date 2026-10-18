/** @odoo-module */

/**
 * evie_personal_link field widget (short-personal-link-surfaces).
 *
 * Fetches the record's short personal outreach link from Evie on demand and
 * offers it for copying — for use in ad-hoc messages (mail, LinkedIn, …)
 * written by the rep. The link is never stored in Odoo: every fetch goes to
 * the Evie copy-surface endpoint. When Evie is unreachable the widget shows
 * a clear, non-blocking message; the form always keeps working.
 *
 * Usage in a form view (bound to the capsule anchor field):
 *     <field name="x_evie_capsule_id" widget="evie_personal_link"
 *            options="{'kind': 'lead'}"/>
 *
 * Options:
 *     kind (string, required): 'lead' or 'activity' — selects the Evie
 *         endpoint variant (lead-only link vs. (lead, activity) link).
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
        this.state = useState({ loading: false, url: "", error: "", target: "" });
    }

    get targetLabel() {
        // Where the link lands (lead-level-outreach-link-target): the
        // endpoint resolves the target live; shown so the rep copies with
        // the right expectation. Display-only — the choice itself is the
        // x_evie_outreach_link_target field on the form.
        if (this.state.target === "WEBSITE") {
            return _t("Lands on: website");
        }
        if (this.state.target === "CHAT_DIRECT") {
            return _t("Lands on: chat client");
        }
        return "";
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
            if (result.ok && result.url) {
                this.state.url = result.url;
                this.state.target = result.target || "";
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

    async onCopy() {
        try {
            await navigator.clipboard.writeText(this.state.url);
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
