# Evolution API — نشر سريع على VPS

دليل مختصر لتشغيل Evolution API كـ QR engine لـ SocialHub.

## 1️⃣ على VPS — جهّز المجلد

```bash
ssh root@76.13.220.229
mkdir -p /root/evolution
cd /root/evolution
```

## 2️⃣ ولّد مفتاح API عشوائي وخزّنه

```bash
openssl rand -hex 32
```

انسخ الناتج — هذا هو `EVOLUTION_API_KEY`. احفظه عندك في مكان آمن.

## 3️⃣ أنشئ ملف `.env` في `/root/evolution/.env`

```bash
cat > /root/evolution/.env <<'EOF'
EVOLUTION_API_KEY=ضع_المفتاح_هنا
POSTGRES_PASSWORD=ضع_كلمة_مرور_قوية_للقاعدة
EOF
```

## 4️⃣ أنشئ `/root/evolution/docker-compose.yml`

```bash
cat > /root/evolution/docker-compose.yml <<'EOF'
services:
  evolution-postgres:
    image: postgres:16-alpine
    container_name: evolution-postgres
    restart: always
    environment:
      POSTGRES_USER: evolution
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: evolution
    volumes:
      - evolution_pg_data:/var/lib/postgresql/data
    networks:
      - evolution_net

  evolution-redis:
    image: redis:7-alpine
    container_name: evolution-redis
    restart: always
    command: redis-server --appendonly yes
    volumes:
      - evolution_redis_data:/data
    networks:
      - evolution_net

  evolution-api:
    image: atendai/evolution-api:latest
    container_name: evolution-api
    restart: always
    depends_on:
      - evolution-postgres
      - evolution-redis
    ports:
      - "127.0.0.1:8080:8080"
    environment:
      SERVER_TYPE: http
      SERVER_PORT: 8080
      SERVER_URL: https://evo.letsm.io
      AUTHENTICATION_TYPE: apikey
      AUTHENTICATION_API_KEY: ${EVOLUTION_API_KEY}
      AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES: "true"
      DATABASE_ENABLED: "true"
      DATABASE_PROVIDER: postgresql
      DATABASE_CONNECTION_URI: postgresql://evolution:${POSTGRES_PASSWORD}@evolution-postgres:5432/evolution
      DATABASE_CONNECTION_CLIENT_NAME: evolution
      CACHE_REDIS_ENABLED: "true"
      CACHE_REDIS_URI: redis://evolution-redis:6379/6
      CACHE_REDIS_PREFIX_KEY: evolution
      CACHE_REDIS_SAVE_INSTANCES: "false"
      CACHE_LOCAL_ENABLED: "false"
      TELEMETRY: "false"
      QRCODE_LIMIT: "30"
      CONFIG_SESSION_PHONE_CLIENT: "SocialHub"
      CONFIG_SESSION_PHONE_NAME: Chrome
      WEBHOOK_GLOBAL_ENABLED: "true"
      WEBHOOK_GLOBAL_URL: https://app.letsm.io/api/webhooks/evolution
      WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS: "false"
      DEL_INSTANCE: "false"
    networks:
      - evolution_net

volumes:
  evolution_pg_data:
  evolution_redis_data:

networks:
  evolution_net:
    driver: bridge
EOF
```

## 5️⃣ شغّل الـ containers

```bash
cd /root/evolution
docker compose --env-file .env up -d
docker compose logs -f evolution-api
```

انتظر لين تشوف: `Evolution API started on port 8080` ثم اضغط `Ctrl+C` للخروج من اللوغ.

## 6️⃣ أضف Nginx reverse proxy للـ `evo.letsm.io`

```bash
cat > /etc/nginx/sites-available/evo.letsm.io <<'EOF'
server {
    listen 443 ssl http2;
    server_name evo.letsm.io;

    ssl_certificate /etc/letsencrypt/live/evo.letsm.io/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/evo.letsm.io/privkey.pem;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 90s;
    }
}

server {
    listen 80;
    server_name evo.letsm.io;
    return 301 https://$host$request_uri;
}
EOF

ln -sf /etc/nginx/sites-available/evo.letsm.io /etc/nginx/sites-enabled/
```

## 7️⃣ أضف DNS A record

في لوحة Hostinger DNS:
- **Type:** `A`
- **Name:** `evo`
- **Value:** `76.13.220.229` (IP الـ VPS)
- **TTL:** `300`

انتظر ~5 دقائق لـ DNS propagation.

## 8️⃣ احصل على SSL certificate

```bash
certbot --nginx -d evo.letsm.io --non-interactive --agree-tos -m mazin@lets-m.com
systemctl reload nginx
```

## 9️⃣ تأكد إن Evolution شغّال خارجياً

```bash
curl -H "apikey: <ضع_المفتاح_هنا>" https://evo.letsm.io/instance/fetchInstances
```

يفترض ترجع `[]` (مصفوفة فارغة) — معناها التشغيل سليم.

## 🔟 أضف env vars لـ SocialHub

```bash
nano /var/www/socialhub/backend/.env
```

أضف في نهاية الملف:

```
EVOLUTION_API_URL=https://evo.letsm.io
EVOLUTION_API_KEY=ضع_نفس_المفتاح_هنا
```

أعد تشغيل API:

```bash
systemctl restart socialhub-api
```

## 1️⃣1️⃣ تأكد إن SocialHub يشوف Evolution

```bash
curl https://app.letsm.io/api/me/channels/whatsapp/qr/config \
     -H "Authorization: Bearer <TOKEN_لأي_عميل>"
```

لازم ترجع: `{"enabled": true}` ✅

---

## ✅ الاختبار النهائي من المتصفح

1. ادخل `app.letsm.io/dashboard/channels` كعميل عادي
2. ستظهر بطاقة جديدة: **"ربط واتساب بـ QR (Lite)"**
3. اضغط "ابدأ الربط بمسح QR" → سيظهر QR code
4. افتح واتساب على جوالك → **الإعدادات → الأجهزة المرتبطة → ربط جهاز → امسح الكود**
5. سيتم الربط تلقائياً + المودال يُغلق + يظهر toast "🎉 تم ربط واتساب بنجاح"
6. ابعت رسالة من رقم آخر للرقم المربوط → ستظهر في Chatwoot تحت inbox **"WhatsApp (Lite / QR)"**

## 🛠️ صيانة سريعة

```bash
# لوغ Evolution
docker logs -f evolution-api

# تحديث Evolution
cd /root/evolution
docker compose pull && docker compose up -d

# حذف instance عالقة يدوياً
curl -X DELETE -H "apikey: $EVOLUTION_API_KEY" \
     https://evo.letsm.io/instance/delete/socialhub-XXXXX

# نسخة احتياطية للقاعدة
docker exec evolution-postgres pg_dump -U evolution evolution > evolution_backup_$(date +%Y%m%d).sql
```
