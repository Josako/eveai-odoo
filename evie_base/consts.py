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

#: Stable Evie language codes (ISO 639-1, Evie is master). Must match the
#: supported-language list on the Evie side (config.py). Used by
#: evie_crm's evie.language_map to bind each code to one res.lang.
EVIE_LANGUAGES = [
    ("en", "English"),
    ("fr", "French"),
    ("de", "German"),
    ("es", "Spanish"),
    ("it", "Italian"),
    ("pt", "Portuguese"),
    ("nl", "Dutch"),
    ("ru", "Russian"),
    ("zh", "Chinese"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
]

EVIE_LANGUAGE_SELECTION = list(EVIE_LANGUAGES)

#: Stable Evie marketing initiative type keys (Evie is master). Must match
#: the seeded keys of the MARKETING_INITIATIVE_TYPE dynamic list on the Evie
#: side. Labels may be renamed per tenant in Evie; these keys never change.
#: Tenant-added keys are a deferred platform capability (marketing change
#: design D3b) — until then this fixed set is complete.
MARKETING_INITIATIVE_TYPES = [
    "Trade Show",
    "Webinar",
    "Campaign",
    "Conference",
    "Roadshow",
    "Other",
]

MARKETING_INITIATIVE_TYPE_SELECTION = [
    (key, key) for key in MARKETING_INITIATIVE_TYPES
]

#: Stable Evie marketing channel type keys (Evie is master). Must match the
#: seeded keys of the MARKETING_CHANNEL_TYPE dynamic list on the Evie side.
#: QR channel types arrive with the anonymous-rendering change (they get
#: behaviour then); tenant-added keys are deferred (design D3b).
MARKETING_CHANNEL_TYPES = [
    "Email",
    "Social",
    "Advertising",
    "Specialist",
    "Rep Capture",
    "Business Card",
    "Import",
    "Other",
]

MARKETING_CHANNEL_TYPE_SELECTION = [
    (key, key) for key in MARKETING_CHANNEL_TYPES
]
