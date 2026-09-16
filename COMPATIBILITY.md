# Evie Odoo module compatibility matrix

Which `evie_*` module release fits which Evie platform / integration
configuration (add-odoo-module-distribution, Channel A). Tenants and
partners pick the newest release whose modules satisfy the
`min_evie_module_versions` contract of their integration configuration —
the integration connection test (Settings → integration → Test connection)
reports the same contract and warns when the activity-type vocabulary has
drifted.

## Tag conventions

- `release/<version>` — the umbrella tag for one published release; the
  version is the highest full module version in the set. The tag message
  records the monorepo ref and commit the release was split from.
- `<module>/<version>` — per-module precision tags (e.g.
  `evie_crm/19.0.1.16.0`), for pinpointing one module's history.
- Releases are immutable: existing tags are never moved.

## Releases

| Umbrella tag | Date | evie_base | evie_crm | evie_marketing_initiative | Requires (platform contract) | Notes |
|---|---|---|---|---|---|---|---|
| `release/19.0.1.20.0` | 2026-09-16 | 19.0.1.14.0 | 19.0.1.20.0 | 19.0.1.2.0 | ODOO_CRM config ≥ 1.9.7 | Business card view from Odoo (odoo-capture-card-view): `business_card` on the capture mirror opens the scanned card in a tokenised read-only Evie media page via the new `capture_media` open-in-Evie kind; the `EVIE_OPEN_KINDS` registry moves into `evie_base` (`evie_crm` inherits it) so mirror models resolve all kinds without per-model overrides; initiative Captures/Channels tabs gain explicit inline list columns (mobile never renders blank rows); the "Answers (raw)" group leaves the capture form |
| `release/19.0.1.19.0` | 2026-09-16 | 19.0.1.13.0 | 19.0.1.19.0 | 19.0.1.1.0 | ODOO_CRM config ≥ 1.9.6 | Duplicate-proof outbound creates (fix-sync-duplicate-remote-creates): unique constraints on the identity anchors — `capsule_id` on the `evie.capsule.link` mixin (every mirror model, `<table>_capsule_id_uniq`) and `x_evie_capsule_id` on `crm.lead` / `mail.activity`; a duplicate create fails loudly and the Evie sync falls back to adopt-and-update |
| `release/19.0.1.18.0` | 2026-09-15 | 19.0.1.12.0 | 19.0.1.18.0 | 19.0.1.1.0 | ODOO_CRM config ≥ 1.9.5 | Capture Review activity type + map defaults and the review popup kind in the actions widget: tokenised external capture review from the Odoo capture mirror, no Evie login (business-card-extraction, odoo-external-capture-review); capture lifecycle gains `promoted` next to `processed` (to_review → processed → promoted), mirror list greys terminal captures (evie_marketing_initiative 19.0.1.1.0) |
| `release/19.0.1.17.0` | 2026-09-14 | 19.0.1.11.0 | 19.0.1.17.0 | 19.0.1.0.0 | ODOO_CRM config ≥ 1.9.3 | Originating chat session on the lead: `x_evie_chat_session_id` + `chat_session` open-in-Evie kind (read-only session page) (sync-lead-chat-session) |
| `release/19.0.1.16.0` | 2026-09-14 | 19.0.1.11.0 | 19.0.1.16.0 | 19.0.1.0.0 | ODOO_CRM config ≥ 1.9.2 | Meeting Request activity type + mapping, `has_mapping` helper, health-surface `activity_type_map_keys` (add-odoo-module-distribution, Gitea #66) |
