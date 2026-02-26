#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
#  IT Dashboard — Droplet First-Time Setup
#  Run this ONCE on a fresh Ubuntu 24.04 Droplet:
#    curl -sSL https://raw.githubusercontent.com/JithendraNara/it-dashboard/main/setup-droplet.sh | bash
# ═══════════════════════════════════════════════════════════════════════
set -euo pipefail

REPO="https://github.com/JithendraNara/it-dashboard.git"
APP_DIR="/opt/dashboard/app"
VENV_DIR="/opt/dashboard/venv"
TOKEN="f2e10ce9e211948c6eeacf1b13c0fcf631ec4b70f706f03fe930f647a5013466"

echo ""
echo "═══════════════════════════════════════════════════"
echo "  IT Jobs Intelligence Dashboard — Setup"
echo "═══════════════════════════════════════════════════"
echo ""

# ─── System packages ──────────────────────────────────
echo "[1/6] Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3-pip python3-venv nginx ufw git > /dev/null 2>&1
echo "  ✓ Packages installed"

# ─── Clone repo ───────────────────────────────────────
echo "[2/6] Cloning repository..."
mkdir -p /opt/dashboard
if [ -d "$APP_DIR/.git" ]; then
  cd "$APP_DIR"
  git pull origin main
  echo "  ✓ Updated existing clone"
else
  rm -rf "$APP_DIR"
  git clone "$REPO" "$APP_DIR"
  echo "  ✓ Cloned from GitHub"
fi
mkdir -p "$APP_DIR/data"

# ─── Python venv ──────────────────────────────────────
echo "[3/6] Setting up Python environment..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install -q --upgrade pip
"$VENV_DIR/bin/pip" install -q -r "$APP_DIR/requirements.txt"
chown -R www-data:www-data "$APP_DIR/data"
echo "  ✓ Python environment ready"

# ─── Systemd service ─────────────────────────────────
echo "[4/6] Configuring systemd service..."
cat > /etc/systemd/system/dashboard.service << SVCEOF
[Unit]
Description=IT Jobs Intelligence Dashboard
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin:/usr/bin:/bin"
Environment="DASHBOARD_UPDATE_TOKEN=$TOKEN"
ExecStart=$VENV_DIR/bin/gunicorn -w 2 -b 127.0.0.1:8000 --timeout 120 --access-logfile /var/log/dashboard-access.log --error-logfile /var/log/dashboard-error.log app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable dashboard
systemctl start dashboard
echo "  ✓ Dashboard service started"

# ─── Nginx ────────────────────────────────────────────
echo "[5/6] Configuring Nginx..."
cat > /etc/nginx/sites-available/dashboard << 'NGXEOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
    
    location /css/ {
        alias /opt/dashboard/app/static/css/;
        expires 1h;
    }
    location /js/ {
        alias /opt/dashboard/app/static/js/;
        expires 1h;
    }
}
NGXEOF

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/dashboard /etc/nginx/sites-enabled/dashboard
nginx -t && systemctl restart nginx
echo "  ✓ Nginx configured"

# ─── Firewall ─────────────────────────────────────────
echo "[6/6] Configuring firewall..."
ufw allow 22/tcp > /dev/null
ufw allow 80/tcp > /dev/null
ufw allow 443/tcp > /dev/null
ufw --force enable > /dev/null
echo "  ✓ Firewall enabled (22, 80, 443)"

# ─── Generate SSH deploy key for GitHub Actions ───────
echo ""
echo "Generating SSH deploy key for GitHub Actions..."
ssh-keygen -t ed25519 -f /root/.ssh/deploy_key -N "" -C "github-actions-deploy" > /dev/null 2>&1
cat /root/.ssh/deploy_key.pub >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
echo "  ✓ Deploy key generated"

# ─── Verify ──────────────────────────────────────────
echo ""
sleep 3
IP=$(curl -s ifconfig.me || hostname -I | awk '{print $1}')

if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
  echo "═══════════════════════════════════════════════════"
  echo "  ✓ DASHBOARD IS LIVE"
  echo "═══════════════════════════════════════════════════"
else
  echo "  ⚠ Service may still be starting..."
fi

echo ""
echo "  Dashboard:  http://$IP"
echo "  Health:     http://$IP/health"
echo "  Jobs API:   http://$IP/api/jobs.py"
echo "  Update API: http://$IP/api/update.py"
echo ""
echo "  ─── FOR GITHUB ACTIONS ───"
echo "  Add these as secrets at:"
echo "  https://github.com/JithendraNara/it-dashboard/settings/secrets/actions"
echo ""
echo "  DROPLET_IP = $IP"
echo ""
echo "  SSH_PRIVATE_KEY = (copy the output below)"
echo "  ─────────────────────────────────────────"
cat /root/.ssh/deploy_key
echo "  ─────────────────────────────────────────"
echo ""
echo "  ─── FOR HUNTER/ATLAS ───"
echo "  DASHBOARD_URL=http://$IP"
echo "  DASHBOARD_UPDATE_TOKEN=$TOKEN"
echo ""
echo "  Done! Push to main branch → auto-deploys."
echo ""