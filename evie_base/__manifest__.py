{
    'name': 'Evie Base',
    'version': '19.0.1.9.1',
    'category': 'Technical',
    'summary': 'Base layer for the Ask Eve AI (Evie) integration: conventions, settings and health surface',
    'description': """
Evie Base
=========

Foundation module for all Evie (Ask Eve AI) Odoo modules.

* Namespace conventions: modules ``evie_*``, models ``evie.*``, fields ``x_evie_*``
* Evie settings (webhook URL + TenantProject API key) under Settings
* Health/diagnostic surface (``evie.health``) so the Evie platform can verify
  installed module versions and required fields remotely
* A full-duplex "Test connection" action in the Evie settings: pings Evie
  with the configured credentials and reports both directions (Odoo → Evie
  and the live reverse check Evie → Odoo) with actionable error detail
* Shared phase vocabulary (stable Evie funnel phase keys)
* Evie menu root (Evie ▸ Configuration)
* Evie brand assets and web extensions shared by all verticals: the
  ``o_evie_icon`` CSS icon class, the ``evie_link`` field widget, the
  notebook tab branding (pure CSS on the core ``[name]`` tab hook) and
  the ``evie_brand_header`` view widget (odoo-evie-form-branding) for
  forms without a core notebook, where Odoo hides a single tab
* The generic ``evie_actions`` field widget (odoo-capsule-actions): renders
  the data capsule actions discovered live from Evie for the record's
  capsule type, with specialist selection and running-state feedback —
  no hardcoded action definitions in Odoo. The running state follows the
  discovery payload's per-action busy metadata (busy_statuses matched
  against the bound status field), with a fallback for older payloads
  (sync-activity-proposal-to-odoo)

This module contains no business logic itself; vertical modules
(``evie_crm``, ...) build on it.
""",
    'author': 'Ask Eve AI',
    'website': 'https://askeveai.be',
    'license': 'LGPL-3',
    'depends': ['base', 'base_setup'],
    'data': [
        'views/evie_menus.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'evie_base/static/src/scss/evie_brand.scss',
            'evie_base/static/src/js/evie_link_field.js',
            'evie_base/static/src/xml/evie_link_field.xml',
            'evie_base/static/src/js/evie_actions_field.js',
            'evie_base/static/src/xml/evie_actions_field.xml',
            'evie_base/static/src/js/evie_brand_header.js',
            'evie_base/static/src/xml/evie_brand_header.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
