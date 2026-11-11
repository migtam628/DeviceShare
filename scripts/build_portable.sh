#!/usr/bin/env bash
# Build, smoke-test and package both portable executables on a native runner.
set -euo pipefail
suffix="${1:?Usage: bash scripts/build_portable.sh platform-suffix}"
python -m pip install --upgrade pip
python -m pip install ".[usb,hid]" "pyinstaller>=6,<8"
if [[ "${RUNNER_OS:-}" == "Windows" ]]; then
  python -m pip install ".[windows]"
fi

agent_name="deviceshare-agent-${suffix}"
hub_name="deviceshare-hub-${suffix}"

python -m PyInstaller --noconfirm --clean --onefile \
  --name "$agent_name" \
  --hidden-import hid \
  --hidden-import usb.core \
  --hidden-import serial.tools.list_ports \
  --hidden-import win32print \
  scripts/agent_launcher.py

python -m PyInstaller --noconfirm --clean --onefile \
  --name "$hub_name" \
  --collect-submodules uvicorn \
  --collect-data deviceshare \
  scripts/hub_launcher.py

ext=""
if [[ "${RUNNER_OS:-}" == "Windows" ]]; then ext=".exe"; fi

python scripts/smoke_frozen.py \
  --agent "dist/${agent_name}${ext}" \
  --hub "dist/${hub_name}${ext}"
python scripts/package_release.py \
  --agent "dist/${agent_name}${ext}" \
  --hub "dist/${hub_name}${ext}" \
  --suffix "$suffix"
