# Odoo module deploy scripts

Branch-deployment workflow for the `evie_*` modules on the dev Odoo (Minty).
The compose stack mounts `custom-addons-repo/integrations/Odoo` read-only into
the container, so "deploying" = putting the right code in that directory +
running a module upgrade per database.

| Script | Runs on | Purpose |
|--------|---------|---------|
| `update_odoo_modules.sh [ref]` | Minty | Deploy a git ref (branch/tag/commit; default `develop`) and upgrade all databases |
| `sync_odoo_modules_dev.sh` | dev machine | Rsync the local working tree (incl. uncommitted changes) and upgrade |
| `odoo_module_upgrade.sh` | Minty | Shared upgrade step; called by both, not run directly |

On Minty, `~/.local/bin/update_odoo_modules.sh` is a symlink to
`containers/odoo/deploy/update_odoo_modules.sh` — a persistent copy **outside**
the git checkout (a ref switch hard-resets/cleans the checkout and would
delete the scripts themselves). That copy is refreshed from the checked-out
ref on every deploy, so the scripts stay versioned with the code they deploy
without ever deleting themselves.

## Feature-branch workflow

```bash
# 1. Iterate on the feature branch
git push origin my-feature
ssh pieter@minty.homelab.askeveai.be update_odoo_modules.sh my-feature
# ... test on https://odoo.frps.askeveai.be ...

# 2. Changed something? Push and re-run — the checkout hard-resets to the
#    branch's new HEAD.

# 3. After merge to develop, return the environment:
ssh pieter@minty.homelab.askeveai.be update_odoo_modules.sh
```

Rapid WIP iteration without committing (uncommitted changes included):

```bash
integrations/Odoo/deploy/sync_odoo_modules_dev.sh
```

Always do a final `update_odoo_modules.sh <branch>` run before review/merge —
a WORKTREE deploy is not traceable to a commit.

## What's running where

The last deploy is recorded in `/home/pieter/containers/odoo/deployed-ref`
(ref, sha, source, timestamp). `source=git` = traceable commit;
`source=rsync:<host>` = someone's working tree.

## Caveats

- Odoo never "downgrades": returning to `develop` after testing a newer
  module version leaves newer database columns in place (harmless — the
  registry just stops loading them).
- The dev Odoo tracks one ref at a time; two features can't be live-tested
  simultaneously on the same environment.
