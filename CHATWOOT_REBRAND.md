# Chatwoot Rebrand to "SocialHub"

This guide turns the white-labeled Chatwoot instance into a pure "SocialHub"
experience for the end client. After applying these env vars and asset
overrides, the Chatwoot name disappears from:
- Browser tab title
- Page favicon
- Login screen logo
- Top-left header logo
- Footer "Powered by Chatwoot" link
- Email templates' branding

---

## 1. Update `/root/.env` on VPS

Add (or replace) these branding variables. **Run after deploying SocialHub
frontend** so the logo URLs resolve.

```env
# === Brand identity ===
INSTALLATION_NAME=SocialHub
BRAND_NAME=SocialHub

# === Assets — served by SocialHub frontend ===
LOGO=https://app.letsm.io/socialhub-logo.svg
LOGO_THUMBNAIL=https://app.letsm.io/socialhub-logo-thumbnail.svg
LOGO_DARK=https://app.letsm.io/socialhub-logo.svg

# === Outbound links (when client clicks the logo or visits help) ===
BRAND_URL=https://app.letsm.io
WIDGET_BRAND_URL=https://app.letsm.io
TERMS_URL=https://app.letsm.io/terms
PRIVACY_URL=https://app.letsm.io/privacy

# === Default locale (so the client lands on Arabic UI) ===
DEFAULT_LOCALE=ar

# === Hide "Powered by Chatwoot" footer in the help-center widget ===
DISABLE_TELEMETRY=true
```

## 2. Restart Chatwoot to pick up env changes

```bash
cd /root
docker compose up -d --force-recreate rails sidekiq
# wait ~60 seconds for rails to fully boot
sleep 60
docker exec root-rails-1 printenv | grep -E "INSTALLATION_NAME|BRAND|LOGO" | sort
```

You should see all the new variables echoed back.

## 3. Verify in browser

Open `https://letsm.io/app/login` in a private window:

- ✅ Browser tab shows "SocialHub" (no "Chatwoot")
- ✅ Tab favicon is the SocialHub icon
- ✅ Login page logo is the SocialHub wordmark
- ✅ Footer says "SocialHub" (no Chatwoot link)

If anything still shows "Chatwoot":

1. **Force-refresh the page** (Cmd/Ctrl + Shift + R) to bust cache
2. Check that `https://app.letsm.io/socialhub-logo.svg` returns a valid SVG
   (the deployed SocialHub frontend must be reachable from the public internet)
3. Some hardcoded text strings inside Chatwoot's Vue bundle can't be changed
   via env vars — these are addressed in Phase 2 (HTML rewriting via Traefik).

## 4. (Optional) Phase 2 — strip remaining "Chatwoot" text via Traefik

If you want to remove every last occurrence of the word "Chatwoot" from the
HTML responses, add a Traefik middleware that rewrites the response body:

```yaml
# /docker/traefik/dynamic/sub-filter.yml
http:
  middlewares:
    rewrite-chatwoot:
      plugin:
        rewriteBody:
          rewrites:
            - regex: "Chatwoot"
              replacement: "SocialHub"
```

Then attach the middleware to the chatwoot router in `/root/docker-compose.yaml`:

```yaml
- "traefik.http.routers.letsm-chatwoot-secure.middlewares=rewrite-chatwoot@file"
```

Requires the `rewrite-body` Traefik plugin to be installed — see
https://plugins.traefik.io/plugins/628c9eb5108ecc83915d775b/rewrite-body

---

## Files this guide references

- `/app/frontend/public/socialhub-logo.svg` — wordmark logo (login screen, header)
- `/app/frontend/public/socialhub-logo-thumbnail.svg` — square thumbnail (apple-touch)
- `/app/frontend/public/favicon.svg` — browser tab favicon
- `/app/frontend/public/index.html` — wired up to use the new favicon
