#!/usr/bin/env bash
# SocialHub - One-shot deployment script for Hostinger VPS
# Usage:  bash <(curl -s https://raw.githubusercontent.com/letsm-ai/socialhub/main/deploy.sh)
#
# This script:
#   - Installs Node.js, Python, MongoDB, Nginx, Certbot
#   - Clones the repo to /var/www/socialhub
#   - Writes production .env files
#   - Builds the frontend
#   - Registers a systemd service for the backend
#   - Configures Nginx + SSL for app.letsm.io
set -euo pipefail

# =============================================================
# Configuration (edit before running if you fork the project)
# =============================================================
DOMAIN="app.letsm.io"
SSL_EMAIL="mazin@lets-m.com"
APP_DIR="/var/www/socialhub"
REPO_URL="https://github.com/letsm-ai/socialhub.git"
BRANCH="main"
DB_NAME="socialhub_prod"
ADMIN_EMAIL="admin@letsm.io"
ADMIN_PASSWORD="Woot@Ch4321"
CHATWOOT_URL="https://letsm.io"
CHATWOOT_PLATFORM_API_KEY="6bEjxAWaJn55LHyadv5SwzRF"

log()  { echo -e "\033[1;32m==>\033[0m $*"; }
warn() { echo -e "\033[1;33m==>\033[0m $*"; }
die()  { echo -e "\033[1;31m==> ERROR:\033[0m $*" >&2; exit 1; }

[ "$EUID" -eq 0 ] || die "Run this script as root (sudo bash deploy.sh)"

# -------------------------------------------------------------
# 1. System packages
# -------------------------------------------------------------
log "Updating apt and installing system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y curl gnupg ca-certificates lsb-release software-properties-common \
                   git build-essential nginx certbot python3-certbot-nginx \
                   python3 python3-pip python3-venv

# -------------------------------------------------------------
# 2. Node.js 20 + yarn
# -------------------------------------------------------------
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | cut -dv -f2 | cut -d. -f1)" -lt 20 ]; then
  log "Installing Node.js 20..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi
if ! command -v yarn >/dev/null 2>&1; then
  log "Installing yarn..."
  npm install -g yarn
fi

# -------------------------------------------------------------
# 3. MongoDB 8 (supports Ubuntu 22.04 jammy & 24.04 noble)
# -------------------------------------------------------------
if ! command -v mongod >/dev/null 2>&1; then
  log "Installing MongoDB 8.0..."
  UBUNTU_CODENAME=$(lsb_release -cs)
  # MongoDB 8.0 supports jammy (22.04) and noble (24.04); fall back to jammy if codename unknown
  case "$UBUNTU_CODENAME" in
    jammy|noble) MONGO_CODENAME="$UBUNTU_CODENAME" ;;
    *)           MONGO_CODENAME="jammy" ;;
  esac
  # Clean any older mongo lists from previous failed runs
  rm -f /etc/apt/sources.list.d/mongodb-*.list /usr/share/keyrings/mongo-*.gpg
  curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | gpg --dearmor -o /usr/share/keyrings/mongo-8.gpg
  echo "deb [signed-by=/usr/share/keyrings/mongo-8.gpg] https://repo.mongodb.org/apt/ubuntu ${MONGO_CODENAME}/mongodb-org/8.0 multiverse" \
       > /etc/apt/sources.list.d/mongodb-8.list
  apt-get update -y
  apt-get install -y mongodb-org
fi
systemctl enable --now mongod
sleep 2

# -------------------------------------------------------------
# 4. Clone / pull repo
# -------------------------------------------------------------
if [ -d "$APP_DIR/.git" ]; then
  log "Repo exists, pulling latest..."
  git -C "$APP_DIR" fetch origin
  git -C "$APP_DIR" reset --hard "origin/${BRANCH}"
else
  log "Cloning $REPO_URL ..."
  mkdir -p "$(dirname "$APP_DIR")"
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

# -------------------------------------------------------------
# 5. Backend .env
# -------------------------------------------------------------
log "Writing backend/.env ..."
JWT_SECRET=$(openssl rand -hex 32)
cat > "$APP_DIR/backend/.env" <<EOF
MONGO_URL="mongodb://localhost:27017"
DB_NAME="${DB_NAME}"
CORS_ORIGINS="https://${DOMAIN}"
JWT_SECRET="${JWT_SECRET}"
ADMIN_EMAIL="${ADMIN_EMAIL}"
ADMIN_PASSWORD="${ADMIN_PASSWORD}"
FRONTEND_URL="https://${DOMAIN}"
CHATWOOT_URL="${CHATWOOT_URL}"
CHATWOOT_PLATFORM_API_KEY="${CHATWOOT_PLATFORM_API_KEY}"
EOF
chmod 600 "$APP_DIR/backend/.env"

# -------------------------------------------------------------
# 6. Backend venv + deps
# -------------------------------------------------------------
log "Setting up backend Python venv..."
cd "$APP_DIR/backend"
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# -------------------------------------------------------------
# 7. systemd service
# -------------------------------------------------------------
log "Registering systemd service socialhub-api ..."
cat > /etc/systemd/system/socialhub-api.service <<EOF
[Unit]
Description=SocialHub FastAPI Backend
After=network.target mongod.service
Requires=mongod.service

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}/backend
EnvironmentFile=${APP_DIR}/backend/.env
ExecStart=${APP_DIR}/backend/venv/bin/uvicorn server:app --host 127.0.0.1 --port 8001 --workers 2
Restart=always
RestartSec=5
StandardOutput=append:/var/log/socialhub-api.log
StandardError=append:/var/log/socialhub-api.log

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable socialhub-api
systemctl restart socialhub-api
sleep 3
systemctl is-active --quiet socialhub-api || { warn "Backend service failed, tail logs:"; tail -n 40 /var/log/socialhub-api.log; die "Backend service not running"; }

# -------------------------------------------------------------
# 8. Frontend production build
# -------------------------------------------------------------
log "Writing frontend/.env and building React app..."
cat > "$APP_DIR/frontend/.env" <<EOF
REACT_APP_BACKEND_URL=https://${DOMAIN}
WDS_SOCKET_PORT=443
EOF

cd "$APP_DIR/frontend"
yarn install --frozen-lockfile --network-timeout 600000
CI=false yarn build

# -------------------------------------------------------------
# 9. Nginx site
# -------------------------------------------------------------
log "Configuring Nginx for ${DOMAIN} ..."
cat > /etc/nginx/sites-available/${DOMAIN} <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    root ${APP_DIR}/frontend/build;
    index index.html;

    client_max_body_size 50M;

    # API → FastAPI backend
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

    # SPA fallback
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(?:js|css|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf)\$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }
}
EOF

ln -sf /etc/nginx/sites-available/${DOMAIN} /etc/nginx/sites-enabled/${DOMAIN}
nginx -t
systemctl reload nginx

# -------------------------------------------------------------
# 10. SSL via Let's Encrypt
# -------------------------------------------------------------
log "Requesting SSL certificate (Let's Encrypt) for ${DOMAIN} ..."
if ! certbot certificates 2>/dev/null | grep -q "${DOMAIN}"; then
  certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "${SSL_EMAIL}" --redirect
else
  log "SSL certificate already exists, skipping issuance."
fi
systemctl reload nginx

# -------------------------------------------------------------
# 11. Smoke tests
# -------------------------------------------------------------
log "Smoke testing..."
sleep 2
curl -fs "https://${DOMAIN}/api/health" >/dev/null && \
  echo -e "\n\033[1;32m✅  SocialHub deployed successfully at https://${DOMAIN}\033[0m\n" || \
  warn "Health check failed — check 'systemctl status socialhub-api' and 'tail /var/log/socialhub-api.log'"

cat <<EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉  Deployment complete!

  • Site:        https://${DOMAIN}
  • Admin login: ${ADMIN_EMAIL}
  • Password:    ${ADMIN_PASSWORD}

Useful commands:
  • Backend logs:  tail -f /var/log/socialhub-api.log
  • Restart API:   systemctl restart socialhub-api
  • Update app:    bash ${APP_DIR}/update.sh
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EOF
