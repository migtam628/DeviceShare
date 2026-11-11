# Changelog

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
