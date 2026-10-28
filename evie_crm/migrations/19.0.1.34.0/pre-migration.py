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
the intended stage is occupied by an active entry or missing. When the stage
is free the script does nothing and the data loader creates the full default
row. Idempotent by construction: the ``ir.model.data`` lookup makes reruns a
no-op.

Raw SQL on purpose: at pre-migration time the module's own models are not
yet in the registry, so the ORM cannot resolve ``evie.phase_stage_map``
(same reason the evie_base precedent uses plain SQL).
"""

import logging

_logger = logging.getLogger(__name__)

XMLID = 'map_sales_accepted'
PHASE = 'Sales Accepted'
DEFAULT_STAGE_XMLID = 'stage_lead2'  # crm "Qualified"


def migrate(cr, version):
    # Already present (rerun, or an earlier data load created it)?
    cr.execute(
        """
        SELECT 1
          FROM ir_model_data
         WHERE module = 'evie_crm' AND name = %s AND model = 'evie.phase_stage_map'
        """,
        (XMLID,),
    )
    if cr.rowcount:
        return

    # Resolve the default stage id via its xmlid (tenant may have deleted it).
    cr.execute(
        """
        SELECT res_id
          FROM ir_model_data
         WHERE module = 'crm' AND name = %s AND model = 'crm.stage'
        """,
        (DEFAULT_STAGE_XMLID,),
    )
    stage_row = cr.fetchone()
    stage_id = stage_row[0] if stage_row else None

    stage_taken = False
    if stage_id:
        cr.execute(
            """
            SELECT 1
              FROM evie_phase_stage_map
             WHERE odoo_stage_id = %s AND active
            """,
            (stage_id,),
        )
        stage_taken = bool(cr.rowcount)

    if stage_id and not stage_taken:
        return  # stage free: the noupdate data load creates the default row

    cr.execute(
        """
        INSERT INTO evie_phase_stage_map
            (sequence, phase, odoo_type, odoo_stage_id, is_default_for_phase,
             active, create_uid, create_date, write_uid, write_date)
        VALUES (65, %s, 'opportunity', NULL, TRUE, FALSE,
                1, NOW() AT TIME ZONE 'UTC', 1, NOW() AT TIME ZONE 'UTC')
        RETURNING id
        """,
        (PHASE,),
    )
    row_id = cr.fetchone()[0]
    cr.execute(
        """
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate,
                                   create_date, write_date)
        VALUES ('evie_crm', %s, 'evie.phase_stage_map', %s, TRUE,
                NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC')
        """,
        (XMLID, row_id),
    )
    _logger.info(
        "evie_crm: created inactive '%s' mapping row (id %s) — the default "
        "stage was %s; an admin completes and activates the row",
        PHASE, row_id,
        "occupied by another entry" if stage_id else "missing",
    )
