#!/usr/bin/env bash
#
# update_odoo_modules.sh — deploy Odoo custom modules from a git ref.
#
# Runs ON Minty. Updates the sparse checkout of integrations/Odoo to the
# requested ref (branch, tag or commit) and upgrades the modules in every
# Odoo database. The deployed ref is recorded in $DEPLOY_DIR/deployed-ref.
#
# Usage:
#   update_odoo_modules.sh                 # deploy origin/develop (default)
#   update_odoo_modules.sh my-feature      # deploy origin/my-feature
#   update_odoo_modules.sh 1a2b3c4d        # deploy a specific commit
#
# Iterating on a feature branch: push, re-run this script with the branch
# name — the checkout hard-resets to the branch's new HEAD every time.
# After merging, run without arguments to return the environment to develop.
#
# Configuration via environment:
#   ODOO_DEPLOY_DIR   compose project dir (/home/pieter/containers/odoo)
#
# Installation on Minty: ~/.local/bin/update_odoo_modules.sh symlinks to
# $DEPLOY_DIR/deploy/update_odoo_modules.sh — a persistent copy OUTSIDE the
# git checkout (a ref switch hard-resets/cleans the checkout, which would
# otherwise delete the scripts themselves). After every fetch the persistent
# copy is refreshed from the checked-out ref when it carries deploy/.
#
set -euo pipefail

REF="${1:-develop}"
DEPLOY_DIR="${ODOO_DEPLOY_DIR:-/home/pieter/containers/odoo}"
REPO_DIR="$DEPLOY_DIR/custom-addons-repo"
PERSISTENT_DEPLOY_DIR="$DEPLOY_DIR/deploy"
MARKER="$DEPLOY_DIR/deployed-ref"

log() { echo "[odoo-deploy] $*"; }

cd "$REPO_DIR"
git fetch --quiet origin

# Resolve the ref: prefer a remote branch, then any commit-ish (tag, sha).
if git rev-parse --verify --quiet "origin/$REF" >/dev/null; then
    TARGET="origin/$REF"
elif git rev-parse --verify --quiet "$REF^{commit}" >/dev/null; then
    TARGET="$REF"
else
    log "ERROR: unknown ref '$REF' (not a remote branch, tag or commit)"
    exit 1
fi

# Detached checkout, hard reset and clean: guarantees the mounted tree is
# exactly the requested commit, also after a working-tree (rsync) deploy.
# The checkout must be forced: sync_odoo_modules_dev.sh deliberately leaves
# the tree dirty, and a plain checkout aborts when those dirty files differ
# between the current checkout and the target — before the reset could run.
git checkout --quiet --detach --force "$TARGET"
git reset --quiet --hard "$TARGET"
git clean -fdq -- integrations/Odoo

SHA="$(git rev-parse --short HEAD)"
{
    echo "ref=$REF"
    echo "sha=$(git rev-parse HEAD)"
    echo "source=git"
    echo "deployed_at=$(date -Is)"
} > "$MARKER"

log "Deployed ref '$REF' ($SHA)"

# Self-update: refresh the persistent script copy from the checked-out ref.
if [ -d "$REPO_DIR/integrations/Odoo/deploy" ]; then
    rsync -a --delete \
        "$REPO_DIR/integrations/Odoo/deploy/" "$PERSISTENT_DEPLOY_DIR/"
    chmod +x "$PERSISTENT_DEPLOY_DIR"/*.sh
fi

"$PERSISTENT_DEPLOY_DIR/odoo_module_upgrade.sh"
log "Done. Deployed: $REF ($SHA)"
