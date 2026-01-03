#!/usr/bin/env bash
set -euo pipefail

export TZ=${TZ:-Asia/Shanghai}
export LANG=${LANG:-en_US.UTF-8}
export LC_ALL=${LC_ALL:-en_US.UTF-8}
export ADMIN_PORT=${ADMIN_PORT:-8080}
export NOVNC_PORT=${NOVNC_PORT:-6080}
export LOG_MAX_BYTES=${LOG_MAX_BYTES:-10485760}
export LOG_BACKUP_COUNT=${LOG_BACKUP_COUNT:-5}

if [[ -z "${VNC_PASSWORD:-}" ]]; then
  echo "VNC_PASSWORD is required" >&2
  exit 1
fi

# Timezone
ln -sf "/usr/share/zoneinfo/${TZ}" /etc/localtime || true
echo "${TZ}" > /etc/timezone || true

# Locale (default en_US.UTF-8, allow override)
if ! locale -a | grep -qi "${LANG}"; then
  if ! grep -q "^${LANG} UTF-8" /etc/locale.gen; then
    echo "${LANG} UTF-8" >> /etc/locale.gen
  fi
  locale-gen "${LANG}" || true
fi
# Always ensure en_US.UTF-8 exists as fallback
if ! locale -a | grep -qi "en_US.utf8"; then
  if ! grep -q "^en_US.UTF-8 UTF-8" /etc/locale.gen; then
    echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
  fi
  locale-gen en_US.UTF-8 || true
fi

mkdir -p /data /data/logs /data/profiles /root/.vnc
if [[ ! -f /data/accounts.json ]]; then
  echo "[]" > /data/accounts.json
fi

# Ensure noVNC has a default index to avoid directory listing
NOVNC_DIR=/usr/share/novnc
if [[ -d "${NOVNC_DIR}" && ! -f "${NOVNC_DIR}/index.html" ]]; then
  cat >"${NOVNC_DIR}/index.html" <<'EOF'
<!doctype html>
<html><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=/vnc_lite.html"></head><body></body></html>
EOF
fi

VNC_PASS_CMD=$(command -v vncpasswd || command -v tigervncpasswd || true)
if [[ -z "${VNC_PASS_CMD}" ]]; then
  echo "vncpasswd command not found" >&2
  exit 1
fi
printf "%s\n" "${VNC_PASSWORD}" | "${VNC_PASS_CMD}" -f > /root/.vnc/passwd
chmod 600 /root/.vnc/passwd

cat >/root/.vnc/xstartup <<'EOF'
#!/usr/bin/env bash
exec startfluxbox
EOF
chmod +x /root/.vnc/xstartup

exec /usr/bin/supervisord -c /app/supervisor/supervisord.conf
