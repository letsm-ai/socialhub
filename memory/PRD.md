# SocialHub — Product Requirements Document

## Original Problem Statement
Build a SaaS marketing website and billing dashboard for an omnichannel customer service platform called "SocialHub" (similar to respond.io). The actual messaging engine is a self-hosted Chatwoot instance. Required: landing page, auth, client dashboard, super admin dashboard, integrations with Chatwoot (auto-provisioning + SSO), Stripe (billing/credits), and WhatsApp.

User language: **Arabic** (must always respond in Arabic).

## Current Status — LIVE IN PRODUCTION ✅
Deployed at: **https://app.letsm.io**
- Production VPS: Hostinger 76.13.220.229 (managed alongside Chatwoot via Coolify/Traefik)
- Frontend: nginx-alpine Docker container on `coolify` network
- Backend: FastAPI systemd service `socialhub-api` on host (`0.0.0.0:8001`)
- SSL: Auto-managed by Traefik via Let's Encrypt

## Architecture
- **Frontend**: React 18, Tailwind, shadcn/ui, RTL/LTR
- **Backend**: FastAPI + MongoDB (Motor), JWT auth + brute-force protection
- **Integrations**:
  - Chatwoot Platform API (auto-provisioning + SSO) — currently broken upstream
  - Meta WhatsApp Cloud API as Tech Provider — backend READY, awaiting credentials
  - Stripe — MOCKED

## Completed Features
- ✅ RTL landing page (AR/EN)
- ✅ Auth (register/login/JWT, brute force)
- ✅ Client dashboard with company_name pill (Chatwoot UI fully removed Feb 2026)
- ✅ Super admin dashboard
- ✅ Wallet & credits (mock top-up)
- ✅ Chatwoot Platform API integration (backend logic intact, UI hidden from clients)
- ✅ **WhatsApp Meta Tech Provider backend endpoints** (gated by env vars, ready to flip live):
  - `GET /api/whatsapp/config` — exposes app_id + config_id + enabled flag
  - `POST /api/whatsapp/connect` — full provisioning pipeline (code → token → subscribe WABA → register phone)
  - `GET /api/webhooks/whatsapp` — Meta verify handshake (PlainTextResponse)
  - `POST /api/webhooks/whatsapp` — X-Hub-Signature-256 HMAC-SHA256 verify
  - `whatsapp_meta.py` module: exchange_code_for_token, subscribe_waba, register_phone_number, send_text_message, get_phone_number_details, provision_whatsapp

## Production Credentials
| Role | Email | Password |
|------|-------|----------|
| Admin | admin@socialhub.om | Admin@2026 |
| Client (test) | ahmed@test.com | Test@1234 |

## To Activate Real WhatsApp Integration
User must obtain from Meta Business Manager and add to `/app/backend/.env`:
```
META_APP_ID="..."
META_APP_SECRET="..."
META_SYSTEM_USER_TOKEN="..."      # long-lived, with whatsapp_business_management + messaging
META_EMBEDDED_SIGNUP_CONFIG_ID="..."
META_TECH_PROVIDER_BUSINESS_ID="..."
WHATSAPP_WEBHOOK_VERIFY_TOKEN="..."  # any random string, must match Meta app config
```
Once set, frontend auto-detects via `GET /api/whatsapp/config` and switches from mock to real flow.

## Meta App Setup Requirements
- Verified Meta Business
- Meta App with WhatsApp product
- Tech Provider (Solution Partner) mode approved
- Embedded Signup configuration (Tech Provider mode)
- Webhook URL set in Meta App: `https://app.letsm.io/api/webhooks/whatsapp`
- OAuth Redirect URI: `https://app.letsm.io/api/meta/oauth/callback`
- Domain whitelist: `app.letsm.io`

## Backlog
### P1
- Activate real WhatsApp Meta credentials (backend ready, awaiting user)
- Real Stripe Checkout (currently MOCKED)
- Fix Chatwoot upstream URL — `https://letsm.io` returns 404 for `/platform/api/v1/accounts`
  (Chatwoot containers running but Coolify/Traefik routing seems broken; not blocking since UI is hidden from clients)

### P2
- Public system status page
- Email notifications (SendGrid/Resend)
- Audit log for admin actions
- Refactor server.py (913 lines) into routers/ directory

## Key Files
| File | Purpose |
|------|---------|
| `/app/backend/server.py` | FastAPI routes (auth, account, wallet, channels, admin, whatsapp, webhooks) |
| `/app/backend/whatsapp_meta.py` | Meta Cloud API client + signature verify |
| `/app/backend/chatwoot_client.py` | Chatwoot Platform API client |
| `/app/backend/auth.py` | JWT + brute force |
| `/app/frontend/src/lib/facebook.js` | FB SDK loader (reads runtime config) |
| `/app/frontend/src/pages/(dashboard)/Channels.jsx` | WhatsApp connect UI |
| `/app/frontend/src/layouts/DashboardLayout.jsx` | Client side-nav + company_name pill |
| `/app/deploy.sh` | First-run VPS installer |
| `/app/deploy-traefik.sh` | Production deploy via Traefik |

## Key Commands
```bash
# Update app on VPS after git push
cd /var/www/socialhub && git pull && cd frontend && CI=false yarn build && docker restart socialhub-web

# Restart backend
systemctl restart socialhub-api

# Logs
tail -f /var/log/socialhub-api.log
docker logs -f socialhub-web
```

## Changelog
- **2026-05-13/15**: Initial build (auth, landing, dashboards, Chatwoot integration, wallet, channels mock)
- **2026-05-16**: Production deployment to app.letsm.io via Traefik. Removed Made-with-Emergent badge. Deleted broken GitHub Actions workflow.
- **2026-05-16**: Hid all Chatwoot references from client dashboard. Added company_name pill in header + below greeting. Built complete WhatsApp Meta Tech Provider backend (gated by env vars). Frontend dynamically loads Meta config from `/api/whatsapp/config`.
