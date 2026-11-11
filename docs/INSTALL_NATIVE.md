# DeviceShare Native Installers (early alpha)

DeviceShare publishes native installer **formats** for its command-line Hub and Agent:

| OS | Package | Installs to | Remove |
|---|---|---|---|
| Windows x64 | `.msi` (WiX) | `C:\Program Files\DeviceShare` | Apps & Features / `msiexec /x` |
| Windows x64 | Setup `.exe` (Inno Setup) | `C:\Program Files\DeviceShare Setup` | Apps & Features / uninstaller |
| macOS Apple Silicon | `.pkg` or `.dmg` with app/PKG | `/Applications/DeviceShare.app` | Stop services; remove app and user data separately |
| macOS Intel | `.pkg` or `.dmg` with app/PKG | `/Applications/DeviceShare.app` | Stop services; remove app and user data separately |
| Debian/Ubuntu x64 | `.deb` | `/usr/bin/`, `/usr/share/deviceshare/` | `sudo apt remove deviceshare` |

**Choose one Windows installer format, not both.** These packages install
command-line executables and sample configuration files. The macOS alpha.3 package includes a native SwiftUI management app; none of these builds are production-hardened or Developer-ID-signed/notarized.
The DeviceShare dashboard is provided by the hub at `/dashboard`.

## Before installation

1. Download from the official DeviceShare GitHub Releases page.
2. Compare SHA-256 against `SHA256SUMS.txt`.
3. Use only the build for your CPU architecture.
4. Do not override organizational SmartScreen, Gatekeeper or device policy
   just to run this alpha. If your system blocks unsigned packages, use
   the repository's source-based development installation instead.

## Windows x64

For GUI installation, double-click `DeviceShare-Setup-windows-x64.exe`.
For enterprise distribution, use `DeviceShare-windows-x64.msi`.
Both support standard Windows uninstall mechanisms and contain:

- `deviceshare-agent-windows-x64.exe` — local hardware agent.
- `deviceshare-hub-windows-x64.exe` — HTTP/WebSocket hub.
- `config\agent.example.json` — sample config only.
- `docs\INSTALL_NATIVE.md` — setup details.

After installation, open PowerShell and verify:

```powershell
& "C:\Program Files\DeviceShare\deviceshare-agent-windows-x64.exe" --version
& "C:\Program Files\DeviceShare\deviceshare-hub-windows-x64.exe" --version
```

Use `C:\Program Files\DeviceShare Setup` for the setup-EXE edition.

**Configuration lives outside Program Files**. For example, create
`$env:LOCALAPPDATA\DeviceShare\config`, copy the example JSON there,
and put your paired token in `agent.token` alongside `agent.json`.
Set the JSON `token_file` to the absolute location of that token file;
choose a private absolute `simulator_dir` too. Never use real API tokens
in GitHub issues, screenshots, or bundled sample configuration.

To run the agent manually:

```powershell
& "C:\Program Files\DeviceShare\deviceshare-agent-windows-x64.exe" --config "$env:LOCALAPPDATA\DeviceShare\config\agent.json"
```

Agent startup can be configured for the logged-in user using
`scripts/install_agent_windows.ps1` from the source repository. It is
not turned on by the MSI or setup EXE; no hardware access is silently
approved. There is no Windows background-system-service installation yet.

## macOS Apple Silicon or Intel

**Version 0.2.0-alpha.4** includes a real native SwiftUI
`/Applications/DeviceShare.app` with station setup, local-hub management,
pairing, device approvals and per-user service start/stop.

### Installer options

- **PKG:** Run `DeviceShare-macos-arm64.pkg` or the Intel `macos-x64.pkg`.
  The installer places `DeviceShare.app` in `/Applications` and updates
  the legacy `/usr/local/bin/deviceshare-agent` and
  `/usr/local/bin/deviceshare-hub` paths as links into the app.
- **DMG:** Mount it and either drag `DeviceShare.app` into Applications,
  or run the included PKG. Dragging the app installs the GUI and its bundled
  executables but does **not** install the two optional command-line links.
  Do not run the app from the mounted disk image; move it to Applications first.

### First launch

1. Open Finder → Applications → **DeviceShare**.
2. Under **First-run setup**, click **Start Local Hub** if this Mac will
   host both the hub and agent, or enter the HTTPS URL of an existing
   DeviceShare hub.
3. Enter a unique Station ID, then **Save Station Settings**.
4. Choose **Pair / Rotate Credential**. The local hub uses a newly
   generated private administrator key file. A remote hub requires you
   to enter its admin key (used once, not saved by the app).
   Alternatively, paste a pre-issued station token.
5. Select **Local devices** and scan. Explicitly approve only printers,
   serial ports, and read-only HID devices that you trust, then save.
6. Under **Background services**, click **Start / Restart** for the
   Peripheral Agent. A per-user LaunchAgent enables reconnection while
   your user session is active.
7. Use **Open Hub Dashboard** to confirm the station shows as online;
   a loaded LaunchAgent is not proof of a working network connection.

The app never grants blanket USB access or opens the hub to your network.
Its local hub binds to loopback `127.0.0.1:8765` only.

### Local state and diagnostics

Persistent user data stays outside the installer in:

```text
~/Library/Application Support/DeviceShare/
  agent.json
  agent.token
  hub-api-key       (when using the optional local hub)
  deviceshare.db    (when using the optional local hub)
  logs/
  simulator/
```

Files containing tokens, keys and configs have private permissions. The
LaunchAgent plists are created only after you explicitly start a service:

```text
~/Library/LaunchAgents/com.mttechservices.deviceshare.agent.plist
~/Library/LaunchAgents/com.mttechservices.deviceshare.hub.plist
```

For command-line diagnostics after installing the PKG:

```bash
/usr/local/bin/deviceshare-agent --version
/usr/local/bin/deviceshare-hub --version
```

The older `com.deviceshare.agent` startup definition from the portable
installer is separate. If you enabled it previously, stop and disable it
before enabling the new app-managed agent, or two agents may connect using
the same station ID.

### Uninstall notes

Stop both services from DeviceShare.app before uninstalling. Removing
`/Applications/DeviceShare.app` and the CLI symlinks removes the program
but **does not erase private pairing tokens or user data**. Delete those
separately if you intend to decommission the station. With a PKG install,
macOS package receipts can remain after manual file removal.

This alpha app has no Apple Developer ID signature or notarization.
It is ad-hoc signed for basic platform integrity, not trusted distribution.
Do not bypass organizational device policies to run it.

## Debian/Ubuntu x64

Install:

```bash
sudo apt install ./DeviceShare_0.2.0.alpha4_amd64.deb
deviceshare-agent --version
deviceshare-hub --version
```

Sample configuration:
`/usr/share/deviceshare/agent.example.json`.

Copy the sample into your own private `~/.config/deviceshare/`
directory with an absolute path to the paired token file and simulator
output directory. To run it:

```bash
deviceshare-agent --config "$HOME/.config/deviceshare/agent.json"
```

No listener or service is enabled automatically. For optional
per-user systemd startup, use the repository's
`scripts/install_agent_linux.sh` after creating the configuration.
Remove with `sudo apt remove deviceshare`.

## Starting the hub and pairing an agent

1. On a trusted machine, set `DEVICESHARE_API_KEY` to a random secret
   at least 16 characters long. Do not include it inside any installer.
2. Run `deviceshare-hub` (Windows: installed hub EXE) and open
   `http://127.0.0.1:8765/dashboard` from that same machine.
3. Enter the administrator API key. Create credentials for
   `station-01` (or your chosen agent ID).
4. Store the one-time station token in a protected local file. Point
   `token_file` to it in the station JSON configuration.
5. For remote agents, change `hub_url` to an HTTPS URL and put the
   hub behind a secure TLS proxy. Do not expose the alpha hub on the
   open internet or use an unencrypted remote URL.
6. Run the agent explicitly using the configuration file.
7. Test the simulator before adding local printer, serial or HID
   device allowlist entries.

## Security and limitations

- **Installers are unsigned and not notarized**. We cannot provide an
  Apple Developer ID certificate or Windows Authenticode signature
  without credentials and a code-signing pipeline.
- Configurations, passwords, station tokens, and SQLite runtime data
  must **not** be put under machine-wide installation directories.
- Windows raw printing, CUPS PDF/PNG and serial communication use
  operating system drivers; installer creation does not prove any
  physical device works.
- HID report reads remain explicit, bounded and local-allowlist-only.
- MSI and PKG provide standard package formats and uninstall/receipt
  metadata. Setup EXE provides normal application uninstallation.
- macOS now includes a native pairing and device-approval window. Windows/Linux
  remain CLI-first; no tray app, Windows system service, driver installation,
  automatic device approval, or privileged USB permissions helper is included.
