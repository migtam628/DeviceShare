"""Submit a sample job to the simulated printer after starting hub + agent."""
import base64
import json
import os
import urllib.request

base = os.getenv("DEVICESHARE_URL", "http://127.0.0.1:8765").rstrip("/")
token = os.environ["DEVICESHARE_API_KEY"]
data = json.dumps({
    "agent_id": "station-01",
    "device_id": "sim:printer",
    "operation": "simulate",
    "data_base64": base64.b64encode(b"DeviceShare test output\\n").decode(),
    "idempotency_key": "first-simulator-demo",
}).encode()
request = urllib.request.Request(
    base + "/v1/jobs", data=data, method="POST",
    headers={"X-API-Key": token, "Content-Type": "application/json"}
)
with urllib.request.urlopen(request, timeout=10) as response:
    print(json.dumps(json.load(response), indent=2))
