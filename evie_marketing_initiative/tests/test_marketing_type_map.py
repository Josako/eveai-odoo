"""Tests for the tenant-extensible marketing type map
(odoo-marketing-mirror-create, D3b).

Covers the seed contract (platform defaults present), the dynamic
selection feeds on the mirror models, and tenant extensibility without a
module upgrade.
"""

from odoo.tests.common import TransactionCase


class TestMarketingTypeMap(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.TypeMap = cls.env['evie.marketing.type.map']
        cls.Initiative = cls.env['marketing.initiative']
        cls.Channel = cls.env['marketing.initiative.channel']

    def test_platform_defaults_seeded(self):
        initiative_keys = set(
            self.TypeMap.search([('kind', '=', 'initiative')])
            .mapped('evie_key'))
        self.assertIn('Trade Show', initiative_keys)
        self.assertIn('Other', initiative_keys)
        channel_keys = set(
            self.TypeMap.search([('kind', '=', 'channel')])
            .mapped('evie_key'))
        self.assertIn('Specialist', channel_keys)
        self.assertIn('Other', channel_keys)

    def test_selection_feeds_follow_the_map(self):
        initiative_options = dict(
            self.Initiative._selection_type())
        channel_options = dict(
            self.Channel._selection_channel_type())
        self.assertIn('Trade Show', initiative_options)
        self.assertIn('Specialist', channel_options)
        # Kinds never mix.
        self.assertNotIn('Specialist', initiative_options)
        self.assertNotIn('Trade Show', channel_options)

    def test_tenant_added_key_becomes_selectable(self):
        self.TypeMap.create({
            'kind': 'channel',
            'evie_key': 'Podcast',
            'label': 'Podcast Series',
        })
        options = dict(self.Channel._selection_channel_type())
        self.assertEqual(options.get('Podcast'), 'Podcast Series')
        # The stored value is the stable key, never the label.
        channel = self.Channel.create({
            'name': 'Podcast ads',
            'channel_type': 'Podcast',
        })
        self.assertEqual(channel.channel_type, 'Podcast')

    def test_keys_are_unique_per_kind(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.TypeMap.create({
                'kind': 'channel',
                'evie_key': 'Specialist',
                'label': 'Duplicate key',
            })
