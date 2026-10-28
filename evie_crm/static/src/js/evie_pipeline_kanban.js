/** @odoo-module */

/**
 * Evie Pipeline kanban (sales-accepted-phase-funnel-mapping).
 *
 * A js_class-scoped extension of the native kanban for the Evie Pipeline
 * board only: every lane header keeps the Evie phase as its title and shows
 * the mapped Odoo stage name(s) as a small muted subtitle beneath it
 * (default stage first). Lead phases and stages without a mapping render
 * without a subtitle.
 *
 * The subtitle map is fetched once per board mount by the renderer into a
 * shared reactive store; headers read it synchronously. Doing this in a
 * per-header onWillStart deadlocks the kanban's own render/update cycle
 * (silent blank board — verified on Odoo 19), so the async work lives one
 * level up.
 *
 * Odoo 19 note: the kanban column header lives in `KanbanHeader`
 * (`web.KanbanHeader` template); there is no separate KanbanColumn component
 * any more.
 */

import { onWillStart, reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanHeader } from "@web/views/kanban/kanban_header";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";

// Shared reactive store, (re)filled by the renderer on each board mount.
// Read during header rendering, so subtitles appear as soon as the RPC lands.
const subtitleStore = reactive({ map: {} });

export class EviePipelineKanbanHeader extends KanbanHeader {
    static template = "evie_crm.EviePipelineKanbanHeader";

    get stageSubtitle() {
        const value = this.props.group && this.props.group.value;
        const names = (value && subtitleStore.map[value]) || [];
        return names.join(" · ");
    }
}

export class EviePipelineKanbanRenderer extends KanbanRenderer {
    static components = {
        ...KanbanRenderer.components,
        KanbanHeader: EviePipelineKanbanHeader,
    };

    setup() {
        super.setup();
        this.orm = useService("orm");
        onWillStart(async () => {
            subtitleStore.map = await this.orm.call(
                "evie.phase_stage_map", "stage_subtitles", []);
        });
    }
}

export const eviePipelineKanbanView = {
    ...kanbanView,
    Renderer: EviePipelineKanbanRenderer,
};

registry.category("views").add("evie_pipeline_kanban", eviePipelineKanbanView);
