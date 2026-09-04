{
    'name': 'Evie CRM',
    'version': '19.0.1.15.0',
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
* Inbound sync (add-inbound-odoo-sync): automations notify Evie of lead
  creation, mirrored-field writes and archive/unarchive; ``x_evie_phase``
  is directly editable (Selection of the mapped phases); lead merges are
  reported to Evie (survivor + merged ids)

* Mirrored standard fields (complete-lead-sync-fields): job position
  (``function``) and company name (``partner_name``) are watched by the
  upsert automation so edits on either side stay in sync (mapping
  CRM_LEAD_ODOO_CRM 1.4.0). NB: ``mobile``/``title`` were removed from
  Odoo in 19.0 and are deliberately not mirrored

* Assignee & team sync (add-user-assignment-sync, mapping CRM_LEAD_ODOO_CRM
  1.5.0): the upsert automation also watches ``user_id`` and ``team_id``,
  so Odoo-side (re)assignment of the salesperson (manual or via Odoo's own
  assignment rules) flows into Evie as the ``CRM_ASSIGNED_TO_USER``
  relation, and the sales team lands read-only on the capsule. Evie-side
  assignments resolve via the identity-assertion bridge; unresolvable
  assignees produce a chatter warning posted from Evie

* Capsule actions (odoo-capsule-actions): the ``evie_actions`` widget from
  ``evie_base`` on the lead form (capsule type ``CRM_LEAD``), the action
  lifecycle fields ``x_evie_action_status``/``x_evie_action_message``, and a
  chatter notification when an action finishes or fails

* Evie Lead Pipeline (odoo-lead-pipeline-board): kanban, graph and pivot
  views over Evie-linked leads, grouped by the stable Evie phase — drag &
  drop phase changes via the existing phase-edit channel, a colour-coded
  qualification score on the cards, and drill-down reporting (count and
  average score per phase)

* Tags (add-tag-sync, mapping CRM_LEAD_ODOO_CRM 1.7.0): the upsert
  automation also watches ``tag_ids``, so rep tagging on a lead flows into
  Evie as ``TAGGED_WITH`` relations (and Evie-side tagging lands on the
  lead via the native field), and the Evie Lead Pipeline cards show the
  tags as coloured chips via the native many2many-tags widget. The tag
  dictionary itself stays anchorless — no ``x_evie_`` fields on
  ``crm.tag``; identity lives Evie-side

* Activities (add-crm-activity-sync): ``x_evie_`` anchors on
  ``mail.activity`` (capsule link + stable Evie activity-type key),
  ``evie.activity_type_map`` translating Evie type keys to this database's
  activity types (seeded defaults, tenant-editable), Evie-native activity
  types (LinkedIn outreach) as module data, and automation rules notifying
  Evie of activity create/write/done and cancel (unlink)

* Activity outcomes (add-activity-sequences): ``x_evie_outcome`` selection
  on ``mail.activity`` backed by the ``evie.activity_outcome`` module data
  (stable keys: accepted / not_accepted / no_answer), editable on the
  activity form before marking done and synced to Evie with the
  completion, where it drives sequence branching

* Activity proposals (sync-activity-proposal-to-odoo): the specialist's
  proposal (``x_evie_proposed_content``, read-only) and the rep's final
  text (``x_evie_final_content``, editable and mirrored back to Evie) on
  ``mail.activity`` as two separate fields, the action feedback fields
  ``x_evie_action_status``/``x_evie_action_message`` (mirroring the lead),
  and the ``evie_actions`` widget bound on the activity popup (capsule
  type ``CRM_ACTIVITY``) so Evie actions like *Generate Proposal* and
  *Approve Proposal* run straight from the activity (mapping
  CRM_ACTIVITY_ODOO_CRM 1.2.0)

* Evie form branding (odoo-evie-form-branding): the activity popup shows
  the same recognisable Evie section as the lead's Evie tab —
  ``evie_brand_header`` (icon + title) on top, then Actions /
  Synchronisation / Evie Context, including the new ``x_evie_last_synced``
  anchor on ``mail.activity`` (mapping CRM_ACTIVITY_ODOO_CRM 1.3.0)

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
        'data/evie_language_map_data.xml',
        'data/evie_activity_types.xml',
        'data/evie_activity_type_map_data.xml',
        'data/evie_activity_outcome_data.xml',
        'data/evie_automations.xml',
        'views/evie_phase_stage_map_views.xml',
        'views/evie_language_map_views.xml',
        'views/evie_activity_type_map_views.xml',
        'views/mail_activity_views.xml',
        'views/crm_lead_views.xml',
        'views/evie_lead_pipeline_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
