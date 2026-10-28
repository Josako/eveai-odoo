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
 * Written against the Odoo 19 kanban internals (`web.KanbanColumn` template,
 * `@web/views/kanban/*` export paths); smoke-checked per module upgrade.
 */

import { onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanColumn } from "@web/views/kanban/kanban_column";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";

let subtitlesPromise = null;

function loadStageSubtitles(orm) {
    subtitlesPromise ||= orm.call("evie.phase_stage_map", "stage_subtitles", []);
    return subtitlesPromise;
}

export class EviePipelineKanbanColumn extends KanbanColumn {
    static template = "evie_crm.EviePipelineKanbanColumn";

    setup() {
        super.setup();
        this.orm = useService("orm");
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
        KanbanColumn: EviePipelineKanbanColumn,
    };
}

export const eviePipelineKanbanView = {
    ...kanbanView,
    Renderer: EviePipelineKanbanRenderer,
};

registry.category("views").add("evie_pipeline_kanban", eviePipelineKanbanView);
