#!/usr/bin/env bash
#
# odoo_module_upgrade.sh — shared module-upgrade step for Odoo deploys.
#
# Runs ON Minty. Applies the currently mounted module code to every Odoo
# database: Odoo only applies field/data/view changes on install/upgrade,
# so a plain restart is never enough.
#
# Called by update_odoo_modules.sh (git deploys) and sync_odoo_modules_dev.sh
# (working-tree deploys); not meant to be run directly.
#
# Configuration via environment (defaults match the Minty layout):
#   ODOO_DEPLOY_DIR    compose project dir  (/home/pieter/containers/odoo)
#   ODOO_DB_REGEX      databases to upgrade (^(dev-pieter-db|dev-toska-db|demo-db|test-db)$)
#   ODOO_UPGRADE_MODULES  modules to upgrade (evie_base,evie_crm —
#                         dependencies are NOT upgraded implicitly)
#
set -euo pipefail

PROJECT_DIR="${ODOO_DEPLOY_DIR:-/home/pieter/containers/odoo}"
REPO_DIR="$PROJECT_DIR/custom-addons-repo"
COMPOSE_FILE="$PROJECT_DIR/compose.yaml"
PODMAN_COMPOSE="${PODMAN_COMPOSE:-$HOME/.local/bin/podman-compose}"
ODOO_IMAGE="${ODOO_IMAGE:-docker.io/library/odoo:19}"
DB_REGEX="${ODOO_DB_REGEX:-^(dev-pieter-db|dev-toska-db|demo-db|test-db)$}"
MODULES="${ODOO_UPGRADE_MODULES:-evie_base,evie_crm}"

source "$PROJECT_DIR/.env"

log() { echo "[odoo-module-upgrade] $*"; }

DATABASES=$(podman exec odoo-db psql -U odoo -d postgres -tAc \
    "SELECT datname FROM pg_database WHERE datname ~ '$DB_REGEX'")
if [ -z "$DATABASES" ]; then
    log "ERROR: no databases match '$DB_REGEX'"
    exit 1
fi

log "Stopping Odoo server (database keeps running)"
"$PODMAN_COMPOSE" -f "$COMPOSE_FILE" stop odoo

upgrade_failed=0
for db in $DATABASES; do
    log "Upgrading modules [$MODULES] in $db"
    # Note: the official image entrypoint translates HOST/USER/PASSWORD into
    # --db_* flags (default HOST=db) — pass them as env, not as flags.
    if ! podman run --rm \
            --network odoo-network \
            -e HOST=odoo-db -e USER=odoo -e PASSWORD="$ODOO_DB_PASSWORD" \
            -e ODOO_ADMIN_PASSWORD="$ODOO_ADMIN_PASSWORD" \
            -v "$PROJECT_DIR/data/odoo:/var/lib/odoo:U" \
            -v "$REPO_DIR/integrations/Odoo:/mnt/extra-addons:ro,Z" \
            "$ODOO_IMAGE" \
            odoo --config=/var/lib/odoo/odoo.conf \
                 -d "$db" -u "$MODULES" --stop-after-init; then
        log "ERROR: module upgrade failed for database '$db'"
        upgrade_failed=1
    fi
done

log "Starting Odoo server"
"$PODMAN_COMPOSE" -f "$COMPOSE_FILE" up -d odoo

if [ "$upgrade_failed" -ne 0 ]; then
    log "ERROR: at least one database upgrade failed — check the one-shot output above"
    exit 1
fi

sleep 15
curl -sf http://localhost:3050/web/health >/dev/null \
    && log "Module update finished — Odoo is healthy" \
    || { log "ERROR: health check FAILED — check: podman logs odoo --tail 100"; exit 1; }
