#!/bin/bash
set -euo pipefail
if [[ $# -ne 1 ]]; then echo "Usage: build_native_macos.sh macos-arm64|macos-x64" >&2; exit 2; fi
suffix="$1"
case "$suffix" in macos-arm64|macos-x64) ;; *) echo "Invalid macOS suffix" >&2; exit 2 ;; esac
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
agent="$root/dist/deviceshare-agent-$suffix"
hub="$root/dist/deviceshare-hub-$suffix"
for binary in "$agent" "$hub"; do [[ -x "$binary" ]] || { echo "Missing $binary" >&2; exit 1; }; done
workspace="$(mktemp -d)"
trap 'rm -rf "$workspace"' EXIT
stage="$workspace/root"
mkdir -p "$stage/usr/local/bin" "$stage/usr/local/share/deviceshare" "$stage/usr/local/share/doc/deviceshare"
install -m 0755 "$agent" "$stage/usr/local/bin/deviceshare-agent"
install -m 0755 "$hub" "$stage/usr/local/bin/deviceshare-hub"
install -m 0644 config/agent.example.json "$stage/usr/local/share/deviceshare/agent.example.json"
install -m 0644 docs/INSTALL_NATIVE.md "$stage/usr/local/share/doc/deviceshare/INSTALL_NATIVE.md"
install -m 0644 SECURITY.md "$stage/usr/local/share/doc/deviceshare/SECURITY.md"
mkdir -p release-assets
pkg="release-assets/DeviceShare-$suffix.pkg"
dmg="release-assets/DeviceShare-$suffix.dmg"
pkgbuild --root "$stage" --identifier "com.mttechservices.deviceshare.cli" --version "0.2.2" --install-location "/" "$pkg"
pkgutil --expand "$pkg" "$workspace/expanded"
test -s "$workspace/expanded/Bom"
pkgutil --payload-files "$pkg" | grep -q "usr/local/bin/deviceshare-agent"
pkgutil --payload-files "$pkg" | grep -q "usr/local/bin/deviceshare-hub"
folder="$workspace/diskimage"
mkdir -p "$folder"
ditto "$pkg" "$folder/DeviceShare-$suffix.pkg"
ditto docs/INSTALL_NATIVE.md "$folder/INSTALL_NATIVE.md"
ditto SECURITY.md "$folder/SECURITY.md"
hdiutil create -quiet -srcfolder "$folder" -volname "DeviceShare Installer" -format UDZO -ov "$dmg"
hdiutil verify -quiet "$dmg"
test -s "$pkg" && test -s "$dmg"
echo "macOS $suffix .pkg and .dmg verified (unsigned/unnotarized)."
