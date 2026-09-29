/** @odoo-module */

/**
 * evie_notifications service (odoo-notification-center).
 *
 * Holds the current user's Evie notifications for the systray bell and keeps
 * them live: new notifications arrive over the Odoo bus (and show a short
 * toast), and read/clear actions taken in one tab are mirrored in the
 * user's other tabs via the sync message. All reads and writes go through
 * the bell methods on ``evie.notification``, which scope to the current
 * user server-side.
 *
 * Bus types must match BUS_NEW / BUS_SYNC in models/evie_notification.py.
 */

import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";

const MODEL = "evie.notification";
const BUS_NEW = "evie_notification/new";
const BUS_SYNC = "evie_notification/sync";
const MAX_ITEMS = 30;

const TOAST_TYPES = { info: "info", success: "success", warning: "warning", danger: "danger" };

export const evieNotificationService = {
    dependencies: ["bus_service", "orm", "notification", "action"],

    start(env, { bus_service, orm, notification, action }) {
        const state = reactive({
            items: [],
            older: [],
            olderLoaded: false,
            unreadCount: 0,
            loaded: false,
        });

        async function load() {
            const result = await orm.silent.call(MODEL, "systray_get", []);
            state.items = result.items;
            state.unreadCount = result.unread_count;
            state.loaded = true;
        }

        async function loadOlder() {
            state.older = await orm.silent.call(MODEL, "systray_get_older", []);
            state.olderLoaded = true;
        }

        function applyRead(ids) {
            for (const item of state.items) {
                if (ids === true || ids.includes(item.id)) {
                    item.is_read = true;
                }
            }
        }

        function applyDismissed(ids) {
            const moved = state.items.filter((item) => ids === true || ids.includes(item.id));
            if (!moved.length) {
                return;
            }
            state.items = state.items.filter((item) => !moved.includes(item));
            if (state.olderLoaded) {
                state.older = [...moved.map((item) => ({ ...item, is_read: true })), ...state.older];
            }
        }

        bus_service.subscribe(BUS_NEW, (payload) => {
            if (state.items.some((item) => item.id === payload.id)) {
                return;
            }
            const { unread_count, ...item } = payload;
            state.items = [item, ...state.items].slice(0, MAX_ITEMS);
            state.unreadCount = unread_count;
            notification.add(item.body || item.title, {
                title: item.body ? item.title : undefined,
                type: TOAST_TYPES[item.tone] || "info",
            });
        });

        bus_service.subscribe(BUS_SYNC, (payload) => {
            state.unreadCount = payload.unread_count;
            applyRead(payload.all_read ? true : payload.read_ids);
            applyDismissed(payload.all_dismissed ? true : payload.dismissed_ids);
        });
        bus_service.start();

        load().catch(() => {
            // The bell simply stays empty; it retries when opened.
        });

        return {
            state,
            load,
            loadOlder,

            async markRead(ids) {
                applyRead(ids);
                const result = await orm.silent.call(MODEL, "mark_read", [ids]);
                state.unreadCount = result.unread_count;
            },

            async markAllRead() {
                applyRead(true);
                const result = await orm.silent.call(MODEL, "mark_all_read", []);
                state.unreadCount = result.unread_count;
            },

            async dismiss(ids) {
                applyRead(ids);
                applyDismissed(ids);
                const result = await orm.silent.call(MODEL, "dismiss", [ids]);
                state.unreadCount = result.unread_count;
            },

            async dismissAll() {
                applyRead(true);
                applyDismissed(true);
                const result = await orm.silent.call(MODEL, "dismiss_all", []);
                state.unreadCount = result.unread_count;
            },

            /** Mark read and open the related record / action, if any. */
            async open(item) {
                applyRead([item.id]);
                const result = await orm.call(MODEL, "action_open", [[item.id]]);
                if (result) {
                    await action.doAction(result);
                }
                return Boolean(result);
            },

            async viewAll() {
                await action.doAction("evie_notifications.action_evie_notification_my");
            },
        };
    },
};

registry.category("services").add("evie_notifications", evieNotificationService);
