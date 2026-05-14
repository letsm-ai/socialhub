# SocialHub — Product Requirements Document (PRD)

> Updated automatically by the main agent. Living document.

## Original Problem Statement (user, verbatim)
> اريد اعمل نظام برفق لك الملف واعطني رأيك فالنظام وطريقة تنفيذه
>
> (User then provided "SocialHub: Marketing Website & Admin Dashboard Specification for Emergent AI" markdown file describing a SaaS platform on top of a self-hosted Chatwoot instance for the Omani/GCC SME market.)

## Vision
SocialHub is a customer-facing marketing site + billing/subscription layer + admin dashboard sitting on top of a self-hosted **Chatwoot** instance. It provides omnichannel customer service (WhatsApp, Instagram, Facebook, Email) + AI automation to SMEs, replicating the Freshworks / Respond.io business model — priced in **OMR** for the **Omani / Gulf SME market**.

## Architecture
- **Frontend**: React 19 + TypeScript-ready + TailwindCSS + shadcn/ui + react-router-dom v7 + react-hook-form + zod
- **Backend**: FastAPI + Motor (async MongoDB)
- **Database**: MongoDB (used in place of Prisma/PostgreSQL from spec — same business shape, faster to ship)
- **Auth**: Custom JWT (bcrypt + PyJWT) with httpOnly cookies + Bearer-token fallback
- **Payments**: Stripe (placeholder)
- **Messaging Engine**: Self-hosted Chatwoot on user's Hostinger VPS (placeholder integration)

## User Personas
1. **Client (SME owner / support team)** — uses `/dashboard` to manage subscription, buy message credits, open Chatwoot inbox.
2. **SaaS Owner (Super Admin)** — uses `/admin` to view MRR, manage clients, allocate credits.
3. **Marketing visitor** — visits `/`, evaluates pricing & features, signs up.

## Static Core Requirements
- Arabic RTL as **default** language; English LTR toggle.
- Premium emerald + alabaster + amber palette (no SaaS purple slop).
- Mobile / tablet / desktop responsive.
- Brand: "سوشال هَب" / "SocialHub".
- Currency: **OMR** (ر.ع).
- Locale: gulf-friendly tone, omani touch.

## Implemented (chronological)

### Phase 1 — Marketing Landing Page  *(2026-05-13)*
- Bilingual landing at `/` with: Navbar (glass), Hero (with live Chatwoot inbox mock), Stats bar, Features (Bento — 5 cards), How It Works (3 steps), Pricing (3 tiers + credits add-on), Testimonials, FAQ, CTA banner, Footer.
- AR/EN switcher with full RTL ↔ LTR.

### Phase 1.5 — Project Skeleton  *(2026-05-13)*
- Route-Groups folder layout, TypeScript config, Tajawal/Cairo/Alexandria fonts, Tailwind `rtl:` variant, 4 layout shells.

### Phase 2 — Auth & DB Models  *(2026-05-13)*
- MongoDB `users`, `subscriptions`, `wallets` collections (mirror of Prisma schema), JWT auth, bcrypt, brute-force lockout, admin seeding.
- `/login` + `/register` with react-hook-form + zod, ProtectedRoute, role-based redirect.
- Testing: 17/17 backend + 14/14 frontend passing.

### Phase 3 — Client Dashboard (Overview + Billing)  *(2026-05-13)*
- `/dashboard` — Overview with Open Inbox CTA + Plan/Status/Credits/Activity cards.
- `/dashboard/billing` — Current plan card + 3-tier upgrade grid + smooth scroll.
- Endpoints: `GET /api/me/account`, `GET /api/plans`, `POST /api/me/subscription/upgrade`.

### Phase 4 — Wallet & Credits  *(2026-05-13)*
- `/dashboard/wallet` — Solution Partner billing layer: Balance card, Estimated msgs (Balance / 0.025), 3 top-up packages (Basic/Pro/Enterprise), Recent transactions list.
- Endpoints: `GET /api/wallet/packages`, `GET /api/me/wallet`, `POST /api/me/wallet/topup`.
- **MOCKED**: top-up credits wallet instantly (no Stripe checkout yet).

### Phase 5 — Channels (WhatsApp Embedded Signup)  *(2026-05-14)*
- `/dashboard/channels` — WhatsApp connect hero card + Tech Provider/Solution Partner explainer + 5-field connected state (Phone, WABA ID, Display Name, Phone Number ID, Business ID).
- `src/lib/facebook.js` — FB SDK loader + `launchWhatsAppSignup` using `FB.login({config_id, feature: whatsapp_embedded_signup})`.
- Demo mode falls back to mock when `REACT_APP_FACEBOOK_APP_ID` + `REACT_APP_WA_CONFIG_ID` not set.
- Endpoints: `GET /api/me/channels`, `POST /api/me/channels/whatsapp`, `DELETE /api/me/channels/whatsapp`.

### Phase 6 — Super Admin Dashboard  *(2026-05-14)*
- `/admin` — Platform overview with 4 KPI cards (MRR, Active Subscribers, Total Promotional Sent, Total Wallet Balances) + tier-breakdown card.
- `/admin/clients` — shadcn `Table` data-table with sortable headers (name/email/balance/created_at), search box, plan + status filters, suspend/activate toggle, manual wallet credit/debit dialog with note.
- Endpoints: `GET /api/admin/overview`, `GET /api/admin/clients`, `POST /api/admin/clients/{id}/status`, `POST /api/admin/clients/{id}/wallet/credit`.

## Backlog (Prioritized)

### P0 — Next phase
- Client Dashboard: real overview (subscription card, credits balance card, "Open Inbox" button)
- Admin Dashboard: real overview (MRR, active subscribers, churn, clients table)

### P1
- Stripe integration: Checkout session for plan upgrade + webhooks (`/api/stripe/webhook` is stubbed)
- Chatwoot Super Admin integration: provision account on registration + SSO/link to inbox
- Promotional Message Credits: top-up flow + deduct hooks
- Email notifications (welcome, billing receipts)

### P2
- Forgot/reset password flow
- Server-side JWT revocation list (so logout invalidates Bearer immediately)
- Audit log for admin actions
- Multi-team / multi-user under same client account

## Routes
| Path | Layout | Auth | Status |
|---|---|---|---|
| `/` | Marketing | public | ✅ live |
| `/login` | Auth | public | ✅ live |
| `/register` | Auth | public | ✅ live |
| `/dashboard` | Dashboard | CLIENT | ✅ live (Overview) |
| `/dashboard/billing` | Dashboard | CLIENT | ✅ live |
| `/dashboard/wallet` | Dashboard | CLIENT | ✅ live |
| `/dashboard/channels` | Dashboard | CLIENT | ✅ live (WhatsApp) |
| `/admin` | Admin | ADMIN | ✅ live (Overview) |
| `/admin/clients` | Admin | ADMIN | ✅ live |

## Test Credentials
See `/app/memory/test_credentials.md`.

## Notes
- `REACT_APP_BACKEND_URL` in frontend `.env` and `FRONTEND_URL` in backend `.env` must match the active preview origin.
- In this Kubernetes preview, ingress rewrites CORS to `*`, so auth uses Bearer tokens in `localStorage` (cookies are also set as a defense-in-depth fallback).
