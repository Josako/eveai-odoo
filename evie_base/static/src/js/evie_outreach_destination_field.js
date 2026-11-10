/** @odoo-module */

/**
 * Dynamic outreach destination editor. Loads active landing pages and direct
 * chat from Evie, storing CHAT_DIRECT or LANDING_PAGE:<capsule_id>. On an
 * activity, an empty stored value displays the effective inherited choice.
 */

import {
    Component, onMounted, onPatched, onWillStart, useRef, useState,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

export class EvieOutreachDestinationField extends Component {
    static template = "evie_base.EvieOutreachDestinationField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            error: "",
            destinations: [],
            effectiveValue: "",
            useEffectiveValue: true,
        });
        this.destinationSelect = useRef("destinationSelect");
        onWillStart(async () => this.loadOptions());
        onMounted(() => this.syncSelectValue());
        onPatched(() => this.syncSelectValue());
    }

    get capsuleId() {
        return this.props.record.data.x_evie_capsule_id;
    }

    get currentValue() {
        const storedValue = this.props.record.data[this.props.name] || "";
        if (this.props.record.resModel !== "mail.activity") {
            return storedValue;
        }
        const explicitValue = storedValue === "CHAT_DIRECT"
            || storedValue.startsWith("LANDING_PAGE:") ? storedValue : "";
        if (explicitValue || !this.state.useEffectiveValue) {
            return explicitValue;
        }
        return this.state.effectiveValue;
    }

    syncSelectValue() {
        const select = this.destinationSelect.el;
        if (select && select.value !== this.currentValue) {
            select.value = this.currentValue;
        }
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
                this.state.effectiveValue = result.effective_value || "";
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
        this.state.useEffectiveValue = false;
        this.props.record.update({ [this.props.name]: value });
    }
}

export const evieOutreachDestinationField = {
    component: EvieOutreachDestinationField,
};

registry.category("fields").add(
    "evie_outreach_destination", evieOutreachDestinationField);
