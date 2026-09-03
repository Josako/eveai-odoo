"""Evie activity outcomes (add-activity-sequences).

Stable outcome keys (``accepted``, ``not_accepted``, ``no_answer``, ...)
shipped as module data. They back the ``x_evie_outcome`` selection on
``mail.activity`` — the rep sets the outcome on the activity form before
marking it done, and the key travels to Evie with the completion, where it
drives the sequence engine's branch evaluation. The same keys are
referenced by the Evie-side sequence configs, so they are stable
identifiers: labels are tenant-editable (noupdate data), keys are not.
"""

from odoo import fields, models


class EvieActivityOutcome(models.Model):
    _name = 'evie.activity_outcome'
    _description = 'Evie Activity Outcome'
    _order = 'sequence, id'

    key = fields.Char(required=True, index=True)
    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _key_unique = models.Constraint(
        'unique(key)',
        'The outcome key must be unique.',
    )
