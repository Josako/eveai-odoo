"""Tests for ``evie.actions.execute_action`` response handling.

Covers the selector-first specialist flow
(odoo-selector-first-specialist-flow): a ``choice_required`` response from
the action-execute endpoint is passed through to the caller (the OWL widget
opens the picker and re-executes), while real failures still raise
``UserError``.
"""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestExecuteAction(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.actions = cls.env['evie.actions']

    def _post(self, result):
        return patch.object(
            type(self.env['evie.webhook']), 'post_for_json',
            return_value=result)

    def test_choice_required_passes_through(self):
        candidates = [{'id': 7, 'name': 'Research A'},
                      {'id': 9, 'name': 'Research B'}]
        with self._post((True, {'choice_required': True,
                                'message': 'choose one',
                                'specialists': candidates})):
            result = self.actions.execute_action(
                'START_LEAD_RESEARCH_ACTION', capsule_id=42)
        self.assertEqual(result, {'choice_required': True,
                                  'specialists': candidates})

    def test_failure_raises_user_error(self):
        with self._post((False, 'No active specialist available')), \
             self.assertRaises(UserError):
            self.actions.execute_action(
                'START_LEAD_RESEARCH_ACTION', capsule_id=42)

    def test_background_acceptance_passes_through(self):
        with self._post((True, {'success': True, 'message': 'started'})):
            result = self.actions.execute_action(
                'START_LEAD_RESEARCH_ACTION', capsule_id=42)
        self.assertEqual(result, {'success': True, 'message': 'started'})

    def test_action_arguments_are_forwarded_to_evie(self):
        arguments = {'preview_hash': 'abc123', 'template_id': 9}
        with self._post((True, {'success': True})) as post:
            result = self.actions.execute_action(
                'SEND_ACTIVITY_EMAIL_ACTION', capsule_id=42, arguments=arguments)
        self.assertEqual(result, {'success': True})
        payload = post.call_args.args[1]
        self.assertEqual(payload['arguments'], arguments)

    def test_template_choice_and_message_pass_through(self):
        templates = [{'id': 9, 'name': 'Customer outreach'}]
        with self._post((True, {
                'choice_required': True, 'message': 'Choose a template.',
                'templates': templates})):
            result = self.actions.execute_action(
                'PREVIEW_ACTIVITY_EMAIL_ACTION', capsule_id=42)
        self.assertEqual(result, {
            'choice_required': True, 'specialists': [],
            'message': 'Choose a template.', 'templates': templates})
