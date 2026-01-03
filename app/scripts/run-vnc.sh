#!/usr/bin/env bash
set -euo pipefail

export DISPLAY=${VNC_DISPLAY:-:1}
GEOMETRY=${VNC_GEOMETRY:-1280x800}
DEPTH=${VNC_DEPTH:-24}

mkdir -p /root/.vnc

Xvnc "${DISPLAY}" \
  -geometry "${GEOMETRY}" \
  -depth "${DEPTH}" \
  -SecurityTypes=VncAuth \
  -PasswordFile=/root/.vnc/passwd \
  -localhost \
  -rfbport 5901 &
XVNC_PID=$!

sleep 2
fluxbox &

wait ${XVNC_PID}
