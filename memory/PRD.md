# SocialHub — Product Requirements Document

## Original Problem Statement
Build a SaaS marketing website and billing dashboard for an omnichannel customer service platform called "SocialHub" (similar to respond.io). The actual messaging engine is a self-hosted Chatwoot instance on a Hostinger VPS. The platform requires a landing page, authentication, a client dashboard, a super admin dashboard, and integrations with Chatwoot (for auto-provisioning and SSO), Stripe (for billing/credits), and WhatsApp.

User language: **Arabic** (must always respond in Arabic).

## Current Status — LIVE IN PRODUCTION ✅
Deployed at: **https://app.letsm.io**
- Production server: Hostinger VPS (76.13.220.229)
- Coexists with Chatwoot (managed by Coolify) without conflicts
- Traefik (managed by Coolify) handles SSL via Let's Encrypt automatically
- FastAPI backend on host (systemd: socialhub-api), nginx-alpine container (`socialhub-web`) on `coolify` Docker network

## Architecture
- **Frontend**: React 18, Tailwind, shadcn/ui, RTL/LTR toggle, served by nginx:alpine container
- **Backend**: FastAPI + MongoDB (Motor), runs as systemd service `socialhub-api` on `0.0.0.0:8001`
- **Proxy**: Container nginx forwards `/api/*` to `172.16.2.1:8001` (coolify gateway)
- **SSL**: Traefik auto-issues + renews via Let's Encrypt
- **Firewall**: UFW allows 22/80/443 + Docker subnets to 8001

## Completed Features
- RTL landing page (AR/EN toggle)
- Auth (register/login/JWT, brute force protection)
- Client dashboard (respond.io-style mini-sidebar)
- Super admin dashboard (KPIs, client mgmt, wallet adjustments)
- Wallet & credits system (mocked top-up)
- Chatwoot Platform API integration (auto-provisioning + SSO link generation)

## Deployment Artifacts
- `/app/deploy.sh` — First-run installer (MongoDB 8, Node, build, systemd, nginx)
- `/app/deploy-traefik.sh` — Final production deploy (Traefik integration via Docker labels)
- `/app/fix-ssl.sh` — Legacy SSL fix (superseded by Traefik approach)

## Production Credentials
| Role | Email | Password |
|------|-------|----------|
| Admin | admin@letsm.io | Woot@Ch4321 |
| Client (test) | ahmed@test.com | Ahmed@123 |

## Backlog
### P1
- Real Stripe Checkout for subscription + wallet top-ups (currently MOCKED)
- Real WhatsApp Embedded Signup via Meta Tech Provider (currently MOCKED UI)

### P2
- System status page (public health/metrics page)
- Email notifications (SendGrid/Resend)
- Audit log for admin actions

## Key Commands
```bash
# Update app after git push
cd /var/www/socialhub && git pull && cd frontend && CI=false yarn build && docker restart socialhub-web

# Restart backend
systemctl restart socialhub-api

# Logs
tail -f /var/log/socialhub-api.log
docker logs -f socialhub-web
```
