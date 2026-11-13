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
        case diagnostics = "Diagnostics"
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
                    Text("v0.2.0-alpha.5").font(.caption.monospacedDigit())
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
                .frame(width: 177)
                .frame(maxHeight: .infinity, alignment: .topLeading)
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
        case .diagnostics: return "stethoscope"
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
        case .diagnostics: diagnosticsPanel
        case .services: servicesPanel
        case .settings: settingsPanel
        }
    }

    private func setupStatus(_ title: String, done: Bool) -> some View {
        HStack(spacing: 5) {
            Image(systemName: done ? "checkmark.circle.fill" : "circle.dotted")
                .foregroundStyle(done ? Color.green : Color.secondary)
            Text(title).font(.caption.weight(.semibold))
        }
        .padding(.horizontal, 9)
        .padding(.vertical, 8)
        .background(Color.accentColor.opacity(done ? 0.10 : 0.03), in: Capsule())
    }

    private var setupPanel: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Activate DeviceShare")
                        .font(.title2.bold())
                    Text("Complete these steps once. Your existing station credentials and printing history are preserved.")
                        .font(.subheadline).foregroundStyle(.secondary)
                    HStack(spacing: 8) {
                        setupStatus("Hub", done: controller.hubHealth == "Hub responding")
                        setupStatus("Account", done: controller.adminActivated)
                        setupStatus("Station", done: controller.agentConnected)
                        setupStatus("Printer", done: controller.selectedPrinter != nil)
                    }
                }
                .padding(15)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 12))
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
                        HStack {
                            Text("2. Create your administrator account")
                                .font(.headline)
                            Spacer()
                            if controller.adminActivated {
                                Label("Activated", systemImage: "checkmark.circle.fill")
                                    .foregroundStyle(Color.green)
                                    .font(.caption)
                            }
                        }
                        Text("Your email and password replace the browser API-key login. DeviceShare stores only a memory-hard password hash in the Hub database.")
                            .font(.subheadline).foregroundStyle(.secondary)
                        if controller.adminActivated {
                            HStack {
                                Label("Administrator account is ready", systemImage: "checkmark.shield.fill")
                                    .foregroundStyle(Color.green)
                                Spacer()
                                Button("Open sign-in") { controller.openDashboard() }
                            }
                        } else {
                            TextField("Email address", text: $controller.adminSetupEmail)
                                .textFieldStyle(.roundedBorder)
                            SecureField("Create password (12+ characters)", text: $controller.adminSetupPassword)
                                .textFieldStyle(.roundedBorder)
                            SecureField("Confirm password", text: $controller.adminSetupConfirmation)
                                .textFieldStyle(.roundedBorder)
                            Text(controller.activationMessage)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            HStack {
                                Button("Recheck status") { controller.refreshActivationStatus() }
                                Spacer()
                                Button("Activate administrator") { controller.activateOwnerAccount() }
                                    .buttonStyle(.borderedProminent)
                                    .disabled(controller.activationBusy ||
                                              controller.adminSetupEmail.isEmpty ||
                                              controller.adminSetupPassword.count < 12 ||
                                              controller.adminSetupPassword != controller.adminSetupConfirmation)
                            }
                        }
                    }
                }

                GroupBox {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("3. Configure this station")
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
                        Text("4. Pair the station")
                            .font(.headline)
                        Text("This computer uses its private Host key to pair the station automatically. Only remote agent provisioning needs an integration key; your browser now signs in with email and password.")
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
        .onAppear { controller.refreshActivationStatus() }
    }


    private var printerPanel: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Printers")
                        .font(.title2.bold())
                    Text("Select a Mac printer queue, approve it locally, then use it in Print Studio.")
                        .font(.subheadline).foregroundStyle(.secondary)
                }
                Spacer()
                Button {
                    controller.scanDevices()
                } label: {
                    Label("Scan printers", systemImage: "arrow.clockwise")
                }
                .disabled(controller.isBusy)
            }

            if controller.availablePrinters.isEmpty {
                VStack(spacing: 11) {
                    Image(systemName: "printer.slash")
                        .font(.system(size: 37))
                        .foregroundStyle(.secondary)
                    Text("No printers discovered")
                        .font(.headline)
                    Text("Check System Settings → Printers & Scanners, then scan again.")
                        .font(.subheadline).foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 12))
            } else {
                ScrollView {
                    LazyVStack(spacing: 10) {
                        ForEach(controller.availablePrinters) { printer in
                            VStack(alignment: .leading, spacing: 11) {
                                HStack(spacing: 13) {
                                    Image(systemName: "printer.fill")
                                        .font(.system(size: 23))
                                        .foregroundStyle(Color.accentColor)
                                        .frame(width: 47, height: 47)
                                        .background(Color.accentColor.opacity(0.12), in: RoundedRectangle(cornerRadius: 10))
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(printer.label)
                                            .font(.headline)
                                        Text(printer.state == "disabled"
                                             ? "Queue disabled — do not submit jobs"
                                             : printer.accepting == false
                                               ? "Queue not accepting new print jobs"
                                               : "Queue available — physical status not verified")
                                            .font(.caption)
                                            .foregroundStyle(printer.state == "disabled" ? Color.orange : Color.secondary)
                                        Text(printer.id)
                                            .font(.caption.monospaced())
                                            .foregroundStyle(.tertiary)
                                            .textSelection(.enabled)
                                    }
                                    Spacer()
                                    Toggle("Approved", isOn: Binding(
                                        get: { controller.isApproved(printer) },
                                        set: { controller.setApproved(printer, enabled: $0) }
                                    ))
                                    .toggleStyle(.switch)
                                    .labelsHidden()
                                }
                                HStack {
                                    if controller.selectedPrinterID == printer.id {
                                        Label("Selected", systemImage: "checkmark.circle.fill")
                                            .font(.caption)
                                            .foregroundStyle(Color.green)
                                    }
                                    Spacer()
                                    Button(controller.selectedPrinterID == printer.id ? "Selected" : "Select printer") {
                                        controller.choosePrinter(printer.id)
                                    }
                                    .disabled(printer.state == "disabled" || printer.accepting == false)
                                    Button("Open Print Studio") {
                                        controller.choosePrinter(printer.id)
                                        currentTab = .studio
                                    }
                                    .disabled(printer.state == "disabled" || printer.accepting == false)
                                    .buttonStyle(.borderedProminent)
                                }
                            }
                            .padding(16)
                            .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 12))
                        }
                    }
                }
            }
            HStack {
                Image(systemName: "info.circle")
                    .foregroundStyle(.orange)
                Text("A queue can be enabled even when your HP printer is offline. Verify paper, ink and network before printing.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Button("Save Printer Approvals") { controller.saveApprovals() }
                    .buttonStyle(.borderedProminent)
            }
        }
        .padding(12)
        .onAppear {
            if controller.availablePrinters.isEmpty { controller.scanDevices() }
        }
    }

    private var studioPanel: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 15) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Print Studio")
                        .font(.title2.bold())
                    Text("Test pages, custom text, or PDF/PNG documents using an explicitly selected printer.")
                        .font(.subheadline).foregroundStyle(.secondary)
                }

                GroupBox {
                    VStack(alignment: .leading, spacing: 11) {
                        Text("1. Choose destination")
                            .font(.headline)
                        Picker("Printer", selection: Binding(
                            get: { controller.selectedPrinterID },
                            set: { controller.choosePrinter($0) }
                        )) {
                            Text("Select a printer").tag("")
                            ForEach(controller.availablePrinters) { printer in
                                Text(printer.label).tag(printer.id)
                            }
                        }
                        .pickerStyle(.menu)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        HStack {
                            Label(controller.printerReady ? "Printer selected and locally approved" :
                                  "Approve a printer and pair this station to print",
                                  systemImage: controller.printerReady ? "checkmark.shield.fill" : "exclamationmark.triangle")
                                .font(.caption)
                                .foregroundStyle(controller.printerReady ? Color.green : Color.orange)
                            Spacer()
                            Button("Manage printers") { currentTab = .printers }
                        }
                        Text("Queue status alone does not confirm the physical printer is online.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                GroupBox {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("2. Print options")
                            .font(.headline)
                        HStack {
                            Stepper("Copies: \(controller.copies)", value: $controller.copies, in: 1...5)
                                .frame(maxWidth: .infinity, alignment: .leading)
                            Picker("Paper", selection: $controller.paperSize) {
                                Text("US Letter").tag("Letter")
                                Text("A4").tag("A4")
                            }
                            .frame(width: 155)
                            Toggle("Duplex", isOn: $controller.printDuplex)
                                .frame(width: 94)
                        }
                    }
                }

                GroupBox {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("3. Test page")
                            .font(.headline)
                        Text("A one-page PDF checks printer alignment, grayscale and text. Each click sends a separate physical print job.")
                            .font(.caption).foregroundStyle(.secondary)
                        HStack {
                            Button {
                                controller.submitTestPrint()
                            } label: {
                                Label("Print Test Page", systemImage: "printer.fill")
                            }
                            .buttonStyle(.borderedProminent)
                            .disabled(!controller.printerReady || controller.printInProgress)
                            Spacer()
                            Text("Use single-sided Letter unless your printer requires A4.")
                                .font(.caption).foregroundStyle(.tertiary)
                        }
                    }
                }

                GroupBox {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("4. Custom print")
                            .font(.headline)
                        TextField("Document title", text: $controller.customPrintTitle)
                            .textFieldStyle(.roundedBorder)
                        TextEditor(text: $controller.customPrintText)
                            .font(.system(.body, design: .monospaced))
                            .frame(minHeight: 125, maxHeight: 175)
                            .overlay(RoundedRectangle(cornerRadius: 7).stroke(Color.secondary.opacity(0.2)))
                        HStack {
                            Button("Print Custom Text") { controller.submitCustomText() }
                                .disabled(!controller.printerReady || controller.printInProgress ||
                                          controller.customPrintText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                            Button("Choose PDF / PNG…") { controller.chooseDocumentAndPrint() }
                                .disabled(!controller.printerReady || controller.printInProgress)
                            Spacer()
                        }
                    }
                }

                GroupBox {
                    VStack(alignment: .leading, spacing: 7) {
                        Text("Job status").font(.headline)
                        Text(controller.printStatus)
                            .font(.callout).foregroundStyle(.secondary)
                            .textSelection(.enabled)
                        if !controller.lastPrintJobID.isEmpty {
                            Text("Job ID: " + controller.lastPrintJobID)
                                .font(.caption.monospaced()).textSelection(.enabled)
                        }
                        HStack {
                            Spacer()
                            Button("View activity in Hub") { controller.openDashboard() }
                        }
                    }
                }
            }
            .padding(12)
        }
        .onAppear {
            if controller.availablePrinters.isEmpty { controller.scanDevices() }
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

    private var diagnosticsPanel: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    VStack(alignment: .leading, spacing: 5) {
                        Text("Diagnostics").font(.title2.bold())
                        Text("Check the Hub, station connection and printer queues without changing credentials or sending a print job.")
                            .font(.subheadline).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button {
                        controller.checkDiagnostics()
                    } label: {
                        Label("Run Checks", systemImage: "arrow.clockwise")
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(controller.isCheckingDiagnostics)
                }
                GroupBox {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Live connection").font(.headline)
                        HStack {
                            Label(controller.hubHealth, systemImage: "server.rack")
                                .foregroundStyle(controller.hubHealth == "Hub responding" ? Color.green : Color.secondary)
                            Spacer()
                            Label(controller.agentState, systemImage: "antenna.radiowaves.left.and.right")
                                .foregroundStyle(controller.agentConnected ? Color.green : Color.orange)
                        }
                        Text(controller.diagnosticMessage)
                            .font(.callout).foregroundStyle(.secondary)
                            .textSelection(.enabled)
                        HStack {
                            Button("Refresh Service State") { controller.refreshServices() }
                            Button("Rescan Station Devices") { controller.requestLocalInventoryRescan() }
                                .disabled(!controller.agentConnected)
                            Spacer()
                            Button("Open Full Diagnostics") { controller.openDiagnosticsConsole() }
                        }
                        Text("A safe rescan only re-enumerates devices. It does not approve any hardware or replay print jobs.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
                GroupBox {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Text("Recommended actions").font(.headline)
                            Spacer()
                            if let report = controller.hubDiagnostics {
                                Text(report.findings.filter { $0.severity == "attention" }.count == 0
                                     ? "No configuration warnings" : "Review required")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        if let report = controller.hubDiagnostics {
                            if report.findings.isEmpty {
                                Text("No problems were reported. Confirm physical printing separately.")
                                    .font(.callout).foregroundStyle(.secondary)
                            } else {
                                ForEach(report.findings) { finding in
                                    VStack(alignment: .leading, spacing: 7) {
                                        HStack(spacing: 8) {
                                            Image(systemName: finding.severity == "attention" ? "exclamationmark.triangle.fill" : "info.circle")
                                                .foregroundStyle(finding.severity == "attention" ? Color.orange : Color.secondary)
                                            Text(finding.title).font(.subheadline.bold())
                                            Spacer()
                                        }
                                        Text(finding.detail)
                                            .font(.callout)
                                            .foregroundStyle(.secondary)
                                            .textSelection(.enabled)
                                    }
                                    .padding(12)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 9))
                                }
                            }
                        } else {
                            VStack(spacing: 8) {
                                Image(systemName: "checkmark.shield")
                                    .font(.largeTitle).foregroundStyle(.secondary)
                                Text("Run Checks to inspect your setup")
                                    .font(.headline)
                                Text("You'll get specific next steps for offline stations, missing approvals, disabled queues and uncertain jobs.")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(26)
                        }
                    }
                }
                Text("An accepted spooler job is not proof a physical page was printed. Never blindly resend a job with an unknown outcome.")
                    .font(.caption)
                    .foregroundStyle(.orange)
            }
            .padding(12)
        }
        .onAppear {
            controller.refreshServices()
            controller.checkDiagnostics()
        }
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
                        Text("Account recovery").font(.headline)
                        Text("If you forget your dashboard password, generate a 10-minute recovery code on this Mac and use it on the browser's Forgot Password screen. The code is never sent by email.")
                            .font(.subheadline).foregroundStyle(.secondary)
                        HStack {
                            Button("Generate recovery code") { controller.issueRecoveryCode() }
                                .disabled(controller.activationBusy || !controller.adminActivated)
                            Spacer()
                            Button("Open browser sign-in") { controller.openDashboard() }
                        }
                        if !controller.recoveryCode.isEmpty {
                            Text(controller.recoveryCode)
                                .font(.system(.body, design: .monospaced))
                                .textSelection(.enabled)
                            Text("Copy this code privately. It expires in 10 minutes and can be used only once.")
                                .font(.caption).foregroundStyle(.orange)
                            Button("Hide code") { controller.recoveryCode = "" }
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
                        Text("The web dashboard uses email and password with remembered HttpOnly browser sessions. The local app retains a separate private machine credential for agent provisioning. Optional remote integration keys are kept in macOS Keychain.")
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
                        Text(controller.agentConnectivityNote)
                            .font(.caption).foregroundStyle(controller.agentConnected ? Color.green : Color.secondary)
                        Text("The status above checks the Hub's live station connection, not just whether launchd has registered a service. Restart the Agent after credential or printer-approval changes.")
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
                Text("The Agent connection status is checked against the Hub. Real printer output must still be confirmed physically.")
                    .font(.caption).foregroundStyle(.secondary)
                    .font(.caption).foregroundStyle(.secondary)
            }
            .padding(12)
        }
    }
}
