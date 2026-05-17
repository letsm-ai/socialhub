# GitHub Actions Auto-Deploy Setup

This repo auto-deploys to the production VPS (`app.letsm.io`) on every push to `main` via `.github/workflows/deploy.yml`.

## One-time setup (run once)

### 1. Generate a deploy SSH key on the VPS

SSH into the VPS and run:

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/socialhub_deploy -N ""
cat ~/.ssh/socialhub_deploy.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# Print the PRIVATE key — copy ALL of this output (including BEGIN/END lines)
cat ~/.ssh/socialhub_deploy
```

### 2. Add 4 secrets in GitHub

Go to: **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

| Name           | Value                                                    |
|----------------|----------------------------------------------------------|
| `VPS_HOST`     | `76.13.220.229`                                          |
| `VPS_USER`     | `root`                                                   |
| `VPS_PORT`     | `22` (optional — defaults to 22)                         |
| `VPS_SSH_KEY`  | Full contents of `~/.ssh/socialhub_deploy` (private key) |

### 3. Test it

Push any change to `main` (or click **Run workflow** in the Actions tab). The workflow will:
1. SSH into VPS
2. `git pull` latest from `main`
3. `pip install` backend deps
4. Restart `socialhub-api` systemd service
5. `yarn build` frontend
6. Restart `socialhub-web` Docker container
7. Smoke-test `/api/payments/config`

Watch progress in **Actions** tab. Each run takes ~3–5 minutes.

## Manual rollback (if needed)

```bash
ssh root@76.13.220.229
cd /var/www/socialhub
git log --oneline | head -10
git reset --hard <previous-commit-sha>
systemctl restart socialhub-api
cd frontend && CI=false yarn build && docker restart socialhub-web
```
