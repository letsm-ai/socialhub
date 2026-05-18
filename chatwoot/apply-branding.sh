#!/usr/bin/env bash
# Chatwoot custom branding (no EE license needed).
# Replaces Chatwoot's default favicon and logo files inside the running container,
# updates browser tab title, and injects custom CSS to hide the inbox sidebar logo
# and "Powered by Chatwoot" mentions.
#
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/letsm-ai/socialhub/main/chatwoot/apply-branding.sh)
set -euo pipefail

DEPLOY_DIR="/root/chatwoot"
ASSETS_BASE="https://raw.githubusercontent.com/letsm-ai/socialhub/main/chatwoot/branding"
RAILS_CONTAINER="chatwoot-rails"

log()  { echo -e "\033[1;32m==>\033[0m $*"; }
die()  { echo -e "\033[1;31m==> ERROR:\033[0m $*" >&2; exit 1; }

[ "$EUID" -eq 0 ] || die "Run as root"
docker ps --format '{{.Names}}' | grep -q "^${RAILS_CONTAINER}$" || die "Container ${RAILS_CONTAINER} not running"

# --------------------------------------------------------------------------
# 1. Download fresh assets to the host
# --------------------------------------------------------------------------
log "Step 1: Downloading branding assets from GitHub..."
ASSET_DIR="${DEPLOY_DIR}/branding"
mkdir -p "$ASSET_DIR"
for f in favicon.ico favicon-16.png favicon-32.png favicon-64.png apple-touch-icon.png logo-128.png logo-256.png logo-512.png; do
  curl -fsSL "${ASSETS_BASE}/${f}" -o "${ASSET_DIR}/${f}"
done
log "Downloaded $(ls "$ASSET_DIR" | wc -l) files."

# --------------------------------------------------------------------------
# 2. Replace favicon and PWA icons in the running container
# --------------------------------------------------------------------------
log "Step 2: Replacing favicon and logo files inside chatwoot-rails..."
# Chatwoot stores public assets at /app/public/ (favicon, apple-touch-icon)
# and brand assets at /app/public/brand-assets/
docker cp "${ASSET_DIR}/favicon.ico"          "${RAILS_CONTAINER}:/app/public/favicon.ico"
docker cp "${ASSET_DIR}/favicon-32.png"       "${RAILS_CONTAINER}:/app/public/favicon-32x32.png"
docker cp "${ASSET_DIR}/favicon-16.png"       "${RAILS_CONTAINER}:/app/public/favicon-16x16.png"
docker cp "${ASSET_DIR}/apple-touch-icon.png" "${RAILS_CONTAINER}:/app/public/apple-touch-icon.png"
docker cp "${ASSET_DIR}/logo-512.png"         "${RAILS_CONTAINER}:/app/public/android-chrome-512x512.png"
docker cp "${ASSET_DIR}/logo-256.png"         "${RAILS_CONTAINER}:/app/public/android-chrome-256x256.png" 2>/dev/null || true
docker cp "${ASSET_DIR}/logo-128.png"         "${RAILS_CONTAINER}:/app/public/android-chrome-192x192.png"

# Also overwrite brand assets that the app references at runtime
for path in /app/public/brand-assets/logo.svg /app/public/brand-assets/logo_dark.svg /app/public/brand-assets/logo_thumbnail.svg; do
  docker exec "$RAILS_CONTAINER" mkdir -p "$(dirname $path)" 2>/dev/null || true
done
docker cp "${ASSET_DIR}/logo-512.png" "${RAILS_CONTAINER}:/app/public/brand-assets/logo.png"
docker cp "${ASSET_DIR}/logo-512.png" "${RAILS_CONTAINER}:/app/public/brand-assets/logo_thumbnail.png"
docker cp "${ASSET_DIR}/logo-512.png" "${RAILS_CONTAINER}:/app/public/brand-assets/logo_dark.png"

log "Favicons + brand assets replaced ✅"

# --------------------------------------------------------------------------
# 3. Patch the page title and meta in index.html
# --------------------------------------------------------------------------
log "Step 3: Patching browser tab title to 'SocialHub'..."
docker exec "$RAILS_CONTAINER" sh -c '
  if [ -f /app/public/index.html ]; then
    sed -i "s|<title>[^<]*</title>|<title>SocialHub</title>|g" /app/public/index.html || true
  fi
' || true

# --------------------------------------------------------------------------
# 4. Inject custom CSS to hide Chatwoot brand text in the inbox sidebar
# --------------------------------------------------------------------------
log "Step 4: Injecting custom CSS..."
CSS_FILE="${DEPLOY_DIR}/branding/custom.css"
cat > "$CSS_FILE" <<'CSS_EOF'
/* SocialHub custom branding — hides residual Chatwoot brand references */

/* Hide "Powered by Chatwoot" footer in widget */
.cw-powered-by,
.cw-branding,
a[href*="chatwoot.com"][target="_blank"] {
  display: none !important;
}

/* Sidebar logo on the inbox: make sure our replaced asset shows nicely */
.logo img,
.app-logo,
.brand-image {
  max-height: 32px !important;
  object-fit: contain !important;
}

/* Hide "What's new" / Chatwoot product update buttons */
.headway-badge,
[data-testid="whats-new"] {
  display: none !important;
}
CSS_EOF

# Inject the CSS link into Chatwoot's index.html (idempotent — only adds once)
docker cp "$CSS_FILE" "${RAILS_CONTAINER}:/app/public/custom-branding.css"
docker exec "$RAILS_CONTAINER" sh -c '
  if [ -f /app/public/index.html ] && ! grep -q "custom-branding.css" /app/public/index.html; then
    sed -i "s|</head>|<link rel=\"stylesheet\" href=\"/custom-branding.css\"></head>|" /app/public/index.html
  fi
' || true

# --------------------------------------------------------------------------
# 4b. Inject runtime JS that replaces "Chatwoot" text everywhere
# --------------------------------------------------------------------------
log "Step 4b: Injecting text-replacement JS (no source rebuild needed)..."
JS_FILE="${DEPLOY_DIR}/branding/brand-rewrite.js"
cat > "$JS_FILE" <<'JS_EOF'
/* SocialHub brand rewrite — replaces "Chatwoot" text everywhere at runtime.
 * Works for: login page, dashboard, emails preview, settings, modals, etc.
 * Does NOT touch URLs / form values / asset names — only visible text. */
(function () {
  "use strict";
  var REPLACEMENTS = [
    [/Login to Chatwoot/gi, "Login to SocialHub"],
    [/Sign up for Chatwoot/gi, "Sign up for SocialHub"],
    [/Welcome to Chatwoot/gi, "Welcome to SocialHub"],
    [/Powered by Chatwoot/gi, ""],
    [/Chatwoot Inc\.?/gi, "SocialHub"],
    [/Chatwoot SDK/gi, "SocialHub SDK"],
    [/Chatwoot Mobile/gi, "SocialHub Mobile"],
    [/Chatwoot App/gi, "SocialHub App"],
    [/\bChatwoot\b/g, "SocialHub"]
  ];

  function rewriteText(node) {
    if (!node) return;
    if (node.nodeType === 3) {
      // Text node
      var t = node.nodeValue;
      if (!t || t.indexOf("Chatwoot") === -1) return;
      for (var i = 0; i < REPLACEMENTS.length; i++) {
        t = t.replace(REPLACEMENTS[i][0], REPLACEMENTS[i][1]);
      }
      if (t !== node.nodeValue) node.nodeValue = t;
      return;
    }
    if (node.nodeType !== 1) return;
    var tag = node.tagName;
    if (tag === "SCRIPT" || tag === "STYLE" || tag === "INPUT" || tag === "TEXTAREA") return;
    // Walk children
    for (var c = node.firstChild; c; c = c.nextSibling) rewriteText(c);
    // Also handle common attributes
    ["placeholder", "title", "alt", "aria-label"].forEach(function (attr) {
      var v = node.getAttribute && node.getAttribute(attr);
      if (v && v.indexOf("Chatwoot") !== -1) {
        for (var i = 0; i < REPLACEMENTS.length; i++) v = v.replace(REPLACEMENTS[i][0], REPLACEMENTS[i][1]);
        node.setAttribute(attr, v);
      }
    });
  }

  function rewriteTitle() {
    if (document.title && document.title.indexOf("Chatwoot") !== -1) {
      document.title = document.title.replace(/Chatwoot/g, "SocialHub");
    }
  }

  function fullSweep() {
    rewriteTitle();
    if (document.body) rewriteText(document.body);
  }

  // Initial sweep + observe future DOM changes (SPA navigation, modals, etc.)
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", fullSweep);
  } else {
    fullSweep();
  }
  var mo = new MutationObserver(function (mutations) {
    for (var i = 0; i < mutations.length; i++) {
      var m = mutations[i];
      if (m.type === "childList") {
        m.addedNodes.forEach(function (n) { rewriteText(n); });
      } else if (m.type === "characterData") {
        rewriteText(m.target);
      }
    }
    rewriteTitle();
  });
  // Defer observer attach until body exists
  function attachObs() {
    if (!document.body) { setTimeout(attachObs, 50); return; }
    mo.observe(document.body, { childList: true, subtree: true, characterData: true });
  }
  attachObs();
})();
JS_EOF

docker cp "$JS_FILE" "${RAILS_CONTAINER}:/app/public/brand-rewrite.js"
docker exec "$RAILS_CONTAINER" sh -c '
  if [ -f /app/public/index.html ] && ! grep -q "brand-rewrite.js" /app/public/index.html; then
    sed -i "s|</head>|<script src=\"/brand-rewrite.js\" defer></script></head>|" /app/public/index.html
  fi
' || true
log "Brand-rewrite JS injected ✅"

# --------------------------------------------------------------------------
# 5. Update INSTALLATION_NAME (already done in .env, but make sure)
# --------------------------------------------------------------------------
log "Step 5: Ensuring INSTALLATION_NAME=SocialHub..."
if grep -q "^INSTALLATION_NAME=" "${DEPLOY_DIR}/.env"; then
  sed -i 's|^INSTALLATION_NAME=.*|INSTALLATION_NAME=SocialHub|' "${DEPLOY_DIR}/.env"
else
  echo "INSTALLATION_NAME=SocialHub" >> "${DEPLOY_DIR}/.env"
fi

# Brand name and URLs (used by emails + widget where supported)
for line in "BRAND_NAME=SocialHub" "BRAND_URL=https://app.letsm.io" "WIDGET_BRAND_URL=https://app.letsm.io"; do
  KEY="${line%%=*}"
  if grep -q "^${KEY}=" "${DEPLOY_DIR}/.env"; then
    sed -i "s|^${KEY}=.*|${line}|" "${DEPLOY_DIR}/.env"
  else
    echo "$line" >> "${DEPLOY_DIR}/.env"
  fi
done

# --------------------------------------------------------------------------
# 6. Restart chatwoot-rails to pick up env + flush asset cache
# --------------------------------------------------------------------------
log "Step 6: Restarting chatwoot-rails to apply env changes..."
cd "$DEPLOY_DIR"
docker compose up -d
docker restart "$RAILS_CONTAINER" >/dev/null
log "Waiting for Chatwoot to be ready..."
for i in $(seq 1 24); do
  CODE=$(curl -sk -o /dev/null -w "%{http_code}" "https://inbox.letsm.io/favicon.ico" 2>/dev/null || echo "000")
  if [ "$CODE" = "200" ] || [ "$CODE" = "304" ]; then
    log "Chatwoot is back up (status: $CODE)"
    break
  fi
  echo "  waiting... ($i/24 — $CODE)"
  sleep 5
done

# --------------------------------------------------------------------------
# 7. Final verification
# --------------------------------------------------------------------------
log "Step 7: Verifying..."
echo ""
echo "--- favicon ---"
curl -sI "https://inbox.letsm.io/favicon.ico" 2>&1 | grep -iE "HTTP|content-type|content-length" | head -3
echo ""
echo "--- custom-branding.css ---"
curl -sI "https://inbox.letsm.io/custom-branding.css" 2>&1 | grep -iE "HTTP|content-type" | head -2
echo ""
echo "--- brand-rewrite.js ---"
curl -sI "https://inbox.letsm.io/brand-rewrite.js" 2>&1 | grep -iE "HTTP|content-type" | head -2
echo ""
echo "--- HTML <title> ---"
curl -s "https://inbox.letsm.io/" 2>&1 | grep -oE "<title>[^<]*</title>" | head -1

cat <<EOF

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Custom branding applied.

What changed:
  • Favicon: Chatwoot blue → your AI by Let's logo
  • Browser tab title: "SocialHub | سوشال هَب"
  • CSS injected: hides "Powered by Chatwoot" footer + headway buttons
  • Env: INSTALLATION_NAME, BRAND_NAME, BRAND_URL, WIDGET_BRAND_URL

To re-apply (e.g., after Chatwoot upgrade overwrites public/):
  bash <(curl -fsSL https://raw.githubusercontent.com/letsm-ai/socialhub/main/chatwoot/apply-branding.sh)

Hard-refresh your browser (Cmd+Shift+R / Ctrl+Shift+R) to see changes.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF
