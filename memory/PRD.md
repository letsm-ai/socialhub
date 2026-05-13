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
- Logo (`سوشال هَب` + emerald glyph).
- Stack: React + Tailwind + shadcn (Button, Accordion).

### Phase 1.5 — Project Skeleton  *(2026-05-13)*
- Folder layout in **Route Groups** style: `pages/(marketing)`, `pages/(auth)`, `pages/(dashboard)`, `pages/(admin)`.
- TypeScript config (`tsconfig.json`).
- Tajawal + Cairo + Alexandria fonts.
- Tailwind `rtl:` & `ltr:` variants enabled via plugin.
- Four layout shells: `MarketingLayout`, `AuthLayout`, `DashboardLayout`, `AdminLayout`.
- Stub pages with "coming soon" placeholders to keep routing intact.

### Phase 2 — Auth & DB Models  *(2026-05-13)*
- **MongoDB collections** (mirror of requested Prisma models):
  - `users`: id, name, email, password_hash, role (CLIENT/ADMIN), chatwoot_account_id, stripe_customer_id, company_name?, created_at
  - `subscriptions`: id, user_id, plan_tier (GROWTH/PRO/ENTERPRISE), status (TRIALING/ACTIVE/PAST_DUE/CANCELED), stripe_subscription_id, current_period_start, current_period_end
  - `wallets`: id, user_id, balance_omr, promotional_credits, total_promotional_messages_sent
  - Indexes: `users.email` (unique), `users.id` (unique), `subscriptions.user_id`, `wallets.user_id` (unique), `login_attempts.identifier`
- **Auth endpoints** under `/api/auth`: register, login, logout, me, refresh
- **Security**: bcrypt password hashing, JWT (access 15min + refresh 7d), brute-force lockout (5 attempts/15min), CORS bound to FRONTEND_URL
- **Admin seeding** from `.env` on startup (`admin@socialhub.om` / `Admin@2026`).
- **Frontend Auth**:
  - `AuthContext` + axios instance with Bearer interceptor
  - `ProtectedRoute` with role guard
  - `/login` page (react-hook-form + zod) — `data-testid="login-*"`
  - `/register` page with full validation incl. password strength checklist
  - Role-based redirect: ADMIN → `/admin`, CLIENT → `/dashboard`
  - Wired logout buttons in both dashboards
- **Testing**: 17/17 pytest + 14/14 Playwright passing (see `/app/test_reports/iteration_1.json`).

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
| `/dashboard` | Dashboard | CLIENT | ✅ shell only |
| `/admin` | Admin | ADMIN | ✅ shell only |

## Test Credentials
See `/app/memory/test_credentials.md`.

## Notes
- `REACT_APP_BACKEND_URL` in frontend `.env` and `FRONTEND_URL` in backend `.env` must match the active preview origin.
- In this Kubernetes preview, ingress rewrites CORS to `*`, so auth uses Bearer tokens in `localStorage` (cookies are also set as a defense-in-depth fallback).
