# -*- coding: utf-8 -*-
"""Grant the Evie integration identity its required groups — idempotent.

The Evie → Odoo sync authenticates with a personal API key of a dedicated
Odoo user (see "Integration identity" in integrations/Odoo/README.md).
That user needs, per installed mirror module, the module's manager group —
the sales groups deliberately have no create-rights on the mirror models,
so forgetting a group surfaces as an `AccessError` (HTTP 403) on
`marketing.initiative`, `meeting.plan`, ... during the sync.

This script grants the full set in one go and is **safe to re-run**: every
step is a no-op when already applied (groups are looked up, membership is
checked before adding, nothing is ever removed).

Usage
-----
Odoo.sh: paste the whole file in the Shell tab of the correct build
(check `echo $PGDATABASE` against the `database` of the Evie
IntegrationService — each branch/build has its own database).

Self-hosted:

    odoo-bin shell -d <db> < integrations/Odoo/scripts/grant_integration_user_groups.py

Configuration: set LOGIN below, or leave it None to auto-detect the user
that owns an API key (refuses to guess when several users own keys).

Note: `ir.model.access.check` is cached per user; if a 403 persists right
after granting, restart the build/worker (or wait for cache invalidation)
and re-run the sync.
"""

LOGIN = None  # e.g. 'evie-sync' — None = auto-detect the API-key owner

# (providing module, group xmlid) — a group is only granted when its module
# is installed in THIS database.
GROUPS = [
    ("sales_team", "sales_team.group_sale_salesman_all_leads"),
    ("evie_marketing_initiative", "evie_marketing_initiative.group_evie_marketing_manager"),
    ("evie_meeting_planning", "evie_meeting_planning.group_evie_meeting_manager"),
]

# Verification matrix: (model, operation expected to pass afterwards).
# Checked only for models that exist in this database.
VERIFY = [
    ("crm.lead", "create"),
    ("evie.phase_stage_map", "read"),
    ("marketing.initiative", "create"),
    ("meeting.plan", "create"),
    ("meeting.objective", "create"),
]


def _module_installed(env, name):
    return bool(env["ir.module.module"].sudo().search(
        [("name", "=", name), ("state", "=", "installed")], limit=1))


def _resolve_user(env, login):
    if login:
        user = env["res.users"].search([("login", "=", login)], limit=1)
        assert user, f"Geen user met login {login!r}"
        return user
    owners = env["res.users.apikeys"].search([]).mapped("user_id")
    assert owners, (
        "Geen API-keys gevonden — maak eerst een key aan voor de "
        "integratie-user, of zet LOGIN bovenaan dit script."
    )
    logins = owners.mapped("login")
    assert len(logins) == 1, (
        f"Meerdere API-key-eigenaars: {logins} — zet LOGIN bovenaan "
        "dit script op de login van de sync-identiteit."
    )
    return owners[0]


def grant_integration_user_groups(env, login=None):
    user = _resolve_user(env, login)
    print(f"Integratie-user: {user.login} (id {user.id})")

    for module, xmlid in GROUPS:
        if not _module_installed(env, module):
            print(f"  SKIP  {xmlid} (module {module} niet geïnstalleerd)")
            continue
        group = env.ref(xmlid, raise_if_not_found=False)
        if not group:
            print(f"  MISS  {xmlid} (xmlid ontbreekt — module-upgrade nodig?)")
            continue
        if user in group.user_ids:
            print(f"  OK    {xmlid} (al lid)")
        else:
            group.user_ids = [(4, user.id)]
            print(f"  ADD   {xmlid}")

    env.cr.commit()

    print("\nEffectieve rechten (ir.model.access.check):")
    access = env["ir.model.access"].with_user(user)
    ok = True
    for model, op in VERIFY:
        if not env["ir.model"].search([("model", "=", model)], limit=1):
            print(f"  n/a   {model} (model bestaat niet in deze db)")
            continue
        granted = access.check(model, op, False)
        ok = ok and granted
        print(f"  {'PASS' if granted else 'FAIL'}  {op:6} {model}")
    if not ok:
        print("\nLET OP: FAIL hierboven — herstart de build/worker "
              "(rechten-cache) en draai dit script opnieuw ter verificatie.")
    return user


grant_integration_user_groups(env, LOGIN)  # noqa: F821  (env: Odoo shell)
