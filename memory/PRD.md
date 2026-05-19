# SocialHub — Product Requirements Document

## Original Problem Statement
SaaS marketing site + billing dashboard for omnichannel customer service platform (similar to respond.io). Messaging engine = self-hosted Chatwoot. Needs landing, auth, client dashboard, super admin dashboard, integrations with Chatwoot (auto-provisioning + SSO), payment gateway, and WhatsApp.

User language: **Arabic** (must always respond in Arabic).

## Current Status — FULLY LIVE IN PRODUCTION ✅

| Service | URL | Status |
|---------|-----|--------|
| SocialHub app | https://app.letsm.io | ✅ Live with SSL |
| Chatwoot | https://letsm.io | ✅ Live with SSL (self-managed, branded) |

## Infrastructure
- VPS: Hostinger 76.13.220.229 (Ubuntu 24.04)
- Traefik: self-managed, entrypoints `http`/`https`, auto SSL via Let's Encrypt
- Postgres + Redis: Coolify-managed (we don't touch them)
- Chatwoot Rails + Sidekiq: self-managed (`/root/chatwoot/`), GitHub-deployed
- SocialHub backend: systemd `socialhub-api` on host `0.0.0.0:8001`
- SocialHub frontend: nginx-alpine container `socialhub-web` on `coolify` Docker network

## Completed Features
- ✅ RTL landing (AR/EN), Auth (JWT+brute force), Wallet system
- ✅ Client dashboard with company_name pill (no Chatwoot UI exposed)
- ✅ Super admin dashboard (custom SocialHub branding)
- ✅ Chatwoot integration: autoprovision + SSO + per-user access_token
- ✅ **Demo WhatsApp flow**: instant connect with `+968 9999 8888`, seeds 3 Arabic conversations
- ✅ **Simulate new message**: manual button + auto-mode (sends every 45s for 5 min)
- ✅ **Chatwoot custom branding**: favicons, CSS, env vars, idempotent script
- ✅ **WhatsApp Meta Tech Provider backend** (gated by env, ready to flip live)
- ✅ **Thawani Pay backend** (gated by env, ready to flip live)

## Integrations (gating by env)
| Service | File | Status | How to activate |
|---------|------|--------|-----------------|
| Chatwoot | `chatwoot_client.py` | ✅ ACTIVE | (configured, working) |
| Meta WhatsApp | `whatsapp_meta.py` | ⚪ MOCK | Add 6 META_* env vars |
| Thawani Pay | `thawani.py` | ⚪ MOCK | Add THAWANI_SECRET_KEY + PUBLISHABLE_KEY |

## Production Credentials
| Role | Email | Password |
|------|-------|----------|
| SocialHub Admin | admin@letsm.io | Woot@Ch4321 |
| SocialHub Test Client | ahmed@test.com | Test@1234 (`company_name='متجر أحمد'`) |
| Chatwoot Super Admin | (set by user during onboarding) | (set by user) |

## Activate Thawani (when ready)
```env
THAWANI_SECRET_KEY="..."         # from Thawani merchant portal
THAWANI_PUBLISHABLE_KEY="..."
THAWANI_WEBHOOK_SECRET="..."     # set by you in portal
THAWANI_ENV="uat"                # or "production"
```
Webhook URL to register in Thawani portal: `https://app.letsm.io/api/webhooks/thawani`

## Activate Meta WhatsApp (when ready)
```env
META_APP_ID="..."
META_APP_SECRET="..."
META_SYSTEM_USER_TOKEN="..."
META_EMBEDDED_SIGNUP_CONFIG_ID="..."
META_TECH_PROVIDER_BUSINESS_ID="..."
WHATSAPP_WEBHOOK_VERIFY_TOKEN="..."
```
Meta App setup needs:
- Webhook URL: `https://app.letsm.io/api/webhooks/whatsapp`
- OAuth Redirect URI: `https://app.letsm.io/api/meta/oauth/callback`

## Key Files
| File | Purpose |
|------|---------|
| `/app/backend/server.py` | FastAPI routes (~1100 lines — needs refactor to routers/) |
| `/app/backend/whatsapp_meta.py` | Meta Cloud API client |
| `/app/backend/thawani.py` | Thawani checkout sessions + webhook signature |
| `/app/backend/chatwoot_client.py` | Chatwoot Platform + Application API + demo seeding |
| `/app/backend/auth.py` | JWT + brute force |
| `/app/backend/tests/test_phase6_thawani.py` | Phase 6 regression tests |
| `/app/frontend/src/lib/facebook.js` | FB SDK (runtime config) |
| `/app/frontend/src/pages/(dashboard)/Channels.jsx` | Demo connect + simulate + auto-mode |
| `/app/frontend/src/pages/(dashboard)/Wallet.jsx` | Topup with Thawani redirect support |
| `/app/deploy-traefik.sh` | SocialHub production deploy |
| `/app/chatwoot/deploy-chatwoot.sh` | Chatwoot production deploy |
| `/app/chatwoot/apply-branding.sh` | Re-apply branding after upgrades |

## Backlog
### P1
- 🔑 Obtain & install Thawani Pay credentials (test keys available immediately)
- 🔑 Obtain & install Meta WhatsApp Tech Provider credentials
- 🧹 Optional: delete obsolete Coolify "Chatwoot" service entry

### P2
- Refactor `server.py` (~1100 lines) into `/app/backend/routers/`: auth, account, wallet, channels, admin, whatsapp, thawani
- Extract `TOPUP_PACKAGES`, `PLAN_CATALOG`, etc. into `config/billing.py`
- Public system status page
- Email notifications (SendGrid/Resend)
- Audit log for admin actions

## Key Commands
```bash
# Update SocialHub on VPS
cd /var/www/socialhub && git pull && systemctl restart socialhub-api && \
  cd frontend && CI=false yarn build && docker restart socialhub-web

# Update Chatwoot
cd /root/chatwoot && docker compose pull && docker compose up -d
bash <(curl -fsSL https://raw.githubusercontent.com/letsm-ai/socialhub/main/chatwoot/apply-branding.sh)

# Logs
tail -f /var/log/socialhub-api.log
docker logs -f socialhub-web
docker logs -f chatwoot-rails
```

## Changelog
- **2026-05-18/19**: WhatsApp ↔ Chatwoot routing live. New module `whatsapp_routing.py` parses Meta webhooks → finds/creates Chatwoot contact + conversation → posts incoming message. `POST /api/webhooks/chatwoot` handles agent outgoing replies → sends via Meta. Admin setup: `POST /api/admin/whatsapp/setup-routing` (one-time creates API inbox), `GET /api/admin/whatsapp/route` (status). New env vars in `whatsapp_meta.get_config()`: `phone_number_id`, `waba_id`, `display_phone_number`. Chatwoot moved to `inbox.letsm.io` with full SocialHub/letsmAI branding (SVG logo, DB-level installation_configs updated, Rails layout injected with brand-rewrite.js).
- **2026-05-17 evening (later)**: Trial banner UI added to `Dashboard.jsx` (shows days remaining + welcome gift messages, only when `trial.active`). GitHub Actions auto-deploy workflow `.github/workflows/deploy.yml` created (SSH → git pull → pip install → restart systemd → yarn build → docker restart). `DEPLOY.md` documents the one-time secrets setup.
- **2026-05-13/15**: Initial build (auth, landing, dashboards, Chatwoot, wallet, channels mock)
- **2026-05-16 early**: Production deploy to app.letsm.io via Traefik (Coolify-coexistence). Removed Made-with-Emergent badge. Deleted broken GitHub Actions.
- **2026-05-16 mid**: Hid Chatwoot from client UI, added company_name pill, WhatsApp Tech Provider backend (env-gated)
- **2026-05-16 late**: Migrated Chatwoot off Coolify routing. Self-managed via `/root/chatwoot/`. Fixed Traefik entrypoint name mismatch. New Platform API key issued.
- **2026-05-17 morning**: Chatwoot custom branding (favicons + CSS + INSTALLATION_NAME). Re-added "Open Inbox" button on dashboard. Auto-trigger Chatwoot account creation per signup. Demo number `+968 9999 8888` with branded Arabic copy.
- **2026-05-17 afternoon**: Auto-seed 3 Chatwoot demo conversations (Fatima, Salim, Maryam) on demo connect. New `/api/me/channels/whatsapp/demo/simulate` endpoint with 8 Arabic personas. UI "Send test message" + "Auto-send 5 min" buttons.
- **2026-05-17 evening**: Thawani Pay integration (`thawani.py`): create_checkout_session, webhook signature verification (HMAC-SHA256 of body+timestamp), topup gated by env. New `/api/payments/config`, `/api/webhooks/thawani`. Wallet.jsx handles `payment_url` redirect + `?topup=success/cancelled` URL params. All Phase 6 tests pass.
