# Evie Odoo Modules

Custom Odoo modules for the Ask Eve AI (Evie) integration. **Tier 1 only:**
these modules require odoo.sh or self-hosted Odoo (reference: Odoo 19 LTS).
Odoo Online (SaaS) does not support custom modules — see the deferred Tier 2
track in Gitea issue #19.

## Modules

| Module | Purpose |
|--------|---------|
| `evie_base` | Namespace conventions, Evie settings (webhook URL + API key), health surface (`evie.health.get_status`), shared webhook client, Evie menu root |
| `evie_crm` | `x_evie_*` anchor fields on `crm.lead`, `evie.phase_stage_map` (tenant phase ↔ stage mapping, seeded), `[AUTO] Evie` automation rules |

## Conventions

- Modules: `evie_*` — models: `evie.*` — fields: `x_evie_*`
- No Studio for production artefacts; everything declarative in the modules.
- Semver, kept in step with the Evie config/capsule versions they serve.
- Install/upgrade is idempotent; seed data uses `noupdate` so tenant edits
  survive upgrades.

## Install

1. Add this directory to the Odoo addons path (or deploy via odoo.sh).
2. Install `evie_crm` (pulls in `evie_base`).
3. Settings → Evie (Ask Eve AI): set the webhook base URL
   (`https://<evie-host>/api/v1/integrations/odoo`) and the TenantProject
   API key.
4. Review Evie ▸ Configuration ▸ Phase Mapping (seeded with the default
   funnel mapping; adjust stages per tenant).

## Contract with the Evie platform

- Evie → Odoo: push sync writes `type`/`stage_id` per the mapping and
  **always** writes `x_evie_phase`, `x_evie_capsule_id`, `x_evie_last_synced`.
  Evie writes with context `evie_skip_phase_event=True` to prevent echo loops.
- Odoo → Evie: `[AUTO] Evie: stage → phase` reverse-translates the stage via
  the mapping, updates `x_evie_phase` and POSTs the translated phase to
  `<base>/stage-change`. Mapping changes POST to `<base>/mapping-changed`.
- Health: `evie.health.get_status` (callable via the JSON-2 API) reports
  installed `evie_*` versions and missing fields/models.
