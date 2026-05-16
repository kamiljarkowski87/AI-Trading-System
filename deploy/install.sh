#!/bin/bash
# Run as root on mariusz128.mikrus.xyz
set -e

APP_DIR=/home/claude-runner/ai-trading-system
USER=claude-runner

echo "=== Installing AI Trading System ==="

# 1. Create user if not exists
id "$USER" &>/dev/null || useradd -m -s /bin/bash "$USER"

# 2. Clone / pull repo
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull
else
  git clone <REPO_URL> "$APP_DIR"
  chown -R "$USER:$USER" "$APP_DIR"
fi

# 3. Python venv
sudo -u "$USER" python3.11 -m venv "$APP_DIR/.venv"
sudo -u "$USER" "$APP_DIR/.venv/bin/pip" install --upgrade pip
sudo -u "$USER" "$APP_DIR/.venv/bin/pip" install -e "$APP_DIR"

# 4. Copy .env (must already exist)
if [ ! -f "$APP_DIR/.env" ]; then
  echo "ERROR: $APP_DIR/.env not found. Copy .env.example and fill in credentials."
  exit 1
fi

# 5. Systemd service
cp "$APP_DIR/deploy/trading-system.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable trading-system
systemctl restart trading-system

echo "=== Done. Status:"
systemctl status trading-system --no-pager
