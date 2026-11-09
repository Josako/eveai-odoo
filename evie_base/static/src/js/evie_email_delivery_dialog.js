/** @odoo-module */

/** Minimal Email activity preview, confirmation and delivery-result dialog. */

import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

export class EvieEmailDeliveryDialog extends Component {
    static template = "evie_base.EvieEmailDeliveryDialog";
    static components = { Dialog };
    static props = {
        close: Function,
        onPreview: Function,
        onSend: Function,
        onSettled: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({
            loading: false,
            sending: false,
            error: "",
            preview: null,
            templates: [],
            selectedTemplateId: "",
            needsPlainConsent: false,
            allowPlainWebsite: false,
            delivery: null,
            providerResult: {},
        });
        onWillStart(() => this.composePreview());
    }

    async composePreview() {
        this.state.loading = true;
        this.state.error = "";
        this.state.delivery = null;
        try {
            const result = await this.props.onPreview({
                template_id: this.state.selectedTemplateId
                    ? Number(this.state.selectedTemplateId) : null,
                allow_plain_website: this.state.allowPlainWebsite,
            });
            if (result.choice_required) {
                this.state.templates = result.templates || [];
                this.state.error = result.message || _t("Choose a template.");
                return;
            }
            if (result.plain_website_confirmation_required) {
                this.state.needsPlainConsent = true;
                this.state.error = result.message;
                return;
            }
            this.state.preview = result.preview;
            this.state.needsPlainConsent = false;
        } catch (error) {
            this.state.error = error.data?.message || _t("Could not compose the preview.");
        } finally {
            this.state.loading = false;
        }
    }

    async confirmSend() {
        if (!this.state.preview) {
            return;
        }
        this.state.sending = true;
        this.state.error = "";
        try {
            const result = await this.props.onSend({
                preview_hash: this.state.preview.composition_hash,
                template_id: this.state.preview.template_id,
                allow_plain_website: this.state.preview.website_link_mode === "PLAIN_WEBSITE_CONFIRMED",
            });
            this.state.delivery = result.delivery;
            this.state.providerResult = result.provider_result || {};
            if (!result.success) {
                this.state.error = result.message || _t("The Email was not accepted.");
            }
            this.props.onSettled?.(result);
        } catch (error) {
            this.state.error = error.data?.message || _t("Could not send the Email.");
            if (this.state.error.toLowerCase().includes("stale")) {
                this.state.preview = null;
                this.state.error = _t("The preview was stale. Review and confirm the recomposed Email.");
            }
        } finally {
            this.state.sending = false;
        }
    }

    recompose() {
        this.state.preview = null;
        this.state.delivery = null;
        this.state.providerResult = {};
    }
}
