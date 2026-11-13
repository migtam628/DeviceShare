# Changelog

## v0.2.0-alpha.6 — Diagnostics and Printer Center (2026-11-12)

- Added actionable station and printer diagnostics for offline agents, stale inventory, missing local approvals, disabled/non-accepting queues, and uncertain/failed jobs.
- Added authenticated, rate-limited inventory refresh to the live Agent; never runs commands or replays print jobs.
- Added approved/accepting queue states to the Hub, printer selection and safeguards.
- Added web Diagnostics screen with safe station rescans and redacted support summary.
- Added native macOS Diagnostics section with live Hub findings, service status and station rescan.
- Added automated checks for approval flags, connection states, CUPS metadata and CSRF.
- Mac mini user confirmed alpha.5 activation, Agent reconnection, physical test printing and remembered browser login. Hardware-specific acceptance remains open.

## v0.2.0-alpha.5 — Guided activation and owner sign-in (2026-11-11)

- Replaced the Console's administrator API-key sign-in form with email and password, including a first-run activation gate, account recovery and setup-progress checklist.
- Added local-only one-time 10-minute activation/recovery codes; the Mac app can activate the account without exposing its host key to the browser.
- Added salted scrypt password hashing, five-failure login lockout, origin/CSRF validation, and password-bound revocable browser sessions.
- Added macOS guided owner activation, account-state detection and Settings recovery-code generation.
- Preserved existing station tokens, job ledger and machine-to-machine API integrations across upgrade.
- Added auth migration and local recovery instructions. No email verification, password-reset email or enterprise RBAC in this alpha.

## v0.2.0-alpha.4 — Print Studio and safer remembered login (2026-11-11)

- Reorganized the browser UI into distinct Overview, Printers, Print Studio, Activity, Devices, and Settings routes.
- Added selectable printer inventory and CUPS queue enabled/disabled metadata, explicitly distinct from hardware online status.
- Added bounded PDF test page generator, custom text-to-PDF printing, and PDF/PNG file upload to selected approved printers.
- Added validated copies (1–5), Letter/A4, and single/duplex CUPS options.
- Redesigned native macOS SwiftUI UI with a six-section sidebar, printer selection/approval, test print and custom document actions.
- Added optional remote Hub administrator key persistence in macOS Keychain and revocable, HttpOnly remembered browser sessions with CSRF protection.
- Added automated tests for PDF rendering, CUPS arguments, print API dispatch, remembered sessions and console page routes.
- Actual printer output and remote Keychain behavior still require field validation; Windows PDF document printing is not yet implemented.

## v0.2.0-alpha.3 — Native macOS DeviceShare.app (2026-11-11)

- Added a real SwiftUI management window installed at `/Applications/DeviceShare.app`, packaged for Apple Silicon and Intel Macs.
- Added first-run configuration, optional loopback-only local hub with a private generated admin key, station pairing/rotation and token file storage.
- Added explicit local printer, serial and input-only HID approvals, backed by frozen-agent JSON discovery.
- Added opt-in, per-user launchd startup/shutdown for agent and local hub, with private logs and configuration under Application Support.
- macOS PKG now installs app and legacy command-line symlinks; DMG includes the drag-install app and PKG.
- Added secure `--api-key-file` hub startup and `--list-devices` agent CLI, including tests and cross-platform frozen-binary smoke validation.
- GitHub Actions verified all four platforms, package contents, checksums, and GitHub prerelease publication.
- **Known limitation:** the macOS app is ad-hoc signed, not Developer-ID signed/notarized. Real-device and first-run acceptance testing remains outstanding.

## v0.2.0-alpha.2 — Native installer prerelease (2026-11-11)

- Added Windows x64 WiX MSI and Inno Setup EXE installers.
- Added Apple Silicon/Intel macOS PKG installers and DMG images containing the PKG.
- Added Debian/Ubuntu AMD64 DEB installer.
- Installed packages contain both the DeviceShare Hub and Agent, example config and setup documentation.
- Release uses automated unit tests, cross-platform frozen executable smoke tests, native package validation, signed-by-hash SHA256 manifest, and GitHub Release uploads.
- Installation leaves pairing, device approval and service activation to the administrator; no network listeners are started automatically.
- All native packages are unsigned; macOS packages are not notarized, and physical-hardware acceptance is still pending.

## Unreleased - 0.2.0 development

### Added
- Browser-based DeviceShare management console at `/dashboard`.
- Station-specific agent credentials with secure token hashes, rotation and revocation.
- Periodic agent hardware inventory refresh.
- Added agent token-file support, dashboard packaging and pairing/security tests.
- Legacy shared agent secret is now optional and never overrides a paired station.

### New portable release work (unreleased)
- Restricted, allowlisted HID input report backend (read-only).
- Per-user background startup scripts for Linux, macOS and Windows.
- Portable ZIP packaging with frozen hub/agent startup and dashboard smoke tests.
- GitHub portable preview and prerelease gating workflows with checksum generation.

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
