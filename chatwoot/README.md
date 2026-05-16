# Chatwoot — Self-Managed (replaces Coolify-managed app)

This directory contains the self-managed Chatwoot deployment that **replaces** the Coolify-managed Chatwoot application containers (rails + sidekiq), while **keeping the existing Postgres and Redis databases intact**.

## Why?
Coolify's Traefik routing is broken on this server (uses `web`/`websecure` entrypoint names while the actual Traefik instance uses `http`/`https`). Rather than fight with Coolify, we deploy our own Chatwoot containers with proper Traefik labels and let Coolify continue running only the data services (Postgres + Redis).

## Architecture after migration
```
Traefik (our own)
├── app.letsm.io → socialhub-web (nginx) → host:8001 (FastAPI)
└── letsm.io → chatwoot-rails (3000)
                    │
                    ├── (uses) postgres-mu7tqsptecddqgrmg5o4zxs1 (kept from Coolify, unchanged)
                    └── (uses) redis-mu7tqsptecddqgrmg5o4zxs1 (kept from Coolify, unchanged)
              chatwoot-sidekiq (background worker, uses same data services)
```

## Files
- `docker-compose.yml` — Defines `chatwoot-rails` and `chatwoot-sidekiq` services
- `.env.example` — Template; the deploy script auto-extracts real values from the running Coolify container
- `deploy-chatwoot.sh` — Migration script (idempotent, safe to re-run)

## How to deploy
On the VPS run:
```
bash <(curl -fsSL https://raw.githubusercontent.com/letsm-ai/socialhub/main/chatwoot/deploy-chatwoot.sh)
```

The script will:
1. Take a pg_dump backup of the live database to `/root/chatwoot/backups/`
2. Extract all needed env vars (SECRET_KEY_BASE, DB credentials, etc.) from the running Coolify container
3. Write `/root/chatwoot/.env` and `/root/chatwoot/docker-compose.yml`
4. Stop the OLD Coolify Chatwoot rails + sidekiq containers (keeps Postgres + Redis running)
5. Disable Coolify auto-management of those two containers (sets a label so Coolify ignores them)
6. Start NEW chatwoot-rails + chatwoot-sidekiq under our control
7. Add Traefik labels for `letsm.io` → SSL auto-issued

## Rolling back
If anything goes wrong, restore the old Chatwoot via Coolify UI: Project → Chatwoot → Restart.
The data is untouched; the old containers can be re-started any time.

## Updating
To deploy a new Chatwoot version: edit `docker-compose.yml` (change `chatwoot/chatwoot:latest` to a specific tag), push to GitHub, then on the server:
```
cd /root/chatwoot && git pull /var/www/socialhub main:main && docker compose pull && docker compose up -d
```
