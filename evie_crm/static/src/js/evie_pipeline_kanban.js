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
 * The subtitle map is fetched once per page load (module-level promise) —
 * mapping edits surface on the next board reload, which matches how often an
 * admin touches the mapping.
 *
 * Odoo 19 note: the kanban column header lives in `KanbanHeader`
 * (`web.KanbanHeader` template); there is no separate KanbanColumn component
 * any more.
 */

import { onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanHeader } from "@web/views/kanban/kanban_header";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";

let subtitlesPromise = null;

function loadStageSubtitles(orm) {
    subtitlesPromise ||= orm.call("evie.phase_stage_map", "stage_subtitles", []);
    return subtitlesPromise;
}

export class EviePipelineKanbanHeader extends KanbanHeader {
    static template = "evie_crm.EviePipelineKanbanHeader";

    setup() {
        super.setup();  // provides this.orm among others
        this.subtitleState = useState({ subtitle: "" });
        onWillStart(async () => {
            const subtitles = await loadStageSubtitles(this.orm);
            const value = this.props.group && this.props.group.value;
            const names = (value && subtitles[value]) || [];
            this.subtitleState.subtitle = names.join(" · ");
        });
    }

    get stageSubtitle() {
        return this.subtitleState.subtitle;
    }
}

export class EviePipelineKanbanRenderer extends KanbanRenderer {
    static components = {
        ...KanbanRenderer.components,
        KanbanHeader: EviePipelineKanbanHeader,
    };
}

export const eviePipelineKanbanView = {
    ...kanbanView,
    Renderer: EviePipelineKanbanRenderer,
};

registry.category("views").add("evie_pipeline_kanban", eviePipelineKanbanView);
