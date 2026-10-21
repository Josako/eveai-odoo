/** @odoo-module */

/**
 * Reusable Evie capsule documents component.
 *
 * Lists the documents linked to a record's capsule in Evie (the
 * CRM_ENTITY_HAS_DOCUMENT relation) and opens one in the Evie document
 * view on click. Refreshes when the window regains focus (e.g. after an
 * Evie popup produced a document) and whenever ``refreshKey`` changes, so a
 * host can trigger a reload after an action settled.
 *
 * Usage in a component:
 *     <EvieCapsuleDocuments resModel="'mail.activity'" resId="activityId"
 *                           refreshKey="state.documentsKey"/>
 *
 * Usage in a form view (view widget):
 *     <widget name="evie_capsule_documents"/>
 */

import { Component, onWillStart, onWillUpdateProps, useExternalListener, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";

const { DateTime } = luxon;

const FILE_ICONS = {
    pdf: "fa-file-pdf-o",
    doc: "fa-file-word-o",
    docx: "fa-file-word-o",
    xls: "fa-file-excel-o",
    xlsx: "fa-file-excel-o",
    csv: "fa-file-excel-o",
    ppt: "fa-file-powerpoint-o",
    pptx: "fa-file-powerpoint-o",
    md: "fa-file-text-o",
    txt: "fa-file-text-o",
    html: "fa-file-code-o",
    png: "fa-file-image-o",
    jpg: "fa-file-image-o",
    jpeg: "fa-file-image-o",
    mp3: "fa-file-audio-o",
    wav: "fa-file-audio-o",
    m4a: "fa-file-audio-o",
    mp4: "fa-file-video-o",
};

export class EvieCapsuleDocuments extends Component {
    static template = "evie_base.EvieCapsuleDocuments";
    static props = {
        resModel: String,
        resId: { type: [Number, Boolean], optional: true },
        capsuleIdField: { type: String, optional: true },
        refreshKey: { optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loaded: false,
            ok: true,
            linked: true,
            documents: [],
            opening: null,
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
                "evie.capsule.documents", "get_documents",
                [props.resModel, props.resId, props.capsuleIdField || "x_evie_capsule_id"]);
            this.state.ok = result.ok;
            this.state.linked = result.linked;
            this.state.documents = result.documents || [];
        } catch {
            this.state.ok = false;
        } finally {
            this.state.loaded = true;
            this.loading = false;
        }
    }

    fileIcon(document) {
        return FILE_ICONS[String(document.file_type || "").toLowerCase()] || "fa-file-o";
    }

    formatDate(document) {
        if (!document.created_at) {
            return "";
        }
        const value = DateTime.fromISO(document.created_at, { zone: "utc" });
        return value.isValid ? formatDateTime(value) : "";
    }

    get showShare() {
        // The shared-in-outreach flag only makes sense on activities
        // (tracked-document-links): outreach is composed per activity.
        return this.props.resModel === "mail.activity";
    }

    async toggleShared(document) {
        if (this.state.savingShare) {
            return;
        }
        const wanted = !document.shared_in_outreach;
        this.state.savingShare = document.relation_id;
        try {
            const applied = await this.orm.call(
                "evie.capsule.documents", "set_shared_in_outreach",
                [this.props.resModel, this.props.resId, document.relation_id,
                    wanted, this.props.capsuleIdField || "x_evie_capsule_id"]);
            document.shared_in_outreach = applied;
        } catch (error) {
            this.notification.add(
                error.data?.message || _t("Could not update the document."),
                { type: "danger" });
        } finally {
            this.state.savingShare = null;
        }
    }

    async openDocument(document) {
        if (this.state.opening) {
            return;
        }
        this.state.opening = document.document_version_id;
        try {
            const action = await this.orm.call(
                "evie.capsule.documents", "open_document",
                [this.props.resModel, this.props.resId, document.document_version_id,
                    this.props.capsuleIdField || "x_evie_capsule_id"]);
            await this.action.doAction(action);
        } catch (error) {
            this.notification.add(
                error.data?.message || _t("Could not open the document."),
                { type: "danger" });
        } finally {
            this.state.opening = null;
        }
    }
}

export class EvieCapsuleDocumentsWidget extends Component {
    static template = "evie_base.EvieCapsuleDocumentsWidget";
    static components = { EvieCapsuleDocuments };
    static props = {
        record: Object,
        capsuleIdField: { type: String, optional: true },
        readonly: { type: Boolean, optional: true },
    };
}

export const evieCapsuleDocumentsWidget = {
    component: EvieCapsuleDocumentsWidget,
    extractProps: ({ attrs }) => ({
        capsuleIdField: attrs.capsule_id_field,
    }),
};

registry.category("view_widgets").add("evie_capsule_documents", evieCapsuleDocumentsWidget);
