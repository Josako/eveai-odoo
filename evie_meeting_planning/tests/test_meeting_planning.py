"""Tests for the Evie meeting planning mirrors
(add-odoo-meeting-library-sync).

Covers the guard contract (design decision 2): membership links are
create-time only — inline creates carry the link, every later local
link/re-point/unlink is refused; local creation follows the mixin's
opt-in per model; the one-active-plan-per-activity constraint holds;
and sync writes (echo-guard context) bypass the guards.
"""

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

from odoo.addons.evie_base.models.evie_capsule_link import (
    EVIE_SYNC_CONTEXT_KEY,
)

SYNC = {EVIE_SYNC_CONTEXT_KEY: True}


class TestMembershipGuards(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Objective = cls.env['objective.template']
        cls.Template = cls.env['meeting.template']
        cls.Plan = cls.env['meeting.plan']
        cls.PlanObjective = cls.env['meeting.objective']

    def _template(self, **kwargs):
        return self.Template.create({'name': 'Discovery', **kwargs})

    def _objective(self, **kwargs):
        vals = {
            'name': 'Qualify pain',
            'objective_type': 'INFORMATION',
            'intent': 'Map the pain.',
            'success_criterion': 'Pain named.',
        }
        vals.update(kwargs)
        return self.Objective.create(vals)

    def _plan(self, **kwargs):
        vals = {'capsule_id': '9001', 'source': 'USER', 'status': 'DRAFT'}
        vals.update(kwargs)
        return self.Plan.with_context(**SYNC).create(vals)

    # --- Local creation contract ---

    def test_objective_template_is_locally_creatable(self):
        record = self._objective()
        self.assertTrue(record.id)
        self.assertFalse(record.capsule_id)
        self.assertEqual(record.sync_state, 'pending')

    def test_meeting_template_is_locally_creatable(self):
        record = self._template()
        self.assertTrue(record.id)
        self.assertEqual(record.sync_state, 'pending')

    def test_inline_create_carries_membership(self):
        """A new objective created with a template link is a genuine
        create — allowed, and inbound it reconciles the relation."""
        template = self._template()
        record = self._objective(template_id=template.id)
        self.assertEqual(record.template_id, template)
        self.assertIn(record, template.objective_ids)

    def test_plan_create_without_sync_context_is_refused(self):
        """Plans are composed in Evie — never created locally."""
        with self.assertRaises(UserError):
            self.Plan.create({'source': 'USER', 'status': 'DRAFT'})

    def test_plan_sync_create_allowed(self):
        plan = self._plan()
        self.assertTrue(plan.id)
        self.assertEqual(plan.capsule_id, '9001')

    def test_ad_hoc_objective_inline_create(self):
        plan = self._plan()
        record = self.PlanObjective.create({
            'name': 'Ask about timing',
            'objective_type': 'COMMITMENT',
            'intent': 'Commit to a next step.',
            'success_criterion': 'A date is agreed.',
            'plan_id': plan.id,
        })
        self.assertEqual(record.plan_id, plan)
        self.assertIn(record, plan.objective_ids)

    # --- The guard: linking/re-pointing/unlinking is refused ---

    def test_linking_existing_objective_is_refused(self):
        template = self._template()
        record = self._objective()
        with self.assertRaises(UserError):
            record.write({'template_id': template.id})

    def test_unlinking_member_is_refused(self):
        record = self._objective(template_id=self._template().id)
        with self.assertRaises(UserError):
            record.write({'template_id': False})

    def test_repointing_plan_objective_is_refused(self):
        plan_a = self._plan(capsule_id='9101')
        plan_b = self._plan(capsule_id='9102')
        record = self.PlanObjective.create({
            'name': 'X', 'objective_type': 'INFORMATION',
            'intent': 'Y', 'success_criterion': 'Z',
            'plan_id': plan_a.id,
        })
        with self.assertRaises(UserError):
            record.write({'plan_id': plan_b.id})

    def test_sync_write_bypasses_the_guard(self):
        template = self._template()
        record = self._objective()
        record.with_context(**SYNC).write({'template_id': template.id})
        self.assertEqual(record.template_id, template)

    def test_content_write_does_not_touch_the_guard(self):
        record = self._objective(template_id=self._template().id)
        record.write({'intent': 'Updated'})
        self.assertEqual(record.intent, 'Updated')


class TestOneActivePlanPerActivity(TransactionCase):

    def _plan(self, capsule_id, activity=None, active=True):
        return self.env['meeting.plan'].with_context(
            **{EVIE_SYNC_CONTEXT_KEY: True}).create({
                'capsule_id': capsule_id,
                'source': 'USER',
                'status': 'DRAFT',
                'activity_id': activity.id if activity else False,
                'active': active,
            })

    def test_second_active_plan_refused(self):
        activity = self.env['mail.activity'].create({
            'activity_type_id': self.env.ref('mail.mail_activity_data_meeting').id,
            'res_model_id': self.env['ir.model']._get('res.partner').id,
            'res_id': self.env['res.partner'].create({'name': 'Acme'}).id,
            'summary': 'Meeting',
        })
        self._plan('9201', activity=activity)
        with self.assertRaises(ValidationError):
            self._plan('9202', activity=activity)

    def test_archived_plan_does_not_count(self):
        """A SUPERSEDED plan syncs archived — a successor may land."""
        activity = self.env['mail.activity'].create({
            'activity_type_id': self.env.ref('mail.mail_activity_data_meeting').id,
            'res_model_id': self.env['ir.model']._get('res.partner').id,
            'res_id': self.env['res.partner'].create({'name': 'Acme'}).id,
            'summary': 'Meeting',
        })
        self._plan('9203', activity=activity, active=False)
        successor = self._plan('9204', activity=activity)
        self.assertTrue(successor.active)
