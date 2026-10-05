{
    'name': 'Evie Meeting Planning',
    'version': '19.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Mirror models for the Evie meeting library (objective and meeting templates) and meeting plans with objectives',
    'description': """
Evie Meeting Planning
=====================

Odoo projection of the Evie meeting-planning capsules
(add-odoo-meeting-library-sync). Evie is the system of record; this
module gives Odoo users a native window on the meeting library and on
meeting plans through dedicated *mirror models* on the shared
``evie.capsule.link`` mixin — the marketing-initiative precedent.

* Mirror models: ``objective.template`` and ``meeting.template`` (the
  tenant library, master data), ``meeting.plan`` and
  ``meeting.objective`` (runtime instances on meeting activities)
* Ownership matrix enforced by view/field attributes plus server-side
  guards: library content editable by managers (``both``), plan core
  read-only (Evie-master), objective content and ``rep_note`` editable,
  system-written fields (``case_questions``, the outcome distillate,
  ``origin``) read-only
* Membership travels on the member side (``template_id`` / ``plan_id``):
  the parent's objective list is the pure inverse. Composition is a copy
  action in Evie, never a link — linking an existing objective into a
  template or plan is refused by a guard; pulling sources into a
  template runs via the compose wizard (capsule-actions channel);
  removing a template member deletes the copy via the remove action
* Local creation where the semantics are genuine creates: library
  templates and objectives (managers), ad-hoc objectives on a plan
  (reps) — Evie materialises the capsule from the upsert notification
  and writes the anchor back; a failed creation surfaces as ``error``
  with the reason on the chatter
* Access model: module-owned groups ``group_evie_meeting_user`` /
  ``group_evie_meeting_manager`` — the library is curated by managers,
  plans and objectives are rep work; sales groups get the matching
  read/write rights so the meeting window works for every rep; the
  integration user gets the manager group (least privilege: create on
  mirror models only — the synchronisation writes through it)
* Local edits during an Evie outage are queued via ``local_dirty`` and
  retried by the scheduled job

The sync itself (field mappings, per-field ownership, reconciliation)
lives Evie-side in the ODOO_CRM integration configuration; this module
provides the Odoo surface only. The meeting window's plan surface lives
in ``evie_meetings``.
""",
    'author': 'Ask Eve AI',
    'website': 'https://askeveai.be',
    'license': 'LGPL-3',
    'depends': ['evie_base', 'evie_crm'],
    'data': [
        'security/evie_meeting_groups.xml',
        'security/ir.model.access.csv',
        'data/evie_automations.xml',
        'data/evie_cron.xml',
        'views/objective_template_views.xml',
        'views/meeting_template_views.xml',
        'views/meeting_plan_views.xml',
        'views/meeting_objective_views.xml',
        'views/meeting_template_compose_wizard_views.xml',
        'views/evie_meeting_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
