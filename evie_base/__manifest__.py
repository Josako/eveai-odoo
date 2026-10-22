{
    'name': 'Evie Base',
    'version': '19.0.1.29.0',
    'category': 'Technical',
    'summary': 'Base layer for the Ask Eve AI (Evie) integration: conventions, settings and health surface',
    'description': """
Evie Base
=========

Foundation module for all Evie (Ask Eve AI) Odoo modules.

* Namespace conventions: modules ``evie_*``, models ``evie.*``, fields ``x_evie_*``
* Evie settings (webhook URL + TenantProject API key) under Settings
* Health/diagnostic surface (``evie.health``) so the Evie platform can verify
  installed module versions and required fields remotely; also reports the
  tenant's ``evie.activity_type_map`` keys (when the model exists) so Evie
  can detect vocabulary drift (add-odoo-module-distribution)
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
* Reusable record-bound Evie components (1.19.0): ``EvieCapsuleActions``
  (the component behind ``evie_actions``; given ``resModel``/``resId`` it
  discovers the actions applicable to that record's capsule with their live
  running state, so any OWL component can embed them) and
  ``EvieCapsuleDocuments`` (the documents linked to the record's capsule,
  opened in the Evie document view; also the ``evie_capsule_documents``
  form view widget), backed by ``evie.actions.get_record_actions`` and
  ``evie.capsule.documents``
* The ``evie.capsule.link`` abstract mixin (odoo-marketing-adapter):
  reusable link state for mirror models (``capsule_id``,
  ``capsule_version``, ``capsule_url``, ``sync_state``,
  ``last_sync_date``, ``local_dirty``) plus the shared Odoo → Evie event
  plumbing (sync-created guard with a per-model local-create opt-in via
  ``_evie_local_create`` — 1.16.0, odoo-marketing-mirror-create —
  ``/mirror-upsert`` notification, local_dirty retry queue, the generic
  ``action_evie_open`` view-token dispatcher behind the ``evie_link``
  widget)
* The shared ``EVIE_OPEN_KINDS`` registry (odoo-capture-card-view, 1.14.0):
  all open-in-Evie entity kinds (``capsule``, ``document``,
  ``chat_session``, ``capture_media``) live in ``evie_base.consts`` and the
  mixin dispatcher resolves from it, so every model exposing the
  dispatcher — native extensions and mirror models alike — supports the
  same kinds without per-model overrides; adding a kind stays a registry
  entry
* Shared marketing vocabulary (odoo-marketing-adapter): the stable
  MARKETING_INITIATIVE_TYPE / MARKETING_CHANNEL_TYPE key selections,
  mirroring the Evie dynamic lists (like EVIE_PHASES for the funnel)
* The shared tenant language map ``evie.language_map`` (relocated from
  ``evie_crm`` at 19.0.1.20.0, odoo-user-preferences-sync): one mapping
  for every consumer — the lead language sync and the user preferences
  sync — with existing entries adopted on upgrade
* Evie user preferences (odoo-user-preferences-sync): an Evie tab on the
  user's own Preferences form (My Preferences) editing the synced
  ``x_evie_booking_page_url``, with the native language field doubling as
  the Evie preferred language; preference writes are pushed to Evie via
  the ``/user-preferences`` webhook (echo-guarded), and Evie's outbound
  writes land here through the JSON-2 API

This module contains no business logic itself; vertical modules
(``evie_crm``, ...) build on it.
""",
    'author': 'Ask Eve AI',
    'website': 'https://askeveai.be',
    'license': 'LGPL-3',
    'depends': ['base', 'base_setup'],
    'data': [
        'security/ir.model.access.csv',
        'data/evie_language_map_data.xml',
        'views/evie_menus.xml',
        'views/res_config_settings_views.xml',
        'views/evie_language_map_views.xml',
        'views/res_users_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'evie_base/static/src/scss/evie_brand.scss',
            'evie_base/static/src/js/evie_link_field.js',
            'evie_base/static/src/xml/evie_link_field.xml',
            'evie_base/static/src/js/evie_capsule_actions.js',
            'evie_base/static/src/xml/evie_capsule_actions.xml',
            'evie_base/static/src/js/evie_actions_field.js',
            'evie_base/static/src/xml/evie_actions_field.xml',
            'evie_base/static/src/js/evie_capsule_documents.js',
            'evie_base/static/src/xml/evie_capsule_documents.xml',
            'evie_base/static/src/js/evie_brand_header.js',
            'evie_base/static/src/xml/evie_brand_header.xml',
            'evie_base/static/src/js/evie_personal_link_field.js',
            'evie_base/static/src/xml/evie_personal_link_field.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
