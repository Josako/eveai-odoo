"""Adopt the evie.language_map artefacts from evie_crm
(odoo-user-preferences-sync).

The language map model moved from evie_crm to evie_base without a model
rename, so the table and its records survive the upgrade; only the
ir.model.data ownership of the model, fields, access rules, views, window
action, menu and seed records must move to the new providing module. This
runs before evie_base's own data loading, which then adopts the entries in
place — the noupdate seed records keep any tenant edits. No-op on
databases where evie_crm never carried the map.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE ir_model_data
           SET module = 'evie_base'
         WHERE module = 'evie_crm'
           AND (name LIKE '%language\\_map%' ESCAPE '\\'
                OR model = 'evie.language_map')
        """)
    if cr.rowcount:
        _logger.info(
            "evie_base: adopted %s evie.language_map ir.model.data entries "
            "from evie_crm", cr.rowcount)
