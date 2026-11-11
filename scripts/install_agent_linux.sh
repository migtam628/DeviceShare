#!/usr/bin/env bash
# Install DeviceShare Agent as a non-root systemd user service.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: bash install_agent_linux.sh /absolute/path/to/deviceshare-agent /absolute/path/to/config/agent.json" >&2
  exit 2
fi
command -v systemctl >/dev/null || { echo "systemctl is required" >&2; exit 1; }
agent="$(realpath "$1")"
config="$(realpath "$2")"
[[ -x "$agent" && -r "$config" ]] || { echo "Agent must be executable and config readable" >&2; exit 1; }
# systemd has its own specifier/quote expansion. Refuse ambiguous paths.
for value in "$agent" "$config"; do
  if [[ "$value" == *%* || "$value" == *'"'* || "$value" == *$'\n'* || "$value" == *'\'* ]]; then
    echo "Path contains unsupported systemd quote/special characters: $value" >&2
    exit 1
  fi
done
workdir="$(dirname "$(dirname "$config")")"
unitdir="$HOME/.config/systemd/user"
mkdir -p "$unitdir"
chmod 700 "$unitdir"
cat > "$unitdir/deviceshare-agent.service" <<EOF
[Unit]
Description=DeviceShare local peripheral agent
After=network-online.target

[Service]
Type=simple
ExecStart="$agent" --config "$config"
WorkingDirectory="$workdir"
Restart=always
RestartSec=10
UMask=0077
NoNewPrivileges=true

[Install]
WantedBy=default.target
EOF
chmod 600 "$unitdir/deviceshare-agent.service"
systemctl --user daemon-reload
systemctl --user enable --now deviceshare-agent.service
echo "DeviceShare installed for current user."
echo "Check: systemctl --user status deviceshare-agent.service"
echo "Logs:  journalctl --user -u deviceshare-agent.service -f"
echo "Requires an active user session; linger is not enabled automatically."
