/** @odoo-module */

/**
 * Reusable Evie capsule URLs component (odoo-lead-linked-urls).
 *
 * Lists the URL capsules linked to a record's capsule in Evie (the
 * CRM_ENTITY_HAS_URL relation) as external links that open in a new tab.
 * Read-only: linking and unlinking stay in Evie. Refreshes when the
 * window regains focus and whenever ``refreshKey`` changes, mirroring the
 * linked-documents component's lifecycle.
 *
 * Usage in a form view (view widget):
 *     <widget name="evie_capsule_urls"/>
 */

import { Component, onWillStart, onWillUpdateProps, useExternalListener, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class EvieCapsuleUrls extends Component {
    static template = "evie_base.EvieCapsuleUrls";
    static props = {
        resModel: String,
        resId: { type: [Number, Boolean], optional: true },
        capsuleIdField: { type: String, optional: true },
        refreshKey: { optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loaded: false,
            ok: true,
            linked: true,
            urls: [],
        });
        this.loading = false;

        onWillStart(() => this.load(this.props));
        onWillUpdateProps((next) => {
            if (next.refreshKey !== this.props.refreshKey
                    || next.resModel !== this.props.resModel
                    || next.resId !== this.props.resId) {
                return this.load(next);
            }
        });
        useExternalListener(window, "focus", () => this.load(this.props));
    }

    async load(props) {
        if (this.loading || !props.resId) {
            return;
        }
        this.loading = true;
        try {
            const result = await this.orm.silent.call(
                "evie.capsule.urls", "get_urls",
                [props.resModel, props.resId, props.capsuleIdField || "x_evie_capsule_id"]);
            this.state.ok = result.ok;
            this.state.linked = result.linked;
            this.state.urls = result.urls || [];
        } catch {
            this.state.ok = false;
        } finally {
            this.state.loaded = true;
            this.loading = false;
        }
    }

    kindLabel(entry) {
        const labels = {
            PROFILE: _t("Profile"),
            DIRECTORY: _t("Directory"),
            NEWS: _t("News"),
            OTHER: _t("Other"),
        };
        return labels[entry.kind] || entry.kind || labels.OTHER;
    }

    sourceLabel(entry) {
        return entry.source === "LIST_IMPORT" ? _t("List import") : _t("Manual");
    }
}

export class EvieCapsuleUrlsWidget extends Component {
    static template = "evie_base.EvieCapsuleUrlsWidget";
    static components = { EvieCapsuleUrls };
    static props = {
        record: Object,
        capsuleIdField: { type: String, optional: true },
        readonly: { type: Boolean, optional: true },
    };
}

export const evieCapsuleUrlsWidget = {
    component: EvieCapsuleUrlsWidget,
    extractProps: ({ attrs }) => ({
        capsuleIdField: attrs.capsule_id_field,
    }),
};

registry.category("view_widgets").add("evie_capsule_urls", evieCapsuleUrlsWidget);
