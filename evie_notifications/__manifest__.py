{
    'name': 'Evie Notifications',
    'version': '19.0.1.2.0',
    'category': 'Sales/CRM',
    'summary': 'Evie notification center in the Odoo top bar: lead and activity changes, Evie action results',
    'description': """
Evie Notifications
==================

An Evie-branded notification center in the Odoo top bar, modelled on the
notification center of the Evie admin client (odoo-notification-center).

* ``evie.notification``: one row per recipient, stored server-side (survives
  closed tabs and follows the user across devices); users only ever see
  their own notifications
* Bell in the systray with an unread counter, a Recent / Older panel,
  mark-read, clear and "view all"; clicking an item opens the related
  record
* Live delivery over the Odoo bus (no page refresh) plus a short toast
* Built-in triggers (phase 1):

  - lead assigned to you (create and reassignment)
  - stage changed / lead won on your lead
  - your lead marked as lost
  - hot lead: the Evie qualification score crosses 70
  - Evie action finished or failed on your lead
  - activity assigned to you (any model)
  - activity completed on your record by someone else
  - hourly-evaluated morning digest of overdue / due-today activities
    (once per user per local day)
  - meeting transcript ready / transcription failed (with Evie Meetings)

* Morning brief: "Good morning" dialog with today's meetings, activities
  due, Evie drafts to review and hot leads. Pops up once per local day
  (from 05:00, only when there is something to show; remembered on the
  user across devices); the sun button (bottom right) and the daily digest
  notification reopen it

* Never notifies the person who made the change; imports, module
  installs and writes with ``evie_skip_notifications`` stay silent. Evie's
  own sync writes (``evie_skip_phase_event``) do notify: an assignment or
  finished research coming from Evie is exactly what the rep should see
* ``evie.notification._notify_record(record, ...)`` for automation rules on
  any model, so tenants can add their own notifications without code
* Retention: notifications older than ``evie_notifications.retention_days``
  (default 90) are removed daily
""",
    'author': 'Ask Eve AI',
    'website': 'https://askeveai.be',
    'license': 'LGPL-3',
    'depends': ['evie_base', 'evie_crm', 'mail', 'bus'],
    'data': [
        'security/ir.model.access.csv',
        'security/evie_notification_security.xml',
        'data/evie_notification_data.xml',
        'views/evie_notification_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'evie_notifications/static/src/scss/evie_notifications.scss',
            'evie_notifications/static/src/js/evie_notification_service.js',
            'evie_notifications/static/src/js/evie_notification_menu.js',
            'evie_notifications/static/src/xml/evie_notification_menu.xml',
            'evie_notifications/static/src/js/evie_morning_brief.js',
            'evie_notifications/static/src/xml/evie_morning_brief.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
