#!/usr/bin/env bash
# Initial installation; repeating the same revision is supported.
set -euo pipefail

if [[ $EUID -ne 0 || $# -ne 1 ]]; then
    echo "Usage: sudo bash deploy/setup_app.sh /absolute/path/to/repository" >&2
    exit 1
fi
repo=$(realpath "$1")
# sudo reads the administrator's explicitly selected checkout.
revision=$(git -c safe.directory="$repo" -C "$repo" rev-parse HEAD)
if [[ -n $(git -c safe.directory="$repo" -C "$repo" status --porcelain) ]]; then
    echo "Commit changes or use a clean checkout before installation." >&2
    exit 1
fi
if systemctl is-active --quiet confmanager; then
    echo "Stop confmanager before repeating installation." >&2
    exit 1
fi
if [[ -d /opt/confmanager/src ]] && [[ -n $(ls -A /opt/confmanager/src) ]]; then
    if [[ ! -f /opt/confmanager/deployed.sha ]] || \
       [[ $(cat /opt/confmanager/deployed.sha) != "$revision" ]]; then
        echo "Another revision is installed. Do not overwrite it; see docs/lr2-deploy.md." >&2
        exit 1
    fi
fi

if ! id confapp >/dev/null 2>&1; then
    useradd --system --home /opt/confmanager --shell /usr/sbin/nologin confapp
fi
if [[ $(id -u confapp) == 0 || $(getent passwd confapp | cut -d: -f7) != /usr/sbin/nologin ]]; then
    echo "confapp must be a separate account with /usr/sbin/nologin." >&2
    exit 1
fi
install -d -o root -g confapp -m 750 /opt/confmanager /opt/confmanager/src
install -d -o root -g root -m 700 /etc/confmanager
git -c safe.directory="$repo" -C "$repo" archive HEAD | tar -x -C /opt/confmanager/src
python3 -m venv /opt/confmanager/.venv
/opt/confmanager/.venv/bin/python -m pip install -r /opt/confmanager/src/requirements.txt
/opt/confmanager/.venv/bin/python -m pip check
/opt/confmanager/.venv/bin/python -m compileall -q /opt/confmanager/src/app
chown -R root:confapp /opt/confmanager/src /opt/confmanager/.venv
chmod -R u=rwX,g=rX,o= /opt/confmanager/src /opt/confmanager/.venv
printf '%s\n' "$revision" > /opt/confmanager/deployed.sha
chmod 644 /opt/confmanager/deployed.sha
install -o root -g root -m 644 /opt/confmanager/src/deploy/confmanager.service \
    /etc/systemd/system/confmanager.service
systemctl daemon-reload
echo "Installed revision: $revision"
echo "Create /etc/confmanager/app.env (root:root, 600), then follow docs/lr2-deploy.md."
echo "The service has not been started; database access must be checked first."
