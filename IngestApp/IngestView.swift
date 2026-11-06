import SwiftUI

/// Ingest, phase 1: point at drives / cards / network folders, scan read-only, review the
/// proposed Date / Cam / Roll organisation, and import or generate camera reports.
struct IngestView: View {
    @Environment(IngestState.self) private var state

    var body: some View {
        let t = state.theme
        HSplitView {
            VStack(spacing: 12) {
                sourcesCard
                VSplitView {
                    rollsCard.frame(minHeight: 180)
                    clipsCard.frame(minHeight: 140).padding(.top, 12)
                }
            }
            .frame(minWidth: 620)
            .padding(.trailing, 6)
            ScrollView { JobCard() }
                .frame(minWidth: 300, idealWidth: 340, maxWidth: 400)
                .padding(.leading, 6)
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
                            .accessibilityLabel("Remove source")
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
                TableColumn("LUT") { (r: IngestRoll) in RollLUTMenu(roll: r.roll) }
                    .width(min: 70, ideal: 110)
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

/// Per-roll LUT override (EDIT / WEB), falling back to the job defaults.
struct RollLUTMenu: View {
    @Environment(IngestState.self) private var state
    let roll: String

    var body: some View {
        Menu(state.rollLUTLabel(roll)) {
            ForEach(["edit", "web"], id: \.self) { o in
                Menu(o.uppercased()) {
                    Button("Use job default") { state.setRollLUT(roll, output: o, value: nil) }
                    Button("None (keep log)") { state.setRollLUT(roll, output: o, value: "none") }
                    Button("Auto from camera gamma") { state.setRollLUT(roll, output: o, value: "auto") }
                    if !state.lutFiles.isEmpty { Divider() }
                    ForEach(state.lutFiles, id: \.self) { f in
                        Button((f as NSString).lastPathComponent) { state.setRollLUT(roll, output: o, value: f) }
                    }
                }
            }
        }
        .menuStyle(.borderlessButton)
        .fixedSize()
    }
}

/// Folder field for the ingest app (choose / clear, shows the path).
struct IngestFolderField: View {
    @Environment(IngestState.self) private var state
    let label: String
    @Binding var path: String
    var placeholder = "Choose a folder…"
    var message = ""

    var body: some View {
        let t = state.theme
        VStack(alignment: .leading, spacing: 5) {
            Text(label.uppercased()).font(t.font(10, weight: .bold)).foregroundStyle(t.textMuted).kerning(0.8)
            HStack(spacing: 8) {
                Image(systemName: "folder").foregroundStyle(path.isEmpty ? t.textMuted : t.accent)
                Text(path.isEmpty ? placeholder : (path as NSString).abbreviatingWithTildeInPath)
                    .font(t.font(12)).foregroundStyle(path.isEmpty ? t.textMuted : .white)
                    .lineLimit(1).truncationMode(.middle)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .help(path)
                if !path.isEmpty {
                    Button { path = "" } label: { Image(systemName: "xmark.circle.fill") }
                        .accessibilityLabel("Clear")
                        .buttonStyle(.plain).foregroundStyle(t.textMuted)
                }
                Button("Choose…") { if let p = state.chooseFolder(message, start: path) { path = p } }
                    .buttonStyle(AccentButtonStyle(theme: t, prominent: false))
            }
            .padding(.leading, 10).padding(.vertical, 4).padding(.trailing, 4)
            .background(t.recessed, in: RoundedRectangle(cornerRadius: 9))
            .overlay(RoundedRectangle(cornerRadius: 9).stroke(t.border))
        }
    }
}

/// Right-hand job setup: where things go, what to make, LUTs, then Plan / Start.
struct JobCard: View {
    @Environment(IngestState.self) private var state

    var body: some View {
        @Bindable var state = state
        let t = state.theme
        VStack(alignment: .leading, spacing: 14) {
            SectionTitle(text: "Job", symbol: "gearshape.2")
            VStack(alignment: .leading, spacing: 6) {
                Picker("", selection: $state.mode) {
                    ForEach(IngestMode.allCases) { Text($0.title).tag($0) }
                }
                .pickerStyle(.radioGroup).labelsHidden()
                Text(state.mode.detail).font(t.font(11)).foregroundStyle(t.textMuted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            IngestFolderField(label: "Project folder", path: $state.projectFolder,
                              placeholder: "OCF/, TRANSCODES/, REPORTS/ go here",
                              message: "Choose the project folder. It must not be on the source media.")
            if state.mode.copies {
                IngestFolderField(label: "Backup copy (optional)", path: $state.backupFolder,
                                  placeholder: "Second verified copy of OCF/",
                                  message: "Choose a second drive for a backup copy of the originals.")
            }
            if state.mode.transcodes {
                VStack(alignment: .leading, spacing: 6) {
                    Text("OUTPUTS").font(t.font(10, weight: .bold)).foregroundStyle(t.textMuted).kerning(0.8)
                    Toggle("EDIT · ProRes 422 Proxy · 1920×1080", isOn: $state.outputEdit)
                    Toggle("WEB · H.264 4–5 Mbps · 1920×1080", isOn: $state.outputWeb)
                    Stepper("Parallel transcodes: \(state.transcodeWorkers)", value: $state.transcodeWorkers, in: 1...4)
                        .help("How many ffmpeg encodes run at once. 2 keeps the Mac usable.")
                    Toggle("Burn in clip name + timecode (WEB)", isOn: $state.burnIn)
                        .disabled(!state.hasDrawtext)
                        .help(state.hasDrawtext ? "" : "This ffmpeg build has no drawtext filter (needs libfreetype).")
                }
                VStack(alignment: .leading, spacing: 6) {
                    Text("LUTS").font(t.font(10, weight: .bold)).foregroundStyle(t.textMuted).kerning(0.8)
                    IngestFolderField(label: "LUT library", path: $state.lutLibrary,
                                      placeholder: "Folder of .cube files",
                                      message: "Choose a folder of .cube LUTs.")
                    lutPicker("EDIT LUT", selection: $state.lutEdit)
                    lutPicker("WEB LUT", selection: $state.lutWeb)
                    HStack {
                        Text(state.cdlPath.isEmpty ? "No CDL look" : "CDL: " + (state.cdlPath as NSString).lastPathComponent)
                            .foregroundStyle(state.cdlPath.isEmpty ? t.textMuted : .white).lineLimit(1)
                        Spacer()
                        if !state.cdlPath.isEmpty {
                            Button("Clear") { state.cdlPath = "" }.buttonStyle(.borderless)
                        }
                        Button("CDL…") { state.chooseCDL() }
                            .buttonStyle(AccentButtonStyle(theme: t, prominent: false))
                    }
                    Text("Per-roll overrides: LUT column in the Rolls table. Auto picks a library LUT from the camera's gamma (e.g. S-Log3).")
                        .font(t.font(10)).foregroundStyle(t.textMuted).fixedSize(horizontal: false, vertical: true)
                }
            }
            Toggle("Also write camera reports", isOn: $state.cameraReportsWithJob)
            HStack {
                Button { state.checkPlan() } label: { Label("Check Plan…", systemImage: "checklist") }
                    .buttonStyle(AccentButtonStyle(theme: t))
                    .disabled(!state.canPlan)
                    .help("Read-only preflight: space, conflicts, LUTs. Start from the plan sheet.")
                Spacer()
            }
        }
        .font(t.font(12))
        .card(t)
        .sheet(isPresented: $state.showPlan) { PlanSheet() }
    }

    private func lutPicker(_ label: String, selection: Binding<String>) -> some View {
        Picker(label, selection: selection) {
            Text("None (keep log)").tag("none")
            Text("Auto from camera gamma").tag("auto")
            if !state.lutFiles.isEmpty { Divider() }
            ForEach(state.lutFiles, id: \.self) { Text(($0 as NSString).lastPathComponent).tag($0) }
            if !["none", "auto"].contains(selection.wrappedValue) && !state.lutFiles.contains(selection.wrappedValue) {
                Text((selection.wrappedValue as NSString).lastPathComponent).tag(selection.wrappedValue)
            }
        }
    }
}

struct PlanSheet: View {
    @Environment(IngestState.self) private var state
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        let t = state.theme
        let plan = state.plan
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                SectionTitle(text: "Plan · \(state.mode.title)", symbol: "checklist")
                Spacer()
                if let plan {
                    Text(plan.ok ? "Ready" : "Blocked")
                        .font(t.font(12, weight: .bold))
                        .foregroundStyle(plan.ok ? t.success : Color(hex: 0xFF6B63))
                }
            }
            if let plan {
                if state.mode.copies {
                    Text("\(plan.files) files · \(IngestFormat.bytes(plan.bytes)) to copy and verify (\(plan.hash)) to "
                         + ([state.projectFolder] + (state.backupFolder.isEmpty ? [] : [state.backupFolder]))
                            .map { ($0 as NSString).abbreviatingWithTildeInPath }.joined(separator: " and "))
                        .foregroundStyle(t.textMuted)
                }
                ScrollView {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(plan.errors, id: \.self) { e in
                            Label(e, systemImage: "xmark.octagon.fill").foregroundStyle(Color(hex: 0xFF6B63))
                        }
                        ForEach(plan.warnings, id: \.self) { w in
                            Label(w, systemImage: "exclamationmark.triangle.fill").foregroundStyle(t.highlight)
                        }
                        ForEach(plan.rolls) { r in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(r.label).font(t.font(12, weight: .bold))
                                Text(r.detail).foregroundStyle(t.textMuted)
                                if !r.luts.isEmpty { Text("LUT  " + r.luts).foregroundStyle(t.textMuted) }
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                Text("Source media is only read. Existing files are never overwritten: identical ones are skipped, different ones are flagged.")
                    .font(t.font(11)).foregroundStyle(t.textMuted)
            }
            HStack {
                Spacer()
                Button("Cancel") { dismiss() }
                    .buttonStyle(AccentButtonStyle(theme: t, prominent: false))
                    .keyboardShortcut(.cancelAction)
                Button { state.startJob() } label: { Label("Start", systemImage: "play.fill") }
                    .buttonStyle(AccentButtonStyle(theme: t))
                    .disabled(!(plan?.ok ?? false))
                    .keyboardShortcut(.defaultAction)
            }
        }
        .font(t.font(12))
        .padding(20)
        .frame(minWidth: 640, minHeight: 440)
        .background(t.background)
        .foregroundStyle(.white)
    }
}
