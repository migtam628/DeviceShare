# Changelog

## Unreleased - 0.2.0 development

### Added
- Browser-based DeviceShare management console at `/dashboard`.
- Station-specific agent credentials with secure token hashes, rotation and revocation.
- Periodic agent hardware inventory refresh.
- Added agent token-file support, dashboard packaging and pairing/security tests.
- Legacy shared agent secret is now optional and never overrides a paired station.

### Remaining
- Native operating-system installers, production pairing approvals and RBAC, safe HID/USB plugins and multi-user audit.
- Release workflow binaries still require full verification.

## Unreleased - 0.1.0 alpha foundation

### Added
- Self-hosted FastAPI hub and SQLite job ledger.
- Outbound WebSocket-based local agent with mandatory token authentication.
- Printer discovery; CUPS raw/PDF/PNG submissions and optional Windows RAW spooler.
- Serial port discovery, authorized write/read, and loopback testing.
- USB VID/PID discovery (read-only, optional library).
- Simulator that writes job bytes to disk.
- Per-agent idempotency keys and no-blind-retry status model.
- CLI examples, docs, automated tests, and GitHub Actions release definitions.

### Limitations
- No direct USB or HID writes, native OS virtual printer, Windows PDF rendering, device pairing UI, or physical print-status verification.
- Release binaries and multi-platform CI are not yet independently validated.
