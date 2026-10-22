/** @odoo-module */

/**
 * Reusable Evie capsule actions component (odoo-capsule-actions).
 *
 * Renders the configured Evie data capsule actions for a capsule type as
 * buttons, discovered live from the Evie platform — action definitions are
 * never hardcoded here — with specialist selection and running-state
 * feedback. Two modes:
 *
 * - Static (``status`` given, no ``resModel``/``resId``): discovery per
 *   capsule type (cached server-side); the running state matches each
 *   action's ``busy_statuses`` against the given status value. Used by the
 *   ``evie_actions`` field widget, where the form record carries the status.
 * - Live (``resModel`` + ``resId``): discovery scoped to the record's
 *   capsule (applicable actions only, each with its live ``running`` flag),
 *   polled while an action runs and refreshed when the window regains
 *   focus. Usable in any component, with no bound status field.
 *
 * ``stacked`` (default false) renders a wrapping row of buttons — the
 * CRM form layout. Pass ``stacked`` true for full-width rows (icon,
 * label, chevron) as in the meeting window.
 *
 * Actions that declare ``ui_group`` / ``ui_group_label`` /
 * ``ui_group_order`` in their YAML are rendered under labeled sections
 * (Proposal / Meeting / Follow-up, …). Ungrouped actions stay flat.
 *
 * ``onSettled`` is called after an action completed: immediately for
 * accepted non-popup actions, and (live mode) when a running action ends.
 * When Evie is unreachable the component degrades to an unobtrusive
 * placeholder.
 */

import { Component, onMounted, onWillStart, onWillUnmount, onWillUpdateProps, reactive, useExternalListener, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const POLL_INTERVAL_MS = 5000;

// Popup-opening result kinds (whitelist — capture-form-action,
// odoo-external-capture-review): chat opens the proposal session, form the
// capture form, review the capture review; all use the same popup pattern.
const POPUP_WINDOWS = {
    chat: "evie_proposal_chat",
    form: "evie_capture_form",
    review: "evie_capture_review",
};

// The action last started per capsule, as in the Evie admin client: actions
// share their busy field (e.g. action_status GENERATING), so while the
// capsule is busy only this one shows as running; the others holding the
// same busy status are disabled without a spinner. Module-level, so it
// survives remounts.
const startedActionByCapsule = reactive({});

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

export class EvieCapsuleActions extends Component {
    static template = "evie_base.EvieCapsuleActions";
    static props = {
        capsuleType: String,
        capsuleId: { type: [Number, String, Boolean], optional: true },
        remoteId: { type: [Number, Boolean], optional: true },
        status: { type: [String, Boolean], optional: true },
        resModel: { type: String, optional: true },
        resId: { type: [Number, Boolean], optional: true },
        capsuleIdField: { type: String, optional: true },
        onSettled: { type: Function, optional: true },
        // Default false: wrapping button row (CRM forms). Meeting window
        // passes stacked=true for full-width rows.
        stacked: { type: Boolean, optional: true },
    };
    static defaultProps = {
        stacked: false,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialogService = useService("dialog");
        this.state = useState({
            ok: true,
            loaded: false,
            actions: [],
            capsuleId: false,
            pending: {}, // action_type -> true while its request is in flight
        });
        this.started = useState(startedActionByCapsule);
        this.loading = false;

        onWillStart(() => this.load(this.props));
        onWillUpdateProps((next) => {
            if (next.capsuleType !== this.props.capsuleType
                    || next.resModel !== this.props.resModel
                    || next.resId !== this.props.resId) {
                return this.load(next);
            }
        });
        onMounted(() => {
            this.pollTimer = setInterval(() => {
                if (this.live && this.busy && !document.hidden) {
                    this.load(this.props);
                }
            }, POLL_INTERVAL_MS);
        });
        onWillUnmount(() => clearInterval(this.pollTimer));
        useExternalListener(window, "focus", () => {
            if (this.live) {
                this.load(this.props);
            }
        });
    }

    get live() {
        return Boolean(this.props.resModel && this.props.resId);
    }

    get capsuleId() {
        return this.live ? this.state.capsuleId : this.props.capsuleId;
    }

    get remoteId() {
        return this.props.remoteId || (this.live ? this.props.resId : false);
    }

    get capsuleKey() {
        return this.capsuleId ? String(this.capsuleId) : "";
    }

    /** Whether the capsule is busy, i.e. any action holds its busy status. */
    get busy() {
        return this.state.actions.some((action) => this.isActionBusy(action));
    }

    /**
     * Actions clustered by YAML ``ui_group`` for labeled sections.
     * Groups sort by ``ui_group_order`` then key; actions within a group
     * by ``order`` then text. Actions without a group form one unlabeled
     * bucket (kept last) so older payloads still render flat.
     */
    /**
     * Display label for a group key — prefer YAML ``ui_group_label``, else
     * title-case the key so CRM forms always show section chrome.
     */
    _groupLabel(key, explicit) {
        if (explicit) {
            return explicit;
        }
        if (!key) {
            return "Actions";
        }
        return String(key)
            .split(/[_-]+/)
            .filter(Boolean)
            .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
            .join(" ");
    }

    get actionGroups() {
        const buckets = new Map();
        for (const action of this.state.actions) {
            const key = action.ui_group || "";
            if (!buckets.has(key)) {
                buckets.set(key, {
                    key: key || "_ungrouped",
                    label: this._groupLabel(key, action.ui_group_label || ""),
                    order: Number.isFinite(action.ui_group_order)
                        ? action.ui_group_order
                        : (key ? 1000 : Number.POSITIVE_INFINITY),
                    actions: [],
                });
            } else if (action.ui_group_label) {
                // Prefer an explicit label once one arrives in the bucket.
                buckets.get(key).label = action.ui_group_label;
            }
            buckets.get(key).actions.push(action);
        }
        const groups = [...buckets.values()];
        for (const group of groups) {
            group.actions.sort((a, b) => {
                const ao = Number.isFinite(a.order) ? a.order : 1000;
                const bo = Number.isFinite(b.order) ? b.order : 1000;
                if (ao !== bo) {
                    return ao - bo;
                }
                return String(a.text || "").localeCompare(String(b.text || ""));
            });
        }
        groups.sort((a, b) => {
            if (a.order !== b.order) {
                return a.order - b.order;
            }
            return String(a.key).localeCompare(String(b.key));
        });
        return groups;
    }

    /** The started action while the capsule is busy, when known. */
    get runningAction() {
        const started = this.started[this.capsuleKey];
        return this.state.actions.find(
            (action) => action.action_type === started && this.isActionBusy(action)) || null;
    }

    async load(props) {
        if (this.loading) {
            return;
        }
        this.loading = true;
        const wasBusy = this.state.loaded && this.busy;
        try {
            const live = Boolean(props.resModel && props.resId);
            const result = live
                ? await this.orm.silent.call("evie.actions", "get_record_actions", [
                    props.capsuleType, props.resModel, props.resId,
                    props.capsuleIdField || "x_evie_capsule_id",
                ])
                : await this.orm.call("evie.actions", "get_actions", [props.capsuleType]);
            this.state.ok = result.ok;
            this.state.actions = result.actions || [];
            this.state.capsuleId = result.capsule_id || false;
        } catch {
            this.state.ok = false;
        } finally {
            this.state.loaded = true;
            this.loading = false;
        }
        if (wasBusy && !this.busy) {
            this.props.onSettled?.();
        }
    }

    /**
     * Whether Evie would refuse the action now (capsule holds one of its
     * busy statuses). Disabled without a spinner unless it is also running.
     */
    isActionBusy(action) {
        if (this.live) {
            // New discovery: explicit blocked flag. Older payloads used
            // running for "would refuse" — keep that as the disable check.
            if (typeof action?.blocked === "boolean") {
                return action.blocked;
            }
            return Boolean(action?.running);
        }
        // Busy-state metadata from the discovery payload
        // (sync-activity-proposal-to-odoo): the action's declared
        // busy_statuses matched against the given status. An explicitly
        // EMPTY list means the action has no busy concept — the status
        // holds the LAST run's terminal state (e.g. DONE), which must never
        // mark this action as running.
        if (action && Array.isArray(action.busy_statuses)) {
            return action.busy_statuses.length > 0
                && action.busy_statuses.includes(this.props.status);
        }
        // Fallback for discovery payloads predating busy metadata (old
        // Evie version or cache during rollout): any non-empty status
        // means an action is in flight.
        return Boolean(this.props.status);
    }

    /**
     * The action actually in progress: spinner + In progress pill.
     * Prefers the server's ``running`` flag (survives refresh); falls back
     * to the action started in this browser while the capsule is busy.
     */
    isActionRunning(action) {
        if (this.state.pending[action.action_type]) {
            return true;
        }
        if (this.live && typeof action?.blocked === "boolean") {
            return Boolean(action.running);
        }
        return this.runningAction?.action_type === action.action_type;
    }

    isDisabled(action) {
        return !action.available || this.isActionRunning(action) || this.isActionBusy(action);
    }

    get isStacked() {
        return Boolean(this.props.stacked);
    }

    buttonClass(action) {
        // Same meeting-window chrome everywhere; only the flex direction
        // differs (column when stacked, wrapping row otherwise).
        return "o_evie_actions__row";
    }

    actionIcon(action) {
        if (this.isInteractive(action)) {
            return "fa-comments-o";
        }
        if (action.class === "btn-success") {
            return "fa-check";
        }
        return action.action_kind === "START_SPECIALIST" ? "fa-play" : "fa-bolt";
    }

    isInteractive(action) {
        // Interactive actions (interactive-activity-proposal-entry-points)
        // open an Evie popup instead of enqueueing a background run.
        return String(action?.execution || "").toLowerCase() === "interactive";
    }

    async onAction(action) {
        if (this.isDisabled(action)) {
            return;
        }
        // Interactive actions resolve their specialist per capsule (the
        // activity type's item configuration) — no picker.
        if (this.isInteractive(action)) {
            await this._execute(action, null);
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
        this.state.pending[action.action_type] = true;
        try {
            const data = await this.orm.call(
                "evie.actions", "execute_action",
                [action.action_type],
                {
                    capsule_id: this.capsuleId || null,
                    remote_id: this.remoteId || null,
                    specialist_id: specialistId,
                });
            if (data && POPUP_WINDOWS[data.kind] && data.url) {
                window.open(data.url, POPUP_WINDOWS[data.kind], "width=520,height=720,popup=yes");
                return;
            }
            if (this.capsuleKey) {
                this.started[this.capsuleKey] = action.action_type;
            }
            this.notification.add(
                data?.message || _t("The action was accepted by Evie."),
                { type: "success" });
            if (this.live) {
                await this.load(this.props);
            }
            this.props.onSettled?.();
        } catch (error) {
            this.notification.add(
                error.data?.message || _t("Could not execute the Evie action."),
                { type: "danger" });
        } finally {
            delete this.state.pending[action.action_type];
        }
    }
}
