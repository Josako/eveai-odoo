"""Tests for the evie.capsule.urls server surface (odoo-lead-linked-urls).

Covers ``get_urls``: the record's capsule resolution via the shared
helper, the live fetch through ``evie.webhook``, and the never-raise
contract (not-linked and unreachable states).
"""

from unittest.mock import patch

from odoo.tests.common import TransactionCase

GET_FOR_JSON = 'odoo.addons.evie_base.models.evie_webhook.EvieWebhook.get_for_json'


class TestEvieCapsuleUrls(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.urls_model = cls.env['evie.capsule.urls']
        cls.partner = cls.env['res.partner'].create({'name': 'Capsule URLs Test'})

    def test_not_linked_returns_linked_false_without_evie_call(self):
        """An empty capsule id field resolves locally; Evie is not called.

        res.partner has no x_evie_capsule_id in evie_base — the (empty)
        ``ref`` char field stands in: int('' or 0) -> False -> not linked.
        """
        with patch(GET_FOR_JSON) as get:
            result = self.urls_model.get_urls('res.partner', self.partner.id,
                                              capsule_id_field='ref')
        self.assertTrue(result['ok'])
        self.assertFalse(result['linked'])
        self.assertEqual(result['urls'], [])
        get.assert_not_called()

    def test_unreachable_evie_returns_ok_false(self):
        with patch(GET_FOR_JSON, return_value=(False, 'connection_error')) as get:
            result = self.urls_model.get_urls('res.partner', self.partner.id,
                                              capsule_id_field='id')
        self.assertFalse(result['ok'])
        self.assertTrue(result['linked'])
        self.assertEqual(result['urls'], [])
        get.assert_called_once()

    def test_listing_maps_through(self):
        urls = [{'relation_id': 11, 'url': 'https://example.com/acme',
                 'label': 'Partner page', 'kind': 'DIRECTORY',
                 'source': 'LIST_IMPORT', 'created_at': '2026-11-02T12:00:00'}]
        with patch(GET_FOR_JSON, return_value=(True, {'urls': urls})):
            result = self.urls_model.get_urls('res.partner', self.partner.id,
                                              capsule_id_field='id')
        self.assertTrue(result['ok'])
        self.assertTrue(result['linked'])
        self.assertEqual(result['urls'], urls)
