# DeviceShare alpha.8 — Printer Workflow Acceptance

Automated tests exercise CUPS option parsing, Hub dispatch, ZPL sanitization,
PDFium rasterization, and (on Windows CI) mocked Win32 driver submission.
**No CI runner can verify real paper output.** Do the following on your own
trusted printer stations before using customer orders.

## Brother two-tray printing (macOS/Linux, CUPS)

1. In the OS printer settings, install a driver/queue that exposes its actual
   input source. Run `lpoptions -p PRINTER_NAME -l` locally and find either
   `InputSlot` or `media-source`; note the exact names of your two trays.
2. Open DeviceShare.app or browser **Print Studio**, select the Brother queue,
   approve the printer locally and restart/rescan the Agent.
3. Confirm the **Paper source** selector reflects both actual trays. If none
   appear, use the printer default. DeviceShare does not invent tray names.
4. With non-sensitive test paper loaded, select Tray 1 and print one test page;
   physically verify its source, text, alignment and job status. Repeat for
   Tray 2, including a test on your two-tray Brother model.
5. Submit a short packing slip/PDF with two copies and confirm the requested
   tray and copy count. Deliberately select a now-removed tray and verify the
   Agent refuses the job rather than silently printing from another tray.

## Zebra 4×6 ZPL station label

1. Configure an approved Zebra-compatible OS queue for **RAW ZPL passthrough**;
   load **4×6 inch** labels and select that queue in the browser Print Studio.
2. Under **4×6 station label**, enter a test recipient, address and reference.
   Confirm the printer, then submit **one** label.
3. Inspect physical label size, print darkness, legibility, margins and correct
   destination. Do not use this label as shipping postage; it has no postage,
   carrier tracking, or delivery service. A paid, carrier-generated label must
   come from the shipping provider/integration.
4. If the queue is offline, disabled or rejected, fix the device; reconcile
   uncertain jobs before manually submitting another label.

## Windows PDF/PNG document printing

1. On a Windows x64 station, install the native Agent with the Windows printer
   driver and approve its queue.
2. Submit a one-page PDF test, two-page PDF, and one PNG with letter/A4 paper.
   Confirm the chosen driver, print sizing, margins, orientation and copies.
3. Test duplex on a capable printer and verify pages physically. Confirm that
   invalid PDF content, oversized raster pages and jobs larger than 1 MiB fail
   with a visible error. Windows paper-source selection is not yet supported.
4. Unplug the printer while a job is pending. Confirm Activity reports the OS
   response without automatic retries. Manually reconcile spooler and paper
   output before trying again.

## Installation, persistence and support gates

- On the Mac mini M1, confirm background Agent/Hub return after a **full logout
  and reboot**, with no old `com.deviceshare.agent` competing process.
- Upgrade an existing installation after backing up its private state. Verify
  user login, saved station token, approvals, sessions and job history remain.
- Keep DB and agent token backups private, test restoring them to a disposable
  test installation, and make sure a compromised machine key can be rotated.
- For public production distribution, obtain Apple Developer ID signing and
  notarization, and resolve Windows installer trust and deployment policy.
- Use GitHub Actions CI, native previews, and the release workflow to build
  installers. Publication is not equivalent to real-device acceptance.

Record station OS, printer model, driver name/version, exact CUPS tray keyword,
job ID, physical result, photos (no customer PII), and date in GitHub issues
[#1](https://github.com/migtam628/DeviceShare/issues/1) and
[#2](https://github.com/migtam628/DeviceShare/issues/2).
