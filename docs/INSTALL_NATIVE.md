# DeviceShare Native Installers (early alpha)

DeviceShare publishes native installer **formats** for its command-line Hub and Agent:

| OS | Package | Installs to | Remove |
|---|---|---|---|
| Windows x64 | `.msi` (WiX) | `C:\Program Files\DeviceShare` | Apps & Features / `msiexec /x` |
| Windows x64 | Setup `.exe` (Inno Setup) | `C:\Program Files\DeviceShare Setup` | Apps & Features / uninstaller |
| macOS Apple Silicon | `.pkg` or `.dmg` containing .pkg | `/usr/local/bin/` and `/usr/local/share/` | Manual removal, pkg receipt remains |
| macOS Intel | `.pkg` or `.dmg` containing .pkg | `/usr/local/bin/` and `/usr/local/share/` | Manual removal, pkg receipt remains |
| Debian/Ubuntu x64 | `.deb` | `/usr/bin/`, `/usr/share/deviceshare/` | `sudo apt remove deviceshare` |

**Choose one Windows installer format, not both.** These packages install
command-line executables and sample configuration files. They are **not**
signed, notarized, production-hardened services, or graphical management apps.
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
`$env:LOCALAPPDATA\DeviceShare\config\`, copy the example JSON there,
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

The `.dmg` disk image includes the same `.pkg` installer offered
separately, plus setup documentation. Mount the DMG and run the
enclosed PKG, or launch the standalone PKG directly.

**No GUI application is placed in /Applications.** The CLI executables
are installed at `/usr/local/bin/deviceshare-agent` and
`/usr/local/bin/deviceshare-hub`. They can be checked with:

```bash
/usr/local/bin/deviceshare-agent --version
/usr/local/bin/deviceshare-hub --version
```

The example config is installed at
`/usr/local/share/deviceshare/agent.example.json`.
Copy it into a private directory, e.g.
`~/Library/Application Support/DeviceShare/config/agent.json` and
create the paired token file there. Set `token_file` and
`simulator_dir` to private **absolute paths**.

The package installs no privileged helper, launch daemon or
auto-starting user session. To run it automatically after you configure
the agent, use the repository's documented per-user LaunchAgent script.
Uninstall by removing binaries in `/usr/local/bin/`, files in
`/usr/local/share/deviceshare/` and
`/usr/local/share/doc/deviceshare/`. The macOS installer receipt
can remain after manual removal; do not delete other packages' files.

## Debian/Ubuntu x64

Install:

```bash
sudo apt install ./DeviceShare_0.2.0.alpha3_amd64.deb
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
- Not a full GUI app: there is no taskbar/tray app, pairing wizard,
  background Windows service, automatic device approval, driver
  installation or privileged USB permission helper.
