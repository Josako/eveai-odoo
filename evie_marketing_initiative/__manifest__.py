{
    'name': 'Evie Marketing Initiative',
    'version': '19.0.1.0.0',
    'category': 'Marketing',
    'summary': 'Mirror models for Evie marketing initiatives, channels, capture forms and captures',
    'description': """
Evie Marketing Initiative
=========================

Odoo projection of the Evie MARKETING capsules (odoo-marketing-adapter).
Evie is the system of record; this module gives Odoo users a native window
on marketing initiatives, channels, capture forms and captures through
dedicated *mirror models* on the shared ``evie.capsule.link`` mixin — the
second projection pattern, next to the ``x_evie_*`` anchors on native
models.

* Mirror models: ``marketing.initiative``, ``marketing.initiative.channel``,
  ``marketing.capture.form`` (read-only), ``marketing.capture``, plus
  ``marketing.initiative.cost`` (Odoo-owned actual costs)
* Ownership matrix enforced by view/field attributes plus server-side
  guards: initiatives and channels editable on shared fields, forms
  strictly read-only, captures limited to decision fields, costs fully
  editable (Odoo is master)
* Access model (change evie-marketing-access-model): module-owned groups
  ``group_evie_marketing_user`` / ``group_evie_marketing_manager`` —
  initiatives, channels and costs are a marketing domain, captures are
  shared marketing/sales; the integration user gets the manager group
  (least privilege) instead of Sales/Administrator
* ``crm.lead`` extension: ``initiative_id``, ``initiative_channel_id``,
  ``capture_id``, ``capture_score``, ``utm_term``, ``utm_content``
* Action buttons via the generic capsule-actions discovery/execution
  channel — no hardcoded Evie action semantics
* Local edits during an Evie outage are queued via ``local_dirty`` and
  retried by the scheduled job

The sync itself (field mappings, per-field ownership, UTM
materialisation, reconciliation) lives Evie-side in the ODOO_CRM
integration configuration; this module provides the Odoo surface only.
""",
    'author': 'Ask Eve AI',
    'website': 'https://askeveai.be',
    'license': 'LGPL-3',
    'depends': ['evie_base', 'crm'],
    'data': [
        'security/evie_marketing_groups.xml',
        'security/ir.model.access.csv',
        'views/marketing_initiative_views.xml',
        'views/marketing_channel_views.xml',
        'views/marketing_capture_form_views.xml',
        'views/marketing_capture_views.xml',
        'views/crm_lead_views.xml',
        'views/evie_marketing_menus.xml',
        'data/evie_automations.xml',
        'data/evie_cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
