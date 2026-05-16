#!/usr/bin/env bash
# SocialHub - quick update script (pulled by GitHub Actions or run manually).
# - Pulls latest code from main
# - Updates Python + Node deps
# - Rebuilds frontend
# - Restarts the API
set -euo pipefail

APP_DIR="/var/www/socialhub"
BRANCH="main"

log() { echo -e "\033[1;32m==>\033[0m $*"; }

cd "$APP_DIR"

log "Fetching latest code..."
git fetch origin
git reset --hard "origin/${BRANCH}"

log "Updating backend dependencies..."
cd "$APP_DIR/backend"
./venv/bin/pip install -q -r requirements.txt

log "Restarting backend service..."
systemctl restart socialhub-api
sleep 2
systemctl is-active --quiet socialhub-api || { tail -n 30 /var/log/socialhub-api.log; exit 1; }

log "Rebuilding frontend..."
cd "$APP_DIR/frontend"
yarn install --frozen-lockfile --network-timeout 600000 --silent
CI=false yarn build

log "Reloading Nginx..."
nginx -t && systemctl reload nginx

log "Smoke test..."
sleep 1
curl -fs "https://app.letsm.io/api/health" >/dev/null && \
  echo -e "\033[1;32m✅  Update successful\033[0m" || \
  { echo -e "\033[1;31m❌  Health check failed\033[0m"; exit 1; }
