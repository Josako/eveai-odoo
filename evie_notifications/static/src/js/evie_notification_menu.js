/** @odoo-module */

/**
 * Evie notification bell in the systray (odoo-notification-center).
 *
 * Same building blocks as Odoo's own activity menu (Dropdown +
 * useDropdownState, registered in the "systray" registry). The data and
 * live updates live in the ``evie_notifications`` service; this component
 * only renders the panel: Recent / Older tabs, mark read, clear, view all.
 */

import { Component, useState } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const KIND_ICONS = {
    lead: "fa fa-handshake-o",
    activity: "fa fa-clock-o",
    other: "fa fa-bell",
};

export class EvieNotificationMenu extends Component {
    static template = "evie_notifications.EvieNotificationMenu";
    static components = { Dropdown };
    static props = {};

    setup() {
        this.evieNotifications = useService("evie_notifications");
        this.store = useState(this.evieNotifications.state);
        this.ui = useState({ tab: "recent" });
        this.dropdown = useDropdownState();
    }

    get items() {
        return this.ui.tab === "recent" ? this.store.items : this.store.older;
    }

    get counterLabel() {
        const count = this.store.unreadCount;
        return count > 99 ? "99+" : String(count);
    }

    async onBeforeOpen() {
        this.ui.tab = "recent";
        await this.evieNotifications.load();
    }

    async showTab(tab) {
        this.ui.tab = tab;
        if (tab === "older") {
            await this.evieNotifications.loadOlder();
        }
    }

    kindIcon(item) {
        return item.kind === "evie" ? "o_evie_icon" : KIND_ICONS[item.kind] || KIND_ICONS.other;
    }

    relativeTime(item) {
        if (!item.create_date) {
            return "";
        }
        return deserializeDateTime(item.create_date).toRelative() || "";
    }

    itemClass(item) {
        return [
            "o_evie_notification_item",
            `o_evie_notification_item--${item.tone || "info"}`,
            item.is_read ? "" : "o_evie_notification_item--unread",
        ].join(" ");
    }

    async onClickItem(item) {
        const opened = await this.evieNotifications.open(item);
        if (opened) {
            this.dropdown.close();
        }
    }

    async onDismiss(item) {
        await this.evieNotifications.dismiss([item.id]);
    }

    async onMarkAllRead() {
        await this.evieNotifications.markAllRead();
    }

    async onClearAll() {
        await this.evieNotifications.dismissAll();
    }

    async onViewAll() {
        this.dropdown.close();
        await this.evieNotifications.viewAll();
    }

    get emptyLabel() {
        return this.ui.tab === "recent"
            ? _t("You're all caught up.")
            : _t("No cleared notifications.");
    }
}

registry
    .category("systray")
    .add("evie_notifications.menu", { Component: EvieNotificationMenu }, { sequence: 25 });
