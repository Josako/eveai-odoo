{
    'name': 'Evie CRM',
    'version': '19.0.2.0.0',
    'category': 'Sales/CRM',
    'summary': 'Evie (Ask Eve AI) CRM integration: phase mapping, anchor fields and automation',
    'description': """
Evie CRM
========

Everything Evie adds to Odoo CRM:

* ``x_evie_`` fields on ``crm.lead`` (capsule link, Evie phase anchor, last sync)
  with chatter tracking, rendered as branded "open in Evie" links via the
  shared ``evie_link`` widget and brand assets from ``evie_base``
* ``evie.phase_stage_map``: tenant-maintained translation between the stable
  Evie funnel phases and this database's CRM stages, with seeded defaults
* Automation rules keeping the anchor consistent and notifying Evie on
  stage changes and mapping changes

Evie is master over the funnel phase; this module translates to and from
this tenant's stages on stable IDs — never on display names.
""",
    'author': 'Ask Eve AI',
    'website': 'https://askeveai.be',
    'license': 'LGPL-3',
    'depends': ['evie_base', 'crm', 'base_automation'],
    'data': [
        'security/ir.model.access.csv',
        'data/evie_phase_stage_map_data.xml',
        'data/evie_automations.xml',
        'views/evie_phase_stage_map_views.xml',
        'views/crm_lead_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
