#!/usr/bin/env bash
# Fix SSL issuance for app.letsm.io using webroot challenge (more reliable than --nginx plugin)
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/letsm-ai/socialhub/main/fix-ssl.sh)
set -euo pipefail

DOMAIN="app.letsm.io"
SSL_EMAIL="mazin@lets-m.com"
APP_DIR="/var/www/socialhub"
WEBROOT="/var/www/html"

log() { echo -e "\033[1;32m==>\033[0m $*"; }

[ "$EUID" -eq 0 ] || { echo "Run as root"; exit 1; }

log "Step 1: Writing HTTP-only nginx config with explicit ACME path..."
mkdir -p "$WEBROOT/.well-known/acme-challenge"
chmod -R 755 "$WEBROOT"

cat > /etc/nginx/sites-available/${DOMAIN} <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    # ACME challenge must be served over HTTP without redirect
    location /.well-known/acme-challenge/ {
        root ${WEBROOT};
        default_type "text/plain";
        try_files \$uri =404;
    }

    # Everything else
    root ${APP_DIR}/frontend/build;
    index index.html;
    client_max_body_size 50M;

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 60s;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

ln -sf /etc/nginx/sites-available/${DOMAIN} /etc/nginx/sites-enabled/${DOMAIN}
nginx -t
systemctl reload nginx

log "Step 2: Verifying ACME path is reachable..."
TEST_TOKEN="ssl-verification-test-$(date +%s)"
echo "$TEST_TOKEN" > "${WEBROOT}/.well-known/acme-challenge/test"
RESPONSE=$(curl -sf "http://${DOMAIN}/.well-known/acme-challenge/test" || echo "FAIL")
rm -f "${WEBROOT}/.well-known/acme-challenge/test"
if [ "$RESPONSE" != "$TEST_TOKEN" ]; then
  echo -e "\033[1;31m==> ERROR:\033[0m HTTP test failed. Got: $RESPONSE"
  echo "Cannot reach http://${DOMAIN}/.well-known/acme-challenge/ — check DNS or proxy (Cloudflare/Hostinger)."
  exit 1
fi
log "ACME path is reachable ✅"

log "Step 3: Requesting certificate via webroot challenge..."
certbot certonly --webroot -w "${WEBROOT}" \
  -d "${DOMAIN}" \
  --non-interactive --agree-tos -m "${SSL_EMAIL}" \
  --force-renewal || true

if [ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
  echo -e "\033[1;31m==> ERROR:\033[0m Certificate file not found."
  exit 1
fi

log "Step 4: Writing final HTTPS nginx config..."
cat > /etc/nginx/sites-available/${DOMAIN} <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    location /.well-known/acme-challenge/ {
        root ${WEBROOT};
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    http2 on;
    server_name ${DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    root ${APP_DIR}/frontend/build;
    index index.html;
    client_max_body_size 50M;

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 60s;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location ~* \.(?:js|css|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf)\$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }
}
EOF

nginx -t
systemctl reload nginx

log "Step 5: Smoke test..."
sleep 2
if curl -fs "https://${DOMAIN}/api/health" >/dev/null 2>&1; then
  echo -e "\n\033[1;32m✅  SocialHub is LIVE at https://${DOMAIN}\033[0m\n"
else
  echo -e "\033[1;33m==> Warning:\033[0m HTTPS is up but /api/health failed. Check: systemctl status socialhub-api"
fi
