# DeviceShare v0.2.0-alpha.8 — Print Workflow Preview

This prerelease expands printer capabilities for early hardware acceptance. It
does not assert that any of the new output paths have been physically verified.

- Brother two-tray workflow: macOS/Linux queues expose CUPS `InputSlot` or
  `media-source` options; the UI offers only reported tray names and the Agent
  verifies them again before submitting documents.
- Zebra 4×6: the browser Print Studio generates bounded RAW ZPL station labels
  for approved label queues. These **are not carrier-paid shipping labels**.
- Windows x64: PDF and PNG printing now renders document pages with bundled
  PDFium/Pillow, then submits raster pages using the selected printer driver.
  Supports A4/Letter, duplex and up to five copies. Windows tray selection
  remains unsupported.
- Cross-platform workflow tests cover source validation, generated ZPL,
  PDFium raster pages, and mocked Windows GDI driver dispatch.
- Connection recovery and fail-closed scan behavior from alpha.7 remain.
- Failed and uncertain print jobs are **never automatically resent**.

## Packages

Native Apple Silicon/Intel Mac PKG/DMG, Windows x64 MSI/EXE, Debian/Ubuntu AMD64 DEB, and portable ZIP bundles are included. Check `SHA256SUMS.txt` before installing.

## Known limitations

This is an unsigned/unnotarized alpha. macOS full logout/reboot persistence,
Brother physical tray selection, Zebra 4×6 label output, Windows PDF/PNG
output, HID/serial hardware, upgrade/recovery behavior and proof of physical
printing remain unverified. An operating system accepting a job is not
evidence of paper output. See the dedicated printer acceptance guide.

See [printer acceptance](../docs/PRINT_ACCEPTANCE.md), [macOS setup](../docs/MAC_APP.md), [diagnostics](../docs/DIAGNOSTICS.md), and [hardware acceptance](https://github.com/migtam628/DeviceShare/issues/1).
