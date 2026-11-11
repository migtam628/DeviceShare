#!/bin/bash
# Build a true macOS SwiftUI application, Apple PKG and installable DMG.
set -euo pipefail
if [[ $# -ne 1 ]]; then echo "Usage: build_native_macos.sh macos-arm64|macos-x64" >&2; exit 2; fi
suffix="$1"
case "$suffix" in
  macos-arm64) target="arm64-apple-macos13.0" ;;
  macos-x64) target="x86_64-apple-macos13.0" ;;
  *) echo "Invalid macOS suffix" >&2; exit 2 ;;
esac

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
agent="$root/dist/deviceshare-agent-$suffix"
hub="$root/dist/deviceshare-hub-$suffix"
for binary in "$agent" "$hub"; do [[ -x "$binary" ]] || { echo "Missing $binary" >&2; exit 1; }; done

workspace="$(mktemp -d)"
trap 'rm -rf "$workspace"' EXIT
stage="$workspace/root"
app="$stage/Applications/DeviceShare.app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources" \
  "$stage/usr/local/bin" "$stage/usr/local/share/deviceshare" \
  "$stage/usr/local/share/doc/deviceshare"

cp macos/DeviceShareApp/Info.plist "$app/Contents/Info.plist"
# Compile a real native AppKit/SwiftUI executable, not a webpage wrapper.
xcrun swiftc -swift-version 5 -parse-as-library -O \
  -target "$target" \
  -framework AppKit -framework SwiftUI -framework Combine -framework Security \
  macos/DeviceShareApp/DeviceShareController.swift \
  macos/DeviceShareApp/DeviceShareMacApp.swift \
  -o "$app/Contents/MacOS/DeviceShare"
chmod 755 "$app/Contents/MacOS/DeviceShare"
install -m 0755 "$agent" "$app/Contents/MacOS/deviceshare-agent"
install -m 0755 "$hub" "$app/Contents/MacOS/deviceshare-hub"

# Ad-hoc code signing enables local platform integrity checks. It is NOT
# Apple Developer ID signing and does not provide notarization/Gatekeeper trust.
codesign --force --deep --sign - "$app"
codesign --verify --deep --strict --verbose=2 "$app"
test "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$app/Contents/Info.plist")" = "DeviceShare"
test "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleVersion' "$app/Contents/Info.plist")" = "4"
file "$app/Contents/MacOS/DeviceShare"
"$app/Contents/MacOS/deviceshare-agent" --version
"$app/Contents/MacOS/deviceshare-hub" --version

# Keep the previous command-line paths working without copying 30MB twice.
ln -s /Applications/DeviceShare.app/Contents/MacOS/deviceshare-agent "$stage/usr/local/bin/deviceshare-agent"
ln -s /Applications/DeviceShare.app/Contents/MacOS/deviceshare-hub "$stage/usr/local/bin/deviceshare-hub"
install -m 0644 config/agent.example.json "$stage/usr/local/share/deviceshare/agent.example.json"
install -m 0644 docs/INSTALL_NATIVE.md "$stage/usr/local/share/doc/deviceshare/INSTALL_NATIVE.md"
install -m 0644 docs/MAC_APP.md "$stage/usr/local/share/doc/deviceshare/MAC_APP.md"
install -m 0644 SECURITY.md "$stage/usr/local/share/doc/deviceshare/SECURITY.md"

mkdir -p release-assets
pkg="release-assets/DeviceShare-$suffix.pkg"
dmg="release-assets/DeviceShare-$suffix.dmg"
pkgbuild --root "$stage" \
  --identifier "com.mttechservices.deviceshare.cli" \
  --version "0.2.4" \
  --install-location "/" "$pkg"

pkgutil --expand "$pkg" "$workspace/expanded"
test -s "$workspace/expanded/Bom"
pkgutil --payload-files "$pkg" | grep -Fq "Applications/DeviceShare.app/Contents/MacOS/DeviceShare"
pkgutil --payload-files "$pkg" | grep -Fq "Applications/DeviceShare.app/Contents/MacOS/deviceshare-agent"
pkgutil --payload-files "$pkg" | grep -Fq "usr/local/bin/deviceshare-agent"

folder="$workspace/diskimage"
mkdir -p "$folder"
ditto "$app" "$folder/DeviceShare.app"
ditto "$pkg" "$folder/DeviceShare-$suffix.pkg"
ditto docs/INSTALL_NATIVE.md "$folder/INSTALL_NATIVE.md"
ditto docs/MAC_APP.md "$folder/MAC_APP.md"
ln -s /Applications "$folder/Applications"
hdiutil create -quiet -srcfolder "$folder" -volname "DeviceShare" -format UDZO -ov "$dmg"
hdiutil verify -quiet "$dmg"
test -s "$pkg" && test -s "$dmg"
echo "Native SwiftUI DeviceShare.app, PKG and DMG verified for $suffix."
