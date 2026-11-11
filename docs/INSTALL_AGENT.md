# DeviceShare Agent portable install (alpha)

The GitHub Release ZIP contains standalone agent/hub executables and optional
**per-user startup installers**. These are not MSI/PKG packages and are
**not digitally signed**. macOS Gatekeeper or Windows SmartScreen may warn.
Only use artifacts downloaded from a verified release in this repository.
Do not bypass enterprise device security controls.

## 1. Prepare the agent

1. Extract the ZIP to a permanent folder you control, for example
   `DeviceShare/`. Do not move it after installing the startup task.
2. Copy `config/agent.example.json` to `config/agent.json`.
3. Start the hub and visit `/dashboard` with the administrator API key.
   Generate a dedicated token for the `agent_id` from your config.
4. Save that token (only the token, no JSON or quotation marks) to
   `config/agent.token`. On Linux/macOS, run
   `chmod 600 config/agent.token`.
5. Set `hub_url` to an HTTPS URL when the hub is remote. Local
   `http://127.0.0.1:8765` is allowed for same-machine testing.
6. Edit `allowed_printers`, `allowed_serial_ports`, and
   `allowed_hid_devices` to approve only the devices you own and need.
   Leave all lists empty if you're testing the simulator.
7. Start the agent manually at least once with
   `deviceshare-agent-<platform> --config config/agent.json`.
   From the extracted `DeviceShare/` folder, you can use a relative path.
   Look for your station in the web dashboard.

The `token_file` and `simulator_dir` in the sample config are relative
to the **DeviceShare folder**, not to the executable's path. The service
scripts set the appropriate working directory when the config is located
at `DeviceShare/config/agent.json`.

## 2. Start automatically when the current user logs in

Run these from the extracted `DeviceShare/` folder with paths to the
standalone binary and config. They **do not** install a privileged system
service and do not enable system-wide USB access.

### Linux (systemd user)

```bash
bash installers/install_agent_linux.sh \
  "$PWD/deviceshare-agent-linux-x64" "$PWD/config/agent.json"
systemctl --user status deviceshare-agent.service
```

Linux user systemd services normally require a logged-in user session.
Enable linger manually only if your security policy and workload require it.

### macOS Apple Silicon

```bash
bash installers/install_agent_macos.sh \
  "$PWD/deviceshare-agent-macos-arm64" "$PWD/config/agent.json"
launchctl print "gui/$(id -u)/com.deviceshare.agent"
```

For Intel Macs, choose the `macos-x64` release ZIP and matching binary.

### Windows

In PowerShell, from the extracted folder:

```powershell
powershell -ExecutionPolicy RemoteSigned -File .\installers\install_agent_windows.ps1 `
  -AgentBinary "$PWD\deviceshare-agent-windows-x64.exe" `
  -Config "$PWD\config\agent.json"
Get-ScheduledTask -TaskName DeviceShareAgent
```

If your organization restricts PowerShell scripts, follow its IT policy.
Do not disable machine-wide execution restrictions to install an alpha tool.

## Uninstall startup only

- **Linux:** `systemctl --user disable --now deviceshare-agent.service`
  then remove `~/.config/systemd/user/deviceshare-agent.service` and
  run `systemctl --user daemon-reload`.
- **macOS:** `launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.deviceshare.agent.plist"`
  then remove that plist.
- **Windows:** `Unregister-ScheduledTask -TaskName DeviceShareAgent -Confirm:$false`.

Removing the startup registration does not delete a station's token or
printer configuration. Revoke the token separately in the DeviceShare
dashboard when decommissioning a station.

## Important limitations

- HID input is **read-only** and requires exact IDs under
  `allowed_hid_devices`; HID keyboard-emulation scanners may not be
  accessible if the OS owns the interface.
- Direct USB bulk/control transfers are not supported.
- Linux USB/HID access can require device-specific udev permissions.
- A successful print job means accepted by the OS spooler, not proof
  of output.
- No Apple notarization, Windows code-signing, automatic update mechanism,
  or polished GUI installer is included.
