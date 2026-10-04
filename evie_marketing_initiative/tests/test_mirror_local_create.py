"""Tests for the capsule-link local-create opt-in
(odoo-marketing-mirror-create).

Covers the guard contract per mirror model: initiatives and channels are
locally creatable (opted in via ``_evie_local_create``), capture forms
and captures stay sync-created only, and sync writes (echo-guard context)
never notify back.
"""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.evie_base.models.evie_capsule_link import (
    EVIE_SYNC_CONTEXT_KEY,
)


class TestMirrorLocalCreate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Initiative = cls.env['marketing.initiative']
        cls.Channel = cls.env['marketing.initiative.channel']
        cls.CaptureForm = cls.env['marketing.capture.form']

    def test_initiative_is_locally_creatable(self):
        record = self.Initiative.create({'name': 'Beurs X 2026'})
        self.assertTrue(record.id)
        self.assertFalse(record.capsule_id)
        self.assertEqual(record.sync_state, 'pending')

    def test_channel_is_locally_creatable(self):
        record = self.Channel.create({
            'name': 'Booth QR',
            'channel_type': 'Specialist',
        })
        self.assertTrue(record.id)
        self.assertEqual(record.sync_state, 'pending')

    def test_capture_form_create_stays_refused(self):
        with self.assertRaises(UserError):
            self.CaptureForm.create({'name': 'Smuggled form'})

    def test_capture_form_sync_create_allowed(self):
        record = self.CaptureForm.with_context(
            **{EVIE_SYNC_CONTEXT_KEY: True}).create({'name': 'Synced form'})
        self.assertTrue(record.id)

    def test_sync_write_notifies_nothing(self):
        """The echo guard: a notify carrying the sync context is a no-op
        (no webhook call), so sync writes never echo back."""
        record = self.Initiative.create({'name': 'Beurs Y 2026'})
        with patch.object(
                type(self.env['evie.webhook']), 'post') as mock_post:
            record.with_context(
                **{EVIE_SYNC_CONTEXT_KEY: True}).evie_notify_upsert()
        mock_post.assert_not_called()

    def test_channel_links_are_editable(self):
        initiative = self.Initiative.create({'name': 'Beurs Z 2026'})
        form = self.CaptureForm.with_context(
            **{EVIE_SYNC_CONTEXT_KEY: True}).create({'name': 'Booth form'})
        channel = self.Channel.create({
            'name': 'Booth QR',
            'channel_type': 'Specialist',
            'initiative_id': initiative.id,
            'capture_form_id': form.id,
        })
        self.assertEqual(channel.initiative_id, initiative)
        self.assertEqual(channel.capture_form_id, form)
        # The links stay editable after saving (both-direction ownership).
        channel.write({'capture_form_id': False})
        self.assertFalse(channel.capture_form_id)
