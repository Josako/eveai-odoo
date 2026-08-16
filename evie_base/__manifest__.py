{
    'name': 'Evie Base',
    'version': '19.0.2.0.0',
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
* Shared phase vocabulary (stable Evie funnel phase keys)
* Evie menu root (Evie ▸ Configuration)
* Evie brand assets and web extensions shared by all verticals: the
  ``o_evie_icon`` CSS icon class, the ``evie_link`` field widget and the
  notebook tab branding (pure CSS on the core ``[name]`` tab hook)

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
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
