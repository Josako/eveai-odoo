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
|---|---|---|---|---|---|---|
| `release/19.0.1.17.0` | 2026-09-14 | 19.0.1.11.0 | 19.0.1.17.0 | 19.0.1.0.0 | ODOO_CRM config ≥ 1.9.3 | Originating chat session on the lead: `x_evie_chat_session_id` + `chat_session` open-in-Evie kind (read-only session page) (sync-lead-chat-session) |
| `release/19.0.1.16.0` | 2026-09-14 | 19.0.1.11.0 | 19.0.1.16.0 | 19.0.1.0.0 | ODOO_CRM config ≥ 1.9.2 | Meeting Request activity type + mapping, `has_mapping` helper, health-surface `activity_type_map_keys` (add-odoo-module-distribution, Gitea #66) |
