"""Tests for the N:1 Evie phase ↔ stage mapping
(sales-accepted-phase-funnel-mapping).

Covers the structural constraints: several stages per phase, one default
per phase, a stage feeding at most one active entry, per-phase type
consistency (including through later activation) and the relaxed stage
requirement for inactive opportunity entries.
"""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestPhaseStageMap(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Mapping = cls.env['evie.phase_stage_map']
        cls.Stage = cls.env['crm.stage']

    def _stage(self, name):
        return self.Stage.create({'name': name})

    def _entry(self, phase, stage=None, odoo_type=None, **values):
        vals = {
            'phase': phase,
            'odoo_type': odoo_type or ('opportunity' if stage else 'lead'),
            'odoo_stage_id': stage.id if stage else False,
        }
        vals.update(values)
        return self.Mapping.create(vals)

    def test_second_stage_for_same_phase_allowed(self):
        default = self.Mapping.search([('phase', '=', 'Opportunity')], limit=1)
        extra = self._entry('Opportunity', self._stage('Negotiation'),
                            is_default_for_phase=False)
        self.assertEqual(default.odoo_type, 'opportunity')
        self.assertEqual(extra.phase, 'Opportunity')

    def test_second_default_rejected(self):
        with self.assertRaises(ValidationError):
            self._entry('Opportunity', self._stage('Second default'),
                        is_default_for_phase=True)

    def test_stage_feeds_at_most_one_active_entry(self):
        default = self.Mapping.search([
            ('phase', '=', 'Opportunity'),
            ('is_default_for_phase', '=', True),
        ], limit=1)
        with self.assertRaises(ValidationError):
            self._entry('Converted', default.odoo_stage_id)

    def test_inactive_opportunity_entry_may_go_without_stage(self):
        entry = self._entry('Converted', odoo_type='opportunity',
                            active=False, is_default_for_phase=False)
        self.assertFalse(entry.odoo_stage_id)
        with self.assertRaises(ValidationError):
            entry.active = True

    def test_lead_entry_with_stage_rejected(self):
        with self.assertRaises(ValidationError):
            self._entry('MQL', self._stage('Illegal lead stage'),
                        odoo_type='lead')

    def test_divergent_type_rejected(self):
        with self.assertRaises(ValidationError):
            self._entry('Opportunity', odoo_type='lead',
                        is_default_for_phase=False, active=False)

    def test_type_change_to_divergent_type_rejected(self):
        entry = self._entry('Converted', self._stage('Extra won stage'),
                            is_default_for_phase=False)
        with self.assertRaises(ValidationError):
            entry.odoo_type = 'lead'

    def test_reverse_lookup_deterministic_with_extra_stage(self):
        extra_stage = self._stage('Negotiation')
        self._entry('Opportunity', extra_stage, is_default_for_phase=False)
        self.assertEqual(
            self.Mapping.phase_for_stage(extra_stage.id), 'Opportunity')

    def test_forward_target_uses_default_entry(self):
        default = self.Mapping.search([
            ('phase', '=', 'Opportunity'),
            ('is_default_for_phase', '=', True),
        ], limit=1)
        self._entry('Opportunity', self._stage('Negotiation'),
                    is_default_for_phase=False)
        target = self.Mapping.target_for_phase('Opportunity')
        self.assertEqual(target['odoo_stage_id'], default.odoo_stage_id.id)

    def test_inactive_entry_without_stage_ignored_by_lookups(self):
        self._entry('Converted', odoo_type='opportunity', active=False,
                    is_default_for_phase=False)
        # The inactive placeholder must not leak into either direction.
        self.assertIsNone(self.Mapping.target_for_phase('__no_such_phase__'))
        target = self.Mapping.target_for_phase('Converted')
        default = self.Mapping.search([
            ('phase', '=', 'Converted'),
            ('is_default_for_phase', '=', True),
        ], limit=1)
        self.assertEqual(target['odoo_stage_id'], default.odoo_stage_id.id)
