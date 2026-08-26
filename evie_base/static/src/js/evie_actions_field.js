/** @odoo-module */

/**
 * evie_actions field widget (odoo-capsule-actions).
 *
 * Renders the configured Evie data capsule actions for the record's capsule
 * type as buttons, discovered live from the Evie platform (cached
 * server-side with a TTL) — action definitions are never hardcoded here.
 *
 * The widget is bound to the record's ``x_evie_action_status`` field: its
 * value drives the running state (buttons disabled + indicator while an
 * action is in flight). Since sync-activity-proposal-to-odoo the running
 * state is derived from the discovery payload: each action carries its
 * ``busy_statuses`` (matched against the bound status field) instead of the
 * widget hardcoding a status value. Fallback for discovery payloads
 * predating that metadata: any non-empty status means running. When Evie
 * is unreachable the widget degrades to an unobtrusive placeholder; the
 * form always keeps working.
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

import { Component, useState, onWillStart } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";

export class EvieSpecialistDialog extends Component {
    static template = "evie_base.EvieSpecialistDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        title: String,
        specialists: Array,
        onConfirm: Function,
    };

    setup() {
        this.state = useState({
            specialistId: this.props.specialists[0]?.id,
        });
    }

    onConfirm() {
        this.props.onConfirm(this.state.specialistId);
        this.props.close();
    }
}

export class EvieActionsField extends Component {
    static template = "evie_base.EvieActionsField";
    static props = {
        ...standardFieldProps,
        capsuleType: { type: String },
        capsuleIdField: { type: String, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialogService = useService("dialog");
        this.state = useState({ ok: true, actions: [], executing: false });

        onWillStart(async () => {
            try {
                const result = await this.orm.call(
                    "evie.actions", "get_actions", [this.props.capsuleType]);
                this.state.ok = result.ok;
                this.state.actions = result.actions || [];
            } catch {
                this.state.ok = false;
            }
        });
    }

    get status() {
        return this.props.record.data[this.props.name] || false;
    }

    get running() {
        // Any action in flight? Drives the indicator badge; individual
        // buttons disable via isActionRunning (per-action busy metadata).
        return this.state.actions.some((action) => this.isActionRunning(action));
    }

    isActionRunning(action) {
        // Busy-state metadata from the discovery payload
        // (sync-activity-proposal-to-odoo): the action's declared
        // busy_statuses matched against the bound status field.
        const busyStatuses = action && Array.isArray(action.busy_statuses)
            ? action.busy_statuses : [];
        if (busyStatuses.length > 0) {
            return busyStatuses.includes(this.status);
        }
        // Fallback for discovery payloads predating busy metadata (old
        // Evie version or cache during rollout): any non-empty status
        // means an action is in flight.
        return Boolean(this.status);
    }

    buttonClass(action) {
        const base = "btn btn-sm me-1 mb-1";
        return `${base} ${action.class === "btn-primary" ? "btn-primary" : "btn-outline-secondary"}`;
    }

    async onAction(action) {
        if (!action.available || this.isActionRunning(action) || this.state.executing) {
            return;
        }
        const specialists = action.specialists || [];
        if (specialists.length > 1) {
            this.dialogService.add(EvieSpecialistDialog, {
                title: action.text,
                specialists,
                onConfirm: (specialistId) => this._execute(action, specialistId),
            });
        } else {
            await this._execute(action, null);
        }
    }

    async _execute(action, specialistId) {
        this.state.executing = true;
        try {
            const capsuleId = this.props.record.data[this.props.capsuleIdField];
            const data = await this.orm.call(
                "evie.actions", "execute_action",
                [action.action_type],
                {
                    capsule_id: capsuleId || null,
                    remote_id: this.props.record.resId,
                    specialist_id: specialistId,
                });
            this.notification.add(
                data.message || _t("The action was accepted by Evie."),
                { type: "success" });
        } catch (error) {
            this.notification.add(
                error.data?.message || _t("Could not execute the Evie action."),
                { type: "danger" });
        } finally {
            this.state.executing = false;
        }
    }
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
