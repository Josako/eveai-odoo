/** @odoo-module **/

/**
 * Public-page boot for the Evie Chat website building block.
 *
 * Mirrors the Strapi ``evie-chat-widget`` flow: read magic link / base URL /
 * API key from the block's data attributes, load widget assets, call
 * ``EvieChat.init``. Skips live init while the website editor is open.
 */

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

const SCRIPT_ID = "evie-odoo-chat-widget-script";
const CSS_ID = "evie-odoo-chat-widget-styles";

function isWebsiteEditMode(el) {
    return Boolean(
        el.closest(".o_editable")
        || document.documentElement.classList.contains("o_editable")
        || document.body.classList.contains("editor_enable")
        || document.body.classList.contains("editor_has_snippets"),
    );
}

function toAbsoluteUrl(url, baseUrl) {
    const raw = String(url || "").trim();
    if (!raw) {
        return "";
    }
    if (/^https?:\/\//i.test(raw)) {
        return raw;
    }
    const base = String(baseUrl || "").replace(/\/+$/, "");
    return new URL(raw.replace(/^\//, ""), `${base}/`).href;
}

export class EvieChatInteraction extends Interaction {
    static selector = ".s_evie_chat";

    setup() {
        this.mountEl = this.el.querySelector(".s_evie_chat__mount");
        this._booted = false;
    }

    start() {
        if (!this.mountEl) {
            return;
        }
        this._applyHeight();
        if (isWebsiteEditMode(this.el)) {
            return;
        }
        this._boot();
    }

    destroy() {
        this._booted = false;
    }

    _applyHeight() {
        const height = Math.max(
            320,
            parseInt(this.mountEl.dataset.evieHeight || "600", 10) || 600,
        );
        this.mountEl.style.minHeight = `${height}px`;
        this.mountEl.style.height = `${height}px`;
    }

    _config() {
        return {
            magicLinkCode: String(this.mountEl.dataset.evieMagicLinkCode || "").trim(),
            baseUrl: String(this.mountEl.dataset.evieBaseUrl || "").trim().replace(/\/+$/, ""),
            apiKey: String(this.mountEl.dataset.evieApiKey || "").trim(),
        };
    }

    _showError(message) {
        this.mountEl.innerHTML = `
            <div class="s_evie_chat__error" role="alert">
                <p class="s_evie_chat__error-title">Evie Chat</p>
                <p class="s_evie_chat__error-body">${message}</p>
            </div>`;
    }

    async _boot() {
        if (this._booted) {
            return;
        }
        const { magicLinkCode, baseUrl, apiKey } = this._config();
        if (!magicLinkCode || !baseUrl || !apiKey) {
            this._showError(
                "Configure Magic link, Chat client URL and Chat API key in the website editor.",
            );
            return;
        }
        this._booted = true;
        try {
            await this._ensureAssets(baseUrl);
            const EvieChat = window.EvieChat;
            if (!EvieChat || typeof EvieChat.init !== "function") {
                throw new Error("EvieChat failed to load.");
            }
            this.mountEl.innerHTML = "";
            const container = document.createElement("div");
            container.className = "s_evie_chat__widget";
            container.style.cssText = "height:100%;min-height:inherit;display:flex;flex-direction:column;";
            this.mountEl.appendChild(container);
            await Promise.resolve(EvieChat.init({
                container,
                magicLinkCode,
                baseUrl,
                apiKey,
            }));
        } catch (error) {
            this._booted = false;
            console.error("[evie_website] Failed to boot Evie Chat:", error);
            this._showError(
                error?.message || "Could not load the Evie chat widget.",
            );
        }
    }

    async _ensureAssets(baseUrl) {
        const assetsRes = await fetch(`${baseUrl}/chat/api/widget_assets`, {
            headers: { Accept: "application/json" },
        });
        if (!assetsRes.ok) {
            throw new Error(`Could not load widget assets (${assetsRes.status}).`);
        }
        const assets = await assetsRes.json();
        const cssHref = toAbsoluteUrl(assets.scopedCssUrl || assets.cssUrl, baseUrl);
        const scriptSrc = toAbsoluteUrl(assets.scriptUrl, baseUrl);
        if (!cssHref || !scriptSrc) {
            throw new Error("Widget asset URLs are missing.");
        }
        if (!document.getElementById(CSS_ID)) {
            const link = document.createElement("link");
            link.id = CSS_ID;
            link.rel = "stylesheet";
            link.href = cssHref;
            document.head.appendChild(link);
        }
        if (document.getElementById(SCRIPT_ID) && window.EvieChat) {
            return;
        }
        await new Promise((resolve, reject) => {
            const existing = document.getElementById(SCRIPT_ID);
            if (existing) {
                existing.addEventListener("load", () => resolve(), { once: true });
                existing.addEventListener("error", () => reject(new Error("Widget script failed.")), { once: true });
                if (window.EvieChat) {
                    resolve();
                }
                return;
            }
            const script = document.createElement("script");
            script.id = SCRIPT_ID;
            script.src = scriptSrc;
            script.async = true;
            script.onload = () => resolve();
            script.onerror = () => reject(new Error("Widget script failed to load."));
            document.head.appendChild(script);
        });
    }
}

registry.category("public.interactions").add("evie_website.evie_chat", EvieChatInteraction);
