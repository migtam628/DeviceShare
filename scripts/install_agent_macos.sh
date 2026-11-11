#!/bin/bash
# Per-user LaunchAgent; no administrator privileges required.
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo "Usage: bash install_agent_macos.sh /absolute/path/to/deviceshare-agent /absolute/path/to/config/agent.json" >&2
  exit 2
fi
agent="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
config="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
[[ -x "$agent" && -r "$config" ]] || { echo "Agent must be executable and config readable" >&2; exit 1; }
workdir="$(dirname "$(dirname "$config")")"
plist="$HOME/Library/LaunchAgents/com.deviceshare.agent.plist"
logdir="$HOME/Library/Logs/DeviceShare"
mkdir -p "$(dirname "$plist")" "$logdir"
chmod 700 "$(dirname "$plist")" "$logdir"
xml_escape() {
  printf '%s' "$1" | sed -e 's/\&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e 's/"/\&quot;/g'
}
e_agent="$(xml_escape "$agent")"
e_config="$(xml_escape "$config")"
e_workdir="$(xml_escape "$workdir")"
e_stdout="$(xml_escape "$logdir/agent.out.log")"
e_stderr="$(xml_escape "$logdir/agent.err.log")"
cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.deviceshare.agent</string>
  <key>ProgramArguments</key><array>
    <string>$e_agent</string>
    <string>--config</string>
    <string>$e_config</string>
  </array>
  <key>WorkingDirectory</key><string>$e_workdir</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$e_stdout</string>
  <key>StandardErrorPath</key><string>$e_stderr</string>
</dict>
</plist>
EOF
chmod 600 "$plist"
plutil -lint "$plist"
launchctl bootout "gui/$(id -u)" "$plist" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$plist"
launchctl enable "gui/$(id -u)/com.deviceshare.agent"
echo "DeviceShare LaunchAgent installed for current logged-in user."
echo "Check: launchctl print gui/$(id -u)/com.deviceshare.agent"
echo "Logs: $logdir"
