"""Shared constants for all evie_* modules.

Single source of truth for the stable Evie funnel phase keys. These keys are
owned by the Evie platform (master data); they must match the keys of the
CRM_LEAD_PHASE dynamic list on the Evie side. Labels may be renamed per tenant
in Evie; these keys never change.
"""

#: Stable Evie CRM funnel phases (Evie is master). Order matters.
EVIE_PHASES = [
    "Suspect",
    "Prospect",
    "Cold Lead",
    "Warm Lead",
    "MQL",
    "SQL",
    "Opportunity",
    "Converted",
    "Disqualified",
]

#: Odoo crm.lead type per phase default (see evie_crm seed data).
EVIE_PHASE_SELECTION = [(phase, phase) for phase in EVIE_PHASES]
