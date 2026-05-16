# SocialHub — Product Requirements Document

## Original Problem Statement
SaaS marketing site + billing dashboard for omnichannel customer service platform (similar to respond.io). Messaging engine = self-hosted Chatwoot. Needs landing page, auth, client dashboard, super admin dashboard, integrations with Chatwoot (auto-provisioning + SSO), Stripe (billing/credits), WhatsApp.

User language: **Arabic** (must always respond in Arabic).

## Current Status — FULLY LIVE IN PRODUCTION ✅

| Service | URL | Status |
|---------|-----|--------|
| SocialHub app | https://app.letsm.io | ✅ Live with SSL |
| Chatwoot | https://letsm.io | ✅ Live with SSL (self-managed) |

## Infrastructure
- VPS: Hostinger 76.13.220.229 (Ubuntu 24.04)
- Traefik: self-managed (`/root/socialhub/docker-compose.yml`), entrypoints `http`/`https`, auto SSL via Let's Encrypt
- Postgres + Redis: Coolify-managed (we don't touch them)
- Chatwoot Rails + Sidekiq: self-managed (`/root/chatwoot/docker-compose.yml`)
- SocialHub backend: systemd service `socialhub-api` on host `0.0.0.0:8001`
- SocialHub frontend: nginx-alpine container `socialhub-web` on `coolify` Docker network

## Architecture
```
Traefik (entrypoints: http=80, https=443)
├── app.letsm.io → socialhub-web (nginx:alpine) → 127.0.0.1 host gateway → uvicorn (FastAPI :8001)
└── letsm.io → chatwoot-rails (chatwoot/chatwoot :3000)
                    │
                    ├── postgres-mu7tqsptecddqgrmg5o4zxs1 (Coolify-managed)
                    ├── redis-mu7tqsptecddqgrmg5o4zxs1 (Coolify-managed)
                    └── chatwoot-sidekiq (background worker)
```

## Completed Features
- ✅ RTL landing page (AR/EN toggle)
- ✅ Auth (register/login/JWT, brute force protection)
- ✅ Client dashboard with company_name pill (no Chatwoot UI exposed)
- ✅ Super admin dashboard
- ✅ Wallet & credits (mock Stripe top-up)
- ✅ Chatwoot Platform API integration (autoprovision + SSO)
- ✅ WhatsApp Meta Tech Provider backend endpoints (gated by env vars, ready to flip live)
- ✅ Self-managed Chatwoot deployment via GitHub (`/app/chatwoot/`)

## Production Credentials
| Role | Email | Password |
|------|-------|----------|
| SocialHub Admin | admin@letsm.io | Woot@Ch4321 |
| SocialHub Client (test) | ahmed@test.com | Test@1234 |
| Chatwoot Super Admin | (created via onboarding by user) | (set by user) |

## Chatwoot Integration
- `CHATWOOT_URL=https://letsm.io`
- `CHATWOOT_PLATFORM_API_KEY=EpeXJDoXcwmuyYCbCMzoGZoo`
- Connectivity verified: account creation returns 200 ✅
- Test accounts created during validation (ids 1, 2, 3) — can be deleted from Super Admin panel

## To Activate Real WhatsApp Integration
User obtains from Meta Business Manager:
```
META_APP_ID="..."
META_APP_SECRET="..."
META_SYSTEM_USER_TOKEN="..."          # long-lived
META_EMBEDDED_SIGNUP_CONFIG_ID="..."
META_TECH_PROVIDER_BUSINESS_ID="..."
WHATSAPP_WEBHOOK_VERIFY_TOKEN="..."
```
Add to `/app/backend/.env` and `/var/www/socialhub/backend/.env`. Restart backend. Frontend auto-detects.

Meta App setup needs:
- Webhook URL: `https://app.letsm.io/api/webhooks/whatsapp`
- OAuth Redirect URI: `https://app.letsm.io/api/meta/oauth/callback`
- Allowed Domain: `app.letsm.io`

## Backlog
### P1
- Activate real WhatsApp Meta credentials (backend ready, awaiting user)
- Real Stripe Checkout (still MOCKED)

### P2
- Public system status page
- Email notifications (SendGrid/Resend)
- Audit log for admin actions
- Refactor server.py (913 lines) into routers/ directory
- Delete the "Chatwoot" Coolify project entry (Coolify still tracks it in UI; rails+sidekiq containers are stopped)

## Key Files
| File | Purpose |
|------|---------|
| `/app/backend/server.py` | FastAPI routes |
| `/app/backend/whatsapp_meta.py` | Meta Cloud API client |
| `/app/backend/chatwoot_client.py` | Chatwoot Platform API client |
| `/app/backend/auth.py` | JWT + brute force |
| `/app/frontend/src/lib/facebook.js` | FB SDK loader (runtime config) |
| `/app/deploy.sh` | First-run VPS installer |
| `/app/deploy-traefik.sh` | Production SocialHub deploy via Traefik |
| `/app/chatwoot/docker-compose.yml` | Self-managed Chatwoot stack |
| `/app/chatwoot/deploy-chatwoot.sh` | Chatwoot migration/deploy script |

## Key Commands
```bash
# Update SocialHub on VPS
cd /var/www/socialhub && git pull && cd frontend && CI=false yarn build && docker restart socialhub-web

# Update Chatwoot
cd /root/chatwoot && docker compose pull && docker compose up -d

# Restart backend
systemctl restart socialhub-api

# Logs
tail -f /var/log/socialhub-api.log
docker logs -f socialhub-web
docker logs -f chatwoot-rails
```

## Changelog
- **2026-05-13/15**: Initial build (auth, landing, dashboards, Chatwoot integration, wallet, channels mock)
- **2026-05-16 (early)**: Production deployment to app.letsm.io via Traefik (Coolify-coexistence). Removed Made-with-Emergent badge. Deleted broken GitHub Actions.
- **2026-05-16 (mid)**: Hid Chatwoot from client UI, added company_name pill, full WhatsApp Tech Provider backend (env-gated)
- **2026-05-16 (late)**: Migrated Chatwoot off Coolify routing. Self-managed via `/root/chatwoot/`. Fixed Traefik entrypoint name mismatch (web/websecure → http/https). New Platform API key issued and validated end-to-end.
