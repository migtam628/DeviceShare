# DeviceShare v0.2.0-alpha.7 — Connection Recovery

This prerelease improves station reliability and makes device scan failures visible.

- After a temporary OS/driver enumeration error, the Agent keeps running and retries on the next scan or an authorized refresh request.
- Diagnostics reports a failed scan without silently treating the last known devices as current. Generated test pages and custom text jobs are blocked until a successful scan.
- Broken inventory WebSocket sends force a reconnection with bounded jittered backoff; malformed Hub messages are ignored.
- The macOS app can recheck station connectivity and warns when a competing legacy Agent is running.
- Failed and uncertain print jobs are **never automatically resent**.

## Packages

Native Apple Silicon/Intel Mac PKG/DMG, Windows x64 MSI/EXE, Debian/Ubuntu AMD64 DEB, and portable ZIP bundles are included. Check `SHA256SUMS.txt` before installing.

## Known limitations

This is an unsigned/unnotarized alpha. macOS full logout/reboot persistence, Brother dual-tray selection, Zebra 4×6 label output, Windows PDF/PNG rendering, HID/serial hardware acceptance, and proof of physical printing remain unverified. An operating system accepting a job is not evidence of paper output.

See [macOS setup](../docs/MAC_APP.md), [diagnostics](../docs/DIAGNOSTICS.md), and [hardware acceptance](https://github.com/migtam628/DeviceShare/issues/1).
