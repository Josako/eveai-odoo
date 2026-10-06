"""Server side of the meeting window (odoo-meeting-window).

The window is a client action on one Meeting or Call activity linked to an
Evie CRM_ACTIVITY capsule. Details come from Odoo; participants, recordings,
notes and transcripts live in Evie and are fetched through the Evie integration API
with the API key, which never leaves the server. Audio itself goes straight
between the browser and Evie: these methods only hand out short-lived,
single-activity upload and playback links.

Every method checks the current user's access to the activity first, so the
window can do exactly what the user could do with the activity itself.
Done activities are archived, not deleted — the window keeps working on
them so meetings can be completed afterwards.
"""

from odoo import _, fields, models
from odoo.exceptions import UserError

#: Activity type categories that get a meeting window (core Meeting and Call).
MEETING_CATEGORIES = ('meeting', 'phonecall')
#: Generating speech for a long speaker turn can take well over the default 10 s.
SPEAK_TIMEOUT_SECONDS = 45


def _html(value):
    return str(value) if value else ''


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    def _to_store_defaults(self, target):
        return super()._to_store_defaults(target) + ['x_evie_capsule_id']

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _evie_meeting_activity(self, operation='read'):
        """This activity, checked to host a meeting window for the user."""
        self.ensure_one()
        activity = self.with_context(active_test=False)
        activity.check_access(operation)
        if activity.activity_category not in MEETING_CATEGORIES:
            raise UserError(_("The meeting window is only available for Meeting and Call activities."))
        if not activity.x_evie_capsule_id:
            raise UserError(_("This activity is not linked to Evie yet; try again in a moment."))
        return activity

    def _evie_meeting_capsule_id(self):
        try:
            return int(self.x_evie_capsule_id)
        except (TypeError, ValueError):
            raise UserError(_("This activity has an invalid Evie link.")) from None

    def _evie_meeting_user(self):
        user = self.env.user
        return {'name': user.name, 'email': user.email, 'lang': user.lang, 'id': user.id}

    def _evie_meeting_call(self, path, payload, **kwargs):
        ok, data = self.env['evie.webhook'].post_for_json(path, payload, **kwargs)
        if not ok:
            raise UserError(_("Evie could not complete the request: %s") % data)
        return data

    def _evie_meeting_details(self):
        event = self.calendar_event_id
        details = {
            'id': self.id,
            'summary': self.summary or '',
            'type_name': self.activity_type_id.name or '',
            'category': self.activity_category,
            'icon': self.icon or 'fa-tasks',
            'state': self.state,
            'can_write': self.has_access('write'),
            'date_deadline': fields.Date.to_string(self.date_deadline),
            'date_done': fields.Date.to_string(self.date_done),
            'assignee': self.user_id.name or '',
            'note': _html(self.note),
            'feedback': self.feedback or '',
            'preparation': _html(self.x_evie_final_content or self.x_evie_proposed_content),
            'res_model': self.res_model,
            'res_id': self.res_id,
            'res_name': self.res_name or '',
            'event': False,
            'lead': False,
        }
        if event:
            details['event'] = {
                'id': event.id,
                'name': event.name,
                'start': fields.Datetime.to_string(event.start),
                'stop': fields.Datetime.to_string(event.stop),
                'allday': event.allday,
                'location': event.location or '',
                'videocall_location': event.videocall_location or '',
                'attendees': event.partner_ids.mapped('display_name'),
            }
        if self.res_model == 'crm.lead' and self.res_id:
            lead = self.env['crm.lead'].browse(self.res_id).exists()
            if lead:
                details['lead'] = {
                    'id': lead.id,
                    'name': lead.name,
                    'company': lead.partner_id.commercial_company_name or lead.partner_name or '',
                    'contact': lead.contact_name or lead.partner_id.name or '',
                    'email': lead.email_from or '',
                    'phone': lead.phone or '',
                    'stage': lead.stage_id.name or '',
                    'salesperson': lead.user_id.name or '',
                    'score': lead.x_evie_qualification_score or 0,
                }
        details['participant_suggestions'] = self._evie_meeting_participant_suggestions()
        return details

    def _evie_meeting_partner_participant(self, partner):
        internal = any(not user.share for user in partner.user_ids)
        return {
            'name': partner.name or partner.email or '',
            'email': partner.email or '',
            'company': (self.env.company.name if internal else partner.commercial_company_name) or '',
            'role': partner.function or '',
            'internal': internal,
        }

    def _evie_meeting_participant_suggestions(self):
        """People who likely took part: calendar attendees, the lead's
        contact and the assignee (first occurrence per email/name wins)."""
        suggestions = [
            self._evie_meeting_partner_participant(partner)
            for partner in self.calendar_event_id.partner_ids
        ]
        if self.res_model == 'crm.lead' and self.res_id:
            lead = self.env['crm.lead'].browse(self.res_id).exists()
            if lead and lead.partner_id:
                suggestions.append(self._evie_meeting_partner_participant(lead.partner_id))
            elif lead and (lead.contact_name or lead.email_from):
                suggestions.append({
                    'name': lead.contact_name or lead.email_from,
                    'email': lead.email_from or '',
                    'company': lead.partner_name or '',
                    'role': lead.function or '',
                    'internal': False,
                })
        if self.user_id:
            suggestions.append(self._evie_meeting_partner_participant(self.user_id.partner_id))
        bot = self.env.ref('base.partner_root', raise_if_not_found=False)
        seen = {(bot.email or bot.name).strip().lower()} if bot else set()
        unique = []
        for suggestion in suggestions:
            key = (suggestion['email'] or suggestion['name']).strip().lower()
            if key and key not in seen:
                seen.add(key)
                unique.append(suggestion)
        return unique

    # ------------------------------------------------------------------
    # Meeting window API (called from the client action)
    # ------------------------------------------------------------------

    def evie_meeting_window_data(self):
        """Everything the window shows on open. An unreachable Evie does not
        block the details: the Evie part then carries an error instead."""
        activity = self._evie_meeting_activity()
        data = {'activity': activity._evie_meeting_details(), 'evie': False, 'evie_error': False}
        try:
            data['evie'] = activity.evie_meeting_overview()
        except UserError as e:
            data['evie_error'] = str(e)
        # The plan surface reads local mirrors only — always available.
        data['plan'] = activity._evie_meeting_plan_payload()
        return data

    def evie_meeting_overview(self):
        """Recordings (with transcription status) and notes from Evie."""
        activity = self._evie_meeting_activity()
        return activity._evie_meeting_call('/meeting/overview', {
            'capsule_id': activity._evie_meeting_capsule_id(),
        })

    def evie_meeting_save_notes(self, content):
        activity = self._evie_meeting_activity('write')
        if not (content or '').strip():
            raise UserError(_("Notes cannot be empty."))
        return activity._evie_meeting_call('/meeting/notes', {
            'capsule_id': activity._evie_meeting_capsule_id(),
            'content': content,
            'user': activity._evie_meeting_user(),
        })

    def evie_meeting_save_participants(self, participants):
        """Replace who took part in the meeting (stored on the Evie activity)."""
        activity = self._evie_meeting_activity('write')
        if not isinstance(participants, list):
            raise UserError(_("Participants must be a list."))
        return activity._evie_meeting_call('/meeting/participants', {
            'capsule_id': activity._evie_meeting_capsule_id(),
            'participants': participants,
            'user': activity._evie_meeting_user(),
        })

    def evie_meeting_set_document_type(self, document_id, document_type):
        """Set (or clear) the CRM document type of a recording or the notes."""
        activity = self._evie_meeting_activity('write')
        return activity._evie_meeting_call('/meeting/document-type', {
            'capsule_id': activity._evie_meeting_capsule_id(),
            'document_id': int(document_id),
            'document_type': document_type or '',
        })

    def evie_meeting_upload_url(self):
        """One-time link the browser posts a recording to."""
        activity = self._evie_meeting_activity('write')
        return activity._evie_meeting_call('/meeting/upload-url', {
            'capsule_id': activity._evie_meeting_capsule_id(),
            'user': activity._evie_meeting_user(),
        })

    def evie_meeting_audio_url(self, document_id):
        activity = self._evie_meeting_activity()
        return activity._evie_meeting_call('/meeting/audio-url', {
            'capsule_id': activity._evie_meeting_capsule_id(),
            'document_id': int(document_id),
            'user': activity._evie_meeting_user(),
        })

    def evie_meeting_transcript(self, document_id):
        activity = self._evie_meeting_activity()
        return activity._evie_meeting_call('/meeting/transcript', {
            'capsule_id': activity._evie_meeting_capsule_id(),
            'document_id': int(document_id),
        })

    def evie_meeting_transcribe(self, document_id):
        activity = self._evie_meeting_activity('write')
        return activity._evie_meeting_call('/meeting/transcribe', {
            'capsule_id': activity._evie_meeting_capsule_id(),
            'document_id': int(document_id),
            'user': activity._evie_meeting_user(),
        })

    def evie_meeting_replace_in_transcript(self, document_id, find, replace, segment=None, occurrence=None):
        """Replace a word in the transcript: everywhere, or one match of one fragment."""
        activity = self._evie_meeting_activity('write')
        return activity._evie_meeting_call('/meeting/transcript/replace', {
            'capsule_id': activity._evie_meeting_capsule_id(),
            'document_id': int(document_id),
            'find': find or '',
            'replace': replace or '',
            'segment': segment,
            'occurrence': occurrence,
        })

    def evie_meeting_speak_segment(self, document_id, segment):
        """One transcript fragment read aloud by Evie ({audio_base64, mime_type})."""
        activity = self._evie_meeting_activity()
        return activity._evie_meeting_call('/meeting/transcript/speak', {
            'capsule_id': activity._evie_meeting_capsule_id(),
            'document_id': int(document_id),
            'segment': int(segment),
        }, timeout=SPEAK_TIMEOUT_SECONDS)

    def evie_meeting_transcription_finished(self, document_id, document_name, error=False, finished_at=False):
        """Called by Evie when a recording of this activity finished
        transcribing (or failed): the assignee hears about it in the Evie
        bell when the notification center is installed."""
        activity = self._evie_meeting_activity('write')
        if 'evie.notification' not in self.env or not activity.user_id:
            return False
        name = document_name or _("Recording")
        if error:
            title, tone = _("Transcription failed"), 'danger'
            body = _("%(name)s: %(error)s", name=name, error=error)
        else:
            title, tone, body = _("Transcript ready"), 'success', name
        if activity.res_name:
            body = _("%(text)s on %(record)s", text=body, record=activity.res_name)
        self.env['evie.notification']._notify(
            activity.user_id, title, body=body, record=activity, kind='evie', tone=tone,
            dedupe_key=f"meeting-transcription:{int(document_id)}:{finished_at}" if finished_at else None,
            author=self.env['res.users'],
        )
        return True

    def _evie_notification_action(self):
        """Evie bell notifications about a meeting open its meeting window."""
        self.ensure_one()
        if self.activity_category not in MEETING_CATEGORIES:
            return False
        return {
            'type': 'ir.actions.client',
            'tag': 'evie_meetings.meeting_window',
            'name': self.summary or self.activity_type_id.name or _("Meeting"),
            'params': {'resId': self.id},
        }

    def evie_meeting_save_speakers(self, document_id, speaker_labels):
        activity = self._evie_meeting_activity('write')
        if not isinstance(speaker_labels, dict):
            raise UserError(_("Speaker names must be a mapping."))
        return activity._evie_meeting_call('/meeting/speakers', {
            'capsule_id': activity._evie_meeting_capsule_id(),
            'document_id': int(document_id),
            'speaker_labels': speaker_labels,
        })

    # ------------------------------------------------------------------
    # Meeting plan (add-odoo-meeting-library-sync): the window's plan
    # surface reads the LOCAL mirrors — no Evie round-trip; rep_note
    # edits and ad-hoc creates write the mirrors directly from the
    # client (orm), flowing inbound via the mirror automations.
    # ------------------------------------------------------------------

    def _evie_meeting_plan_mirror(self):
        """The activity's single active plan mirror, when it exists.

        Read as sudo: the mirror data is metadata about an activity the
        caller already checked access to (the meeting window works for
        every user who can open the activity); writes from the client go
        through the normal access rules."""
        self.ensure_one()
        return self.env['meeting.plan'].sudo().search(
            [('activity_id', '=', self.id), ('active', '=', True)], limit=1)

    def _evie_meeting_objective_payload(self, objective):
        return {
            'id': objective.id,
            'name': objective.name or '',
            'objective_type': objective.objective_type or '',
            'priority': objective.priority or '',
            'intent': objective.intent or '',
            'success_criterion': objective.success_criterion or '',
            'guiding_questions': objective.guiding_questions or '',
            'case_questions': objective.case_questions or '',
            'rep_note': objective.rep_note or '',
            'origin': objective.origin or '',
            'sync_state': objective.sync_state,
        }

    def _evie_meeting_plan_payload(self):
        """The plan section's data: the active plan mirror with its
        objectives, and the library templates for the add-plan picker."""
        self.ensure_one()
        plan = self._evie_meeting_plan_mirror()
        templates = self.env['meeting.template'].sudo().search(
            [('capsule_id', '!=', False)], order='name')
        return {
            'plan': plan and {
                'id': plan.id,
                'source': plan.source or '',
                'status': plan.status or '',
                'meeting_kind': plan.meeting_kind or '',
                'notes': plan.notes or '',
                'sync_state': plan.sync_state,
                'objectives': [
                    self._evie_meeting_objective_payload(objective)
                    for objective in plan.objective_ids
                ],
            },
            'templates': [{
                'id': template.id,
                'name': template.name,
                'description': template.description or '',
            } for template in templates],
        }

    def evie_meeting_plan_data(self):
        """The plan section (also the poll target after a compose)."""
        activity = self._evie_meeting_activity()
        return activity._evie_meeting_plan_payload()

    def evie_meeting_compose_plan(self, template_mirror_id=False):
        """Instantiate a plan for this meeting via the Evie compose
        endpoint (the copy action): from a library template, or empty
        when no template is given. The resulting plan and objective
        mirrors arrive via the ordinary outbound sync — the client polls
        ``evie_meeting_plan_data`` until they land."""
        import uuid
        activity = self._evie_meeting_activity('write')
        if activity._evie_meeting_plan_mirror():
            raise UserError(_('This meeting already has a plan.'))
        payload = {
            'event_id': str(uuid.uuid4()),
            'activity_capsule_id': activity._evie_meeting_capsule_id(),
        }
        if template_mirror_id:
            template = self.env['meeting.template'].browse(int(template_mirror_id))
            if not template.exists() or not template.capsule_id:
                raise UserError(_(
                    'That template is not linked to Evie (yet); try again in a moment.'))
            payload['template_capsule_id'] = template.capsule_id
        if activity.res_model == 'crm.lead' and activity.res_id:
            payload['odoo_lead_id'] = activity.res_id
        return activity._evie_meeting_call('/meeting-plan-compose', payload)
