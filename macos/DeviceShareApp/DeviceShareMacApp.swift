import AppKit
import SwiftUI

@main
struct DeviceShareMacApp: App {
    @StateObject private var controller = DeviceShareController()

    var body: some Scene {
        WindowGroup("DeviceShare") {
            DeviceShareHome(controller: controller)
                .frame(minWidth: 780, minHeight: 630)
        }
        .windowStyle(.titleBar)
        .defaultSize(width: 900, height: 700)
        .commands {
            CommandGroup(replacing: .newItem) { }
        }
    }
}

struct DeviceShareHome: View {
    @ObservedObject var controller: DeviceShareController
    @State private var currentTab: Tab = .setup

    private enum Tab: String, CaseIterable {
        case setup = "Overview"
        case printers = "Printers"
        case studio = "Print Studio"
        case devices = "Local Devices"
        case services = "Services"
        case settings = "Settings"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .center, spacing: 12) {
                Image(systemName: "point.3.connected.trianglepath.dotted")
                    .font(.system(size: 27, weight: .semibold))
                    .foregroundStyle(Color.accentColor)
                    .frame(width: 48, height: 48)
                    .background(Color.accentColor.opacity(0.10), in: RoundedRectangle(cornerRadius: 12))
                VStack(alignment: .leading, spacing: 3) {
                    Text("DeviceShare").font(.system(size: 26, weight: .bold))
                    Text("Local hardware bridge · macOS alpha")
                        .font(.subheadline).foregroundStyle(.secondary)
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 3) {
                    Text("v0.2.0-alpha.4").font(.caption.monospacedDigit())
                    Text("Agent: " + controller.agentState)
                        .font(.caption).foregroundStyle(.secondary)
                }
            }

            HStack(alignment: .top, spacing: 15) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("WORKSPACE")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundStyle(.secondary)
                        .padding(.leading, 9)
                        .padding(.bottom, 6)
                    ForEach(Tab.allCases, id: \.self) { tab in
                        Button {
                            currentTab = tab
                        } label: {
                            HStack(spacing: 10) {
                                Image(systemName: iconName(for: tab))
                                    .frame(width: 20)
                                Text(tab.rawValue)
                                    .font(.system(size: 13, weight: currentTab == tab ? .semibold : .medium))
                                Spacer(minLength: 0)
                            }
                            .foregroundStyle(currentTab == tab ? Color.accentColor : Color.primary)
                            .padding(.horizontal, 11)
                            .padding(.vertical, 12)
                            .background(
                                currentTab == tab ? Color.accentColor.opacity(0.14) : Color.clear,
                                in: RoundedRectangle(cornerRadius: 9)
                            )
                        }
                        .buttonStyle(.plain)
                    }
                    Spacer(minLength: 0)
                    Text("LOCAL DEVICE BRIDGE")
                        .font(.system(size: 9, weight: .medium))
                        .foregroundStyle(.tertiary)
                        .padding(.horizontal, 10)
                }
                .padding(11)
                .frame(width: 177, maxHeight: .infinity, alignment: .topLeading)
                .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 12))
                selectedPanel
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            }
            .frame(maxHeight: .infinity)

            HStack(alignment: .top, spacing: 9) {
                Image(systemName: "info.circle")
                    .foregroundStyle(.secondary)
                Text(controller.notice)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(11)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 10))

            HStack {
                Text("Unsigned developer alpha · peripheral approvals are always local")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Button("Open Hub Dashboard") { controller.openDashboard() }
                Button {
                    controller.refreshServices()
                } label: {
                    Label("Refresh Status", systemImage: "arrow.clockwise")
                }
            }
        }
        .padding(20)
        .onAppear { controller.refreshServices() }
    }

    private func iconName(for tab: Tab) -> String {
        switch tab {
        case .setup: return "square.grid.2x2"
        case .printers: return "printer"
        case .studio: return "doc.text"
        case .devices: return "cable.connector"
        case .services: return "bolt.horizontal.circle"
        case .settings: return "gearshape"
        }
    }

    @ViewBuilder
    private var selectedPanel: some View {
        switch currentTab {
        case .setup: setupPanel
        case .printers: printerPanel
        case .studio: studioPanel
        case .devices: devicePanel
        case .services: servicesPanel
        case .settings: settingsPanel
        }
    }

    private var setupPanel: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                GroupBox {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("1. Select the hub")
                            .font(.headline)
                        Text("Start a local hub on this Mac, or connect to an existing HTTPS hub.")
                            .font(.subheadline).foregroundStyle(.secondary)
                        LabeledContent("Hub URL") {
                            TextField("https://your-hub.example.com", text: $controller.hubURL)
                                .textFieldStyle(.roundedBorder)
                                .frame(minWidth: 380)
                        }
                        HStack {
                            Label(controller.hubHealth, systemImage: "network")
                                .font(.callout)
                            Spacer()
                            Button("Start Local Hub") { controller.startLocalHub() }
                            Button("Check Connection") { controller.checkHubHealth() }
                        }
                    }
                }

                GroupBox {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("2. Configure this station")
                            .font(.headline)
                        LabeledContent("Station ID") {
                            TextField("station-01", text: $controller.stationID)
                                .textFieldStyle(.roundedBorder)
                                .frame(minWidth: 380)
                        }
                        Text("Use a unique ID per computer. Re-pairing an existing ID rotates its credential.")
                            .font(.caption).foregroundStyle(.secondary)
                        HStack {
                            Spacer()
                            Button("Save Station Settings") { controller.saveSetup() }
                        }
                    }
                }

                GroupBox {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("3. Pair the station")
                            .font(.headline)
                        Text("A locally started hub can pair using its private key file. For a remote hub, enter the administrator key once. This GUI never saves the administrator key.")
                            .font(.subheadline).foregroundStyle(.secondary)
                        LabeledContent("Hub administrator key") {
                            SecureField("Required for a remote hub", text: $controller.adminAPIKey)
                                .textFieldStyle(.roundedBorder)
                                .frame(minWidth: 380)
                        }
                        Toggle("Remember remote administrator key in macOS Keychain after pairing",
                               isOn: $controller.rememberRemoteAdminKey)
                            .font(.callout)
                        Text("The local Hub already saves its key in a private file. Remote keys are only kept if you explicitly enable this option.")
                            .font(.caption).foregroundStyle(.secondary)
                        HStack {
                            Image(systemName: controller.hasToken ? "checkmark.shield.fill" : "lock.shield")
                                .foregroundStyle(controller.hasToken ? Color.green : Color.secondary)
                            Text(controller.hasToken ? "Station credential saved" : "No station credential saved")
                                .font(.callout)
                            Spacer()
                            Button("Pair / Rotate Credential") { controller.pairStation() }
                                .disabled(controller.isBusy)
                                .buttonStyle(.borderedProminent)
                        }
                        Divider()
                        Text("Already have a station token?")
                            .font(.subheadline).bold()
                        HStack {
                            SecureField("Paste station token", text: $controller.manualToken)
                                .textFieldStyle(.roundedBorder)
                            Button("Save Existing Token") { controller.saveManualToken() }
                                .disabled(controller.manualToken.isEmpty)
                        }
                    }
                }

                HStack {
                    Spacer()
                    Button("Continue to Devices") { currentTab = .devices }
                        .buttonStyle(.borderedProminent)
                }
            }
            .padding(12)
        }
    }

    private var devicePanel: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Device permissions").font(.headline)
                    Text("Scan printers, serial interfaces and HID readers. DeviceShare denies access by default.")
                        .font(.subheadline).foregroundStyle(.secondary)
                }
                Spacer()
                Button {
                    controller.scanDevices()
                } label: {
                    Label("Scan Local Devices", systemImage: "arrow.triangle.2.circlepath")
                }
                .disabled(controller.isBusy)
            }
            if controller.peripherals.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "printer.slash")
                        .font(.system(size: 36))
                        .foregroundStyle(.secondary)
                    Text("No devices scanned").font(.headline)
                    Text("Select Scan Local Devices to inspect attached hardware.")
                        .font(.subheadline).foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List {
                    ForEach(controller.peripherals) { peripheral in
                        HStack(spacing: 10) {
                            Image(systemName: symbol(for: peripheral))
                                .frame(width: 25)
                                .foregroundStyle(.secondary)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(peripheral.label)
                                    .font(.body)
                                Text(peripheral.id)
                                    .font(.caption.monospaced())
                                    .foregroundStyle(.secondary)
                                    .textSelection(.enabled)
                            }
                            Spacer()
                            if peripheral.canApprove {
                                Toggle("Approved", isOn: Binding(
                                    get: { controller.isApproved(peripheral) },
                                    set: { controller.setApproved(peripheral, enabled: $0) }
                                ))
                                .labelsHidden()
                                .help("Explicit local approval for this device")
                            } else {
                                Text("Discovery only")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .padding(.vertical, 5)
                    }
                }
                .listStyle(.inset)
            }
            HStack {
                Image(systemName: "shield.lefthalf.filled")
                    .foregroundStyle(.secondary)
                Text("HID input is read-only; unrestricted USB writes and remote shell access are disabled.")
                    .font(.caption).foregroundStyle(.secondary)
                Spacer()
                Button("Save Approvals") { controller.saveApprovals() }
                    .buttonStyle(.borderedProminent)
                Button("Services") { currentTab = .services }
            }
        }
        .padding(12)
    }

    private func symbol(for device: LocalPeripheral) -> String {
        if device.id.hasPrefix("printer:") { return "printer" }
        if device.id.hasPrefix("serial:") { return "cable.connector" }
        if device.id.hasPrefix("hid:") { return "keyboard" }
        if device.id.hasPrefix("usb:") { return "externaldrive" }
        return "circle.dotted.circle"
    }

    private var settingsPanel: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                GroupBox {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Hub authentication").font(.headline)
                        Text("Local Hub keys are saved privately by DeviceShare. To remember a remote administrator key, use macOS Keychain instead of a plain-text configuration file.")
                            .font(.subheadline).foregroundStyle(.secondary)
                        LabeledContent("Hub URL") {
                            TextField("https://trusted-hub.example.com", text: $controller.hubURL)
                                .textFieldStyle(.roundedBorder)
                                .frame(minWidth: 350)
                        }
                        HStack(spacing: 10) {
                            Image(systemName: controller.savedAdminKeyAvailable ? "key.fill" : "lock.shield")
                                .foregroundStyle(controller.savedAdminKeyAvailable ? Color.green : Color.secondary)
                            Text(controller.savedAdminKeyAvailable ? "Remote key saved in Keychain" : "No remote key saved in Keychain for this URL")
                                .font(.callout)
                            Spacer()
                            Button("Check Keychain") { controller.refreshKeychainStatus() }
                        }
                        LabeledContent("Administrator key") {
                            SecureField("Enter remote administrator key", text: $controller.adminAPIKey)
                                .textFieldStyle(.roundedBorder)
                                .frame(minWidth: 350)
                        }
                        HStack {
                            Text("The saved key is accessible only to this app through macOS Keychain. Removing it does not revoke an existing Hub session.")
                                .font(.caption).foregroundStyle(.secondary)
                            Spacer()
                            Button("Forget Key") { controller.forgetAdminKeyFromKeychain() }
                                .disabled(!controller.savedAdminKeyAvailable)
                            Button("Save to Keychain") { controller.saveAdminKeyToKeychain() }
                                .buttonStyle(.borderedProminent)
                                .disabled(controller.adminAPIKey.isEmpty)
                        }
                    }
                }
                GroupBox {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Station & local data").font(.headline)
                        LabeledContent("Station ID") {
                            Text(controller.stationID).font(.body.monospaced()).textSelection(.enabled)
                        }
                        LabeledContent("Configuration folder") {
                            Text(controller.applicationSupportLocation)
                                .font(.caption.monospaced()).textSelection(.enabled)
                        }
                        HStack {
                            Button("Open Data Folder") { controller.openSupportDirectory() }
                            Button("Refresh Service Status") { controller.refreshServices() }
                            Spacer()
                            Button("Open Hub Dashboard") { controller.openDashboard() }
                        }
                    }
                }
                GroupBox {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("About & security").font(.headline)
                        Text("DeviceShare v0.2.0-alpha.4")
                        Text("The web dashboard stores no raw administrator key. Its optional remembered browser login is an HttpOnly, SameSite=Strict, revocable session cookie. Keys for remote hubs can be saved in macOS Keychain on this computer.")
                            .font(.caption).foregroundStyle(.secondary)
                        Text("Unsigned developer alpha. Limit the Hub to loopback or HTTPS on a trusted network. A print job accepted by the spooler does not prove physical paper output.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
            .padding(12)
        }
        .onAppear { controller.refreshKeychainStatus() }
    }

    private var servicesPanel: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                GroupBox {
                    VStack(alignment: .leading, spacing: 14) {
                        HStack {
                            Image(systemName: "server.rack").font(.title2).foregroundStyle(.secondary)
                            VStack(alignment: .leading) {
                                Text("Local Hub").font(.headline)
                                Text(controller.localHubState).font(.subheadline).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Button("Start / Restart") { controller.startLocalHub() }
                                .buttonStyle(.borderedProminent)
                            Button("Stop") { controller.stopLocalHub() }
                        }
                        Text("Runs locally on 127.0.0.1:8765 with a private administrator key file. Starting a local hub does not publish it on your network.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
                GroupBox {
                    VStack(alignment: .leading, spacing: 14) {
                        HStack {
                            Image(systemName: "antenna.radiowaves.left.and.right").font(.title2).foregroundStyle(.secondary)
                            VStack(alignment: .leading) {
                                Text("Peripheral Agent").font(.headline)
                                Text(controller.agentState).font(.subheadline).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Button("Start / Restart") { controller.startAgent() }
                                .buttonStyle(.borderedProminent)
                                .disabled(!controller.hasToken)
                            Button("Stop") { controller.stopAgent() }
                        }
                        Text("Agent startup is per-user using launchd. It can run while you are logged in and reconnects to the hub after disconnections.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
                GroupBox {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Local data & diagnostics")
                            .font(.headline)
                        LabeledContent("Configuration folder") {
                            Text(controller.applicationSupportLocation)
                                .font(.caption.monospaced())
                                .textSelection(.enabled)
                        }
                        Text("Agent and hub logs are stored privately under the logs subfolder. Credentials and database files are never bundled inside the app or installer.")
                            .font(.caption).foregroundStyle(.secondary)
                        HStack {
                            Spacer()
                            Button("Open Data Folder") { controller.openSupportDirectory() }
                            Button("Open Hub Dashboard") { controller.openDashboard() }
                        }
                    }
                }
                Text("This view checks launchd registration, not proof of an active WebSocket connection. Verify live agent status and actual print output in the hub dashboard.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            .padding(12)
        }
    }
}
