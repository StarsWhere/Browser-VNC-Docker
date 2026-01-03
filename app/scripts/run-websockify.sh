#!/usr/bin/env bash
set -euo pipefail

PORT=${NOVNC_PORT:-6080}
exec websockify 0.0.0.0:${PORT} 127.0.0.1:5901 --web=/usr/share/novnc
