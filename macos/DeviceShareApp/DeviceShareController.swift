import AppKit
import Combine
import Foundation
import UniformTypeIdentifiers
import Security
import SwiftUI
import Darwin

struct LocalPeripheral: Codable, Identifiable {
    let id: String
    let kind: String
    let label: String
    let state: String?
    let accepting: Bool?

    var canApprove: Bool {
        id.hasPrefix("printer:") || id.hasPrefix("serial:") || id.hasPrefix("hid:")
    }
}

struct HubFinding: Decodable, Identifiable {
    let code: String
    let severity: String
    let title: String
    let detail: String
    let action: String
    let href: String
    let agent_id: String
    let device_id: String

    var id: String { code + ":" + agent_id + ":" + device_id }
}

struct HubDiagnosticReport: Decodable {
    let overall: String
    let findings: [HubFinding]
    let counts: [String: Int]
}

@MainActor
final class DeviceShareController: ObservableObject {
    @Published var hubURL = "http://127.0.0.1:8765"
    @Published var stationID = "station-01"
    @Published var adminAPIKey = ""
    @Published var rememberRemoteAdminKey = false
    @Published var savedAdminKeyAvailable = false
    @Published var manualToken = ""
    @Published var peripherals: [LocalPeripheral] = []
    @Published var approvals = Set<String>()
    @Published var hubDiagnostics: HubDiagnosticReport?
    @Published var diagnosticMessage = "Run checks to see current station and printer status."
    @Published var isCheckingDiagnostics = false
    @Published var hubHealth = "Not checked"
    @Published var agentState = "Stopped"
    @Published var localHubState = "Stopped"
    @Published var notice = "Choose a local hub or enter the URL of a trusted remote hub."
    @Published var agentConnected = false
    @Published var agentConnectivityNote = "Station connection not checked"
    @Published var adminActivated = false
    @Published var adminSetupEmail = ""
    @Published var adminSetupPassword = ""
    @Published var adminSetupConfirmation = ""
    @Published var activationBusy = false
    @Published var activationMessage = "Create an administrator account to sign in with email and password."
    @Published var recoveryCode = ""
    @Published var isBusy = false
    @Published var selectedPrinterID = ""
    @Published var customPrintTitle = "My custom print"
    @Published var customPrintText = ""
    @Published var copies = 1
    @Published var paperSize = "Letter"
    @Published var printDuplex = false
    @Published var printInProgress = false
    @Published var printStatus = "Select an approved printer to begin."
    @Published var lastPrintJobID = ""

    private let agentLabel = "com.mttechservices.deviceshare.agent"
    private let hubLabel = "com.mttechservices.deviceshare.hub"

    private var supportURL: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/DeviceShare", isDirectory: true)
    }
    private var configURL: URL { supportURL.appendingPathComponent("agent.json") }
    private var tokenURL: URL { supportURL.appendingPathComponent("agent.token") }
    private var hubKeyURL: URL { supportURL.appendingPathComponent("hub-api-key") }
    private var localDBURL: URL { supportURL.appendingPathComponent("deviceshare.db") }
    private var logURL: URL { supportURL.appendingPathComponent("logs", isDirectory: true) }
    private var launchAgentsURL: URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/LaunchAgents", isDirectory: true)
    }
    private var agentBinary: URL {
        Bundle.main.bundleURL.appendingPathComponent("Contents/MacOS/deviceshare-agent")
    }
    private var hubBinary: URL {
        Bundle.main.bundleURL.appendingPathComponent("Contents/MacOS/deviceshare-hub")
    }

    var hasToken: Bool { ((try? Data(contentsOf: tokenURL).count) ?? 0) >= 16 }
    var hasLocalHubKey: Bool { FileManager.default.fileExists(atPath: hubKeyURL.path) }
    var applicationSupportLocation: String { supportURL.path }

    init() {
        selectedPrinterID = UserDefaults.standard.string(forKey: "deviceshare_selected_printer") ?? ""
        if let config = try? readConfig() {
            if let value = config["hub_url"] as? String { hubURL = value }
            if let value = config["agent_id"] as? String { stationID = value }
            let printerNames = config["allowed_printers"] as? [String] ?? []
            let serialNames = config["allowed_serial_ports"] as? [String] ?? []
            let hidNames = config["allowed_hid_devices"] as? [String] ?? []
            approvals = Set(printerNames.map { "printer:" + $0 }
                + serialNames.map { "serial:" + $0 } + hidNames)
            peripherals = approvals.sorted().map { LocalPeripheral(id: $0, kind: "saved", label: $0 + " (previously approved)", state: nil, accepting: nil) }
        }
    }

    private func makePrivateDirectory(_ directory: URL) throws {
        try FileManager.default.createDirectory(
            at: directory, withIntermediateDirectories: true,
            attributes: [.posixPermissions: 0o700])
        _ = chmod(directory.path, 0o700)
    }

    private func writePrivate(_ data: Data, to url: URL) throws {
        try makePrivateDirectory(url.deletingLastPathComponent())
        try data.write(to: url, options: .atomic)
        if chmod(url.path, 0o600) != 0 {
            throw NSError(domain: "DeviceShare", code: 100,
                          userInfo: [NSLocalizedDescriptionKey: "Cannot restrict permissions on " + url.lastPathComponent])
        }
    }

    private func readConfig() throws -> [String: Any] {
        let data = try Data(contentsOf: configURL)
        guard let value = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw NSError(domain: "DeviceShare", code: 101,
                          userInfo: [NSLocalizedDescriptionKey: "Agent configuration is not a JSON object"])
        }
        return value
    }

    private func validatedHubURL() throws -> URL {
        let raw = hubURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let value = URLComponents(string: raw),
              let scheme = value.scheme?.lowercased(),
              let host = value.host?.lowercased(),
              value.user == nil, value.password == nil,
              value.query == nil, value.fragment == nil,
              !host.isEmpty else {
            throw NSError(domain: "DeviceShare", code: 102,
                          userInfo: [NSLocalizedDescriptionKey: "Enter a valid hub URL without credentials or query parameters."])
        }
        let local = ["127.0.0.1", "localhost", "::1"].contains(host)
        guard scheme == "https" || (scheme == "http" && local),
              let url = value.url else {
            throw NSError(domain: "DeviceShare", code: 103,
                          userInfo: [NSLocalizedDescriptionKey: "Remote hubs must use HTTPS. HTTP is only allowed on loopback."])
        }
        return url
    }

    private func validateStationID() throws {
        let pattern = "^[a-zA-Z0-9_.-]{1,80}$"
        guard stationID.range(of: pattern, options: .regularExpression) != nil else {
            throw NSError(domain: "DeviceShare", code: 104,
                          userInfo: [NSLocalizedDescriptionKey: "Station ID must contain 1–80 letters, numbers, dots, hyphens or underscores."])
        }
    }

    func saveConfiguration() throws {
        try validateStationID()
        _ = try validatedHubURL()
        var config = (try? readConfig()) ?? [:]
        config["agent_id"] = stationID
        config["hub_url"] = hubURL.trimmingCharacters(in: .whitespacesAndNewlines)
        config["token_file"] = tokenURL.path
        config["simulator_dir"] = supportURL.appendingPathComponent("simulator").path
        config["allow_simulator"] = true
        config["allow_insecure_remote"] = false
        config["allowed_printers"] = approvals.filter { $0.hasPrefix("printer:") }
            .map { String($0.dropFirst("printer:".count)) }.sorted()
        config["allowed_serial_ports"] = approvals.filter { $0.hasPrefix("serial:") }
            .map { String($0.dropFirst("serial:".count)) }.sorted()
        config["allowed_hid_devices"] = approvals.filter { $0.hasPrefix("hid:") }.sorted()
        let data = try JSONSerialization.data(withJSONObject: config, options: [.prettyPrinted, .sortedKeys])
        try writePrivate(data, to: configURL)
        objectWillChange.send()
    }

    func saveSetup() {
        do {
            try saveConfiguration()
            notice = "Configuration saved privately. Pair a station token before starting the agent."
        } catch { notice = error.localizedDescription }
    }

    func saveManualToken() {
        do {
            let value = manualToken.trimmingCharacters(in: .whitespacesAndNewlines)
            guard value.count >= 16, !value.contains("\n"), !value.contains("\r") else {
                throw NSError(domain: "DeviceShare", code: 105,
                              userInfo: [NSLocalizedDescriptionKey: "Enter the full station token (16+ characters)."])
            }
            try saveConfiguration()
            try writePrivate(Data(value.utf8), to: tokenURL)
            manualToken = ""
            notice = "Station token saved privately. You can now start the agent."
        } catch { notice = error.localizedDescription }
    }

    private func keychainQuery(for hub: URL) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "com.mttechservices.deviceshare.admin-api-key",
            kSecAttrAccount as String: hub.absoluteString
        ]
    }

    private func rememberedKey(for hub: URL) -> String? {
        var query = keychainQuery(for: hub)
        query[kSecReturnData as String] = kCFBooleanTrue
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    func refreshKeychainStatus() {
        do {
            let hub = try validatedHubURL()
            savedAdminKeyAvailable = rememberedKey(for: hub) != nil
        } catch { savedAdminKeyAvailable = false }
    }

    private func persistAdminKey(_ value: String, for hub: URL) throws {
        guard value.count >= 16 else {
            throw NSError(domain: "DeviceShare", code: 115,
                          userInfo: [NSLocalizedDescriptionKey: "Enter an administrator key of at least 16 characters."])
        }
        var query = keychainQuery(for: hub)
        let data = Data(value.utf8)
        let update: [String: Any] = [kSecValueData as String: data]
        let result = SecItemUpdate(query as CFDictionary, update as CFDictionary)
        if result == errSecItemNotFound {
            query[kSecValueData as String] = data
            query[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
            let created = SecItemAdd(query as CFDictionary, nil)
            guard created == errSecSuccess else {
                throw NSError(domain: "DeviceShare", code: Int(created),
                              userInfo: [NSLocalizedDescriptionKey: "Keychain could not store the administrator key."])
            }
        } else if result != errSecSuccess {
            throw NSError(domain: "DeviceShare", code: Int(result),
                          userInfo: [NSLocalizedDescriptionKey: "Keychain could not update the administrator key."])
        }
        savedAdminKeyAvailable = true
    }

    func saveAdminKeyToKeychain() {
        do {
            let hub = try validatedHubURL()
            let entered = adminAPIKey.trimmingCharacters(in: .whitespacesAndNewlines)
            try persistAdminKey(entered, for: hub)
            adminAPIKey = ""
            notice = "Hub administrator key saved in macOS Keychain for this Hub URL. It is never placed in agent.json."
        } catch { notice = error.localizedDescription }
    }

    func forgetAdminKeyFromKeychain() {
        do {
            let hub = try validatedHubURL()
            let result = SecItemDelete(keychainQuery(for: hub) as CFDictionary)
            guard result == errSecSuccess || result == errSecItemNotFound else {
                throw NSError(domain: "DeviceShare", code: Int(result),
                              userInfo: [NSLocalizedDescriptionKey: "Unable to remove Keychain entry."])
            }
            adminAPIKey = ""
            savedAdminKeyAvailable = false
            notice = "Saved remote administrator key removed from macOS Keychain."
        } catch { notice = error.localizedDescription }
    }

    func refreshActivationStatus() {
        Task {
            for attempt in 0..<10 {
                do {
                    let hub = try validatedHubURL()
                    var request = URLRequest(url: hub.appendingPathComponent("v1/auth/status"))
                    request.timeoutInterval = 3
                    let (data, response) = try await URLSession.shared.data(for: request)
                    guard (response as? HTTPURLResponse)?.statusCode == 200,
                          let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                        throw NSError(domain: "DeviceShare", code: 186,
                                      userInfo: [NSLocalizedDescriptionKey: "Account status unavailable"])
                    }
                    adminActivated = json["activated"] as? Bool == true
                    activationMessage = adminActivated
                        ? "Account active. Sign into the web dashboard with your email and password."
                        : "Create your owner account here. Your private machine key will not appear in the browser."
                    return
                } catch {
                    if attempt < 9 {
                        try? await Task.sleep(nanoseconds: 350_000_000)
                    }
                }
            }
            adminActivated = false
            activationMessage = "Local Hub is not responding. Check Services and retry."
        }
    }

    func activateOwnerAccount() {
        guard !activationBusy else { return }
        let email = adminSetupEmail.trimmingCharacters(in: .whitespacesAndNewlines)
        let password = adminSetupPassword
        guard password.count >= 12 && password == adminSetupConfirmation else {
            activationMessage = "Use at least 12 characters and enter matching passwords."
            return
        }
        activationBusy = true
        activationMessage = "Securing your administrator account…"
        Task {
            defer {
                adminSetupPassword = ""
                adminSetupConfirmation = ""
                activationBusy = false
            }
            do {
                let hub = try validatedHubURL()
                guard let hostKey = localHubKey(for: hub), hostKey.count >= 16 else {
                    throw NSError(domain: "DeviceShare", code: 180,
                        userInfo: [NSLocalizedDescriptionKey: "Activation from the Mac app requires its local Hub. For remote Hubs, generate a setup code on that host."])
                }
                var codeRequest = URLRequest(url: hub.appendingPathComponent("v1/auth/code"))
                codeRequest.httpMethod = "POST"
                codeRequest.timeoutInterval = 10
                codeRequest.setValue(hostKey, forHTTPHeaderField: "X-API-Key")
                codeRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
                codeRequest.httpBody = try JSONSerialization.data(withJSONObject: ["purpose": "activate"])
                let (codeData, codeResponse) = try await URLSession.shared.data(for: codeRequest)
                guard (codeResponse as? HTTPURLResponse)?.statusCode == 200,
                      let payload = try JSONSerialization.jsonObject(with: codeData) as? [String: Any],
                      let code = payload["code"] as? String else {
                    throw NSError(domain: "DeviceShare", code: 181,
                        userInfo: [NSLocalizedDescriptionKey: "Could not generate activation code. Account may already be activated."])
                }
                var activateRequest = URLRequest(url: hub.appendingPathComponent("v1/auth/activate"))
                activateRequest.httpMethod = "POST"
                activateRequest.timeoutInterval = 15
                activateRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
                activateRequest.setValue("1", forHTTPHeaderField: "X-DeviceShare-CSRF")
                activateRequest.httpBody = try JSONSerialization.data(withJSONObject: [
                    "code": code, "email": email, "password": password, "remember": true
                ] as [String: Any])
                let (resultData, resultResponse) = try await URLSession.shared.data(for: activateRequest)
                guard (resultResponse as? HTTPURLResponse)?.statusCode == 201 else {
                    var reason = "Account setup failed. Check your email and password."
                    if let errorBody = try? JSONSerialization.jsonObject(with: resultData) as? [String: Any],
                       let detail = errorBody["detail"] as? String { reason = detail }
                    throw NSError(domain: "DeviceShare", code: 182,
                        userInfo: [NSLocalizedDescriptionKey: reason])
                }
                adminActivated = true
                activationMessage = "Administrator created. Open the web dashboard and sign in with your email and password."
                notice = activationMessage
            } catch {
                activationMessage = error.localizedDescription
                notice = "Account setup: " + error.localizedDescription
            }
        }
    }

    func issueRecoveryCode() {
        guard !activationBusy else { return }
        activationBusy = true
        recoveryCode = ""
        Task {
            defer { activationBusy = false }
            do {
                let hub = try validatedHubURL()
                guard let hostKey = localHubKey(for: hub) else {
                    throw NSError(domain: "DeviceShare", code: 183,
                        userInfo: [NSLocalizedDescriptionKey: "Recovery codes must be requested on the local Hub host."])
                }
                var request = URLRequest(url: hub.appendingPathComponent("v1/auth/code"))
                request.httpMethod = "POST"
                request.setValue(hostKey, forHTTPHeaderField: "X-API-Key")
                request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                request.httpBody = try JSONSerialization.data(withJSONObject: ["purpose": "reset"])
                let (data, response) = try await URLSession.shared.data(for: request)
                guard (response as? HTTPURLResponse)?.statusCode == 200,
                      let result = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                      let code = result["code"] as? String else {
                    throw NSError(domain: "DeviceShare", code: 184,
                        userInfo: [NSLocalizedDescriptionKey: "Could not create recovery code."])
                }
                recoveryCode = code
                notice = "Recovery code generated. Valid for 10 minutes; use it only in your own browser."
            } catch { notice = error.localizedDescription }
        }
    }

    private func localHubKey(for url: URL) -> String? {
        guard let host = url.host?.lowercased(),
              ["127.0.0.1", "localhost", "::1"].contains(host),
              (url.port ?? 8765) == 8765 else { return nil }
        return try? String(contentsOf: hubKeyURL, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines)
    }

    func pairStation() {
        guard !isBusy else { return }
        isBusy = true
        Task {
            defer { isBusy = false }
            do {
                try validateStationID()
                let hub = try validatedHubURL()
                let enteredKey = adminAPIKey.trimmingCharacters(in: .whitespacesAndNewlines)
                let key = localHubKey(for: hub) ?? (!enteredKey.isEmpty ? enteredKey : rememberedKey(for: hub) ?? "")
                guard key.count >= 16 else {
                    throw NSError(domain: "DeviceShare", code: 106,
                                  userInfo: [NSLocalizedDescriptionKey: "Start the local hub or provide the administrator key for the remote hub."])
                }
                try saveConfiguration()
                let encodedID = stationID.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? stationID
                let endpoint = hub.appendingPathComponent("v1/agents/" + encodedID + "/credential")
                var request = URLRequest(url: endpoint)
                request.httpMethod = "POST"
                request.setValue(key, forHTTPHeaderField: "X-API-Key")
                request.timeoutInterval = 12
                let (data, response) = try await URLSession.shared.data(for: request)
                guard let status = response as? HTTPURLResponse, status.statusCode == 200 else {
                    let code = (response as? HTTPURLResponse)?.statusCode ?? 0
                    throw NSError(domain: "DeviceShare", code: 107,
                                  userInfo: [NSLocalizedDescriptionKey: "Pairing request failed (HTTP \(code)). Verify hub and key."])
                }
                guard let result = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                      let token = result["token"] as? String,
                      token.count >= 16 else {
                    throw NSError(domain: "DeviceShare", code: 108,
                                  userInfo: [NSLocalizedDescriptionKey: "Hub returned an invalid station credential."])
                }
                try writePrivate(Data(token.utf8), to: tokenURL)
                if rememberRemoteAdminKey && !enteredKey.isEmpty && localHubKey(for: hub) == nil {
                    try persistAdminKey(enteredKey, for: hub)
                }
                adminAPIKey = ""
                notice = "Station paired. Previous station credentials are invalidated; restart the agent if it was running."
                refreshServices()
            } catch {
                notice = error.localizedDescription
            }
        }
    }

    private nonisolated static func capture(_ executable: URL, arguments: [String]) throws -> (Int32, Data) {
        let process = Process()
        process.executableURL = executable
        process.arguments = arguments
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        try process.run()
        let output = pipe.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        return (process.terminationStatus, output)
    }

    func scanDevices() {
        guard !isBusy else { return }
        isBusy = true
        let binary = agentBinary
        Task {
            defer { isBusy = false }
            do {
                let (status, data) = try await Task.detached(priority: .userInitiated) {
                    try Self.capture(binary, arguments: ["--list-devices"])
                }.value
                guard status == 0 else {
                    throw NSError(domain: "DeviceShare", code: 109,
                                  userInfo: [NSLocalizedDescriptionKey: "Device discovery returned an error."])
                }
                let live = try JSONDecoder().decode([LocalPeripheral].self, from: data)
                var seen = Set<String>()
                var result: [LocalPeripheral] = []
                for device in live where seen.insert(device.id).inserted {
                    result.append(device)
                }
                for id in approvals.sorted() where !seen.contains(id) {
                    result.append(LocalPeripheral(id: id, kind: "saved", label: id + " (offline / approved)", state: nil, accepting: nil))
                }
                peripherals = result.sorted { $0.kind + $0.label < $1.kind + $1.label }
                notice = "Discovered \(live.count) peripheral entries. Only checked devices receive local approval."
            } catch {
                notice = "Device scan failed: " + error.localizedDescription
            }
        }
    }

    var availablePrinters: [LocalPeripheral] {
        peripherals.filter { $0.id.hasPrefix("printer:") }
    }

    var selectedPrinter: LocalPeripheral? {
        availablePrinters.first(where: { $0.id == selectedPrinterID })
    }

    var printerReady: Bool {
        guard let printer = selectedPrinter else { return false }
        return printer.state != "disabled" && printer.accepting != false && approvals.contains(printer.id) && hasToken
    }

    func choosePrinter(_ id: String) {
        selectedPrinterID = id
        UserDefaults.standard.set(id, forKey: "deviceshare_selected_printer")
    }

    private func submitPrintRequest(path: String, body: [String: Any]) async throws -> String {
        let base = try validatedHubURL()
        guard base.scheme == "https" || ["localhost", "127.0.0.1", "::1"].contains(base.host?.lowercased() ?? "") else {
            throw NSError(domain: "DeviceShare", code: 170,
                          userInfo: [NSLocalizedDescriptionKey: "Remote print jobs require HTTPS."])
        }
        let key = localHubKey(for: base)
                  ?? rememberedKey(for: base)
                  ?? adminAPIKey.trimmingCharacters(in: .whitespacesAndNewlines)
        guard key.count >= 16 else {
            throw NSError(domain: "DeviceShare", code: 171,
                          userInfo: [NSLocalizedDescriptionKey: "Hub administrator key unavailable. Start the local Hub, or save the remote key under Settings."])
        }
        var request = URLRequest(url: base.appendingPathComponent(path))
        request.httpMethod = "POST"
        request.timeoutInterval = 20
        request.setValue(key, forHTTPHeaderField: "X-API-Key")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, response) = try await URLSession.shared.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard status == 202 else {
            var detail = "Hub rejected print job (HTTP \(status))."
            if let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let message = object["detail"] as? String { detail = message }
            throw NSError(domain: "DeviceShare", code: status,
                          userInfo: [NSLocalizedDescriptionKey: detail])
        }
        guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let jobID = object["id"] as? String else {
            throw NSError(domain: "DeviceShare", code: 172,
                          userInfo: [NSLocalizedDescriptionKey: "Hub returned an invalid print response."])
        }
        return jobID
    }

    private func printOptions() -> [String: Any] {
        ["copies": copies, "media": paperSize,
         "sides": printDuplex ? "two-sided-long-edge" : "one-sided"]
    }

    func submitTestPrint() {
        performPrint(test: true)
    }

    func submitCustomText() {
        performPrint(test: false)
    }

    private func performPrint(test: Bool) {
        guard !printInProgress else { return }
        guard let printer = selectedPrinter, printerReady else {
            printStatus = "Select and approve an enabled printer, then pair your station."
            return
        }
        if !test && customPrintText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            printStatus = "Enter text before submitting a custom print."
            return
        }
        let id = printer.id
        var body = printOptions()
        body["agent_id"] = stationID
        body["device_id"] = id
        if !test {
            body["title"] = customPrintTitle
            body["text"] = customPrintText
        }
        printInProgress = true
        printStatus = "Submitting to " + printer.label + "…"
        Task {
            defer { printInProgress = false }
            do {
                let job = try await submitPrintRequest(path: test ? "v1/print/test" : "v1/print/text",
                                                        body: body)
                lastPrintJobID = job
                printStatus = "Job " + String(job.prefix(12)) + " submitted to " + printer.label +
                    ". Confirm spooler status and physical paper output in the Hub dashboard."
                notice = printStatus
            } catch {
                printStatus = error.localizedDescription
                notice = "Print request failed: " + error.localizedDescription
            }
        }
    }

    func chooseDocumentAndPrint() {
        guard !printInProgress else { return }
        guard let printer = selectedPrinter, printerReady else {
            printStatus = "Select and approve a connected printer before choosing a document."
            return
        }
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.pdf, .png]
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        guard panel.runModal() == .OK, let fileURL = panel.url else { return }
        let printerID = printer.id
        do {
            let attributes = try FileManager.default.attributesOfItem(atPath: fileURL.path)
            if (attributes[.size] as? NSNumber)?.intValue ?? 0 > 1024 * 1024 {
                throw NSError(domain: "DeviceShare", code: 173,
                              userInfo: [NSLocalizedDescriptionKey: "PDF/PNG file must not exceed 1 MiB."])
            }
            let data = try Data(contentsOf: fileURL)
            let pdf = data.starts(with: Data("%PDF-".utf8))
            let png = data.starts(with: Data([137, 80, 78, 71, 13, 10, 26, 10]))
            guard pdf || png else {
                throw NSError(domain: "DeviceShare", code: 174,
                              userInfo: [NSLocalizedDescriptionKey: "Only valid PDF or PNG documents are supported."])
            }
            var body: [String: Any] = [
                "agent_id": stationID,
                "device_id": printerID,
                "operation": "print_document",
                "data_base64": data.base64EncodedString(),
                "options": printOptions().merging(
                    ["mime_type": pdf ? "application/pdf" : "image/png"],
                    uniquingKeysWith: { _, new in new })
            ]
            printInProgress = true
            printStatus = "Submitting " + fileURL.lastPathComponent + "…"
            Task {
                defer { printInProgress = false }
                do {
                    let job = try await submitPrintRequest(path: "v1/jobs", body: body)
                    lastPrintJobID = job
                    printStatus = "Document queued as " + String(job.prefix(12)) + ". Verify physical output."
                } catch { printStatus = error.localizedDescription }
            }
        } catch { printStatus = error.localizedDescription }
    }

    func isApproved(_ device: LocalPeripheral) -> Bool { approvals.contains(device.id) }

    func setApproved(_ device: LocalPeripheral, enabled: Bool) {
        guard device.canApprove else { return }
        if enabled { approvals.insert(device.id) } else { approvals.remove(device.id) }
    }

    func saveApprovals() {
        do {
            try saveConfiguration()
            notice = "Device approvals saved locally. Restart the agent to apply changes."
        } catch { notice = error.localizedDescription }
    }

    private func serviceTarget(_ label: String) -> String {
        "gui/\(getuid())/\(label)"
    }

    private func isLoaded(_ label: String) -> Bool {
        guard let result = try? Self.capture(URL(fileURLWithPath: "/bin/launchctl"),
                                             arguments: ["print", serviceTarget(label)]) else { return false }
        return result.0 == 0
    }

    func refreshServices() {
        agentState = isLoaded(agentLabel) ? "Checking connection…" : "Stopped"
        agentConnected = false
        localHubState = isLoaded(hubLabel) ? "Local hub service loaded" : "Stopped"
        objectWillChange.send()
        checkHubHealth()
        checkAgentConnection()
    }

    func checkAgentConnection() {
        Task {
            let loaded = isLoaded(agentLabel)
            if !loaded {
                agentConnected = false
                agentState = "Stopped"
                agentConnectivityNote = "Enable the Peripheral Agent in Services."
                return
            }
            do {
                let hub = try validatedHubURL()
                let key = localHubKey(for: hub) ?? rememberedKey(for: hub)
                    ?? adminAPIKey.trimmingCharacters(in: .whitespacesAndNewlines)
                guard key.count >= 16 else {
                    agentConnected = false
                    agentState = "Service loaded · connection unverified"
                    agentConnectivityNote = "A remote Hub integration key is required to verify this station."
                    return
                }
                var request = URLRequest(url: hub.appendingPathComponent("v1/agents"))
                request.setValue(key, forHTTPHeaderField: "X-API-Key")
                request.timeoutInterval = 6
                let (data, response) = try await URLSession.shared.data(for: request)
                guard (response as? HTTPURLResponse)?.statusCode == 200,
                      let stations = try JSONSerialization.jsonObject(with: data) as? [[String: Any]] else {
                    throw NSError(domain: "DeviceShare", code: 185,
                                  userInfo: [NSLocalizedDescriptionKey: "Hub could not verify station status"])
                }
                let online = stations.contains(where: {
                    ($0["agent_id"] as? String) == stationID && ($0["online"] as? Bool) == true
                })
                agentConnected = online
                agentState = online ? "Connected to Hub" : "Service loaded · offline"
                agentConnectivityNote = online
                    ? "Station " + stationID + " is online and available for printing."
                    : "Agent registered with launchd but the Hub sees this station offline. Check its token and error logs."
            } catch {
                agentConnected = false
                agentState = "Service loaded · connection error"
                agentConnectivityNote = "Unable to verify agent connection: " + error.localizedDescription
            }
        }
    }

    func checkHubHealth() {
        Task {
            do {
                let base = try validatedHubURL()
                var request = URLRequest(url: base.appendingPathComponent("healthz"))
                request.timeoutInterval = 5
                let (data, response) = try await URLSession.shared.data(for: request)
                guard (response as? HTTPURLResponse)?.statusCode == 200,
                      let payload = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                      payload["service"] as? String == "deviceshare" else {
                    hubHealth = "Hub did not return a valid DeviceShare health response"
                    return
                }
                hubHealth = "Hub responding"
            } catch { hubHealth = "Hub unreachable" }
        }
    }

    private func secureRandomSecret() throws -> String {
        var bytes = [UInt8](repeating: 0, count: 32)
        guard SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes) == errSecSuccess else {
            throw NSError(domain: "DeviceShare", code: 110,
                          userInfo: [NSLocalizedDescriptionKey: "Secure random generation failed."])
        }
        return Data(bytes).base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }

    private func installLaunchAgent(label: String, binary: URL,
                                    arguments: [String], environment: [String: String] = [:]) throws {
        guard FileManager.default.isExecutableFile(atPath: binary.path) else {
            throw NSError(domain: "DeviceShare", code: 111,
                          userInfo: [NSLocalizedDescriptionKey: "Bundled agent/hub executable is missing. Reinstall DeviceShare.app."])
        }
        try makePrivateDirectory(supportURL)
        try makePrivateDirectory(logURL)
        try makePrivateDirectory(launchAgentsURL)
        let plistURL = launchAgentsURL.appendingPathComponent(label + ".plist")
        let definition: [String: Any] = [
            "Label": label,
            "ProgramArguments": [binary.path] + arguments,
            "WorkingDirectory": supportURL.path,
            "EnvironmentVariables": environment,
            "RunAtLoad": true,
            "KeepAlive": true,
            "ProcessType": "Background",
            "Umask": 63,
            "StandardOutPath": logURL.appendingPathComponent(label + ".out.log").path,
            "StandardErrorPath": logURL.appendingPathComponent(label + ".err.log").path
        ]
        let plist = try PropertyListSerialization.data(fromPropertyList: definition, format: .xml, options: 0)
        if isLoaded(label) {
            _ = try Self.capture(URL(fileURLWithPath: "/bin/launchctl"),
                                 arguments: ["bootout", serviceTarget(label)])
        }
        try writePrivate(plist, to: plistURL)
        let (status, output) = try Self.capture(URL(fileURLWithPath: "/bin/launchctl"),
                                                 arguments: ["bootstrap", "gui/\(getuid())", plistURL.path])
        guard status == 0 else {
            throw NSError(domain: "DeviceShare", code: 112,
                          userInfo: [NSLocalizedDescriptionKey: "launchctl bootstrap failed: " +
                                    String(decoding: output.prefix(350), as: UTF8.self)])
        }
    }

    private func stopLaunchAgent(_ label: String) throws {
        if isLoaded(label) {
            let (status, output) = try Self.capture(URL(fileURLWithPath: "/bin/launchctl"),
                                                     arguments: ["bootout", serviceTarget(label)])
            guard status == 0 else {
                throw NSError(domain: "DeviceShare", code: 113,
                              userInfo: [NSLocalizedDescriptionKey:
                                        "launchctl bootout failed: " + String(decoding: output.prefix(350), as: UTF8.self)])
            }
        }
    }

    func startLocalHub() {
        do {
            hubURL = "http://127.0.0.1:8765"
            _ = try validatedHubURL()
            if !hasLocalHubKey {
                let secret = try secureRandomSecret()
                try writePrivate(Data(secret.utf8), to: hubKeyURL)
            }
            try installLaunchAgent(
                label: hubLabel,
                binary: hubBinary,
                arguments: ["--api-key-file", hubKeyURL.path],
                environment: [
                    "DEVICESHARE_DB": localDBURL.path,
                    "DEVICESHARE_HOST": "127.0.0.1",
                    "DEVICESHARE_PORT": "8765"
                ])
            notice = "Local hub started on loopback. Pair your station to connect the agent."
            refreshServices()
            refreshActivationStatus()
        } catch { notice = error.localizedDescription }
    }

    func stopLocalHub() {
        do {
            try stopLaunchAgent(hubLabel)
            notice = "Local hub service stopped. No stored pairing credentials were removed."
            refreshServices()
        } catch { notice = error.localizedDescription }
    }

    func startAgent() {
        do {
            try saveConfiguration()
            guard hasToken else {
                throw NSError(domain: "DeviceShare", code: 114,
                              userInfo: [NSLocalizedDescriptionKey: "Pair a station token before enabling the agent."])
            }
            try installLaunchAgent(label: agentLabel, binary: agentBinary,
                                   arguments: ["--config", configURL.path])
            notice = "Station agent enabled for this user session. Check the hub dashboard for connection status."
            refreshServices()
        } catch { notice = error.localizedDescription }
    }

    func stopAgent() {
        do {
            try stopLaunchAgent(agentLabel)
            notice = "Station agent stopped. Your local configuration and credentials remain saved."
            refreshServices()
        } catch { notice = error.localizedDescription }
    }

    func openDiagnosticsConsole() {
        do {
            let url = try validatedHubURL().appendingPathComponent("diagnostics")
            NSWorkspace.shared.open(url)
        } catch { notice = error.localizedDescription }
    }

    func checkDiagnostics() {
        guard !isCheckingDiagnostics else { return }
        isCheckingDiagnostics = true
        diagnosticMessage = "Checking live station and printer state…"
        Task {
            defer { isCheckingDiagnostics = false }
            do {
                let hub = try validatedHubURL()
                let key = localHubKey(for: hub)
                    ?? rememberedKey(for: hub)
                    ?? adminAPIKey.trimmingCharacters(in: .whitespacesAndNewlines)
                guard key.count >= 16 else {
                    throw NSError(domain: "DeviceShare", code: 190,
                        userInfo: [NSLocalizedDescriptionKey:
                            "Unable to verify a remote Hub without its integration key. Check Keychain settings or sign in through the web console."])
                }
                var request = URLRequest(url: hub.appendingPathComponent("v1/diagnostics"))
                request.setValue(key, forHTTPHeaderField: "X-API-Key")
                request.timeoutInterval = 10
                let (data, response) = try await URLSession.shared.data(for: request)
                guard (response as? HTTPURLResponse)?.statusCode == 200 else {
                    throw NSError(domain: "DeviceShare", code: 191,
                        userInfo: [NSLocalizedDescriptionKey: "Hub diagnostics endpoint is unavailable. Upgrade the Hub and check its service status."])
                }
                let report = try JSONDecoder().decode(HubDiagnosticReport.self, from: data)
                hubDiagnostics = report
                let attention = report.findings.filter { $0.severity == "attention" }.count
                diagnosticMessage = attention == 0
                    ? "No configuration issues detected. Physical printer output is not verified by this check."
                    : "\(attention) diagnostic finding(s) need review. No automatic repair has been performed."
            } catch {
                hubDiagnostics = nil
                diagnosticMessage = error.localizedDescription
            }
        }
    }

    func requestLocalInventoryRescan() {
        Task {
            do {
                let hub = try validatedHubURL()
                let key = localHubKey(for: hub) ?? rememberedKey(for: hub)
                    ?? adminAPIKey.trimmingCharacters(in: .whitespacesAndNewlines)
                guard key.count >= 16 else {
                    throw NSError(domain: "DeviceShare", code: 192,
                        userInfo: [NSLocalizedDescriptionKey: "Hub integration key is unavailable."])
                }
                let encoded = stationID.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? stationID
                let url = hub.appendingPathComponent("v1/agents/" + encoded + "/refresh")
                var request = URLRequest(url: url)
                request.httpMethod = "POST"
                request.setValue(key, forHTTPHeaderField: "X-API-Key")
                request.timeoutInterval = 10
                let (data, response) = try await URLSession.shared.data(for: request)
                let status = (response as? HTTPURLResponse)?.statusCode ?? 0
                guard status == 200 else {
                    var message = "Station inventory refresh failed (HTTP \(status))."
                    if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                       let reason = json["detail"] as? String { message = reason }
                    throw NSError(domain: "DeviceShare", code: status,
                        userInfo: [NSLocalizedDescriptionKey: message])
                }
                diagnosticMessage = "Safe inventory rescan requested. Re-run checks to see updated results."
            } catch {
                diagnosticMessage = error.localizedDescription
            }
        }
    }

    func openDashboard() {
        do {
            let url = try validatedHubURL().appendingPathComponent("dashboard")
            NSWorkspace.shared.open(url)
        } catch { notice = error.localizedDescription }
    }

    func openSupportDirectory() {
        do {
            try makePrivateDirectory(supportURL)
            NSWorkspace.shared.open(supportURL)
        } catch { notice = error.localizedDescription }
    }
}
