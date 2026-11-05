/** @odoo-module */

/**
 * Dynamic preferred outreach destination editor. Loads active landing pages
 * and direct chat from Evie, storing one encoded value:
 * CHAT_DIRECT or LANDING_PAGE:<capsule_id>. Empty means no preference.
 */

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

export class EvieOutreachDestinationField extends Component {
    static template = "evie_base.EvieOutreachDestinationField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ loading: true, error: "", destinations: [] });
        onWillStart(async () => this.loadOptions());
    }

    get capsuleId() {
        return this.props.record.data.x_evie_capsule_id;
    }

    get currentValue() {
        return this.props.record.data[this.props.name] || "";
    }

    optionLabel(destination) {
        const make = destination.make ? ` (${destination.make.name})` : "";
        const preferred = destination.preferred ? ` — ${_t("Preferred")}` : "";
        return `${destination.name}${make}${preferred}`;
    }

    async loadOptions() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const result = await this.orm.call(
                "evie.personal.link", "get_destination_options", [this.capsuleId]);
            if (result.ok) {
                this.state.destinations = result.destinations;
            } else {
                this.state.error = result.message
                    || _t("Could not load outreach destinations. Try again later.");
            }
        } catch {
            this.state.error = _t("Evie is unreachable — try again later.");
        } finally {
            this.state.loading = false;
        }
    }

    onChange(event) {
        const value = event.target.value || false;
        this.props.record.update({ [this.props.name]: value });
    }
}

export const evieOutreachDestinationField = {
    component: EvieOutreachDestinationField,
};

registry.category("fields").add(
    "evie_outreach_destination", evieOutreachDestinationField);
