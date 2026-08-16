# Evie Odoo Modules

Custom Odoo modules for the Ask Eve AI (Evie) integration. **Tier 1 only:**
these modules require odoo.sh or self-hosted Odoo (reference: Odoo 19 LTS).
Odoo Online (SaaS) does not support custom modules — see the deferred Tier 2
track in Gitea issue #19.

## Modules

| Module | Purpose |
|--------|---------|
| `evie_base` | Namespace conventions, Evie settings (webhook URL + API key), health surface (`evie.health.get_status`), shared webhook client, Evie menu root, shared brand assets (`o_evie_icon`, `evie_link` widget, notebook tab branding) |
| `evie_crm` | `x_evie_*` anchor fields on `crm.lead` (chatter-tracked, rendered as branded open-in-Evie links), `evie.phase_stage_map` (tenant phase ↔ stage mapping, seeded), `[AUTO] Evie` automation rules |

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

## Integration identity (security best practice)

The Evie → Odoo sync authenticates with a **personal Odoo API key** — and an
API key is always bound to an internal user. Whose key the tenant uses is a
conscious choice with security, audit and licence consequences:

| Option | Licence cost | Consequence |
|--------|--------------|-------------|
| **A. Reuse an existing (admin) user's key** | none | Chatter entries for sync writes are attributed to that user; setting the user's avatar to the Evie logo also brands their *manual* actions — not recommended beyond a quick trial. |
| **B. Dedicated "Evie" internal user (recommended)** | Odoo **Enterprise**: one extra licensed user per tenant; Odoo **Community**: none | Clean audit identity, least privilege (grant only rights on the synced models), avatar can carry the Evie logo. This is the security best practice. |
| **C. "Evie" partner as note author** | none (partners are not users) | Only applies to notes Evie *posts* to the chatter (follow-up, Gitea issue Ask-Eve-AI/eveAI#22); automatic field-tracking entries always take the API-key user as author. |

Recommendation: option B. Create a dedicated internal user (e.g. `evie-sync`),
restrict its rights to the synced models, generate its API key under
*My Preferences → Account Security*, and upload the Evie logo as its avatar.

## Branding assets

`evie_base` ships the shared web assets (backend bundle): the `o_evie_icon`
CSS class (turns any `icon="o_evie_icon"` button attribute into the Evie
logo), the `evie_link` field widget and the notebook tab branding patch.
Master logos live in `integrations/Odoo/brand/logos/`; module copies under
`static/` are derived from them (colour variant by default). When the master
logos change, refresh the derived copies.

## Adding a new "open in Evie" reference type

The lead form renders Evie references via the `evie_link` widget, which calls
the single dispatcher `crm.lead.action_evie_open(kind, reference)`. To add a
reference type:

1. Add the kind to `EVIE_OPEN_KINDS` in `evie_crm/models/crm_lead.py`
   (maps the kind to the view-token request field).
2. Teach the Evie view-token endpoint the new kind
   (`ENTITY_ID_KEYS` in `external_document_view_services.py`, plus a view
   route that renders it).
3. Render the field with `widget="evie_link"` and `options="{'kind': ...}"`.

Existing kinds: `document` (document version) and `capsule` (Data Capsule).

## Contract with the Evie platform

- Evie → Odoo: push sync writes `type`/`stage_id` per the mapping and
  **always** writes `x_evie_phase`, `x_evie_capsule_id`, `x_evie_last_synced`.
  Evie writes with context `evie_skip_phase_event=True` to prevent echo loops.
- Odoo → Evie: `[AUTO] Evie: stage → phase` reverse-translates the stage via
  the mapping, updates `x_evie_phase` and POSTs the translated phase to
  `<base>/stage-change`. Mapping changes POST to `<base>/mapping-changed`.
- Health: `evie.health.get_status` (callable via the JSON-2 API) reports
  installed `evie_*` versions and missing fields/models.
