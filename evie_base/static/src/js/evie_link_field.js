/** @odoo-module */

/**
 * evie_link field widget (extend-odoo-lead-sync-2).
 *
 * Renders an Evie reference field (capsule id, document version id, ...) as
 * its value plus an "open in Evie" button carrying the Evie icon. Clicking
 * calls the single server-side dispatcher `action_evie_open(kind, reference)`
 * on the record, which exchanges the API key for a view token and returns
 * the URL to open.
 *
 * Usage in a form view:
 *     <field name="x_evie_capsule_id" widget="evie_link"
 *            options="{'kind': 'capsule'}" readonly="1"/>
 */

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class EvieLinkField extends Component {
    static template = "evie_base.EvieLinkField";
    static props = {
        ...standardFieldProps,
        kind: { type: String },
    };

    setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");
    }

    get rawValue() {
        return this.props.record.data[this.props.name];
    }

    get hasValue() {
        const value = this.rawValue;
        return value !== false && value !== null && value !== undefined && value !== "" && value !== 0;
    }

    async onOpen() {
        const action = await this.orm.call(
            this.props.record.resModel,
            "action_evie_open",
            [[this.props.record.resId], this.props.kind, this.rawValue],
        );
        await this.actionService.doAction(action);
    }
}

export const evieLinkField = {
    component: EvieLinkField,
    supportedOptions: [
        {
            label: "Evie entity kind",
            name: "kind",
            type: "string",
        },
    ],
    extractProps: ({ options }) => ({
        kind: options.kind || "document",
    }),
};

registry.category("fields").add("evie_link", evieLinkField);
