import AppKit
import Observation
import SwiftUI
import UniformTypeIdentifiers

@MainActor
@Observable
final class WorkstationState {
    static var todayString: String {
        let f = DateFormatter()
        f.dateFormat = "yyyy_MM_dd"
        return f.string(from: Date())
    }

    // Branding
    var theme: BrandTheme

    // Workflow
    var mode: WorkflowMode = .batch
    var fps = "23.976"
    var aspect: Aspect = .r16x9
    var slateCodec: SlateCodec = .h264MOV { didSet { save() } }
    var autoTranscode = true { didSet { save() } }
    var dryRun = false
    var outputDir = "" { didSet { save() } }

    // Build Slates
    var slatesOnly = false
    var templatePath = "" { didSet { save() } }
    var videosDir = "" { didSet { save() } }
    var spreadsheetPath = ""
    var campaign = CampaignFields() { didSet { save() } }
    private var isApplyingCampaign = false
    var rows: [SlateRow] = [] {
        didSet {
            guard !isApplyingCampaign else { return }
            syncCampaignFromRows()
        }
    }
    var selection: Set<SlateRow.ID> = []
    var scanAspects: Set<Aspect> = []

    // Marry
    var slatesDir = "" { didSet { save() } }
    var marryCSV = ""
    var marryPairs: [MarryPair] = []

    // Un-Slate
    var unslateDir = "" { didSet { save() } }

    // Run state
    var isRunning = false
    var log: [LogLine] = []
    var showConsole = false
    var alert: AlertMessage?
    var previews: [PreviewItem] = []
    var showPreviews = false

    @ObservationIgnored private let worker = PythonWorker()
    @ObservationIgnored private var loading = true
    @ObservationIgnored private var marryScanGeneration = 0

    init(theme: BrandTheme) {
        self.theme = theme
        let d = UserDefaults.standard
        outputDir = d.string(forKey: "outputDir") ?? ""
        templatePath = d.string(forKey: "templatePath") ?? ""
        videosDir = d.string(forKey: "videosDir") ?? ""
        slatesDir = d.string(forKey: "slatesDir") ?? ""
        unslateDir = d.string(forKey: "unslateDir") ?? ""
        if let rawCodec = d.string(forKey: "slateCodec"), let c = SlateCodec(rawValue: rawCodec) {
            slateCodec = c
        }
        if d.object(forKey: "autoTranscode") != nil { autoTranscode = d.bool(forKey: "autoTranscode") }
        if let data = d.data(forKey: "campaign"), let c = try? JSONDecoder().decode(CampaignFields.self, from: data) {
            campaign = c
        }
        if campaign.copyright.isEmpty || campaign.copyright == "© 2026" {
            campaign.copyright = CampaignFields.defaultCopyright(for: campaign.client)
        }
        loading = false
    }

    private func save() {
        guard !loading else { return }
        let d = UserDefaults.standard
        d.set(outputDir, forKey: "outputDir")
        d.set(templatePath, forKey: "templatePath")
        d.set(videosDir, forKey: "videosDir")
        d.set(slatesDir, forKey: "slatesDir")
        d.set(unslateDir, forKey: "unslateDir")
        d.set(slateCodec.rawValue, forKey: "slateCodec")
        d.set(autoTranscode, forKey: "autoTranscode")
        d.set(try? JSONEncoder().encode(campaign), forKey: "campaign")
    }

    // MARK: - Rows

    func addRow() {
        var r = SlateRow(fields: [:])
        r.adID = ""
        r.title = ""
        r.aspect = aspect.rawValue
        r["trt"] = ":30"
        r["date"] = Self.todayString
        r["day"] = Self.todayString
        applyCampaign(to: &r, overwrite: true)
        rows.append(r)
        selection = [r.id]
    }

    func removeSelectedRows() {
        rows.removeAll { selection.contains($0.id) }
        selection = []
    }

    func duplicateSelectedRows(as newAspect: Aspect) {
        let picked = rows.filter { selection.contains($0.id) }
        for var r in picked.map({ SlateRow(fields: $0.fields) }) {
            r.aspect = newAspect.rawValue
            rows.append(r)
        }
    }

    /// Push the campaign card's fields into every row (blank fields only, unless overwrite).
    func applyCampaignToAll(overwrite: Bool) {
        isApplyingCampaign = true
        defer { isApplyingCampaign = false }
        for i in rows.indices { applyCampaign(to: &rows[i], overwrite: overwrite) }
    }

    /// Auto-update the campaign card to match current batch rows.
    /// If multiple clients/campaigns exist in the batch, default the changer to empty.
    func syncCampaignFromRows() {
        guard !rows.isEmpty else { return }

        func distinctValues(for keys: [String]) -> [String] {
            var seen = Set<String>()
            var list: [String] = []
            for r in rows {
                for k in keys {
                    let v = r[k].trimmingCharacters(in: .whitespacesAndNewlines)
                    if !v.isEmpty {
                        if !seen.contains(v) {
                            seen.insert(v)
                            list.append(v)
                        }
                        break
                    }
                }
            }
            return list
        }

        let clients = distinctValues(for: ["client", "brand", "advertiser"])
        let workspaces = distinctValues(for: ["workspace", "workspace_artist"])
        let agencies = distinctValues(for: ["agency"])
        let dates = distinctValues(for: ["date", "day"])
        let audios = distinctValues(for: ["audio"])
        let copyrights = distinctValues(for: ["copyright"])

        // If multiple clients/campaigns in batch, default changer to empty
        campaign.client = (clients.count == 1) ? clients[0] : ""
        campaign.workspace = (workspaces.count == 1) ? workspaces[0] : ""

        if agencies.count == 1 {
            campaign.agency = agencies[0]
        } else if agencies.count > 1 {
            campaign.agency = ""
        }

        if dates.count == 1 && dates[0] >= Self.todayString {
            campaign.date = dates[0]
        } else {
            campaign.date = Self.todayString
        }

        if audios.count == 1 {
            campaign.audio = audios[0]
        } else if audios.count > 1 {
            campaign.audio = ""
        }

        if copyrights.count == 1 {
            campaign.copyright = copyrights[0]
        } else if copyrights.count > 1 {
            campaign.copyright = ""
        } else {
            campaign.copyright = CampaignFields.defaultCopyright(for: campaign.client)
        }

        let flameValues = Set(rows.map(\.flame))
        campaign.flame = (flameValues.count == 1) ? (flameValues.first ?? false) : false

        let nfaValues = Set(rows.map { ["nfa", "y", "yes", "true", "1"].contains($0["nfa"].lowercased()) })
        campaign.nfa = (nfaValues.count == 1) ? (nfaValues.first ?? false) : false
    }

    private func applyCampaign(to r: inout SlateRow, overwrite: Bool) {
        func set(_ key: String, _ value: String, alias: String? = nil) {
            guard overwrite || r[key].isEmpty else { return }
            r[key] = value
            if let alias { r[alias] = value }
        }
        set("agency", campaign.agency)
        set("client", campaign.client)
        if !campaign.date.isEmpty { set("date", campaign.date, alias: "day") }
        set("workspace", campaign.workspace, alias: "workspace_artist")
        set("audio", campaign.audio)
        set("copyright", campaign.copyright)
        if overwrite { r.flame = campaign.flame; r["nfa"] = campaign.nfa ? "NFA" : "" }
    }

    // MARK: - Worker-backed actions

    func importSpreadsheetWithPanel() {
        guard let url = pick(files: true, types: ["xlsx", "csv", "tsv", "txt"]) else { return }
        importSpreadsheet(url.path)
    }

    /// Saves a fresh copy of the bundled sheet template, opens it in the default spreadsheet app and links it.
    func newSheetTemplate() {
        guard let src = Bundle.main.url(forResource: "Slates From Spreadsheet_Template_001", withExtension: "xlsx") else {
            appendLog(.error, "Bundled spreadsheet template not found"); return
        }
        let panel = NSSavePanel()
        panel.title = "Save New Copy of Spreadsheet Template"
        panel.allowedContentTypes = [UTType(filenameExtension: "xlsx")].compactMap { $0 }
        let f = DateFormatter(); f.dateFormat = "yyyy_MM_dd"
        panel.nameFieldStringValue = "Slates From Spreadsheet_\(f.string(from: Date())).xlsx"
        let start = [spreadsheetPath, outputDir, videosDir].first { !$0.isEmpty }
        if let start { panel.directoryURL = URL(fileURLWithPath: start).deletingLastPathComponent() }
        guard panel.runModal() == .OK, let dest = panel.url else { return }
        do {
            if FileManager.default.fileExists(atPath: dest.path) { try FileManager.default.removeItem(at: dest) }
            try FileManager.default.copyItem(at: src, to: dest)
            spreadsheetPath = dest.path
            mode = .batch
            NSWorkspace.shared.activateFileViewerSelecting([dest])
            NSWorkspace.shared.open(dest)
            appendLog(.info, "Created sheet template: \(dest.path)")
        } catch {
            appendLog(.error, "Could not save template copy: \(error.localizedDescription)")
        }
    }

    func importSpreadsheet(_ path: String) {
        spreadsheetPath = path
        mode = .batch
        Task {
            guard let res = await call(["parse", "--file", path], label: "Parsing \((path as NSString).lastPathComponent)") else { return }
            var parsed = (res["rows"] as? [[String: Any]] ?? []).map(SlateRow.init(any:))
            let today = Self.todayString
            for i in parsed.indices {
                let d = parsed[i]["date"].trimmingCharacters(in: .whitespacesAndNewlines)
                if d.isEmpty || d < today || d.uppercased().hasPrefix("YYYY") {
                    parsed[i]["date"] = today
                    parsed[i]["day"] = today
                }
            }
            rows = parsed
            appendLog(.info, "Imported \(parsed.count) row(s) from \((path as NSString).lastPathComponent)")
        }
    }

    func scanVideosIntoRows() {
        guard !videosDir.isEmpty else { return }
        var args = ["scan-videos", "--videos", videosDir, "--shared", campaign.json]
        if !scanAspects.isEmpty { args += ["--aspects", scanAspects.map(\.rawValue).sorted().joined(separator: ",")] }
        Task {
            guard let res = await call(args, label: "Scanning master videos") else { return }
            let found = (res["rows"] as? [[String: Any]] ?? []).map(SlateRow.init(any:))
            rows = found
            appendLog(.info, "Built \(found.count) row(s) from master video names")
        }
    }

    func scanMarryPairs() {
        marryScanGeneration += 1
        let generation = marryScanGeneration
        guard !slatesDir.isEmpty, !videosDir.isEmpty else { marryPairs = []; return }
        var args = ["scan-marry", "--slates", slatesDir, "--videos", videosDir]
        if !marryCSV.isEmpty { args += ["--csv", marryCSV] }
        Task {
            // A newer scan (folder changed again) supersedes this one, whichever finishes last.
            guard let res = await call(args, label: nil), generation == marryScanGeneration else { return }
            marryPairs = (res["pairs"] as? [[String: Any]] ?? []).map(MarryPair.init)
        }
    }

    var canRun: Bool {
        guard !isRunning else { return false }
        switch mode {
        case .batch:
            return !rows.isEmpty && (slatesOnly ? !(outputDir.isEmpty && spreadsheetPath.isEmpty) : !videosDir.isEmpty)
        case .marry: return !slatesDir.isEmpty && !videosDir.isEmpty
        case .unslate: return !unslateDir.isEmpty
        }
    }

    func run() {
        guard canRun else { return }
        var job: [String: Any] = [
            "mode": mode.rawValue,
            "theme": theme.key,
            "fps": fps,
            "aspect": aspect.rawValue,
            "slate_codec": slateCodec.rawValue,
            "output_dir": outputDir,
            "auto_transcode": autoTranscode,
            "dry_run": dryRun,
        ]
        switch mode {
        case .batch:
            job["rows"] = rows.map(\.fields)
            job["videos_dir"] = videosDir
            job["slates_only"] = slatesOnly
            job["workspace"] = campaign.workspace
            if !templatePath.isEmpty { job["template"] = templatePath }
            // Rows win over the file; the path only sets the default output parent (as in the Tk app).
            if !spreadsheetPath.isEmpty { job["spreadsheet"] = spreadsheetPath }
        case .marry:
            job["slates_dir"] = slatesDir
            job["videos_dir"] = videosDir
            if !marryCSV.isEmpty { job["csv"] = marryCSV }
        case .unslate:
            job["unslate_dir"] = unslateDir
        }
        guard let data = try? JSONSerialization.data(withJSONObject: job) else { return }
        showConsole = true
        let what = dryRun ? "Dry run: \(mode.title)" : mode.title
        Task {
            guard let res = await call(["run", "--job", "-"], stdin: data, label: what) else { return }
            if let items = res["previews"] as? [[String: Any]], !items.isEmpty { setPreviews(items) }
        }
    }

    func cancel() { worker.cancel() }

    /// Runs one worker command, routing events to the console and alerts. nil on failure.
    private func call(_ args: [String], stdin: Data? = nil, label: String?) async -> [String: Any]? {
        let isRun = args.first == "run"
        if isRun { isRunning = true }
        defer { if isRun { isRunning = false } }
        if let label { appendLog(.info, "▶︎ \(label)") }
        do {
            let res = try await worker.run(arguments: args, stdin: stdin) { [weak self] event in
                self?.handle(event)
            }
            if res["ok"] as? Bool != true {
                let err = res["error"] as? String
                if let err { appendLog(.error, err) }
                // Workflow failures already raised an alert event; only surface plain errors here.
                if !isRun || err != nil {
                    alert = AlertMessage(level: "error", title: "Worker Error", message: err ?? "The worker reported a failure.")
                }
                return nil
            }
            return res
        } catch {
            appendLog(.error, error.localizedDescription)
            alert = AlertMessage(level: "error", title: "Worker Error", message: error.localizedDescription)
            return nil
        }
    }

    private func handle(_ event: WorkerEvent) {
        switch event {
        case .log(let s): appendLog(.output, s)
        case .stderr(let s): appendLog(.output, s)
        case .alert(let level, let title, let message):
            appendLog(level == "error" ? .error : level == "warning" ? .warning : .info, "\(title): \(message)")
            alert = AlertMessage(level: level, title: title, message: message)
        case .previews(let items): setPreviews(items)
        case .progress, .result: break
        }
    }

    private func setPreviews(_ items: [[String: Any]]) {
        previews = items.compactMap { d in
            guard let p = d["image_path"] as? String else { return nil }
            return PreviewItem(adID: d["id"] as? String ?? "", aspect: d["aspect"] as? String ?? "",
                               title: d["title"] as? String ?? "", imagePath: p)
        }
        showPreviews = !previews.isEmpty
    }

    func appendLog(_ kind: LogLine.Kind, _ text: String) {
        log.append(LogLine(kind: kind, text: text))
        if log.count > 2000 { log.removeFirst(log.count - 2000) }
    }

    func revealPreviewsInFinder() {
        if let first = previews.first {
            let url = URL(fileURLWithPath: first.imagePath)
            NSWorkspace.shared.activateFileViewerSelecting([url])
        }
    }

    func exportThumbnailSheet() {
        guard let first = previews.first else { return }
        let previewsDir = URL(fileURLWithPath: first.imagePath).deletingLastPathComponent().path
        let projectFilesDir = URL(fileURLWithPath: previewsDir).deletingLastPathComponent().path
        let outDir = URL(fileURLWithPath: projectFilesDir).deletingLastPathComponent().path

        let clientToken = campaign.client.isEmpty ? "Slates" : campaign.client.replacingOccurrences(of: " ", with: "_")
        let outputBase = "\(outDir)/\(clientToken)_Contact_Sheet"
        let tpl = spreadsheetPath  // empty: order and metadata come from the preview file names

        appendLog(.info, "Generating high-res thumbnail sheet for \(previews.count) slates...")

        guard let pythonURL = PythonWorker.resolvePython() else {
            appendLog(.error, "Could not find python3 to generate thumbnail sheet.")
            return
        }

        let fm = FileManager.default
        var scriptURL: URL? = Bundle.main.resourceURL?.appendingPathComponent("make_contact_sheet.py")
        if scriptURL == nil || !fm.fileExists(atPath: scriptURL!.path) {
            let repoCandidates = ["tools/make_contact_sheet.py", "engine/make_contact_sheet.py"]
            for c in repoCandidates {
                if fm.fileExists(atPath: c) {
                    scriptURL = URL(fileURLWithPath: c)
                    break
                }
            }
        }

        guard let script = scriptURL else {
            appendLog(.error, "Could not locate make_contact_sheet.py")
            return
        }

        Task {
            let proc = Process()
            proc.executableURL = pythonURL
            proc.arguments = [script.path, previewsDir, tpl, outputBase,
                              "--client", campaign.client, "--agency", campaign.agency,
                              "--workspace", campaign.workspace, "--date", campaign.date]

            do {
                try proc.run()
                proc.waitUntilExit()

                if proc.terminationStatus == 0 {
                    let pdfPath = outputBase + ".pdf"
                    let pngPath = outputBase + ".png"
                    appendLog(.info, "Thumbnail sheet generated: \(pdfPath)")

                    if fm.fileExists(atPath: pdfPath) {
                        let openProc = Process()
                        openProc.executableURL = URL(fileURLWithPath: "/usr/bin/open")
                        openProc.arguments = ["-a", "Preview", pdfPath]
                        try? openProc.run()
                    }
                    if fm.fileExists(atPath: pngPath) {
                        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: pngPath)])
                    }
                } else {
                    appendLog(.error, "Contact sheet generator exited with status \(proc.terminationStatus)")
                }
            } catch {
                appendLog(.error, "Failed to run contact sheet generator: \(error.localizedDescription)")
            }
        }
    }

    // MARK: - Panels

    func pick(files: Bool, types: [String] = []) -> URL? {
        let panel = NSOpenPanel()
        panel.canChooseFiles = files
        panel.canChooseDirectories = !files
        panel.canCreateDirectories = true
        panel.allowsMultipleSelection = false
        if files, !types.isEmpty {
            panel.allowedContentTypes = types.compactMap { UTType(filenameExtension: $0) }
        }
        return panel.runModal() == .OK ? panel.url : nil
    }
}
