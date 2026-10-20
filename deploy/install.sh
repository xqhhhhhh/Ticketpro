#!/usr/bin/env bash
set -euo pipefail
umask 027
if [[ "$(id -u)" != 0 ]]; then
  echo 'Run on the backend host as root.' >&2
  exit 1
fi
bundle_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
command -v python3 >/dev/null
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11 or newer is required"'
command -v systemctl >/dev/null
getent group ticketpro-web >/dev/null || groupadd --system ticketpro-web
id ticketpro >/dev/null 2>&1 || useradd --system --no-create-home --gid ticketpro-web --shell /usr/sbin/nologin ticketpro
install -d -m 0755 /opt/ticketpro /opt/ticketpro/server /opt/ticketpro/deploy /opt/ticketpro/scripts
install -d -o ticketpro -g ticketpro-web -m 0700 /var/lib/ticketpro /var/backups/ticketpro
install -d -o root -g root -m 0700 /var/lib/ticketpro-restock
install -d -o ticketpro -g ticketpro-web -m 2750 /opt/ticketpro-shared
if [[ -f /opt/ticketpro/server/app.py ]]; then
  backup_dir="/var/backups/ticketpro/source-$(date -u +%Y%m%dT%H%M%SZ)"
  install -d -m 0700 "$backup_dir"
  cp -a /opt/ticketpro/server "$backup_dir/"
fi
for file in "$bundle_dir"/server/*.py "$bundle_dir"/server/requirements.lock "$bundle_dir"/server/catalog.json "$bundle_dir"/server/product-projects.json "$bundle_dir"/server/license-projects.json; do
  install -m 0644 "$file" /opt/ticketpro/server/
done
install -o root -g ticketpro-web -m 0640 "$bundle_dir/server/tutorials.local.json" /opt/ticketpro/server/tutorials.local.json
install -m 0644 "$bundle_dir/scripts/connect-unified-console.py" /opt/ticketpro/scripts/
install -m 0644 "$bundle_dir/scripts/configure-stock-sources.py" /opt/ticketpro/scripts/
install -m 0644 "$bundle_dir"/deploy/* /opt/ticketpro/deploy/
python3 -m venv /opt/ticketpro/.venv
/opt/ticketpro/.venv/bin/python -m pip install --index-url https://pypi.org/simple -r /opt/ticketpro/server/requirements.lock
chgrp -R ticketpro-web /opt/ticketpro/.venv
chmod -R g+rX /opt/ticketpro/.venv
if [[ ! -e /opt/ticketpro-shared/web-reserved-codes.json ]]; then
  printf '%s\n' '{"version":1,"projects":{}}' | install -o ticketpro -g ticketpro-web -m 0640 /dev/stdin /opt/ticketpro-shared/web-reserved-codes.json
fi
if [[ ! -e /etc/ticketpro.env ]]; then
  install -o root -g root -m 0600 "$bundle_dir/deploy/ticketpro.env.example" /etc/ticketpro.env
fi
install -m 0644 "$bundle_dir"/deploy/*.service "$bundle_dir"/deploy/*.timer "$bundle_dir"/deploy/*.path /etc/systemd/system/
if [[ ! -e /var/lib/ticketpro/restock.request ]]; then
  install -o ticketpro -g ticketpro-web -m 0600 /dev/null /var/lib/ticketpro/restock.request
fi
systemctl daemon-reload
echo 'Backend installed. Existing environment and delivery database were preserved.'
echo 'Configure /etc/ticketpro.env, install the Nginx snippet and unified-console stock filter, then run the production checks before enabling purchases.'
