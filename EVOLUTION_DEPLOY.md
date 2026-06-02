# Evolution API — Self-Hosted QR WhatsApp for SocialHub

Evolution API is the open-source engine that powers our **WhatsApp Lite (QR)** option for clients who don't have a Meta developer account. It speaks the unofficial WhatsApp Web protocol via Baileys, so it's free to use but ⚠️ **not officially supported by Meta**.

> Use Cloud API (Tech Provider) for any client serious about broadcasts, verified badge, or long-term stability. QR is for the lowest-tier package only.

## 1. Deploy on VPS (one-time)

SSH into the VPS:

```bash
ssh root@76.13.220.229
mkdir -p /root/evolution
cd /root/evolution
```

Create `/root/evolution/docker-compose.yml`:

```yaml
services:
  evolution-api:
    image: atendai/evolution-api:latest
    container_name: evolution-api
    restart: always
    ports:
      - "127.0.0.1:8080:8080"   # localhost only; Traefik handles TLS
    environment:
      # --- Server ---
      SERVER_TYPE: http
      SERVER_PORT: 8080
      SERVER_URL: https://evo.letsm.io
      # --- Auth ---
      AUTHENTICATION_TYPE: apikey
      AUTHENTICATION_API_KEY: ${EVOLUTION_API_KEY}
      AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES: "true"
      # --- Database (reuses Postgres from the Chatwoot stack) ---
      DATABASE_ENABLED: "true"
      DATABASE_PROVIDER: postgresql
      DATABASE_CONNECTION_URI: ${EVOLUTION_DATABASE_URL}
      DATABASE_CONNECTION_CLIENT_NAME: evolution_exchange
      # --- Disable telemetry to keep instances private ---
      TELEMETRY: "false"
      QRCODE_LIMIT: "30"
      QRCODE_COLOR: "#000000"
      CONFIG_SESSION_PHONE_CLIENT: "SocialHub"
      CONFIG_SESSION_PHONE_NAME: Chrome
      # --- Webhook → SocialHub backend (we already handle /api/webhooks/evolution) ---
      WEBHOOK_GLOBAL_ENABLED: "true"
      WEBHOOK_GLOBAL_URL: https://app.letsm.io/api/webhooks/evolution
      WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS: "false"
    networks:
      - coolify
    labels:
      - traefik.enable=true
      - traefik.http.routers.evolution.rule=Host(`evo.letsm.io`)
      - traefik.http.routers.evolution.entrypoints=https
      - traefik.http.routers.evolution.tls=true
      - traefik.http.routers.evolution.tls.certresolver=letsencrypt
      - traefik.http.services.evolution.loadbalancer.server.port=8080

networks:
  coolify:
    external: true
```

Create `/root/evolution/.env`:

```bash
EVOLUTION_API_KEY="<long-random-string>"
EVOLUTION_DATABASE_URL="postgresql://postgres:<your-pg-password>@coolify-postgres:5432/evolution"
```

Generate `EVOLUTION_API_KEY`:
```bash
openssl rand -hex 32
```

Bootstrap the database (one-time):
```bash
docker exec -it coolify-postgres psql -U postgres -c "CREATE DATABASE evolution;"
```

Start:
```bash
cd /root/evolution
docker compose --env-file .env up -d
docker logs -f evolution-api
```

You should see `Evolution API started on port 8080`. Verify externally:
```bash
curl -H "apikey: $EVOLUTION_API_KEY" https://evo.letsm.io/manager/fetchInstances
# → []  (empty list, since no instances yet — means it's live)
```

## 2. Configure SocialHub backend

Append to `/var/www/socialhub/backend/.env` on the VPS:

```bash
EVOLUTION_API_URL="https://evo.letsm.io"
EVOLUTION_API_KEY="<same-key-as-above>"
```

Then:
```bash
systemctl restart socialhub-api
```

`GET /api/me/channels/whatsapp/qr/config` should now return `{"enabled": true}`.

## 3. End-to-end test

1. Log into SocialHub as a regular client.
2. Channels page → "Connect via QR (Lite)" → scan with your WhatsApp.
3. Send yourself a message from another phone → it should land in **Chatwoot** under the inbox **"WhatsApp (Lite / QR)"** of that client's account.
4. Reply in Chatwoot → the reply should arrive on the customer's WhatsApp.

## 4. Daily ops

- **Logs:** `docker logs -f evolution-api`
- **Update:** `docker compose pull && docker compose up -d`
- **Wipe a stuck instance:**
  ```bash
  curl -X DELETE -H "apikey: $EVOLUTION_API_KEY" \
       https://evo.letsm.io/instance/delete/socialhub-<USER_ID_PREFIX>
  ```

## 5. Known limitations of QR (communicate to clients)

- 🚫 **No template broadcasts** — Baileys cannot send the 24h-window-bypass templates that Cloud API supports.
- ⚠️ **Risk of WhatsApp banning the number** — especially with high outbound volume or marketing content.
- 🔒 **Cannot get the green-tick badge.**
- 📞 **Number can't be used by the WhatsApp app at the same time** (Linked Devices slot).
