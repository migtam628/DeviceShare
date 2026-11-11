"""Submit a file or a text command to DeviceShare without extra dependencies.

Examples:
    python examples/send_job.py --device sim:printer --operation simulate --text 'hello'
    python examples/send_job.py --device printer:Zebra --operation print_raw --file label.zpl
    python examples/send_job.py --device printer:Office --operation print_document --file slip.pdf --mime application/pdf
    python examples/send_job.py --device serial:COM3 --operation serial_exchange --text '?ID' --read-size 64
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default="station-01")
    parser.add_argument("--device", required=True)
    parser.add_argument("--operation", required=True,
                        choices=["simulate", "print_raw", "print_document", "serial_exchange", "hid_read"])
    payload = parser.add_mutually_exclusive_group(required=False)
    payload.add_argument("--file")
    payload.add_argument("--text")
    parser.add_argument("--mime", choices=["application/pdf", "image/png"])
    parser.add_argument("--baudrate", type=int, default=9600)
    parser.add_argument("--read-size", type=int, default=0)
    parser.add_argument("--timeout-ms", type=int, default=500)
    parser.add_argument("--idempotency-key")
    args = parser.parse_args()

    if args.operation == "hid_read":
        if args.file is not None or args.text is not None:
            parser.error("hid_read does not accept outgoing data")
    elif args.file is None and args.text is None:
        parser.error("--file or --text is required for this operation")
    data = open(args.file, "rb").read() if args.file else (args.text or "").encode("utf-8")
    if len(data) > 1024 * 1024:
        parser.error("file/text must be <=1 MiB")
    options = {}
    if args.operation == "print_document":
        if not args.mime:
            parser.error("--mime required for print_document")
        options["mime_type"] = args.mime
    if args.operation == "serial_exchange":
        options.update(baudrate=args.baudrate, read_size=args.read_size)
    if args.operation == "hid_read":
        options.update(read_size=args.read_size or 64, timeout_ms=args.timeout_ms)
    body = {
        "agent_id": args.agent,
        "device_id": args.device,
        "operation": args.operation,
        "data_base64": base64.b64encode(data).decode(),
        "options": options,
    }
    if args.idempotency_key:
        body["idempotency_key"] = args.idempotency_key
    token = os.getenv("DEVICESHARE_API_KEY")
    if not token:
        parser.error("DEVICESHARE_API_KEY must be set")
    url = os.getenv("DEVICESHARE_URL", "http://127.0.0.1:8765").rstrip("/") + "/v1/jobs"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST",
        headers={"X-API-Key": token, "Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(json.dumps(json.load(resp), indent=2))
    except urllib.error.HTTPError as exc:
        print(f"Request failed HTTP {exc.code}: {exc.read().decode(errors='replace')}",
              file=sys.stderr)
        raise SystemExit(1) from exc

if __name__ == "__main__":
    main()
