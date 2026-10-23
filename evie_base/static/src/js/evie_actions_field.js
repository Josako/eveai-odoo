/** @odoo-module */

/**
 * evie_actions field widget (odoo-capsule-actions).
 *
 * Form binding of the reusable ``EvieCapsuleActions`` component: renders
 * the configured Evie data capsule actions for the record's capsule type.
 *
 * Uses live discovery (``resModel`` / ``resId``) so CRM forms get the same
 * grouped actions payload as the meeting window. The bound status field
 * remains a fallback for older payloads that lack ``blocked`` / ``running``.
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
 *     stacked (boolean, optional): full-width column rows (default false —
 *         wrapping button row for CRM forms). Pass true for the meeting-
 *         window layout.
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
        stacked: { type: Boolean, optional: true },
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
        {
            label: "Stacked (meeting-window) layout",
            name: "stacked",
            type: "boolean",
        },
    ],
    extractProps: ({ options }) => ({
        capsuleType: options.capsule_type || "",
        capsuleIdField: options.capsule_id_field || "x_evie_capsule_id",
        // Default false: CRM forms use a wrapping button row. Meeting
        // window passes stacked explicitly on EvieCapsuleActions.
        stacked: options.stacked === true,
    }),
};

registry.category("fields").add("evie_actions", evieActionsField);
