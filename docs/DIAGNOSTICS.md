# DeviceShare diagnostics & printer checks (alpha.6)

DeviceShare's **Diagnostics** screen shows actionable observations from the Hub, connected agents, and the last 100 job records. It **never claims to have detected physical paper output**.

## Quick use

1. Open DeviceShare.app on your Mac → **Diagnostics**, or sign in to the browser Console → **Diagnostics**.
2. Click **Run Checks**. This reads live station connection, the most recently reported hardware scan and job states.
3. Review the recommended action for each finding. No action is automatically executed.
4. If a station's hardware state is old, use **Rescan Station Devices** (Mac app) or **Rescan** (browser).
5. Run checks again. A successful scan does not confirm the physical printer is ready; inspect paper output separately.

The browser can copy a redacted diagnostics summary; it does not include administrator keys, station tokens, passwords or binary job payloads.

### What each diagnostic means

| Finding | Meaning | Safe next step |
| --- | --- | --- |
| Offline station | No live authenticated WebSocket is registered at the Hub | Confirm Agent started on the machine and matches saved station ID/token |
| No or stale inventory | No inventory received, or last report is older than 90 seconds | Request a safe rescan; check agent log if still stale |
| Queue disabled | CUPS or another OS reports the queue disabled | Examine the printer and OS queue settings; do not force-retry jobs |
| Queue not accepting | CUPS may report an enabled queue that is rejecting new requests | Inspect/correct local CUPS accepting status before sending print |
| Printer not approved | Agent configuration explicitly excludes a discovered printer | In Mac Printers page enable **Approved**, save and restart Agent |
| Unknown printer state | OS did not provide a reliable queue state | Confirm OS queue and physical device manually |
| Unknown job | Job may have been sent before a connection broke | Reconcile OS spooler and actual physical output before creating a new job |
| Failed job | Agent reported an error | Read Activity details and remedy the root cause before manually retrying |

### Remote scan safety

`POST /v1/agents/{station_id}/refresh` requires an authenticated administrator. It can request **read-only local device enumeration** from an online Agent, with a 10-second rate limit. It does not issue shell commands, grant device access, pair stations, reset tokens, install drivers, or resend print jobs.

The agent additionally reports whether discovered printers, serial devices and HID inputs are *locally allowlisted*. This is device-approval metadata, not the list of secrets or credentials. Existing alpha.5 agents may not report it; the UI shows **Approval not reported** rather than assuming approved or denied. Restart the Agent using alpha.6 to get full diagnostics.

### CUPS queue status is not physical availability

Two independent read-only checks are used on macOS/Linux:
- `lpstat -p`: reports queue enabled/disabled state
- `lpstat -a`: reports whether the queue accepts requests

Neither API proves that the USB/network printer is awake, has paper, receives a print job, or physically printed. The Agent will reject a known disabled/non-accepting queue for the new test-page API, but an OS can still accept a job for a disconnected printer.

### Privacy and security

- Diagnostics endpoints are authenticated and honor browser session CSRF protections for actions.
- Diagnostics include current station ID, printer queue labels, queue state and recent job status, but no secret keys, passwords or print payloads.
- Agent refresh does not automatically reprint any uncertain job.
- Hub authentication and private user files are unchanged.
- The Hub must remain on loopback or behind trusted HTTPS for remote use.

### Remaining acceptance tests

The Mac mini owner has verified the alpha.5 login, automatic Agent reconnection after restarting, a real printer test page, and browser login persistence. Still unverified: restart after full logout/reboot, printer-specific Zebra/Brother queue options, tray selection, Windows PDF rendering, and macOS signing/notarization. Track these separately in GitHub issues #1 and #2.

**If a diagnostic says "ready to test", it means the Hub observes a connected station and configured queue, not that printing physically succeeded.**
