# DeviceShare.app for macOS (v0.2.0-alpha.10)

DeviceShare now has a **native SwiftUI management window** in
`/Applications/DeviceShare.app`. This is an alpha; it has no Apple Developer
ID signature or notarization. It does **not** include an elevated helper or
USB drivers. Local background services start automatically in the signed-in
owner's session; the Hub remains bound to loopback.

## Quick start — all on one Mac

1. Use the matching Apple Silicon or Intel **PKG**, or open the **DMG**
   and drag `DeviceShare.app` into Applications. On a Mac mini M1,
   use **macos-arm64**.
2. Launch **DeviceShare** from Applications.
3. Enter your **email and password** in Overview. On first use, this creates the
   owner account; on later launches, it signs in. The local Hub starts on
   `127.0.0.1:8765` automatically and can remember the session.
4. The app creates or reuses a unique station ID, pairs a private credential,
   discovers installed OS printer queues and enables the background Agent.
5. Open **Printers** or **Print Studio** when you want to print. Always verify a
   physical test print before using real customer orders or labels.

The legacy multi-step setup remains in **Advanced setup and troubleshooting**
for custom environments. The web dashboard uses a separate browser session;
the native Mac app does not transfer its session cookie into your browser.

## Connecting to a remote hub instead

- Enter the remote HTTPS hub URL.
- Enter the administrator API key for that hub only when pairing (the
  app clears it after successful pairing). Alternatively, paste a
  station-specific token generated elsewhere.
- Never use an unencrypted, non-loopback HTTP hub URL.
- The default hub remains local; the app does not expose it remotely
  or configure TLS on your behalf.

## Selecting printers and running test prints (alpha.6)

DeviceShare.app uses a sidebar with separate **Printers**, **Print Studio**, **Local Devices**, **Services** and **Settings** sections.

1. **Printers:** signed-in first-run automatically approves installed macOS queues. You can revoke approvals, choose a different default or rescan later. An enabled queue is not necessarily physically connected.
2. **Print Studio:** select the approved queue, choose **copies (1–5)**, **US Letter or A4**, optional double-sided printing, and a **paper source** if CUPS advertises one. The **Print Test Page** action submits a single PDF containing identity, time, grayscale swatches, and an alignment border.
3. **Custom print:** enter a title and custom text (up to 12,000 characters), then press **Print Custom Text**. The Hub creates a bounded PDF and sends it to the selected station.
4. **Document print:** choose a PDF or PNG (up to 1 MiB) and send it to the selected printer. macOS/Linux use CUPS; Windows uses PDFium/Pillow and the printer's GDI driver in alpha.8, pending physical test.
5. **Activity:** open the web Hub's Activity page to inspect job state. **Accepted** means accepted by the OS spooler, not proof the paper emerged.

CUPS `lpstat -p` reports queue state, whereas network/USB hardware can still be offline. Check your HP ENVY's queue and physical connection before repeatedly submitting print jobs.

The **Settings** tab can generate a short-lived account recovery code and optionally keep a remote integration key in macOS **Keychain** (not in agent.json). The local Hub keeps its internal key in a private file. The web dashboard uses email/password sign-in and can remember a revocable browser session without storing the password or raw machine key in localStorage.

## Diagnosing offline agents and print queues (alpha.6)

Under **Diagnostics**, select **Run Checks**. The Mac app reads Hub findings and can request a safe device inventory rescan. It does not approve hardware, rotate tokens, or resend uncertain print jobs.

This distinguishes a registered service from an actually connected Agent; an enabled CUPS queue from a queue accepting new requests; and a spooler-accepted job from physical paper output.

See the [Diagnostics guide](DIAGNOSTICS.md) and the browser **Diagnostics** screen for more detail.

In alpha.7, the **Services** page provides **Recheck connection** and displays a warning if the older `com.deviceshare.agent` launchd service is still loaded. Two Agents sharing the same station ID can disconnect each other repeatedly. Confirm which service is obsolete before stopping it; the new app does not disable legacy services automatically. A successful Agent startup is checked again after a brief delay because the initial Hub request may finish before the station connects.

## Device approval model

| Device | Alpha permission model |
|---|---|
| Operating-system printers | Locally auto-approved for the signed-in owner; individually revocable |
| Serial ports | Explicit local device path approval |
| HID input readers | Explicit full HID identifier, **input reports only** |
| USB VID/PID inventory | Discovery only; no bulk/control transfers |
| Simulator | Always available unless disabled locally |

The device list may include hardware you can see but cannot read because
macOS or its driver owns the interface. Those permission restrictions should
not be bypassed.

## File locations

```text
/Applications/DeviceShare.app
  Contents/MacOS/DeviceShare        # native GUI
  Contents/MacOS/deviceshare-agent  # bundled headless agent
  Contents/MacOS/deviceshare-hub    # bundled local hub

~/Library/Application Support/DeviceShare/
  agent.json
  agent.token
  hub-api-key
  deviceshare.db
  logs/

~/Library/LaunchAgents/
  com.mttechservices.deviceshare.agent.plist
  com.mttechservices.deviceshare.hub.plist
```

The per-user LaunchAgent plists are created **only** when you click
Start/Restart for a specific service. Pairing, enabling a device,
and starting a service are separate choices.

PKG installations preserve legacy CLI commands:

```bash
/usr/local/bin/deviceshare-agent --version
/usr/local/bin/deviceshare-hub --version
```

A drag-to-Applications DMG installation does not create CLI links;
the bundled agent and hub are still available from the app itself.

## Diagnostics and troubleshooting

```bash
launchctl print "gui/$(id -u)/com.mttechservices.deviceshare.agent"
launchctl print "gui/$(id -u)/com.mttechservices.deviceshare.hub"

ls -la "$HOME/Library/Application Support/DeviceShare/logs/"
ls -lh /Applications/DeviceShare.app/Contents/MacOS/
```

A disconnected station can mean the hub is down, station ID or token
is incorrect, the network is unavailable, or a device's OS permissions
block its use. Restart the agent after changing approval settings.

If you previously activated the old portable setup's LaunchAgent
`com.deviceshare.agent`, stop it before using the GUI-managed one to
avoid duplicate connections for the same station ID.

## Limitations

The app runs only while a user session exists; it manages per-user
launchd jobs, not machine-wide system daemons. There is no code
signing/notarization with an Apple Developer ID, auto-update framework,
tray/menu bar service, print driver, or proof-of-paper-print output.
Do not rely on this alpha for safety-critical devices.
