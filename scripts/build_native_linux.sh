#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
agent="$root/dist/deviceshare-agent-linux-x64"
hub="$root/dist/deviceshare-hub-linux-x64"
for binary in "$agent" "$hub"; do [[ -x "$binary" ]] || { echo "Missing $binary" >&2; exit 1; }; done
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
mkdir -p "$staging/DEBIAN" "$staging/usr/bin" "$staging/usr/share/deviceshare" "$staging/usr/share/doc/deviceshare"
install -m 0755 "$agent" "$staging/usr/bin/deviceshare-agent"
install -m 0755 "$hub" "$staging/usr/bin/deviceshare-hub"
install -m 0644 config/agent.example.json "$staging/usr/share/deviceshare/agent.example.json"
install -m 0644 docs/INSTALL_NATIVE.md "$staging/usr/share/doc/deviceshare/INSTALL_NATIVE.md"
install -m 0644 SECURITY.md "$staging/usr/share/doc/deviceshare/SECURITY.md"
cat > "$staging/DEBIAN/control" <<'CONTROL'
Package: deviceshare
Version: 0.2.0~alpha2
Section: utils
Priority: optional
Architecture: amd64
Maintainer: MT Tech Services LLC <tech@mttechservicesllc.com>
Description: DeviceShare local and remote peripheral bridge
 Portable device agent and authenticated HTTP hub for printers,
 serial devices and read-only allowlisted HID input.
 No network services are automatically enabled on installation.
Homepage: https://github.com/migtam628/DeviceShare
CONTROL
mkdir -p release-assets
deb="release-assets/DeviceShare_0.2.0~alpha2_amd64.deb"
dpkg-deb --root-owner-group --build "$staging" "$deb"
dpkg-deb --info "$deb"
dpkg-deb --contents "$deb" | grep -E 'usr/bin/deviceshare-(agent|hub)'
verify="$(mktemp -d)"
trap 'rm -rf "$staging" "$verify"' EXIT
dpkg-deb --extract "$deb" "$verify"
"$verify/usr/bin/deviceshare-agent" --version
"$verify/usr/bin/deviceshare-hub" --version
test -s "$verify/usr/share/doc/deviceshare/INSTALL_NATIVE.md"
echo "DEB payload and frozen executables verified."
