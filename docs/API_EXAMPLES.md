# API integration examples

The hub provides `/docs` for its OpenAPI schema, and `GET /v1/jobs` for an authenticated audit trail.

## Simulated printer

```bash
python examples/send_job.py --agent station-01 --device sim:printer --operation simulate --text "Hello DeviceShare"
```

Check the local agent's `simulator_dir` for the binary output. This is a file generator, **not** a printer installed into the operating system.

## Zebra ZPL label

Add the exact printer name to `allowed_printers` on the agent, verify the OS sees the printer, then submit an approved ZPL label:

```bash
python examples/send_job.py --agent station-01 --device printer:Zebra --operation print_raw --file label.zpl
```

CUPS sends raw bytes with `lp -o raw`. The Windows implementation uses the raw print spooler. Physical success/label presence is not tracked.

## PDF packing slip (CUPS macOS/Linux)

```bash
python examples/send_job.py --agent station-01 --device printer:Office --operation print_document --file packing-slip.pdf --mime application/pdf
```

PDF document rendering on Windows needs a separate implementation; do not send PDFs to `print_raw` unless your printer natively understands PDF.

## Serial communication

Add the exact serial port (e.g. `COM3`, `/dev/ttyUSB0`) to the local agent config. For harmless loopback testing use `loop://` as a specifically approved port.

```bash
python examples/send_job.py --agent station-01 --device serial:loop:// --operation serial_exchange --text "HELLO" --baudrate 9600 --read-size 5
```

The returned `received_base64` value should decode to `HELLO`. For physical devices, the supported baud rates are restricted and the maximum reply size is 4096 bytes per request. **Never transmit arbitrary commands to safety-critical equipment.**

## API security

```http
POST /v1/jobs
X-API-Key: YOUR_PRIVATE_API_KEY
Content-Type: application/json
```

```json
{
  "agent_id": "station-01",
  "device_id": "sim:printer",
  "operation": "simulate",
  "data_base64": "SGVsbG8=",
  "idempotency_key": "order-123-label-1"
}
```

The caller must not assume status `accepted` proves the printer produced output. Job ID and timestamps can be used to reconcile physical processing.

For browser apps, send requests through your own trusted backend instead of embedding the hub API key in client-side JavaScript.

## Approved HID input read

Install the optional `hidapi` dependency (`pip install 'deviceshare[hid]'`).
Use the local agent's reported `hid:vvvv:pppp:hhhhhhhhhhhhhhhh` device ID, and add
that exact ID to `allowed_hid_devices` in the agent config. Restart the agent
for new config to take effect. Then request a short input report:

```bash
python examples/send_job.py --agent station-01 \\
  --device hid:1a2b:3c4d:0123456789abcdef --operation hid_read \\
  --read-size 64 --timeout-ms 500
```

Replace the sample ID with the discovered device's exact identifier. The
reported bytes arrive as `received_base64`. This is **input only**:
HID output reports, feature reports, keyboard injection, and unrestricted
USB bulk/control operations are not supported.
