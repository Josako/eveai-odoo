"""Tests for the res.users Evie preferences extension and the shared
language map (odoo-user-preferences-sync).

Covers the self-service whitelist, the write hook's compare-before-write
and echo guard, the language translation through ``evie.language_map``
(both directions unambiguous; unmapped is skipped, never cleared) and the
seeded map entries (which double as the relocation check: the map is
served from evie_base since 19.0.1.20.0).
"""

from unittest.mock import patch

from odoo.tests.common import TransactionCase

WEBHOOK_POST = ('odoo.addons.evie_base.models.evie_webhook.'
                'EvieWebhook.post')


class TestEvieUserPreferences(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].create({
            'name': 'Prefs Tester',
            'login': 'prefs.tester@example.com',
            'email': 'prefs.tester@example.com',
        })

    # -- self-service whitelist ----------------------------------------

    def test_field_is_self_readable_and_writeable(self):
        self.assertIn('x_evie_booking_page_url',
                      self.env['res.users'].SELF_READABLE_FIELDS)
        self.assertIn('x_evie_booking_page_url',
                      self.env['res.users'].SELF_WRITEABLE_FIELDS)

    def test_own_preferences_editable_without_admin(self):
        with patch(WEBHOOK_POST, return_value=(True, 'event-id')):
            self.user.with_user(self.user).write({
                'x_evie_booking_page_url': 'https://calendly.com/tester',
            })
        self.assertEqual(self.user.x_evie_booking_page_url,
                         'https://calendly.com/tester')

    # -- write hook ------------------------------------------------------

    def test_write_fires_webhook_on_actual_change(self):
        with patch(WEBHOOK_POST, return_value=(True, 'event-id')) as post:
            self.user.write({
                'x_evie_booking_page_url': 'https://calendly.com/tester',
            })
        self.assertEqual(post.call_count, 1)
        path, payload = post.call_args[0]
        self.assertEqual(path, '/user-preferences')
        self.assertEqual(payload['external_user']['id'], self.user.id)
        self.assertEqual(payload['external_user']['email'],
                         'prefs.tester@example.com')
        self.assertEqual(payload['customisation_options'],
                         {'booking_page_url': 'https://calendly.com/tester'})

    def test_clearing_sends_null(self):
        self.user.x_evie_booking_page_url = 'https://calendly.com/tester'
        with patch(WEBHOOK_POST, return_value=(True, 'event-id')) as post:
            self.user.write({'x_evie_booking_page_url': False})
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args[0][1]['customisation_options'],
                         {'booking_page_url': None})

    def test_noop_write_fires_no_webhook(self):
        with patch(WEBHOOK_POST, return_value=(True, 'event-id')) as post:
            self.user.write({'x_evie_booking_page_url': False})
        post.assert_not_called()

    def test_unrelated_write_fires_no_webhook(self):
        with patch(WEBHOOK_POST, return_value=(True, 'event-id')) as post:
            self.user.write({'signature': 'Regards'})
        post.assert_not_called()

    def test_sync_origin_context_suppresses_webhook(self):
        with patch(WEBHOOK_POST, return_value=(True, 'event-id')) as post:
            self.user.with_context(evie_sync_origin=True).write({
                'x_evie_booking_page_url': 'https://calendly.com/tester',
            })
        post.assert_not_called()

    def test_webhook_failure_does_not_block_the_write(self):
        with patch(WEBHOOK_POST, return_value=(False, 'http_500')):
            self.user.write({
                'x_evie_booking_page_url': 'https://calendly.com/tester',
            })
        self.assertEqual(self.user.x_evie_booking_page_url,
                         'https://calendly.com/tester')

    # -- language translation -------------------------------------------

    def test_language_translated_via_map(self):
        mapping = self.env['evie.language_map'].search(
            [('evie_language', '=', 'en')], limit=1)
        self.assertTrue(mapping)
        self.user.lang = mapping.odoo_lang_id.code
        self.assertEqual(self.user._evie_language_code(), 'en')

    def test_unmapped_language_returns_none(self):
        mapping = self.env['evie.language_map'].search(
            [('evie_language', '=', 'en')], limit=1)
        self.user.lang = mapping.odoo_lang_id.code
        mapping.active = False
        self.assertIsNone(self.user._evie_language_code())

    def test_language_change_sends_evie_code(self):
        mapping = self.env['evie.language_map'].search(
            [('evie_language', '=', 'en')], limit=1)
        other = self.env['evie.language_map'].search(
            [('evie_language', '!=', 'en')], limit=1)
        self.user.lang = mapping.odoo_lang_id.code
        # Activate the target language so the lang selection accepts it.
        other.odoo_lang_id.sudo().active = True
        with patch(WEBHOOK_POST, return_value=(True, 'event-id')) as post:
            self.user.write({'lang': other.odoo_lang_id.code})
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args[0][1]['preferred_language'],
                         other.evie_language)

    # -- shared map (relocation) -----------------------------------------

    def test_seeded_map_entries_present(self):
        codes = self.env['evie.language_map'].search([]).mapped('evie_language')
        for expected in ('en', 'fr', 'de', 'es', 'it', 'pt',
                         'nl', 'ru', 'zh', 'ja', 'ko'):
            self.assertIn(expected, codes)

    def test_map_unique_both_directions(self):
        from odoo.tools import mute_logger
        from psycopg2 import IntegrityError as PgIntegrityError
        existing = self.env['evie.language_map'].search([], limit=1)
        with mute_logger('odoo.sql_db'), \
                self.assertRaises(PgIntegrityError):
            self.env['evie.language_map'].create({
                'evie_language': existing.evie_language,
                'odoo_lang_id': existing.odoo_lang_id.id,
            })
