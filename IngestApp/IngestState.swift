import AppKit
import Observation
import SwiftUI
import UniformTypeIdentifiers

/// State for the MSTR-SL8R Ingest companion app. Everything here is read-only with respect
/// to the source media: ingest_worker.py only reads cards and writes camera reports to a
/// folder outside them.
@MainActor
@Observable
final class IngestState {
    private static let script = "ingest_worker.py"

    var theme: BrandTheme

    var sources: [String] = []
    var rolls: [IngestRoll] = []
    var scanSources: [String] = []
    var selection: Set<IngestRoll.ID> = []
    var imports: [String] = []

    var probe = true { didSet { save() } }
    var thumbnails = true { didSet { save() } }
    var dayStartHour = 0 { didSet { save() } }
    var reportFolder = "" { didSet { save() } }

    var busy = false
    var progress = ""
    var log: [LogLine] = []
    var showConsole = false
    var alert: AlertMessage?

    @ObservationIgnored private let worker = PythonWorker()
    @ObservationIgnored private var loading = true

    init(theme: BrandTheme) {
        self.theme = theme
        let d = UserDefaults.standard
        if d.object(forKey: "probe") != nil { probe = d.bool(forKey: "probe") }
        if d.object(forKey: "thumbnails") != nil { thumbnails = d.bool(forKey: "thumbnails") }
        dayStartHour = d.integer(forKey: "dayStartHour")
        reportFolder = d.string(forKey: "reportFolder") ?? ""
        loading = false
    }

    private func save() {
        guard !loading else { return }
        let d = UserDefaults.standard
        d.set(probe, forKey: "probe")
        d.set(thumbnails, forKey: "thumbnails")
        d.set(dayStartHour, forKey: "dayStartHour")
        d.set(reportFolder, forKey: "reportFolder")
    }

    // MARK: - Sources

    func addSourcesWithPanel() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = true
        panel.prompt = "Add Source"
        panel.message = "Choose a drive, card, or folder (network shares work too). It is only read, never changed."
        guard panel.runModal() == .OK else { return }
        addSources(panel.urls.map(\.path))
    }

    func addSources(_ paths: [String]) {
        for p in paths where !sources.contains(p) { sources.append(p) }
    }

    func removeSource(_ path: String) {
        sources.removeAll { $0 == path }
    }

    // MARK: - Worker-backed actions

    var canScan: Bool { !busy && !sources.isEmpty }

    func scan() {
        guard canScan else { return }
        var args = ["scan"]
        for s in sources { args += ["--source", s] }
        if !probe { args.append("--no-probe") }
        if dayStartHour > 0 { args += ["--day-start-hour", String(dayStartHour)] }
        runWorker(args, label: "Scanning \(sources.count) source(s) (read-only)") { res in
            self.applyResult(res)
            self.imports = (res["imports"] as? [[String: Any]] ?? []).map(Self.describeImport)
            let clips = self.rolls.reduce(0) { $0 + $1.clipCount }
            self.appendLog(.info, "Found \(self.rolls.count) roll(s), \(clips) clip(s)")
            for line in self.imports { self.appendLog(.info, line) }
            let tools = res["tools"] as? [String: Any] ?? [:]
            if self.probe, tools["ffprobe"] as? String == nil {
                self.appendLog(.warning, "ffprobe not found: clip metadata limited to Sony XML / file names")
            }
        }
    }

    func importCameraReportWithPanel() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.allowedContentTypes = ["csv", "tsv", "xlsx", "txt"].compactMap { UTType(filenameExtension: $0) }
        guard panel.runModal() == .OK, let url = panel.url, let data = scanJSON() else { return }
        runWorker(["import-report", "--scan", "-", "--report", url.path], stdin: data,
                  label: "Importing camera report \(url.lastPathComponent)") { res in
            self.applyResult(res)
            if let s = res["import_summary"] as? [String: Any] {
                let line = Self.describeImport(s.merging(["path": url.path]) { _, b in b })
                self.imports.append(line)
                self.appendLog(.info, line)
            }
        }
    }

    func generateCameraReportsWithPanel(selectedOnly: Bool) {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.prompt = "Save Reports Here"
        panel.message = "Choose where to write camera reports. It must not be on the source media."
        if !reportFolder.isEmpty { panel.directoryURL = URL(fileURLWithPath: reportFolder) }
        guard panel.runModal() == .OK, let out = panel.url else { return }
        reportFolder = out.path
        guard let data = scanJSON(onlySelected: selectedOnly) else { return }
        var args = ["camera-report", "--scan", "-", "--out", out.path]
        if !thumbnails { args.append("--no-thumbs") }
        runWorker(args, stdin: data, label: "Generating camera reports") { res in
            let written = res["written"] as? [[String: Any]] ?? []
            self.appendLog(.info, "Wrote \(written.count) camera report(s) to \(out.path)")
            if let first = written.first?["html"] as? String {
                NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: first)])
            }
        }
    }

    func cancel() { worker.cancel() }

    // MARK: - Helpers

    private func runWorker(_ args: [String], stdin: Data? = nil, label: String,
                           then: @escaping ([String: Any]) -> Void) {
        busy = true
        progress = ""
        appendLog(.info, "▶︎ \(label)")
        Task {
            defer { busy = false; progress = "" }
            do {
                let res = try await worker.run(arguments: args, stdin: stdin, script: Self.script) { [weak self] e in
                    self?.handle(e)
                }
                if res["ok"] as? Bool == true {
                    then(res)
                } else {
                    let err = res["error"] as? String ?? "The worker reported a failure."
                    appendLog(.error, err)
                    alert = AlertMessage(level: "error", title: "Ingest Error", message: err)
                }
            } catch {
                appendLog(.error, error.localizedDescription)
                alert = AlertMessage(level: "error", title: "Ingest Error", message: error.localizedDescription)
            }
        }
    }

    private func handle(_ event: WorkerEvent) {
        switch event {
        case .log(let s), .stderr(let s): appendLog(.output, s)
        case .alert(let level, let title, let message):
            appendLog(level == "error" ? .error : level == "warning" ? .warning : .info, "\(title): \(message)")
            alert = AlertMessage(level: level, title: title, message: message)
        case .progress(let stage, let done, let total):
            let what = ["walk": "Walking folders", "probe": "Reading clip metadata", "thumbs": "Making thumbnails"][stage] ?? stage
            progress = total.map { "\(what) \(done)/\($0)" } ?? "\(what)… \(done)"
        case .previews, .result: break
        }
    }

    func appendLog(_ kind: LogLine.Kind, _ text: String) {
        log.append(LogLine(kind: kind, text: text))
        if log.count > 2000 { log.removeFirst(log.count - 2000) }
    }

    private func applyResult(_ res: [String: Any]) {
        let previous = Dictionary(uniqueKeysWithValues: rolls.map { ($0.id, ($0.cam, $0.roll)) })
        let keepEdits = (res["sources"] as? [String]) == scanSources
        scanSources = res["sources"] as? [String] ?? []
        rolls = (res["rolls"] as? [[String: Any]] ?? []).map { d in
            var r = IngestRoll(any: d)
            if keepEdits, let e = previous[r.id] { r.cam = e.0; r.roll = e.1 }
            return r
        }
        selection = selection.filter { id in rolls.contains { $0.id == id } }
        if selection.isEmpty, let first = rolls.first { selection = [first.id] }
    }

    private func scanJSON(onlySelected: Bool = false) -> Data? {
        let picked = onlySelected && !selection.isEmpty ? rolls.filter { selection.contains($0.id) } : rolls
        guard !picked.isEmpty else { return nil }
        let payload: [String: Any] = ["sources": scanSources, "rolls": picked.map(\.edited)]
        return try? JSONSerialization.data(withJSONObject: payload)
    }

    private static func describeImport(_ d: [String: Any]) -> String {
        let name = ((d["path"] as? String ?? "") as NSString).lastPathComponent
        if let err = d["error"] as? String { return "Camera report \(name): could not read (\(err))" }
        let matched = d["matched"] as? Int ?? 0, rows = d["rows"] as? Int ?? 0
        return "Camera report \(name): matched \(matched) of \(rows) row(s) to clips"
    }
}
