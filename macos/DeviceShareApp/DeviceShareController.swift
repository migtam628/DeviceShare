import AppKit
import Combine
import Foundation
import Security
import SwiftUI
import Darwin

struct LocalPeripheral: Codable, Identifiable {
    let id: String
    let kind: String
    let label: String

    var canApprove: Bool {
        id.hasPrefix("printer:") || id.hasPrefix("serial:") || id.hasPrefix("hid:")
    }
}

@MainActor
final class DeviceShareController: ObservableObject {
    @Published var hubURL = "http://127.0.0.1:8765"
    @Published var stationID = "station-01"
    @Published var adminAPIKey = ""
    @Published var manualToken = ""
    @Published var peripherals: [LocalPeripheral] = []
    @Published var approvals = Set<String>()
    @Published var hubHealth = "Not checked"
    @Published var agentState = "Stopped"
    @Published var localHubState = "Stopped"
    @Published var notice = "Choose a local hub or enter the URL of a trusted remote hub."
    @Published var isBusy = false

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

    var hasToken: Bool { (try? Data(contentsOf: tokenURL).count) ?? 0 >= 16 }
    var hasLocalHubKey: Bool { FileManager.default.fileExists(atPath: hubKeyURL.path) }
    var applicationSupportLocation: String { supportURL.path }

    init() {
        if let config = try? readConfig() {
            if let value = config["hub_url"] as? String { hubURL = value }
            if let value = config["agent_id"] as? String { stationID = value }
            let printerNames = config["allowed_printers"] as? [String] ?? []
            let serialNames = config["allowed_serial_ports"] as? [String] ?? []
            let hidNames = config["allowed_hid_devices"] as? [String] ?? []
            approvals = Set(printerNames.map { "printer:" + $0 }
                + serialNames.map { "serial:" + $0 } + hidNames)
            peripherals = approvals.sorted().map { LocalPeripheral(id: $0, kind: "saved", label: $0 + " (previously approved)") }
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
                let key = localHubKey(for: hub) ?? adminAPIKey.trimmingCharacters(in: .whitespacesAndNewlines)
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
                    result.append(LocalPeripheral(id: id, kind: "saved", label: id + " (offline / approved)"))
                }
                peripherals = result.sorted { $0.kind + $0.label < $1.kind + $1.label }
                notice = "Discovered \(live.count) peripheral entries. Only checked devices receive local approval."
            } catch {
                notice = "Device scan failed: " + error.localizedDescription
            }
        }
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
        agentState = isLoaded(agentLabel) ? "LaunchAgent loaded" : "Stopped"
        localHubState = isLoaded(hubLabel) ? "Local hub service loaded" : "Stopped"
        objectWillChange.send()
        checkHubHealth()
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
