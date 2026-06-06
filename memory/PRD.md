# SocialHub PRD — Updated Feb 2026

## Original Problem
SaaS messaging platform "SocialHub" — landing + billing dashboard for a multi-tenant Chatwoot-powered messaging platform. Arabic-first.

## Current Architecture
- **Frontend**: React 18 + Tailwind + shadcn/ui
- **Backend**: FastAPI + Motor (MongoDB) — `socialhub-api.service` (systemd) on VPS / Emergent Deploy
- **Chatwoot**: Self-hosted on VPS Docker (`/root/docker-compose.yaml`)
- **Reverse Proxy**: Traefik (host network) — Chatwoot on `letsm.io`, SocialHub on `app.letsm.io`
- **Deployment**: Production on Emergent Deploy + VPS

## Completed (cumulative)
- JWT auth + brute-force lockout
- Chatwoot auto-provisioning per client (self-healing for stale IDs)
- AI Auto-reply (Dual Provider: Emergent Universal Key OR client OpenAI)
- Auto-Handoff (keyword + repeat + AI fallback)
- WhatsApp BYOK (Phone Number ID + WABA + Access Token)
- **Telegram BYOK** (native form, no popup)
- **Facebook Messenger BYOK** (Page ID + Page Access Token) — Feb 2026
- **Instagram BYOK** (IG Business Account ID + Page Access Token) — Feb 2026
- Wallet + Thawani Pay
- Subscription plans
- Webhook fan-out: WhatsApp Meta → Chatwoot
- Resend email notifications
- Super Admin dashboard
- **Chatwoot Rebrand**: Logo + Brand Name + Title + Favicon all = SocialHub
- **One-click Rebrand endpoint** `POST /api/admin/chatwoot/rebrand`
- Custom SocialHub logo + favicon SVG (served from frontend public/)

## Backlog
### P1 (next sprint)
- **WhatsApp Broadcasts** — Frontend UI (backend `broadcasts.py` already exists)
- **Active Conversations admin page** — see who's replying (bot/human), last msg, override
- **Testing Agent v3** run — full end-to-end test of all flows
- **Pricing/Billing UX** improvements

### P2
- Refactor `server.py` (now 2400+ lines) → modular routers

### P3
- Multi-language email templates
- White-label per tenant (subdomain branding)

## Known Constraints
- Chatwoot stays on VPS (can't host on Emergent)
- VPS deployment via GitHub Actions had SSH timeout — manual `git pull` works
- Browser favicon cache persistent for existing users (auto-refreshes for new visitors)

## Key Environment Variables
**SocialHub backend** (`/var/www/socialhub/backend/.env` on VPS, also Emergent Secrets):
```
MONGO_URL, DB_NAME
JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD
CHATWOOT_URL=https://letsm.io
CHATWOOT_PLATFORM_TOKEN=7ZPmeu...
EMERGENT_LLM_KEY
META_WEBHOOK_VERIFY_TOKEN
RESEND_API_KEY
THAWANI_API_KEY
CHATWOOT_SUPER_ADMIN_EMAIL=admin@letsm.io (for rebrand endpoint)
CHATWOOT_SUPER_ADMIN_PASSWORD=SuperAdmin@2026!
PUBLIC_APP_URL=https://app.letsm.io
```

**Chatwoot** (`/root/.env` on VPS):
```
INSTALLATION_NAME=SocialHub
BRAND_NAME=SocialHub
LOGO=https://app.letsm.io/socialhub-logo.svg
LOGO_THUMBNAIL=https://app.letsm.io/socialhub-logo-thumbnail.svg
BRAND_URL=https://app.letsm.io
DEFAULT_LOCALE=ar
```

## Key Files
- `backend/server.py` — main FastAPI app (2400+ lines, needs refactoring)
- `backend/chatwoot_client.py` — Chatwoot REST helpers (create_telegram/facebook/instagram_inbox)
- `backend/chatwoot_sso.py` — SSO link generation + brute-force user lookup self-heal
- `backend/whatsapp_byok.py` — WhatsApp BYOK with detailed Meta error mapping
- `backend/ai_agent.py` — Dual-provider AI + handoff logic
- `backend/broadcasts.py` — Broadcast worker (UI pending)
- `frontend/src/pages/(dashboard)/Channels.jsx` — channel connection UI (TG/FB/IG/WA cards)
- `frontend/public/socialhub-logo.svg` — used by Chatwoot too
- `frontend/public/favicon.svg`

## Test Credentials
See `/app/memory/test_credentials.md`.

## Last Updated
2026-02-06 — Facebook + Instagram BYOK added. Branding complete.
