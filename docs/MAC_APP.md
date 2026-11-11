# DeviceShare.app for macOS (v0.2.0-alpha.3)

DeviceShare now has a **native SwiftUI management window** in
`/Applications/DeviceShare.app`. This is an alpha; it has no Apple Developer
ID signature or notarization. It does **not** include an elevated helper,
USB drivers, blanket printer access or automatic start of its network services.

## Quick start — all on one Mac

1. Use the matching Apple Silicon or Intel **PKG**, or open the **DMG**
   and drag `DeviceShare.app` into Applications. On a Mac mini M1,
   use **macos-arm64**.
2. Launch **DeviceShare** from Applications.
3. In **First-run setup**, select **Start Local Hub**. The app generates a
   cryptographically random admin API key and saves it privately.
   The hub listens **only on 127.0.0.1:8765**.
4. Keep `station-01` or choose a different unique station name.
   Select **Save Station Settings**.
5. Choose **Pair / Rotate Credential**. The GUI stores the station token
   in a private local file; it never displays the token in logs or
   saves your remote administrator key.
6. Open **Local devices**, press **Scan Local Devices**, and approve
   individual printers, serial ports or read-only HID devices.
   Select **Save Approvals**. USB VID/PID inventory is still read-only.
7. In **Background services**, press **Start / Restart** for the
   Peripheral Agent.
8. Select **Open Hub Dashboard**; verify the station is online. A
   launchd-loaded status alone does not guarantee hub connectivity.
9. Test the simulator before sending a label to a real printer.
   Real print acceptance still requires physical verification.

## Connecting to a remote hub instead

- Enter the remote HTTPS hub URL.
- Enter the administrator API key for that hub only when pairing (the
  app clears it after successful pairing). Alternatively, paste a
  station-specific token generated elsewhere.
- Never use an unencrypted, non-loopback HTTP hub URL.
- The default hub remains local; the app does not expose it remotely
  or configure TLS on your behalf.

## Selecting printers and running test prints (alpha.4)

DeviceShare.app now uses a sidebar with separate **Printers**, **Print Studio**, **Local Devices**, **Services** and **Settings** sections.

1. **Printers:** scan your macOS queues, choose the specific printer you intend to use and enable its local **Approved** switch. Save approvals, then restart the Agent under Services. An enabled queue is not necessarily physically connected.
2. **Print Studio:** select the approved queue, choose **copies (1–5)**, **US Letter or A4**, and optional double-sided printing. The **Print Test Page** action submits a single PDF containing identity, time, grayscale swatches, and an alignment border.
3. **Custom print:** enter a title and custom text (up to 12,000 characters), then press **Print Custom Text**. The Hub creates a bounded PDF and sends it to the selected station.
4. **Document print:** choose a PDF or PNG (up to 1 MiB) and send it to the selected printer. Windows PDF/PNG rendering is not yet supported; macOS/Linux use CUPS.
5. **Activity:** open the web Hub's Activity page to inspect job state. **Accepted** means accepted by the OS spooler, not proof the paper emerged.

CUPS `lpstat -p` reports queue state, whereas network/USB hardware can still be offline. Check your HP ENVY's queue and physical connection before repeatedly submitting print jobs.

The **Settings** tab can optionally keep a remote Hub administrator key in the macOS **Keychain** (not in agent.json). The local Hub already keeps its key in a private file. The browser Settings page can remember a revocable login session without saving the raw administrator key in localStorage.

## Device approval model

| Device | Alpha permission model |
|---|---|
| Operating-system printers | Explicit CUPS queue name approval |
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
