# Evie Odoo Modules

Custom Odoo modules that connect an Odoo database to the Evie platform
(Ask Eve AI). **Tier 1 only:** these modules require Odoo.sh or self-hosted
Odoo (reference: Odoo 19 LTS). Odoo Online (SaaS) does not support custom
modules and is not supported.

The modules are a client of the Evie platform: without a running Evie
instance and a TenantProject API key they do nothing.

## Modules

| Module | Purpose |
|--------|---------|
| `evie_base` | Namespace conventions, Evie settings (webhook URL + API key), health surface (`evie.health.get_status`), shared webhook client, Evie menu root, shared brand assets (`o_evie_icon`, `evie_link` widget, notebook tab branding), generic `evie_actions` widget (dynamic capsule actions) |
| `evie_crm` | `x_evie_*` anchor fields on `crm.lead` (chatter-tracked, rendered as branded open-in-Evie links), `evie.phase_stage_map` (tenant phase ↔ stage mapping, seeded), `[AUTO] Evie` automation rules, Evie actions on the lead form |

## Conventions

- Modules: `evie_*` — models: `evie.*` — fields: `x_evie_*`
- No Studio for production artefacts; everything declarative in the modules.
- Semver, kept in step with the Evie config/capsule versions they serve.
- Install/upgrade is idempotent; seed data uses `noupdate` so tenant edits
  survive upgrades.

## Install

### Odoo.sh

Add this repository as a submodule of your Odoo.sh-linked repository — the
platform auto-detects `evie_base` and `evie_crm` as addons folders:

```bash
git submodule add -b <branch> <this-repo-url> evie
git commit -am "Add Evie modules" && git push
```

### Self-hosted

Copy (or clone) this directory onto the Odoo addons path, e.g. as
`/mnt/extra-addons`, then restart Odoo.

### Both

1. Install `evie_crm` (pulls in `evie_base`) via Apps.
2. Settings → Evie (Ask Eve AI): set the webhook base URL
   (`https://<evie-host>/api/v1/integrations/odoo`) and the TenantProject
   API key.
3. Review Evie ▸ Configuration ▸ Phase Mapping (seeded with the default
   funnel mapping; adjust stages per tenant).

Upgrades: pull the new code, then upgrade the module per database
(`odoo -d <db> -u evie_crm --stop-after-init`) — a plain restart does not
apply field/data/view changes.

## Integration identity (security best practice)

The Evie → Odoo sync authenticates with a **personal Odoo API key** — and an
API key is always bound to an internal user. Whose key the tenant uses is a
conscious choice with security, audit and licence consequences:

| Option | Licence cost | Consequence |
|--------|--------------|-------------|
| **A. Reuse an existing (admin) user's key** | none | Chatter entries for sync writes are attributed to that user; setting the user's avatar to the Evie logo also brands their *manual* actions — not recommended beyond a quick trial. |
| **B. Dedicated "Evie" internal user (recommended)** | Odoo **Enterprise**: one extra licensed user per tenant; Odoo **Community**: none | Clean audit identity, least privilege (grant only rights on the synced models), avatar can carry the Evie logo. This is the security best practice. |
| **C. "Evie" partner as note author** | none (partners are not users) | Only applies to notes Evie *posts* to the chatter; automatic field-tracking entries always take the API-key user as author. |

Recommendation: option B. Create a dedicated internal user (e.g. `evie-sync`),
restrict its rights to the synced models, generate its API key under
*My Preferences → Account Security*, and upload the Evie logo as its avatar.

## Branding assets

`evie_base` ships the shared web assets (backend bundle): the `o_evie_icon`
CSS class (turns any `icon="o_evie_icon"` button attribute into the Evie
logo), the `evie_link` field widget and the notebook tab branding patch.
Master logos live in `brand/logos/`; module copies under `static/` are
derived from them (colour variant by default). When the master logos change,
refresh the derived copies.

## Capsule actions on the lead form (evie_crm ≥ 19.0.1.4.0)

The lead form (Evie tab, *Actions*) offers the data capsule actions Evie
has configured for `CRM_LEAD` (e.g. *Research lead*, *Rescore lead*) —
discovered **live** from Evie via `GET <base>/capsule-actions` and cached
server-side for 30 minutes, so adding an action in the Evie configuration
never requires a module upgrade here. Behaviour:

- An action with no active specialist in Evie renders **disabled** with the
  reason; with several specialists a selection dialog is offered.
- Clicking executes via `POST <base>/action-execute` (the current Odoo user
  is sent as audit info only, together with the provisioned integration
  service id). Errors surface as a dialog, acceptance as a notification.
- While an action runs, the synced `x_evie_action_status` (`RESEARCHING`)
  disables the buttons; on completion the `[AUTO] Evie: action completed`
  rule posts the outcome to the chatter.
- The `evie_actions` widget lives in `evie_base`; future verticals reuse it
  with their own `capsule_type` view option.

## Adding a new "open in Evie" reference type

The lead form renders Evie references via the `evie_link` widget, which calls
the single dispatcher `crm.lead.action_evie_open(kind, reference)`. To add a
reference type:

1. Add the kind to `EVIE_OPEN_KINDS` in `evie_crm/models/crm_lead.py`
   (maps the kind to the view-token request field).
2. Teach the Evie view-token endpoint the new kind (view-token request
   handling plus a view route that renders it) on the Evie platform side.
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
  installed `evie_*` versions and missing fields/models. The call doubles as
  the integration identity handshake (integration-run-attention-audit): Evie
  passes its `integration_service_id`, which the module persists as the
  `evie.integration_service_id` config parameter and sends with every
  `action-execute`; the response carries `database_uuid`, which Evie stores
  as a read-only system field in the integration configuration (refreshed
  automatically, e.g. after a database restore). Evie validates the reported
  id against the authenticated tenant; attentions created by Odoo-initiated
  runs are audit-only records (immediately closed, carrying the Odoo user,
  integration and event id) because follow-up happens in Odoo itself.
- Actions: discovery via `GET <base>/capsule-actions?capsule_type=...`,
  execution via `POST <base>/action-execute` — both generic over the
  action kinds configured in Evie.

## Licence

LGPL-3 (see the module manifests).
