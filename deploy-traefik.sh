#!/usr/bin/env bash
# SocialHub - Traefik integration deploy (for Coolify-managed servers)
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/letsm-ai/socialhub/main/deploy-traefik.sh)
#
# This script:
#   - Creates a Docker container (nginx:alpine) that serves the React build
#     and proxies /api/* to the host FastAPI backend (127.0.0.1:8001)
#   - Adds Traefik labels so Traefik auto-routes app.letsm.io to it
#     with auto-issued Let's Encrypt SSL certificate.
#   - Leaves Chatwoot / Coolify completely untouched.
#
set -euo pipefail

DOMAIN="app.letsm.io"
APP_DIR="/var/www/socialhub"
COMPOSE_DIR="/root/socialhub"
TRAEFIK_NETWORK="coolify"

log()  { echo -e "\033[1;32m==>\033[0m $*"; }
die()  { echo -e "\033[1;31m==> ERROR:\033[0m $*" >&2; exit 1; }

[ "$EUID" -eq 0 ] || die "Run this script as root"

# Sanity checks
[ -d "${APP_DIR}/frontend/build" ] || die "Frontend build not found at ${APP_DIR}/frontend/build. Run deploy.sh first."
command -v docker >/dev/null 2>&1 || die "Docker not installed."
docker network inspect "$TRAEFIK_NETWORK" >/dev/null 2>&1 || die "Docker network '$TRAEFIK_NETWORK' not found."

log "Step 1: Remove obsolete host-nginx config for ${DOMAIN} (Traefik owns port 80)..."
rm -f /etc/nginx/sites-enabled/${DOMAIN} /etc/nginx/sites-available/${DOMAIN}
nginx -t >/dev/null 2>&1 && systemctl reload nginx || true

log "Step 2: Verify backend is running on 127.0.0.1:8001..."
if ! curl -fs http://127.0.0.1:8001/api/health >/dev/null 2>&1; then
  echo "Backend not healthy. Restarting..."
  systemctl restart socialhub-api
  sleep 3
  curl -fs http://127.0.0.1:8001/api/health >/dev/null 2>&1 || die "Backend not responding on 127.0.0.1:8001. Check: journalctl -u socialhub-api -n 50"
fi
log "Backend is healthy ✅"

log "Step 3: Writing compose files at ${COMPOSE_DIR}..."
mkdir -p "$COMPOSE_DIR"

cat > "${COMPOSE_DIR}/nginx.conf" <<'NGINX_EOF'
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;
    client_max_body_size 50M;

    # Forward API calls to host FastAPI backend
    location /api/ {
        proxy_pass http://host.docker.internal:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 60s;
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(?:js|css|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }
}
NGINX_EOF

cat > "${COMPOSE_DIR}/docker-compose.yml" <<COMPOSE_EOF
services:
  socialhub-web:
    image: nginx:alpine
    container_name: socialhub-web
    restart: unless-stopped
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - ${APP_DIR}/frontend/build:/usr/share/nginx/html:ro
      - ${COMPOSE_DIR}/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    networks:
      - ${TRAEFIK_NETWORK}
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=${TRAEFIK_NETWORK}"
      - "traefik.http.routers.socialhub.rule=Host(\`${DOMAIN}\`)"
      - "traefik.http.routers.socialhub.entrypoints=websecure"
      - "traefik.http.routers.socialhub.tls=true"
      - "traefik.http.routers.socialhub.tls.certresolver=letsencrypt"
      - "traefik.http.services.socialhub.loadbalancer.server.port=80"

networks:
  ${TRAEFIK_NETWORK}:
    external: true
COMPOSE_EOF

log "Step 4: Starting socialhub-web container..."
cd "$COMPOSE_DIR"
docker compose down 2>/dev/null || true
docker compose up -d
sleep 5

if ! docker ps --format '{{.Names}}' | grep -q '^socialhub-web$'; then
  echo "Container failed to start. Logs:"
  docker compose logs --tail=30
  die "socialhub-web container is not running"
fi
log "Container started ✅"

log "Step 5: Waiting for Traefik to issue SSL certificate (this can take 30-90 seconds)..."
for i in {1..30}; do
  HTTP_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "https://${DOMAIN}/" || echo "000")
  if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "304" ]; then
    log "HTTPS is live ✅ (status: $HTTP_CODE)"
    break
  fi
  echo "  attempt $i/30 — status: $HTTP_CODE — waiting 3s..."
  sleep 3
done

log "Step 6: Final checks..."
echo ""
echo "=== Frontend test ==="
curl -sI "https://${DOMAIN}/" 2>&1 | head -5 || true
echo ""
echo "=== Backend API test ==="
curl -s "https://${DOMAIN}/api/health" || echo "API health check failed"
echo ""

cat <<EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉  Deployment complete!

  • Site:           https://${DOMAIN}
  • Container:      socialhub-web
  • Compose dir:    ${COMPOSE_DIR}

Useful commands:
  • View web logs:    docker logs -f socialhub-web
  • View API logs:    tail -f /var/log/socialhub-api.log
  • Restart web:      cd ${COMPOSE_DIR} && docker compose restart
  • Restart API:      systemctl restart socialhub-api
  • Rebuild frontend: cd ${APP_DIR}/frontend && CI=false yarn build && docker restart socialhub-web
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If HTTPS is not ready yet, wait 60 seconds and visit https://${DOMAIN} manually.
First request triggers Let's Encrypt cert issuance via Traefik.
EOF
