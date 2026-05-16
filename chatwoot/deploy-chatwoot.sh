#!/usr/bin/env bash
# Self-managed Chatwoot deployment.
# Replaces Coolify-managed chatwoot rails+sidekiq containers, keeps Coolify's postgres+redis.
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/letsm-ai/socialhub/main/chatwoot/deploy-chatwoot.sh)
set -euo pipefail

DOMAIN="letsm.io"
DEPLOY_DIR="/root/chatwoot"
BACKUP_DIR="${DEPLOY_DIR}/backups"
COOLIFY_RAILS="chatwoot-mu7tqsptecddqgrmg5o4zxs1"
COOLIFY_SIDEKIQ="sidekiq-mu7tqsptecddqgrmg5o4zxs1"
COOLIFY_POSTGRES="postgres-mu7tqsptecddqgrmg5o4zxs1"
COOLIFY_REDIS="redis-mu7tqsptecddqgrmg5o4zxs1"
COOLIFY_NETWORK="mu7tqsptecddqgrmg5o4zxs1"
TRAEFIK_NETWORK="coolify"

log()  { echo -e "\033[1;32m==>\033[0m $*"; }
warn() { echo -e "\033[1;33m==> WARN:\033[0m $*"; }
die()  { echo -e "\033[1;31m==> ERROR:\033[0m $*" >&2; exit 1; }

[ "$EUID" -eq 0 ] || die "Run as root"

# --------------------------------------------------------------------------
# 1. Sanity checks
# --------------------------------------------------------------------------
log "Step 1: Sanity checks..."
for c in "$COOLIFY_RAILS" "$COOLIFY_POSTGRES" "$COOLIFY_REDIS"; do
  docker ps --format '{{.Names}}' | grep -q "^${c}$" || die "Container '${c}' not running. Aborting."
done
docker network inspect "$COOLIFY_NETWORK" >/dev/null 2>&1 || die "Network '$COOLIFY_NETWORK' not found"
docker network inspect "$TRAEFIK_NETWORK" >/dev/null 2>&1 || die "Network '$TRAEFIK_NETWORK' not found"
log "All required containers and networks present."

mkdir -p "$DEPLOY_DIR" "$BACKUP_DIR"

# --------------------------------------------------------------------------
# 2. Backup database
# --------------------------------------------------------------------------
log "Step 2: Backing up Postgres database..."
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/chatwoot_db_${TIMESTAMP}.sql.gz"
docker exec "$COOLIFY_POSTGRES" pg_dumpall -c -U postgres 2>/dev/null | gzip > "$BACKUP_FILE" || warn "pg_dumpall failed (maybe wrong user) — trying pg_dump on chatwoot db..."
if [ ! -s "$BACKUP_FILE" ]; then
  POSTGRES_USER=$(docker exec "$COOLIFY_POSTGRES" printenv POSTGRES_USER 2>/dev/null || echo "postgres")
  POSTGRES_DB=$(docker exec "$COOLIFY_POSTGRES" printenv POSTGRES_DB 2>/dev/null || echo "chatwoot")
  docker exec "$COOLIFY_POSTGRES" pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" 2>/dev/null | gzip > "$BACKUP_FILE" || die "Backup failed."
fi
SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log "Backup saved: $BACKUP_FILE ($SIZE)"

# --------------------------------------------------------------------------
# 3. Extract env from running Coolify chatwoot container
# --------------------------------------------------------------------------
log "Step 3: Extracting env vars from existing Chatwoot..."
ENV_FILE="${DEPLOY_DIR}/.env"
docker inspect "$COOLIFY_RAILS" --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep -vE '^(HOME|PATH|HOSTNAME|TERM|LANG|LANGUAGE|LC_ALL|PWD|SHLVL|GEM_HOME|GEM_PATH|BUNDLE_PATH|RUBY_VERSION|BUNDLE_APP_CONFIG|BUNDLER_VERSION|MALLOC_ARENA_MAX|RAILS_LOG_TO_STDOUT|EXECJS_RUNTIME|_=)' \
  | grep -E '^[A-Z_]+=' > "$ENV_FILE"

# Force-override FRONTEND_URL and INSTALLATION_NAME to the right values
sed -i "/^FRONTEND_URL=/d" "$ENV_FILE"
sed -i "/^INSTALLATION_NAME=/d" "$ENV_FILE"
echo "FRONTEND_URL=https://${DOMAIN}" >> "$ENV_FILE"
echo "INSTALLATION_NAME=SocialHub" >> "$ENV_FILE"
echo "FORCE_SSL=true" >> "$ENV_FILE"
echo "ENABLE_ACCOUNT_SIGNUP=false" >> "$ENV_FILE"

# Make sure POSTGRES_HOST and REDIS_URL point to the coolify-managed instances
sed -i "/^POSTGRES_HOST=/d" "$ENV_FILE"
sed -i "/^REDIS_URL=/d" "$ENV_FILE"
echo "POSTGRES_HOST=${COOLIFY_POSTGRES}" >> "$ENV_FILE"
echo "REDIS_URL=redis://${COOLIFY_REDIS}:6379" >> "$ENV_FILE"

chmod 600 "$ENV_FILE"
log "Env file written: $ENV_FILE ($(wc -l < "$ENV_FILE") vars)"

# --------------------------------------------------------------------------
# 4. Write docker-compose.yml
# --------------------------------------------------------------------------
log "Step 4: Writing docker-compose.yml..."
cat > "${DEPLOY_DIR}/docker-compose.yml" <<'COMPOSE_EOF'
services:
  chatwoot-rails:
    image: chatwoot/chatwoot:latest
    container_name: chatwoot-rails
    restart: unless-stopped
    env_file: .env
    entrypoint: docker/entrypoints/rails.sh
    command: ["bundle", "exec", "rails", "s", "-p", "3000", "-b", "0.0.0.0"]
    networks:
      - chatwoot_data
      - traefik_net
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=coolify"
      - "traefik.http.routers.chatwoot.rule=Host(`letsm.io`) || Host(`www.letsm.io`)"
      - "traefik.http.routers.chatwoot.entrypoints=https"
      - "traefik.http.routers.chatwoot.tls=true"
      - "traefik.http.routers.chatwoot.tls.certresolver=letsencrypt"
      - "traefik.http.services.chatwoot.loadbalancer.server.port=3000"
      - "traefik.http.routers.chatwoot-http.rule=Host(`letsm.io`) || Host(`www.letsm.io`)"
      - "traefik.http.routers.chatwoot-http.entrypoints=http"
      - "traefik.http.routers.chatwoot-http.middlewares=chatwoot-https"
      - "traefik.http.middlewares.chatwoot-https.redirectscheme.scheme=https"

  chatwoot-sidekiq:
    image: chatwoot/chatwoot:latest
    container_name: chatwoot-sidekiq
    restart: unless-stopped
    env_file: .env
    command: ["bundle", "exec", "sidekiq", "-C", "config/sidekiq.yml"]
    networks:
      - chatwoot_data

networks:
  chatwoot_data:
    external: true
    name: mu7tqsptecddqgrmg5o4zxs1
  traefik_net:
    external: true
    name: coolify
COMPOSE_EOF

log "Compose file ready."

# --------------------------------------------------------------------------
# 5. Stop OLD Coolify chatwoot containers (keep data services running)
# --------------------------------------------------------------------------
log "Step 5: Stopping Coolify-managed chatwoot rails + sidekiq (data services KEPT running)..."
docker stop "$COOLIFY_RAILS" 2>/dev/null || warn "Couldn't stop $COOLIFY_RAILS"
docker stop "$COOLIFY_SIDEKIQ" 2>/dev/null || warn "Couldn't stop $COOLIFY_SIDEKIQ"

# Mark old containers so Coolify won't fight us (disable traefik labels on them)
for c in "$COOLIFY_RAILS" "$COOLIFY_SIDEKIQ"; do
  docker container update --restart=no "$c" 2>/dev/null || true
done
log "Old containers stopped (preserved, not deleted)."

# --------------------------------------------------------------------------
# 6. Start NEW chatwoot stack
# --------------------------------------------------------------------------
log "Step 6: Starting new chatwoot-rails and chatwoot-sidekiq..."
cd "$DEPLOY_DIR"
docker compose pull
docker compose up -d

# --------------------------------------------------------------------------
# 7. Wait + verify
# --------------------------------------------------------------------------
log "Step 7: Waiting for Chatwoot to boot (this can take 60-120s)..."
ok=0
for i in $(seq 1 40); do
  STATUS=$(curl -sk -o /dev/null -w "%{http_code}" "https://${DOMAIN}/" 2>/dev/null || echo "000")
  echo "  attempt $i/40 — status: $STATUS"
  if [ "$STATUS" = "200" ] || [ "$STATUS" = "302" ] || [ "$STATUS" = "301" ]; then ok=1; break; fi
  sleep 5
done

echo ""
echo "=== Container status ==="
docker ps --filter "name=chatwoot-" --format "table {{.Names}}\t{{.Status}}"
echo ""
echo "=== Final test ==="
curl -sI "https://${DOMAIN}/" 2>&1 | head -5
echo ""
echo "=== Platform API test ==="
curl -s "https://${DOMAIN}/platform/api/v1/accounts" -H "api_access_token: $(grep -E '^PLATFORM_API_KEY|^CHATWOOT_PLATFORM_API_KEY' .env | head -1 | cut -d= -f2)" -X GET 2>&1 | head -5 || true

if [ "$ok" = "1" ]; then
  cat <<EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉  Chatwoot is now self-managed at https://${DOMAIN}

Files at: ${DEPLOY_DIR}
Backup:   ${BACKUP_FILE}

Useful commands:
  • Logs:    docker logs -f chatwoot-rails
  • Restart: cd ${DEPLOY_DIR} && docker compose restart
  • Update:  cd ${DEPLOY_DIR} && docker compose pull && docker compose up -d

Coolify's chatwoot+sidekiq containers are stopped (not deleted) — DO NOT
restart them from Coolify UI or you will have a port conflict.
You may delete the "Chatwoot" service from Coolify project to clean up.

Postgres + Redis are still managed by Coolify (do not touch them).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF
else
  warn "Health check did not return 200/30x. Check logs: docker logs --tail 100 chatwoot-rails"
fi
