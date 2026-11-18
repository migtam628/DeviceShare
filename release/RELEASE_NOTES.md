# DeviceShare v0.2.0-alpha.10 — One-Step macOS Setup Preview

This prerelease simplifies the native Mac first-run experience: install,
enter an email/password, and DeviceShare configures the station automatically.
It remains for controlled testing, **not production deployment**.

- DeviceShare.app starts its local loopback-only Hub automatically on launch.
- One email/password form creates a local owner account on first run or signs in
  on subsequent runs; no setup-code handling or manual key entry is needed.
- After authentication, the app generates a unique station identity, pairs a
  private credential, discovers and locally approves OS-installed printer queues,
  and enables a persistent per-user background Agent.
- Existing station credentials, printer approvals and configuration are retained
  rather than rotated on every sign-in; conflicting legacy Agents are flagged.
- Serial and HID devices are **never automatically approved**.
- Advanced setup remains available for remote Hubs, manual pairing and repairs.
- SQLite backup and restore, Brother trays, Zebra ZPL and Windows PDF/PNG output
  from previous alphas are preserved.

## Packages

Native Apple Silicon/Intel Mac PKG/DMG, Windows x64 MSI/EXE, Debian/Ubuntu AMD64 DEB, and portable ZIP bundles are included. Check `SHA256SUMS.txt` before installing.

## Limitations and recovery guidance

Read [Backup and Recovery](../docs/BACKUP_RECOVERY.md) **before** upgrading or
restoring. Backups are not encrypted by the tool; protect them through approved
encrypted storage and operating-system access controls. Restore to a new path
while the Hub is stopped; verify printers and queued jobs before resuming work.

This one-sign-in setup is **macOS only**; Windows and Linux still use manual
configuration. An installed OS printer driver is required before the app can
discover its queue. Physical Brother/Zebra/Windows verification, Mac logout/reboot persistence,
real upgrade/restore drills, Developer ID signing/notarization, HID/serial
hardware tests and production monitoring remain open. A spooler accepting a
job is not proof that a physical page printed.

See [hardware acceptance](https://github.com/migtam628/DeviceShare/issues/1)
and [macOS setup](../docs/MAC_APP.md).
