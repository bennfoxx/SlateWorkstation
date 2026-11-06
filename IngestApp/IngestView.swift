import SwiftUI

/// Ingest, phase 1: point at drives / cards / network folders, scan read-only, review the
/// proposed Date / Cam / Roll organisation, and import or generate camera reports.
struct IngestView: View {
    @Environment(IngestState.self) private var state

    var body: some View {
        let t = state.theme
        VStack(spacing: 12) {
            sourcesCard
            VSplitView {
                rollsCard.frame(minHeight: 180)
                clipsCard.frame(minHeight: 140).padding(.top, 12)
            }
        }
        .foregroundStyle(.white)
        .font(t.font(12))
    }

    private var sourcesCard: some View {
        @Bindable var state = state
        let t = state.theme
        return VStack(alignment: .leading, spacing: 10) {
            HStack {
                SectionTitle(text: "Sources", symbol: "externaldrive")
                Label("Read-only: nothing on the source media is changed", systemImage: "lock.fill")
                    .font(t.font(11)).foregroundStyle(t.success)
                Spacer()
                Button { state.addSourcesWithPanel() } label: { Label("Add Source…", systemImage: "plus") }
                    .buttonStyle(AccentButtonStyle(theme: t, prominent: false))
                    .disabled(state.busy)
            }
            if state.sources.isEmpty {
                Text("Drop a drive, camera card, or folder (local or network) here, or use Add Source…")
                    .foregroundStyle(t.textMuted)
                    .frame(maxWidth: .infinity, minHeight: 34)
                    .background(t.recessed, in: RoundedRectangle(cornerRadius: 9))
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(state.sources, id: \.self) { s in
                            HStack(spacing: 6) {
                                Image(systemName: s.hasPrefix("/Volumes/") ? "externaldrive.fill" : "folder.fill")
                                    .foregroundStyle(t.accent)
                                Text((s as NSString).abbreviatingWithTildeInPath).lineLimit(1)
                                Button { state.removeSource(s) } label: { Image(systemName: "xmark.circle.fill") }
                                    .buttonStyle(.plain).foregroundStyle(t.textMuted)
                                    .disabled(state.busy)
                            }
                            .padding(.horizontal, 10).padding(.vertical, 6)
                            .background(t.recessed, in: Capsule())
                            .overlay(Capsule().stroke(t.border))
                        }
                    }
                }
            }
        }
        .card(t)
        .onDrop(of: [.fileURL], isTargeted: nil) { providers in
            for p in providers {
                _ = p.loadObject(ofClass: URL.self) { url, _ in
                    guard let url else { return }
                    var isDir: ObjCBool = false
                    guard FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir), isDir.boolValue else { return }
                    Task { @MainActor in state.addSources([url.path]) }
                }
            }
            return true
        }
    }

    private var rollsCard: some View {
        @Bindable var state = state
        let t = state.theme
        let clips = state.rolls.reduce(0) { $0 + $1.clipCount }
        let bytes = state.rolls.reduce(Int64(0)) { $0 + $1.bytes }
        return VStack(alignment: .leading, spacing: 10) {
            HStack {
                SectionTitle(text: "Rolls  (\(state.rolls.count))", symbol: "square.stack.3d.up")
                if !state.rolls.isEmpty {
                    Text("\(clips) clips · \(IngestFormat.bytes(bytes))").foregroundStyle(t.textMuted)
                }
                Spacer()
                Text("Cam and Roll are editable before making reports")
                    .font(t.font(11)).foregroundStyle(t.textMuted)
            }
            Table(state.rolls, selection: $state.selection) {
                Group {
                TableColumn("Date") { (r: IngestRoll) in Text(r.date.isEmpty ? "—" : r.date) }
                    .width(min: 80, ideal: 90)
                TableColumn("Cam") { (r: IngestRoll) in TextField("A", text: rollBinding(r.id, \.cam)) }
                    .width(min: 34, ideal: 40, max: 50)
                TableColumn("Roll") { (r: IngestRoll) in TextField("A001", text: rollBinding(r.id, \.roll)) }
                    .width(min: 50, ideal: 60, max: 80)
                TableColumn("Type") { (r: IngestRoll) in Text(r.kindLabel) }
                    .width(min: 60, ideal: 80)
                TableColumn("Camera") { (r: IngestRoll) in Text(r.camera.isEmpty ? "—" : r.camera).lineLimit(1) }
                    .width(min: 70, ideal: 100)
                TableColumn("Clips") { (r: IngestRoll) in Text("\(r.clipCount)") }
                    .width(min: 36, ideal: 44)
                TableColumn("Size") { (r: IngestRoll) in Text(IngestFormat.bytes(r.bytes)) }
                    .width(min: 60, ideal: 70)
                }
                Group {
                TableColumn("Duration") { (r: IngestRoll) in Text(IngestFormat.duration(r.duration)) }
                    .width(min: 56, ideal: 64)
                TableColumn("Format") { (r: IngestRoll) in Text(r.format).lineLimit(1) }
                    .width(min: 90, ideal: 130)
                TableColumn("Codec") { (r: IngestRoll) in Text(r.codecs).lineLimit(1) }
                    .width(min: 60, ideal: 90)
                TableColumn("Gamma") { (r: IngestRoll) in Text(r.gammas).lineLimit(1) }
                    .width(min: 60, ideal: 90)
                TableColumn("Report") { (r: IngestRoll) in
                    Text(r.reportStatus)
                        .foregroundStyle(r.reportStatus == "None" ? t.textMuted : t.success)
                        .help((r.importedReports + r.foundReports).joined(separator: "\n"))
                }
                .width(min: 60, ideal: 80)
                TableColumn("Source") { (r: IngestRoll) in
                    Text((r.root as NSString).abbreviatingWithTildeInPath)
                        .lineLimit(1).truncationMode(.head).foregroundStyle(t.textMuted)
                        .help(r.root)
                }
                .width(min: 120, ideal: 220)
                }
            }
            .tableStyle(.bordered(alternatesRowBackgrounds: true))
            .scrollContentBackground(.hidden)
            .background(t.recessed, in: RoundedRectangle(cornerRadius: 8))
            .overlay {
                if state.rolls.isEmpty {
                    VStack(spacing: 6) {
                        Image(systemName: state.busy ? "hourglass" : "magnifyingglass").font(.system(size: 28))
                        Text(state.busy ? "Scanning…" : "Add a source and press Scan. Sony, RED and loose MOV/MP4/MXF folders are recognised.")
                    }
                    .foregroundStyle(t.textMuted).allowsHitTesting(false)
                }
            }
        }
        .card(t)
    }

    private func rollBinding(_ id: IngestRoll.ID, _ key: WritableKeyPath<IngestRoll, String>) -> Binding<String> {
        Binding(
            get: { state.rolls.first { $0.id == id }?[keyPath: key] ?? "" },
            set: { v in
                if let i = state.rolls.firstIndex(where: { $0.id == id }) { state.rolls[i][keyPath: key] = v }
            })
    }

    private var selectedRoll: IngestRoll? {
        guard let id = state.selection.first else { return nil }
        return state.rolls.first { $0.id == id }
    }

    private var clipsCard: some View {
        let t = state.theme
        let roll = selectedRoll
        let clips: [IngestClip] = roll?.clips ?? []
        return VStack(alignment: .leading, spacing: 10) {
            HStack {
                SectionTitle(text: roll.map { "Clips · \($0.cam) Cam · \($0.roll)" } ?? "Clips", symbol: "film")
                Spacer()
                if let roll, !roll.root.isEmpty {
                    Button { NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: roll.root)]) } label: {
                        Label("Show in Finder", systemImage: "folder")
                    }
                    .buttonStyle(AccentButtonStyle(theme: t, prominent: false))
                }
            }
            Table(clips) {
                Group {
                TableColumn("Clip") { (c: IngestClip) in
                    HStack(spacing: 4) {
                        if !c.problem.isEmpty {
                            Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(t.highlight).help(c.problem)
                        }
                        Text(c.name)
                    }
                }
                .width(min: 120, ideal: 170)
                TableColumn("TC In") { (c: IngestClip) in Text(c.timecode).monospacedDigit() }.width(min: 80, ideal: 90)
                TableColumn("Duration") { (c: IngestClip) in Text(IngestFormat.duration(c.duration)) }.width(min: 56, ideal: 64)
                TableColumn("FPS") { (c: IngestClip) in Text(c.fps) }.width(min: 40, ideal: 50)
                TableColumn("Res") { (c: IngestClip) in Text(c.resolution) }.width(min: 70, ideal: 84)
                }
                Group {
                TableColumn("Codec") { (c: IngestClip) in Text(c.codec) }.width(min: 60, ideal: 80)
                TableColumn("Gamma") { (c: IngestClip) in Text(c.gamma) }.width(min: 60, ideal: 90)
                TableColumn("Scene") { (c: IngestClip) in Text(c.scene) }.width(min: 40, ideal: 50)
                TableColumn("Take") { (c: IngestClip) in Text(c.take) }.width(min: 36, ideal: 40)
                TableColumn("Notes") { (c: IngestClip) in Text(c.notes).lineLimit(1).help(c.notes) }.width(min: 80, ideal: 160)
                TableColumn("Size") { (c: IngestClip) in Text(IngestFormat.bytes(c.bytes)) }.width(min: 60, ideal: 70)
                }
            }
            .tableStyle(.bordered(alternatesRowBackgrounds: true))
            .scrollContentBackground(.hidden)
            .background(t.recessed, in: RoundedRectangle(cornerRadius: 8))
        }
        .card(t)
    }
}

/// Bottom bar for the Ingest tab (replaces the slate RunBar).
struct IngestBar: View {
    @Environment(IngestState.self) private var state

    var body: some View {
        @Bindable var state = state
        let t = state.theme
        let hasRolls = !state.rolls.isEmpty
        VStack(spacing: 10) {
            HStack(spacing: 18) {
                Toggle("Read clip metadata (ffprobe)", isOn: $state.probe)
                    .help("Off = faster scan using only file names and Sony XML")
                Stepper(value: $state.dayStartHour, in: 0...12) {
                    Text(state.dayStartHour == 0 ? "Shoot day starts at midnight"
                         : "Shoot day starts at \(state.dayStartHour):00")
                }
                .help("Clips shot after midnight but before this hour count as the previous shoot day")
                Toggle("Thumbnails in reports", isOn: $state.thumbnails)
                Spacer()
                if !state.imports.isEmpty {
                    Text(state.imports.last ?? "").foregroundStyle(t.textMuted).lineLimit(1)
                        .help(state.imports.joined(separator: "\n"))
                }
            }
            HStack(spacing: 10) {
                Button { state.showConsole.toggle() } label: {
                    Label(state.showConsole ? "Hide Log" : "Show Log", systemImage: "terminal")
                }
                .buttonStyle(AccentButtonStyle(theme: t, prominent: false))
                Button { state.importCameraReportWithPanel() } label: {
                    Label("Import Camera Report…", systemImage: "tablecells.badge.ellipsis")
                }
                .buttonStyle(AccentButtonStyle(theme: t, prominent: false))
                .disabled(!hasRolls || state.busy)
                .help("CSV / TSV / XLSX from the camera department, Silverstack or ShotPut; merged onto clips by clip name")
                Menu {
                    Button("All Rolls") { state.generateCameraReportsWithPanel(selectedOnly: false) }
                    Button("Selected Roll") { state.generateCameraReportsWithPanel(selectedOnly: true) }
                        .disabled(state.selection.isEmpty)
                } label: {
                    Label("Generate Camera Reports…", systemImage: "doc.richtext")
                }
                .menuStyle(.borderlessButton).fixedSize()
                .disabled(!hasRolls || state.busy)
                .help("HTML + CSV per roll, with thumbnails, written outside the source media")
                Spacer()
                if state.busy {
                    Text(state.progress).foregroundStyle(t.textMuted).monospacedDigit()
                    ProgressView().controlSize(.small)
                    Button("Stop") { state.cancel() }
                        .buttonStyle(AccentButtonStyle(theme: t, prominent: false))
                }
                Button { state.scan() } label: {
                    Label(state.busy ? "Working…" : (hasRolls ? "Rescan" : "Scan"), systemImage: "magnifyingglass")
                        .frame(minWidth: 150)
                }
                .buttonStyle(AccentButtonStyle(theme: t))
                .disabled(!state.canScan)
            }
        }
        .font(t.font(12))
        .card(t)
        .padding(.horizontal, 20).padding(.vertical, 12)
    }
}
