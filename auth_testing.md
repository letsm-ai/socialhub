# SocialHub — Auth Testing Playbook

## Backend endpoints to verify

### 1. Health check
```
curl https://5b80a838-28ce-4651-af57-8d811f0b9483.preview.emergentagent.com/api/health
```
Expect: `{"status":"healthy",...}`

### 2. Register a new CLIENT user
```
curl -c /tmp/c.txt -X POST $API/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","email":"newuser@test.com","password":"Pass@1234"}'
```
Expect: 201 with user object `{id, name, email, role:"CLIENT", ...}` and `access_token` + `refresh_token` cookies in `/tmp/c.txt`.

### 3. Duplicate registration (should 409)
Re-running the same request must return `409 {"detail":"Email is already registered"}`.

### 4. GET /api/auth/me (authenticated)
```
curl -b /tmp/c.txt $API/api/auth/me
```
Expect: same user object (no password hash).

### 5. Login as ADMIN
```
curl -c /tmp/admin.txt -X POST $API/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@socialhub.om","password":"Admin@2026"}'
```
Expect: `{ ..., "role": "ADMIN" }`.

### 6. Bad password (should 401)
```
curl -X POST $API/api/auth/login -H "Content-Type: application/json" \
  -d '{"email":"admin@socialhub.om","password":"wrong"}'
```
Expect: `401 {"detail":"Invalid email or password"}`.

### 7. Brute force lockout
Repeat (6) 5 times → 6th attempt returns `429 {"detail":"Too many failed attempts..."}` for 15 min.

### 8. Logout clears cookies
```
curl -b /tmp/c.txt -c /tmp/c.txt -X POST $API/api/auth/logout
curl -b /tmp/c.txt $API/api/auth/me
```
The second call must return 401.

---

## Frontend flow tests

### Login flow (CLIENT redirect)
1. Go to `/login`
2. Enter `newuser@test.com` / `Pass@1234`
3. Submit → expect redirect to `/dashboard`
4. Page shows "نظرة عامة" with sidebar

### Login flow (ADMIN redirect)
1. Go to `/login`
2. Enter `admin@socialhub.om` / `Admin@2026`
3. Submit → expect redirect to `/admin`
4. Admin layout (dark sidebar) visible

### Protected route enforcement
1. While logged out, visit `/dashboard` → must redirect to `/login`
2. While logged out, visit `/admin` → must redirect to `/login`
3. While logged in as CLIENT, visit `/admin` → must redirect to `/dashboard`
4. While logged in as ADMIN, visit `/dashboard` → must redirect to `/admin`

### Register validation
1. Go to `/register`
2. Empty submit → field error messages appear
3. Email "abc" → "صيغة البريد غير صحيحة"
4. Password "short" → multiple checklist items red
5. Mismatched passwords → "كلمتا المرور غير متطابقتين"

### Language toggle stays on auth pages
1. On `/login`, click globe → toggles to English / back to Arabic, no crash.

### Logout
1. From `/dashboard`, click "خروج" → redirect to `/login`, session ended.
