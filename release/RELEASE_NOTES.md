# DeviceShare v0.2.0-alpha.9 — Hub Recovery Preview

This prerelease adds local disaster-recovery commands to the packaged Hub and
automated verification of that workflow. It remains for controlled testing,
**not production deployment**.

- `deviceshare-hub --db <existing-db> --backup-db <new-file>` creates a private
  consistent snapshot using SQLite's online backup API while the Hub is live.
- `deviceshare-hub --verify-db <file>` checks SQLite integrity and required
  DeviceShare tables without changing the source file.
- `deviceshare-hub --restore-db <backup> --restore-to <new-file>` restores only
  into a fresh path; refuses existing databases, symlinks and SQLite sidecars.
- Unix snapshot files are mode 0600; backup contents include private account,
  station and print data and must be kept confidential.
- Unit tests cover invalid input, overwrite prevention, preservation of credentials,
  uncertain-job recovery and command-line execution.
- Native installer CI smoke tests now verify that frozen Hub executables can
  back up, validate and restore their own running database.
- Alpha.8 Brother tray, Zebra 4×6 and Windows PDF/PNG features remain; hardware
  acceptance is still required before use with customer orders.

## Packages

Native Apple Silicon/Intel Mac PKG/DMG, Windows x64 MSI/EXE, Debian/Ubuntu AMD64 DEB, and portable ZIP bundles are included. Check `SHA256SUMS.txt` before installing.

## Recovery guidance and limitations

Read [Backup and Recovery](../docs/BACKUP_RECOVERY.md) **before** upgrading or
restoring. Backups are not encrypted by the tool; protect them through approved
encrypted storage and operating-system access controls. Restore to a new path
while the Hub is stopped; verify printers and queued jobs before resuming work.

Physical Brother/Zebra/Windows verification, Mac logout/reboot persistence,
real upgrade/restore drills, Developer ID signing/notarization, HID/serial
hardware tests and production monitoring remain open. A spooler accepting a
job is not proof that a physical page printed.

See [hardware acceptance](https://github.com/migtam628/DeviceShare/issues/1)
and [macOS setup](../docs/MAC_APP.md).
