#!/usr/bin/env bash
#
# sync_odoo_modules_dev.sh — deploy the LOCAL working tree to the dev Odoo.
#
# Runs on your dev machine. Rsyncs integrations/Odoo/ (including uncommitted
# changes) to Minty and upgrades the modules in every Odoo database. The
# fastest iteration loop: edit → run → test, no commits needed.
#
# The git checkout on Minty is left dirty on purpose; the next
# update_odoo_modules.sh run hard-resets it back to a clean git ref.
# Because the deployed state is not a commit, always do a final
# `update_odoo_modules.sh <branch>` run before review/merge so the tested
# state is traceable.
#
# Usage:
#   integrations/Odoo/deploy/sync_odoo_modules_dev.sh
#
# Configuration via environment:
#   MINTY_HOST        ssh target (pieter@minty.homelab.askeveai.be)
#   ODOO_DEPLOY_DIR   compose project dir on Minty
#
set -euo pipefail

MINTY_HOST="${MINTY_HOST:-pieter@minty.homelab.askeveai.be}"
DEPLOY_DIR="${ODOO_DEPLOY_DIR:-/home/pieter/containers/odoo}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

log() { echo "[odoo-dev-sync] $*"; }

log "Syncing working tree (integrations/Odoo) to $MINTY_HOST"
rsync -az --delete \
    "$REPO_ROOT/integrations/Odoo/" \
    "$MINTY_HOST:$DEPLOY_DIR/custom-addons-repo/integrations/Odoo/"

log "Recording deploy marker and upgrading modules"
ssh "$MINTY_HOST" bash -s <<EOF
set -euo pipefail
chmod -R a+rX "$DEPLOY_DIR/custom-addons-repo/integrations/Odoo"
# Refresh the persistent script copy from the synced working tree, then upgrade
rsync -a --delete \
    "$DEPLOY_DIR/custom-addons-repo/integrations/Odoo/deploy/" "$DEPLOY_DIR/deploy/"
chmod +x "$DEPLOY_DIR/deploy"/*.sh
{
    echo "ref=WORKTREE"
    echo "source=rsync:$(hostname)"
    echo "deployed_at=\$(date -Is)"
} > "$DEPLOY_DIR/deployed-ref"
"$DEPLOY_DIR/deploy/odoo_module_upgrade.sh"
EOF

log "Done. Working tree is live on the dev Odoo (marked as WORKTREE — not a commit)."
