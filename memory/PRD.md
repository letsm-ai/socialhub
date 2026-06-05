# SocialHub — Product Requirements Document

## Original Problem Statement
SaaS marketing website + billing dashboard for an omnichannel customer service platform called **SocialHub** (similar to respond.io). The messaging engine is a self-hosted Chatwoot instance on a Hostinger VPS. The platform requires:
- Landing page + JWT authentication
- Client dashboard + Super Admin dashboard
- Chatwoot integration (auto-provisioning + SSO)
- WhatsApp Embedded Signup (Meta Cloud API)
- Local payment gateways (Thawani Pay)
- AI Auto-reply
- Email notifications (Resend)

**User language**: Arabic (always respond in Arabic).

---

## Architecture
- **Frontend**: React 18 + Tailwind + shadcn/ui (Emergent preview + deployed to VPS via GitHub Actions)
- **Backend**: FastAPI + Motor (MongoDB) — runs on VPS as `socialhub-api.service` (systemd)
- **Chatwoot**: Docker stack at `/root/docker-compose.yaml` (rails + sidekiq + postgres + redis)
- **Reverse Proxy**: Traefik (replaces Nginx) — listens on host network ports :80/:443
- **Domains**:
  - `letsm.io` → Chatwoot (Rails app)
  - SocialHub frontend on Emergent preview (configured via `REACT_APP_BACKEND_URL`)

---

## Completed Features (as of Feb 2026)
- ✅ JWT auth + brute-force lockout (5 attempts → 15 min)
- ✅ Chatwoot auto-provisioning on user registration (account + agent user)
- ✅ Demo WhatsApp inbox + simulate-message feature
- ✅ WhatsApp Embedded Signup (Meta SDK) — currently mocked pending Meta App Review
- ✅ WhatsApp BYOK (Bring Your Own Key) — clients paste Meta tokens directly
- ✅ AI Auto-reply with Dual Provider (Emergent Universal Key OR client's OpenAI key)
- ✅ Auto-Handoff system (keyword + repeat + AI fallback triggers)
- ✅ Wallet system + Thawani Pay top-ups
- ✅ Subscription plans + upgrades
- ✅ Chatwoot SSO login for clients (locked to `agent` role + CSS injection to hide sidebar)
- ✅ Webhook fan-out: WhatsApp Meta → Chatwoot + back
- ✅ Resend email notifications
- ✅ Super Admin dashboard (clients, broadcasts, analytics)
- ✅ **Channel SSO Bridge (Telegram POC)** — popup window.open + 3s polling for inbox detection (NEW Feb 2026)

---

## Active P0 Task
**Hybrid SSO + Telegram POC** — DONE on Emergent. Awaiting "Save to GitHub" → VPS deployment → E2E test by user.

Implementation:
- `backend/chatwoot_sso.py` — generates Chatwoot SSO URLs with `redirect_to` to inbox-creation pages
- `server.py` — 3 endpoints: `/sso/supported`, `/sso/link`, `/sso/inboxes`
- `Channels.jsx` — Telegram card + `<ChannelSSOPollingOverlay>` modal
- Polls Chatwoot inboxes every 3s; closes popup & shows toast when new inbox detected

Env required on VPS: `CHATWOOT_PLATFORM_TOKEN` or `CHATWOOT_PLATFORM_API_KEY` + `CHATWOOT_URL` ✅ done

---

## Backlog
### P1
- Facebook Messenger + Instagram DMs via SSO modal (needs FB App credentials in Chatwoot)
- WhatsApp Broadcasts (CSV upload + Meta template messages)
- WhatsApp Embedded Signup (un-mock once Meta App Review approved)

### P2
- Active Conversations page (admin view: who's replying, last msg, manual override)

### P3
- Refactor `server.py` (now 2114 lines) into modular routers (`/routes/whatsapp.py`, `/routes/admin.py`, `/routes/channels.py`)

---

## Known Infrastructure Issues (NON-CODE)
- **VPS has multiple competing Docker stacks**: `/root/docker-compose.yaml` (canonical), `/root/chatwoot/` (broken Coolify leftover — disabled with `restart: "no"`), `/opt/letsm/` (production SocialHub backend in docker)
- **Auto-restart hazard**: If VPS reboots, `unless-stopped` containers from `/root/chatwoot/` may conflict. Workaround: keep `/root/docker-compose.yaml` running and the chatwoot/ folder's restart policy set to "no".
- **Platform App allowlist**: New Platform App in Chatwoot requires manual permissible-resources setup. User ran `PlatformAppPermissible.find_or_create_by(...)` in Rails console to grant access to all Users + Accounts.

---

## Test Credentials
See `/app/memory/test_credentials.md`.

---

## Last Updated
2026-02-06 — Hybrid SSO + Telegram POC built, awaiting deployment + E2E test.
