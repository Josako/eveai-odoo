"""Gap-fill the Sales Accepted mapping row on existing databases
(sales-accepted-phase-funnel-mapping).

Fresh installs receive the ``map_sales_accepted`` row from the seed data
(``evie_phase_stage_map_data.xml``). On upgrade, ``noupdate`` data still
*creates* previously unknown xmlids — which would crash here: the corrected
defaults point Sales Accepted at ``crm.stage_lead2`` (Qualified), and tenant
databases coming from the old defaults already reference that stage from
their SQL row, violating the new stage-uniqueness constraint.

This pre-migration runs before data loading and pre-creates the row
**inactive and without a stage** — plus its ``ir.model.data`` entry, so the
data loader adopts it as an existing noupdate record and skips it — whenever
the intended stage is occupied or missing. When the stage is free the script
does nothing and the data loader creates the full default row. Idempotent by
construction: the ``ir.model.data`` lookup makes reruns a no-op.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

XMLID = 'map_sales_accepted'
PHASE = 'Sales Accepted'
DEFAULT_STAGE_XMLID = 'stage_lead2'  # crm "Qualified"


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1
          FROM ir_model_data
         WHERE module = 'evie_crm' AND name = %s AND model = 'evie.phase_stage_map'
        """,
        (XMLID,),
    )
    if cr.rowcount:
        return  # already present (rerun, or created by an earlier data load)

    env = api.Environment(cr, SUPERUSER_ID, {})

    stage = env.ref(f'crm.{DEFAULT_STAGE_XMLID}', raise_if_not_found=False)
    stage_taken = bool(stage) and bool(env['evie.phase_stage_map'].search(
        [('odoo_stage_id', '=', stage.id)], limit=1))

    if stage and not stage_taken:
        return  # stage free: the noupdate data load creates the default row

    row = env['evie.phase_stage_map'].create({
        'sequence': 65,
        'phase': PHASE,
        'odoo_type': 'opportunity',
        'odoo_stage_id': False,
        'is_default_for_phase': True,
        'active': False,
    })
    cr.execute(
        """
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate,
                                   date_init, date_update)
        VALUES ('evie_crm', %s, 'evie.phase_stage_map', %s, TRUE,
                NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC')
        """,
        (XMLID, row.id),
    )
    _logger.info(
        "evie_crm: created inactive '%s' mapping row (id %s) — the default "
        "stage was %s; an admin completes and activates the row",
        PHASE, row.id,
        "occupied by another entry" if stage else "missing",
    )
