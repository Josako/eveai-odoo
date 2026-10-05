{
    'name': 'Evie Meetings',
    'version': '19.0.1.1.0',
    'category': 'Sales/CRM',
    'summary': 'Meeting window for Meeting and Call activities: details, recording and notes, stored in Evie',
    'description': """
Evie Meetings
=============

A meeting "cockpit" for Meeting and Call activities on Evie-linked leads,
opened from the activity in the lead's chatter (odoo-meeting-window).

* Meeting details: the activity, the calendar event (time, location, video
  link, attendees), the lead and the preparation (activity note and the
  Evie proposal)
* Recording: record the meeting in the browser or add an existing audio
  file; recordings are stored in Evie next to the Workspace client's
  meetings, linked to the activity's CRM_ACTIVITY capsule, and transcribed
  there (with speaker naming)
* Notes: taken during the meeting, kept as a draft in the browser and saved
  to Evie as the activity's meeting notes
* Recording keeps running while you navigate Odoo; a recording indicator in
  the top bar leads back to the window
* The window stays reachable after the activity is done: the "done" message
  in the chatter links back to it (``/odoo/evie-meeting/<activity id>``)

Audio never passes through the Odoo server: the browser uploads to and
streams from Evie with short-lived, single-activity links that Odoo requests
server-side with the API key.
""",
    'author': 'Ask Eve AI',
    'website': 'https://askeveai.be',
    'license': 'LGPL-3',
    'depends': ['evie_base', 'evie_crm', 'mail', 'calendar'],
    'data': [
        'data/mail_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'evie_meetings/static/src/scss/evie_meetings.scss',
            'evie_meetings/static/src/js/meeting_recorder_service.js',
            'evie_meetings/static/src/js/meeting_recording_indicator.js',
            'evie_meetings/static/src/xml/meeting_recording_indicator.xml',
            'evie_meetings/static/src/js/meeting_window.js',
            'evie_meetings/static/src/xml/meeting_window.xml',
            'evie_meetings/static/src/js/activity_patch.js',
            'evie_meetings/static/src/xml/activity_patch.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
