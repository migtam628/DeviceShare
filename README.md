# DeviceShare

**DeviceShare** is a self-hosted peripheral bridge for sending print jobs and communicating with locally attached hardware from websites, POS applications, inventory systems, and remote servers.

**Project status: v0.1.0 alpha source / work in progress.** There is not yet a production-ready installer or stable GitHub Release. Do not connect to untrusted devices, commands, or the open internet.

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
| Direct HID/USB bulk/USB control transfers | **Not implemented yet** |
| Windows PDF print rendering | **Not implemented yet** |
| Printer status monitoring / proof of print | **Not implemented yet** |
| Device pairing, role-based auth, installers | **Not implemented yet** |

For protocol details, security, and the roadmap, read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Development setup (Python 3.11+)

```bash
git clone https://github.com/migtam628/DeviceShare.git
cd DeviceShare
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,usb]"
cp config/agent.example.json config/agent.json
```

On Windows, use `.venv\Scripts\Activate.ps1` and `copy config\agent.example.json config\agent.json`; install `.[dev,windows,usb]` for printer support.

Generate **two different random secrets** and make them available to the hub and agent. For example, in Bash:

```bash
export DEVICESHARE_API_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
export DEVICESHARE_AGENT_TOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
```

Save these locally in a password manager or a protected, untracked environment file. Do not commit real tokens. Open two terminals that have access to the same `DEVICESHARE_AGENT_TOKEN`; the hub also needs `DEVICESHARE_API_KEY`.

**Terminal 1: hub**

```bash
deviceshare-hub
```

Hub defaults to `127.0.0.1:8765`, with the API documentation at http://127.0.0.1:8765/docs.

**Terminal 2: agent**

```bash
deviceshare-agent --config config/agent.json
```

It should connect to the local hub and register the simulated printer. To print a safe test payload (a file, not real paper):

```bash
python examples/submit_simulated_job.py
```

Check `data/simulator/` for the emitted `.bin` file, and inspect the job ledger:

```bash
curl -H "X-API-Key: $DEVICESHARE_API_KEY" http://127.0.0.1:8765/v1/jobs
```

For production integrations, call `POST /v1/jobs` using the JSON schema shown in `/docs`. Operations are `simulate`, `print_raw`, `print_document`, and `serial_exchange`. All payloads are base64-encoded and limited to 1 MiB. For real devices, add **specific** names/ports to the agent's `allowed_printers` / `allowed_serial_ports` configuration. The hub alone cannot override local device approvals.

**Serial loopback test:** set `"allowed_serial_ports": ["loop://"]` in the agent config; then submit a `serial_exchange` job to `serial:loop://` with `"options": {"baudrate": 9600, "read_size": 5}` and base64 data `aGVsbG8=`. The returned base64 response should decode to `hello`.

## Remote access

The local agent initiates an **outbound** WebSocket connection to the hub. For deployment across sites, configure the agent `hub_url` to a hub HTTPS URL behind TLS and a secured reverse proxy. The agent will reject insecure non-loopback HTTP URLs by default. The alpha uses shared agent-token authentication and is **not hardened for a public multi-tenant service**.

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

GitHub Actions tests on Windows, macOS, and Linux. On pushes of version tags like `v0.1.0-alpha.1`, the release workflow attempts to build single-file agent and hub binaries, and publish the results on [GitHub Releases](https://github.com/migtam628/DeviceShare/releases). **These build pipelines are not yet verified on all OSs; do not assume a tagged release succeeded until Actions passes.**

Current priority: validate continuous integration, add device pairing, then implement restricted HID/USB plugins and actual user-facing desktop setup.

## Intended integrations

- E-commerce fulfillment: packing slips, shipping labels, receipt printers.
- Point-of-sale: receipt printers, barcode scanners, scales, customer displays.
- IT field service: serial consoles, device inventory, vendor-specific diagnostics.
- Testing: local virtual peripherals and generated test output.

## Security

DeviceShare never exposes an arbitrary remote shell. The current API grants holders of its API key permission to submit jobs to **locally approved devices**, so protect that key carefully. Do not use serial or print jobs to drive dangerous equipment without independent safety controls.

**Licensing:** No software license has been selected yet. Public source code does not by itself grant broad reuse permissions.
