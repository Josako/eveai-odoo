/** @odoo-module **/

/**
 * Website Builder options for the Evie Chat block (Odoo 19 html_builder).
 *
 * Fields mirror the Strapi ``evie-chat-widget`` component: magic link,
 * chat client base URL, chat API key, and height.
 */

import { BuilderAction } from "@html_builder/core/builder_action";
import { BaseOptionComponent } from "@html_builder/core/utils";
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";

export class EvieChatOption extends BaseOptionComponent {
    static template = "evie_website.EvieChatOption";
    static selector = ".s_evie_chat";
    static applyTo = ".s_evie_chat__mount";
}

/** Keep data-evie-height and the mount box style in sync. */
export class EvieHeightAction extends BuilderAction {
    static id = "evieHeight";

    getValue({ editingElement }) {
        return editingElement.dataset.evieHeight || "600";
    }

    apply({ editingElement, value }) {
        const height = Math.max(320, parseInt(value, 10) || 600);
        editingElement.dataset.evieHeight = String(height);
        editingElement.style.minHeight = `${height}px`;
        editingElement.style.height = `${height}px`;
    }
}

export class EvieChatOptionPlugin extends Plugin {
    static id = "evieChatOption";
    resources = {
        builder_options: [EvieChatOption],
        builder_actions: { EvieHeightAction },
    };
}

registry.category("website-plugins").add(EvieChatOptionPlugin.id, EvieChatOptionPlugin);
