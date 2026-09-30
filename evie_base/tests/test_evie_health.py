"""Tests for the evie.health diagnostic surface.

Covers ``get_model_ids`` (odoo-server-side-model-resolution): the
least-privilege integration API user resolves ``ir.model`` ids through this
method because Odoo 19 restricts ``ir.model`` read access to
administrator-level groups.
"""

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestGetModelIds(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.health = cls.env['evie.health']

    def test_resolves_requested_models_only(self):
        result = self.health.get_model_ids(['res.partner', 'res.users'])
        self.assertEqual(set(result), {'res.partner', 'res.users'})
        self.assertTrue(all(isinstance(v, int) for v in result.values()))
        self.assertEqual(
            result['res.partner'],
            self.env['ir.model'].sudo().search(
                [('model', '=', 'res.partner')], limit=1).id,
        )

    def test_unknown_model_maps_to_none(self):
        result = self.health.get_model_ids(['does.not.exist'])
        self.assertEqual(result, {'does.not.exist': None})

    def test_mixed_known_and_unknown(self):
        result = self.health.get_model_ids(['res.partner', 'does.not.exist'])
        self.assertIsInstance(result['res.partner'], int)
        self.assertIsNone(result['does.not.exist'])

    def test_empty_input(self):
        self.assertEqual(self.health.get_model_ids([]), {})
        self.assertEqual(self.health.get_model_ids(None), {})

    def test_resolvable_without_ir_model_acl(self):
        """A plain user (no ir.model read — the Odoo 19 default) can call
        the method while a direct ORM lookup is refused."""
        user = self.env['res.users'].create({
            'name': 'No Registry Rights',
            'login': 'no-registry-rights',
        })
        with self.assertRaises(AccessError):
            self.env['ir.model'].with_user(user).search(
                [('model', '=', 'res.partner')], limit=1)
        result = self.health.with_user(user).get_model_ids(['res.partner'])
        self.assertIsInstance(result['res.partner'], int)
