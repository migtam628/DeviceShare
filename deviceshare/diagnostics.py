"""Non-destructive, actionable diagnostics for stations and printer queues.

Only reports observed state; never assumes a CUPS queue proves physical output.
No secrets, filesystem contents, or device commands are returned.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_diagnostics(
    agents: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []

    def add(code: str, severity: str, title: str, detail: str, action: str,
            href: str, *, agent_id: str = "", device_id: str = "") -> None:
        findings.append({
            "code": code, "severity": severity, "title": title,
            "detail": detail, "action": action, "href": href,
            "agent_id": agent_id, "device_id": device_id,
        })

    if not agents:
        add(
            "no-stations", "attention", "No stations registered",
            "Create a station in the Mac app or Devices page, pair it, and start its Agent.",
            "Open station setup", "/devices",
        )

    online = 0
    printers = 0
    approved = 0
    for agent in agents:
        aid = str(agent.get("agent_id", ""))[:80]
        active = agent.get("online") is True
        if not active:
            add(
                "agent-offline", "attention", "Station offline: " + aid,
                "The Hub cannot send jobs to this station. On its Mac, check Services, "
                "the station ID, and the saved pairing credential. Do not rotate tokens unnecessarily.",
                "Open station details", "/devices", agent_id=aid,
            )
            continue
        online += 1
        inventory = agent.get("devices", [])
        age = agent.get("inventory_age_seconds")
        if not inventory:
            add(
                "no-inventory", "attention", "Waiting for device scan: " + aid,
                "Agent connected, but the Hub has not received hardware inventory yet. "
                "Request a safe refresh or check local OS permissions.",
                "Refresh station inventory", "/diagnostics", agent_id=aid,
            )
            continue
        if isinstance(age, (int, float)) and age > 90:
            add(
                "inventory-stale", "attention", "Device inventory is stale: " + aid,
                "Last hardware scan is over 90 seconds old. The agent normally reports "
                "every 30 seconds; request a refresh or check agent logs.",
                "Refresh station inventory", "/diagnostics", agent_id=aid,
            )
        station_printers = [d for d in inventory if d.get("kind") == "printer"]
        printers += len(station_printers)
        approved += sum(d.get("allowed") is True for d in station_printers)
        if not station_printers:
            add(
                "no-printers", "attention", "No printers discovered: " + aid,
                "Add a printer in the operating system's printer settings, then scan "
                "again in DeviceShare.app. Printer access still requires local approval.",
                "Open Printer Center", "/printers", agent_id=aid,
            )
        for device in station_printers:
            label = str(device.get("label") or device.get("id", "Printer"))[:100]
            did = str(device.get("id", ""))[:300]
            state = device.get("state", "unknown")
            if state == "disabled":
                add(
                    "printer-disabled", "attention", "Printer queue disabled: " + label,
                    "The OS print queue is disabled. Inspect the device and its CUPS/Windows "
                    "printer settings before resubmitting a job.",
                    "View printer", "/printers", agent_id=aid, device_id=did,
                )
            if device.get("allowed") is False:
                add(
                    "printer-unapproved", "attention", "Printer not approved: " + label,
                    "The Agent local allowlist denies this printer. Approve it in "
                    "DeviceShare.app → Printers, save approvals and restart the Agent.",
                    "View printer", "/printers", agent_id=aid, device_id=did,
                )
            if state not in ("enabled", "disabled"):
                add(
                    "printer-state-unknown", "info", "Printer status unverified: " + label,
                    "This platform or queue has not supplied a reliable enabled/disabled "
                    "state. Confirm physical power and connection before printing.",
                    "View printer", "/printers", agent_id=aid, device_id=did,
                )

    # Job state is separate from printer queue state. A print-job 'accepted'
    # result is spooler acceptance only, never a paper-output acknowledgment.
    uncertain = [j for j in jobs if j.get("status") == "unknown"]
    failed = [j for j in jobs if j.get("status") == "failed"]
    if uncertain:
        add(
            "uncertain-jobs", "attention", str(len(uncertain)) + " uncertain job(s)",
            "A connection was interrupted after dispatch may have begun. Check the "
            "OS spooler and physical output before deciding whether to submit a new job. "
            "DeviceShare will not automatically retry these jobs.",
            "Review activity", "/jobs",
        )
    if failed:
        add(
            "failed-jobs", "attention", str(len(failed)) + " failed job(s)",
            "Review the agent error details and local printer settings. An automatic "
            "retry could duplicate a physical print, so inspect each job first.",
            "Review activity", "/jobs",
        )

    if online and printers and not any(f["severity"] == "attention" for f in findings):
        add(
            "ready-to-test", "info", "Ready for a physical print check",
            "The Hub sees a connected Agent and discovered print queues. This does "
            "not prove the printer is powered on or that a page has printed.",
            "Print one test page", "/studio",
        )
    elif not online and agents:
        add(
            "offline-summary", "info", "No live Agent connection",
            "The Hub responds, but it cannot currently deliver jobs to a station. "
            "Start the Agent on the machine containing the printer.",
            "Open station status", "/devices",
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall": "attention" if any(f["severity"] == "attention" for f in findings) else "observed",
        "counts": {
            "stations": len(agents), "online_stations": online,
            "discovered_printers": printers, "approved_printers": approved,
            "unknown_jobs": len(uncertain), "failed_jobs": len(failed),
        },
        "findings": findings[:100],
        "disclaimer": "Device status is observational. OS queue acceptance is not proof of paper output.",
    }
