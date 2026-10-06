/** @odoo-module */

/**
 * Evie morning brief (odoo-native-evie-surfaces, feature 1).
 *
 * On Odoo load the service asks ``evie.brief`` whether today's brief should
 * pop up (once per local day, server-side, only when there is something to
 * show). The sun button (bottom right) and the ``evie_notifications.morning_brief``
 * client action (opened by the daily digest notification) reopen it.
 */

import { Component } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { Dialog } from "@web/core/dialog/dialog";
import { deserializeDate } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const MODEL = "evie.brief";
/** Let Odoo settle before the popup. */
const AUTO_OPEN_DELAY_MS = 1500;

export class EvieMorningBriefDialog extends Component {
    static template = "evie_notifications.MorningBriefDialog";
    static components = { Dialog };
    static props = {
        brief: Object,
        openItem: Function,
        openMore: Function,
        close: Function,
    };

    get title() {
        return _t("Morning brief");
    }

    get dateLabel() {
        return deserializeDate(this.props.brief.date).toLocaleString({
            weekday: "long",
            month: "long",
            day: "numeric",
        });
    }
}

export const evieMorningBriefService = {
    dependencies: ["orm", "dialog", "action"],

    start(env, { orm, dialog, action }) {
        let closeDialog = null;

        function show(brief) {
            closeDialog?.();
            closeDialog = dialog.add(
                EvieMorningBriefDialog,
                { brief, openItem, openMore },
                { onClose: () => (closeDialog = null) }
            );
        }

        async function open() {
            const { brief } = await orm.call(MODEL, "get_brief", []);
            show(brief);
        }

        async function openItem(item) {
            const result = await orm.call(MODEL, "action_open_item", [item.model, item.id]);
            if (result) {
                closeDialog?.();
                await action.doAction(result);
            }
        }

        async function openMore(xmlid) {
            closeDialog?.();
            await action.doAction(xmlid);
        }

        browser.setTimeout(async () => {
            try {
                const result = await orm.silent.call(MODEL, "get_brief", [], { auto: true });
                if (result.show) {
                    show(result.brief);
                }
            } catch {
                // The brief never gets in the way of using Odoo.
            }
        }, AUTO_OPEN_DELAY_MS);

        return { open };
    },
};

export class EvieMorningBriefButton extends Component {
    static template = "evie_notifications.MorningBriefButton";
    static props = {};

    setup() {
        this.morningBrief = useService("evie_morning_brief");
    }
}

registry.category("services").add("evie_morning_brief", evieMorningBriefService);
registry
    .category("main_components")
    .add("evie_notifications.MorningBriefButton", { Component: EvieMorningBriefButton });
registry
    .category("actions")
    .add("evie_notifications.morning_brief", (env) => env.services.evie_morning_brief.open());
