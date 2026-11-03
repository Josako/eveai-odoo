/** @odoo-module */

/**
 * Reusable Evie capsule URLs component (odoo-lead-linked-urls).
 *
 * Lists the URL capsules linked to a record's capsule in Evie (the
 * CRM_ENTITY_HAS_URL relation) as external links that open in a new tab.
 * Users with write access on the record can link a URL (small dialog:
 * URL, label, kind) and unlink URLs, like the linked documents.
 * Refreshes when the window regains focus and whenever ``refreshKey``
 * changes, mirroring the linked-documents component's lifecycle.
 *
 * Usage in a form view (view widget):
 *     <widget name="evie_capsule_urls"/>
 */

import { Component, onWillStart, onWillUpdateProps, useExternalListener, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

const KIND_LABELS = {
    PROFILE: _t("Profile"),
    DIRECTORY: _t("Directory"),
    NEWS: _t("News"),
    OTHER: _t("Other"),
};

export class EvieLinkUrlDialog extends Component {
    static template = "evie_base.EvieLinkUrlDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        onConfirm: Function,
    };

    setup() {
        this.kinds = Object.entries(KIND_LABELS).map(([value, label]) => ({ value, label }));
        this.state = useState({ url: "", label: "", kind: "OTHER", saving: false, error: "" });
    }

    get validUrl() {
        return /^https?:\/\/\S+$/i.test(this.state.url.trim());
    }

    async onConfirm() {
        if (this.state.saving) {
            return;
        }
        if (!this.validUrl) {
            this.state.error = _t("Enter a URL starting with http:// or https://");
            return;
        }
        this.state.error = "";
        this.state.saving = true;
        try {
            await this.props.onConfirm({
                url: this.state.url.trim(),
                label: this.state.label.trim(),
                kind: this.state.kind,
            });
            this.props.close();
        } catch (error) {
            this.state.error = error.data?.message || _t("Could not link the URL.");
        } finally {
            this.state.saving = false;
        }
    }
}

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
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.state = useState({
            loaded: false,
            ok: true,
            linked: true,
            canWrite: false,
            urls: [],
            unlinking: null,
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

    get capsuleIdField() {
        return this.props.capsuleIdField || "x_evie_capsule_id";
    }

    get showActions() {
        return this.state.ok && this.state.linked && this.state.canWrite;
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
            this.state.canWrite = Boolean(result.can_write);
            this.state.urls = result.urls || [];
        } catch {
            this.state.ok = false;
        } finally {
            this.state.loaded = true;
            this.loading = false;
        }
    }

    kindLabel(entry) {
        return KIND_LABELS[entry.kind] || entry.kind || KIND_LABELS.OTHER;
    }

    sourceLabel(entry) {
        return entry.source === "LIST_IMPORT" ? _t("List import") : _t("Manual");
    }

    openLinkDialog() {
        this.dialog.add(EvieLinkUrlDialog, {
            onConfirm: async ({ url, label, kind }) => {
                await this.orm.call(
                    "evie.capsule.urls", "link_url",
                    [this.props.resModel, this.props.resId, url, label || false, kind,
                        this.capsuleIdField]);
                await this.load(this.props);
                this.notification.add(_t("Linked \"%s\" to this record.", label || url),
                    { type: "success" });
            },
        });
    }

    unlinkUrl(entry) {
        if (this.state.unlinking) {
            return;
        }
        const name = entry.label || entry.url;
        this.dialog.add(ConfirmationDialog, {
            title: _t("Unlink URL"),
            body: _t("Unlink \"%s\" from this record?", name),
            confirmLabel: _t("Unlink from record"),
            confirm: async () => {
                this.state.unlinking = entry.relation_id;
                try {
                    await this.orm.call(
                        "evie.capsule.urls", "unlink_url",
                        [this.props.resModel, this.props.resId, entry.relation_id,
                            this.capsuleIdField]);
                    this.state.urls = this.state.urls.filter(
                        (url) => url.relation_id !== entry.relation_id);
                    this.notification.add(_t("Unlinked \"%s\" from this record.", name),
                        { type: "success" });
                } catch (error) {
                    this.notification.add(
                        error.data?.message || _t("Could not unlink the URL."),
                        { type: "danger" });
                } finally {
                    this.state.unlinking = null;
                }
            },
            cancel: () => {},
        });
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
