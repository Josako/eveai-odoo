"""res.lang extension for the Evie language picker (crm-sync-polish).

The lead's ``x_evie_language`` dropdown must offer exactly the languages
present in ``evie.language_map`` — including languages not activated in
this database (activating a language loads full UI translations, which a
lead-language tag never needs). A view domain can't express "rows of
another model", and dynamic domains on invisible helper fields proved
fragile, so the restriction lives here, gated on a context key so every
other language dropdown in Odoo keeps its default behaviour.
"""

import logging

from odoo import api, models
from odoo.fields import Domain

_logger = logging.getLogger(__name__)

#: Context flag set on the x_evie_language field in the lead form view.
EVIE_MAPPED_ONLY_KEY = 'evie_mapped_only'


class ResLang(models.Model):
    _inherit = 'res.lang'

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        if self.env.context.get(EVIE_MAPPED_ONLY_KEY):
            mapped_ids = (self.env['evie.language_map'].search([])
                          .mapped('odoo_lang_id').ids)
            domain = Domain('id', 'in', mapped_ids) & Domain(domain or Domain.TRUE)
            # Mapped-but-not-activated languages must be offered too —
            # force this server-side instead of relying on the view's
            # active_test context.
            self = self.with_context(active_test=False)
        return super().name_search(
            name=name, domain=domain, operator=operator, limit=limit)
