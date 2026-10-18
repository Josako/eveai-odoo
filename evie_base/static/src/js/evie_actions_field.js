/** @odoo-module */

/**
 * evie_actions field widget (odoo-capsule-actions).
 *
 * Form binding of the reusable ``EvieCapsuleActions`` component: renders
 * the configured Evie data capsule actions for the record's capsule type.
 *
 * The widget is bound to the record's ``x_evie_action_status`` field: its
 * value drives the running state (buttons disabled + indicator while an
 * action is in flight), matched against each action's ``busy_statuses``
 * from the discovery payload (sync-activity-proposal-to-odoo).
 *
 * Usage in a form view:
 *     <field name="x_evie_action_status" widget="evie_actions"
 *            options="{'capsule_type': 'CRM_LEAD'}"/>
 *
 * Options:
 *     capsule_type (string, required): the Evie Data Capsule type whose
 *         actions are discovered (e.g. 'CRM_LEAD', 'CRM_ACTIVITY').
 *     capsule_id_field (string, optional): the record field holding the
 *         Evie capsule id, passed to the execute endpoint. Defaults to
 *         'x_evie_capsule_id' (the anchor contract on every synced model).
 */

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { EvieCapsuleActions } from "@evie_base/js/evie_capsule_actions";

export class EvieActionsField extends Component {
    static template = "evie_base.EvieActionsField";
    static components = { EvieCapsuleActions };
    static props = {
        ...standardFieldProps,
        capsuleType: { type: String },
        capsuleIdField: { type: String, optional: true },
    };
}

export const evieActionsField = {
    component: EvieActionsField,
    supportedOptions: [
        {
            label: "Evie capsule type",
            name: "capsule_type",
            type: "string",
        },
        {
            label: "Field holding the Evie capsule id",
            name: "capsule_id_field",
            type: "string",
        },
    ],
    extractProps: ({ options }) => ({
        capsuleType: options.capsule_type || "",
        capsuleIdField: options.capsule_id_field || "x_evie_capsule_id",
    }),
};

registry.category("fields").add("evie_actions", evieActionsField);
