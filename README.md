# DeviceShare

**DeviceShare** is a self-hosted peripheral bridge for sending print jobs and communicating with locally attached hardware from websites, POS applications, inventory systems, and remote servers.

**Project status: v0.2.0-alpha.4.** Native macOS SwiftUI app and cross-platform installers are available as a prerelease. The Mac app is ad-hoc signed, not Developer-ID-signed/notarized; other packages are unsigned and the project is not production-hardened. Do not connect to untrusted devices, commands, or the open internet.

## Native installation packages

**[Download DeviceShare v0.2.0-alpha.4](https://github.com/migtam628/DeviceShare/releases/tag/v0.2.0-alpha.4)**

| Platform | Native installer |
| --- | --- |
| Windows x64 | [MSI](https://github.com/migtam628/DeviceShare/releases/download/v0.2.0-alpha.4/DeviceShare-windows-x64.msi) or [setup EXE](https://github.com/migtam628/DeviceShare/releases/download/v0.2.0-alpha.4/DeviceShare-Setup-windows-x64.exe) |
| macOS Apple Silicon | [DMG](https://github.com/migtam628/DeviceShare/releases/download/v0.2.0-alpha.4/DeviceShare-macos-arm64.dmg) or [PKG](https://github.com/migtam628/DeviceShare/releases/download/v0.2.0-alpha.4/DeviceShare-macos-arm64.pkg) |
| macOS Intel | [DMG](https://github.com/migtam628/DeviceShare/releases/download/v0.2.0-alpha.4/DeviceShare-macos-x64.dmg) or [PKG](https://github.com/migtam628/DeviceShare/releases/download/v0.2.0-alpha.4/DeviceShare-macos-x64.pkg) |
| Debian / Ubuntu AMD64 | [DEB](https://github.com/migtam628/DeviceShare/releases/download/v0.2.0-alpha.4/DeviceShare_0.2.0.alpha4_amd64.deb) |

Read **[native installer setup](docs/INSTALL_NATIVE.md)** and compare downloads with the release's `SHA256SUMS.txt`. Installer files include both the Agent and Hub; they do not automatically authorize peripherals or install OS drivers. Portable ZIP builds remain available.

### DeviceShare.app on macOS

The Apple Silicon and Intel packages now include a **real SwiftUI application** at `/Applications/DeviceShare.app`, alongside the headless tools. The DMG contains the app for dragging into Applications or a PKG to install both the app and command-line links.

Launch it from Applications and follow these steps:

1. **Start Local Hub** (or enter a trusted remote HTTPS hub URL).
2. Enter and save a station ID; **Pair / Rotate Credential** using the local hub key or a remote administrator key.
3. Scan and selectively approve local printers, serial devices and HID inputs.
4. **Start / Restart** the agent under Background services; confirm its online state in the web dashboard.

User configuration, credentials, logs and database live under `~/Library/Application Support/DeviceShare/`. The app starts services **only when you explicitly request it**. See the [macOS walkthrough](docs/MAC_APP.md). The app is ad-hoc signed for platform integrity; it is not Apple Developer ID–signed or notarized.

## Print Studio and separated console pages (alpha.4)

Open the local Hub at `http://127.0.0.1:8765/dashboard` and use the sidebar:

- **Overview:** connected stations, printer counts and job health.
- **Printers:** choose a discovered OS queue on an online agent.
- **Print Studio:** send a DeviceShare PDF test page, custom text PDF, or PDF/PNG document with paper size, copies and duplex options.
- **Activity:** job history, OS spooler results and failures.
- **Devices:** discovery and station token management.
- **Settings:** remember a revocable 30-day browser session (HttpOnly cookie, not a stored raw API key), sign out other browsers and adjust refresh interval.

On macOS the native `DeviceShare.app` also has a sidebar with a selectable **Printers** page and **Print Studio**. Print jobs still require exact station-local allowlist approval and physical output verification. CUPS queue enabled does not imply a physically available printer. Windows PDF/PNG print rendering remains pending.

## Current implementation

| Capability | Alpha status |
| --- | --- |
| FastAPI HTTP API + Swagger docs | Implemented |
| Authenticated outbound WebSocket agents | Implemented |
| SQLite-backed persistent job queue | Implemented |
| Idempotency key per agent | Implemented |
| Simulated printer (output to local `.bin`) | Implemented |
| CUPS raw data (e.g. ZPL) on macOS/Linux | Implemented; requires local CUPS |
| CUPS PDF/PNG document submission | Implemented; requires local CUPS |
| Windows RAW printer spooler | Implemented; requires optional pywin32 |
| Serial ports: enumerate, write, receive | Implemented; requires explicit port allowlist |
| USB hardware: VID/PID discovery | Read-only optional pyusb |
| HID input reports | Implemented: read-only, exact local allowlist; requires `hidapi` |
| HID output/feature, USB bulk/control | **Not implemented yet** |
| Windows PDF print rendering | **Not implemented yet** |
| Printer status monitoring / proof of print | **Not implemented yet** |
| Station-specific tokens, rotation, revocation | Implemented in hub API and dashboard |
| Web management dashboard | Implemented (inventory, jobs, station credentials) |
| Per-user agent auto-start | Linux systemd, macOS launchd, Windows Scheduled Task scripts |
| Native installer packages (MSI, EXE, DMG, PKG, DEB) | Released in alpha.3 |
| macOS SwiftUI setup, station pairing, device approvals, local hub and launchd controls | Implemented in alpha.3 |
| Windows/Linux desktop GUI, code signing, notarization | **Not implemented yet** |
| Multi-user RBAC and production-grade monitoring | **Not implemented yet** |

For protocol details, security, and the roadmap, read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Development setup (Python 3.11+)

```bash
git clone https://github.com/migtam628/DeviceShare.git
cd DeviceShare
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,usb,hid]"
cp config/agent.example.json config/agent.json
```

On Windows, use `.venv\Scripts\Activate.ps1` and `copy config\agent.example.json config\agent.json`; install `.[dev,windows,usb,hid]` for printer support.

### 1. Start the hub (Terminal 1)

Create a random **administrator API key**. Only the hub needs this secret.

```bash
export DEVICESHARE_API_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
deviceshare-hub
```

Hub defaults to http://127.0.0.1:8765. The API reference is at [`/docs`](http://127.0.0.1:8765/docs) and the **DeviceShare Dashboard** is at [`/dashboard`](http://127.0.0.1:8765/dashboard).

Keep this API key private and available to your API integrations. It is an administrator key that authorizes device jobs, credential creation, and revocation; it must **never** be embedded in a public web page.

### 2. Pair the first station

Use the web dashboard to enter the administrator key and generate a token for `station-01`, **or** create a token through the API from the hub host:

```bash
curl -sS -X POST -H "X-API-Key: $DEVICESHARE_API_KEY" \
  http://127.0.0.1:8765/v1/agents/station-01/credential
```

The response contains a unique station token shown **only once**. Save it privately in `config/agent.token` on the station and secure the file (macOS/Linux: `chmod 600 config/agent.token`). Never commit it or paste it into a support issue. The example configuration includes `"token_file": "./config/agent.token"`. Alternatively, set the station-specific `DEVICESHARE_AGENT_TOKEN` environment variable on the **agent machine**, not on the hub.

### 3. Start the local agent (Terminal 2)

```bash
deviceshare-agent --config config/agent.json
```

It connects outbound to the hub and reports discovered devices about every 30 seconds. The dashboard shows online agents, discovered peripherals, and the last 50 jobs. Rotation and revocation disconnect affected agents and deny use of old credentials.

For an end-to-end test, submit a safe simulator payload (a file, not real paper):

```bash
python examples/submit_simulated_job.py
```

Check `data/simulator/` for the emitted `.bin` file, and inspect the job ledger:

```bash
curl -H "X-API-Key: $DEVICESHARE_API_KEY" http://127.0.0.1:8765/v1/jobs
```

For production integrations, call `POST /v1/jobs` using the JSON schema shown in `/docs`. Operations are `simulate`, `print_raw`, `print_document`, `serial_exchange`, and read-only `hid_read`. All payloads are base64-encoded and limited to 1 MiB. For real devices, add **specific** names/ports to the agent's `allowed_printers`, `allowed_serial_ports`, or `allowed_hid_devices` configuration. The hub alone cannot override local device approvals.

**Serial loopback test:** set `"allowed_serial_ports": ["loop://"]` in the agent config; then submit a `serial_exchange` job to `serial:loop://` with `"options": {"baudrate": 9600, "read_size": 5}` and base64 data `aGVsbG8=`. The returned base64 response should decode to `hello`.

## Remote access

The local agent initiates an **outbound** WebSocket connection to the hub. For deployment across sites, configure the agent `hub_url` to a hub HTTPS URL behind TLS and a secured reverse proxy. The agent will reject insecure non-loopback HTTP URLs by default. The default is per-agent pairing with tokens stored as SHA-256 digests on the hub. For compatibility only, you may explicitly enable an older shared token by setting `DEVICESHARE_LEGACY_AGENT_TOKEN` on the hub; paired agents always require their own token. Disable legacy shared tokens in new deployments. **The alpha is not hardened for a public multi-tenant service.**

## Job delivery semantics

- `queued`: job stored, but not sent.
- `sent`: dispatch attempted.
- `accepted`: agent confirmed successful execution (for printing, **spooler acceptance**, not actual pages printed).
- `failed`: agent reported an execution error.
- `unknown`: dispatch may have occurred before disconnection; **never automatically resend without reconciliation**.

An idempotency key helps prevent duplicate API submissions. It does not guarantee exactly-once hardware execution.

## Development and GitHub Releases

```bash
python -m pytest -q
```

GitHub Actions tests on Windows, macOS, and Linux. The [portable preview workflow](https://github.com/migtam628/DeviceShare/actions/workflows/preview.yml) builds and smoke-tests Windows x64, Linux x64, Intel Mac and Apple Silicon Mac executables. On a matching tag like `v0.2.0-alpha.1`, the [release workflow](https://github.com/migtam628/DeviceShare/actions/workflows/release.yml) publishes ZIPs with checksums only after version validation, unit tests and portable smoke tests pass. See [agent installation](docs/INSTALL_AGENT.md).

Current priority: validate the new macOS app on real user sessions (including login persistence), complete real-printer/HID acceptance, add signing/notarization, develop Windows/Linux GUI onboarding and scoped API permissions.

## Intended integrations

- E-commerce fulfillment: packing slips, shipping labels, receipt printers.
- Point-of-sale: receipt printers, barcode scanners, scales, customer displays.
- IT field service: serial consoles, device inventory, vendor-specific diagnostics.
- Testing: local virtual peripherals and generated test output.

## Security

DeviceShare never exposes an arbitrary remote shell. The current administrator API key grants holders permission to provision agents and submit jobs to **locally approved devices**, so protect that key carefully. Do not use serial or print jobs to drive dangerous equipment without independent safety controls.

**Licensing:** No software license has been selected yet. Public source code does not by itself grant broad reuse permissions.
