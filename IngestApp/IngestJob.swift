import AppKit
import Foundation

enum IngestMode: String, CaseIterable, Identifiable {
    case transcode, offload, offloadTranscode = "offload_transcode"
    var id: String { rawValue }
    var title: String {
        switch self {
        case .transcode: "Transcodes only"
        case .offload: "Copy originals only"
        case .offloadTranscode: "Copy originals + transcodes"
        }
    }
    var detail: String {
        switch self {
        case .transcode: "Originals stay where they are (read-only). Transcodes go to the project folder."
        case .offload: "Verified copy of the cards into OCF/ with MHL checksums. No transcodes."
        case .offloadTranscode: "Verified copy into OCF/, then transcodes made from the verified copy."
        }
    }
    var copies: Bool { self != .transcode }
    var transcodes: Bool { self != .offload }
}

/// Preflight result from ingest_worker.py `plan`.
struct IngestPlan {
    struct Roll: Identifiable {
        let id: String
        let label: String
        let detail: String
        let luts: String
    }
    let ok: Bool
    let errors: [String]
    let warnings: [String]
    let rolls: [Roll]
    let files: Int
    let bytes: Int64
    let hash: String

    init(_ d: [String: Any]) {
        ok = d["ok"] as? Bool ?? false
        errors = d["errors"] as? [String] ?? []
        warnings = d["warnings"] as? [String] ?? []
        files = d["files"] as? Int ?? 0
        bytes = (d["bytes"] as? NSNumber)?.int64Value ?? 0
        hash = d["hash"] as? String ?? ""
        rolls = (d["rolls"] as? [[String: Any]] ?? []).enumerated().map { i, r in
            let cam = r["cam"] as? String ?? "?", roll = r["roll"] as? String ?? "?"
            var bits = ["\(r["clips"] as? Int ?? 0) clips"]
            if let f = r["files"] as? Int { bits.append("\(f) files") }
            if let b = r["bytes"] as? NSNumber { bits.append(IngestFormat.bytes(b.int64Value)) }
            if let raw = r["raw_clips"] as? Int, raw > 0 { bits.append("\(raw) RAW") }
            if let already = r["already_at"] as? [String: Int], !already.isEmpty {
                bits.append("\(already.values.max() ?? 0) already copied")
            }
            let lutMap = r["luts"] as? [String: [String]] ?? [:]
            let luts = lutMap.keys.sorted().map { "\($0.uppercased()): \(lutMap[$0]!.joined(separator: ", "))" }
                .joined(separator: "   ")
            return Roll(id: "\(i)", label: "\(r["date"] as? String ?? "undated") · \(cam)-Cam · \(roll)",
                        detail: bits.joined(separator: " · "), luts: luts)
        }
    }
}

extension IngestState {
    var outputs: [String] { (outputEdit ? ["edit"] : []) + (outputWeb ? ["web"] : []) }
    var hasDrawtext: Bool { (capabilities["filters"] as? [String] ?? []).contains("drawtext") }

    var canPlan: Bool {
        !busy && !rolls.isEmpty && !projectFolder.isEmpty && (!mode.transcodes || !outputs.isEmpty)
    }

    func chooseFolder(_ message: String, start: String = "") -> String? {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.message = message
        if !start.isEmpty { panel.directoryURL = URL(fileURLWithPath: start) }
        return panel.runModal() == .OK ? panel.url?.path : nil
    }

    func chooseCDL() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.allowedContentTypes = ["cdl", "cc", "ccc"].compactMap { .init(filenameExtension: $0) }
        if panel.runModal() == .OK, let p = panel.url?.path { cdlPath = p }
    }

    func setRollLUT(_ roll: String, output: String, value: String?) {
        var m = rollLUTs[roll] ?? [:]
        m[output] = value
        rollLUTs[roll] = m.isEmpty ? nil : m
    }

    func rollLUTLabel(_ roll: String) -> String {
        guard let m = rollLUTs[roll], !m.isEmpty else { return "Default" }
        return m.keys.sorted().map { "\($0.uppercased()): \(Self.lutName(m[$0]!))" }.joined(separator: " ")
    }

    static func lutName(_ v: String) -> String {
        switch v {
        case "none": "None"
        case "auto": "Auto"
        default: (v as NSString).lastPathComponent
        }
    }

    private func lutValue(_ v: String) -> Any {
        v == "none" ? NSNull() : v
    }

    func jobJSON() -> Data? {
        guard let scan = scanJSON(),
              var payload = try? JSONSerialization.jsonObject(with: scan) as? [String: Any] else { return nil }
        var defaults: [String: Any] = [:]
        for (o, v) in [("edit", lutEdit), ("web", lutWeb)] {
            if cdlPath.isEmpty { defaults[o] = lutValue(v) } else { defaults[o] = ["lut": lutValue(v), "cdl": cdlPath] }
        }
        var rollLevel: [String: Any] = [:]
        for (roll, m) in rollLUTs {
            rollLevel[roll] = m.mapValues { lutValue($0) }
        }
        payload["mode"] = mode.rawValue
        payload["destinations"] = [projectFolder] + (backupFolder.isEmpty || !mode.copies ? [] : [backupFolder])
        payload["outputs"] = mode.transcodes ? outputs : []
        payload["luts"] = ["default": defaults, "rolls": rollLevel]
        if !lutLibrary.isEmpty { payload["lut_library"] = lutLibrary }
        payload["burn_in"] = burnIn && hasDrawtext
        payload["camera_reports"] = cameraReportsWithJob
        payload["transcode_workers"] = transcodeWorkers
        return try? JSONSerialization.data(withJSONObject: payload)
    }

    func checkPlan() {
        guard canPlan, let data = jobJSON() else { return }
        runWorker(["plan", "--job", "-"], stdin: data, label: "Checking plan (read-only)") { res in
            self.plan = IngestPlan(res["plan"] as? [String: Any] ?? [:])
            self.showPlan = true
        }
    }

    func startJob() {
        guard let data = jobJSON() else { return }
        showPlan = false
        showConsole = true
        jobRunning = true
        runWorker(["run", "--job", "-"], stdin: data, label: "\(mode.title): \(rolls.count) roll(s)") { res in
            self.jobRunning = false
            self.lastSummary = res
            let copy = res["copy"] as? [String: Int] ?? [:], tc = res["transcode"] as? [String: Int] ?? [:]
            var lines: [String] = []
            if self.mode.copies {
                lines.append("Copied + verified: \(copy["copied"] ?? 0) · already verified: \(copy["verified_existing"] ?? 0)")
                if (copy["conflict"] ?? 0) + (copy["failed"] ?? 0) > 0 {
                    lines.append("⚠︎ Conflicts: \(copy["conflict"] ?? 0) · failed: \(copy["failed"] ?? 0) (left untouched)")
                }
            }
            if self.mode.transcodes {
                lines.append("Transcodes made: \(tc["made"] ?? 0) · already there: \(tc["exists"] ?? 0) · failed: \(tc["failed"] ?? 0)")
                if let raw = tc["needs_raw_backend"], raw > 0 { lines.append("RAW (R3D) waiting for REDline/AME: \(raw)") }
            }
            if res["stopped"] as? Bool == true { lines.append("Stopped before finishing; run again to resume.") }
            for l in lines { self.appendLog(.info, l) }
            self.alert = AlertMessage(level: "info", title: (res["ok"] as? Bool ?? false) ? "Ingest finished" : "Ingest finished with problems",
                                      message: lines.joined(separator: "\n"))
            if let report = res["report"] as? String {
                NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: report)])
            }
        }
    }

    func refreshLUTLibrary() {
        guard !lutLibrary.isEmpty else { lutFiles = []; return }
        let lib = lutLibrary
        Task {
            do {
                let res = try await PythonWorkerShared.worker.run(arguments: ["luts", "--library", lib],
                                                                  script: "ingest_worker.py") { _ in }
                lutFiles = (res["library"] as? [String] ?? []).filter { $0.lowercased().hasSuffix(".cube") }
            } catch {
                lutFiles = []
            }
        }
    }

    func loadCapabilities() {
        Task {
            if let res = try? await PythonWorkerShared.worker.run(arguments: ["tools"], script: "ingest_worker.py", onEvent: { _ in }) {
                capabilities = res
                if let v = res["ffmpeg_version"] as? String { appendLog(.info, v) }
                if (res["hash_default"] as? String) == "md5" {
                    appendLog(.info, "Checksums: md5 (add the xxhash module to the embedded Python for xxh64)")
                }
            }
        }
    }
}

/// A second worker for quick lookups (LUT list, capabilities) so they never share the
/// cancellable process slot with a running job.
enum PythonWorkerShared {
    static let worker = PythonWorker()
}
