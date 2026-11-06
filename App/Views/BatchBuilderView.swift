import SwiftUI

struct BatchBuilderView: View {
    @Environment(WorkstationState.self) private var state

    var body: some View {
        @Bindable var state = state
        let t = state.theme
        HSplitView {
            VStack(spacing: 12) {
                sourcesCard
                queueCard
            }
            .frame(minWidth: 560)
            .padding(.trailing, 6)

            ScrollView {
                VStack(spacing: 12) {
                    CampaignCard()
                    SlatePreviewCard(row: selectedRow)
                }
            }
            .frame(minWidth: 280, idealWidth: 320, maxWidth: 380)
            .padding(.leading, 6)
        }
        .foregroundStyle(.white)
        .font(t.font(12))
    }

    private var selectedRow: SlateRow? {
        guard let id = state.selection.first else { return state.rows.first }
        return state.rows.first { $0.id == id }
    }

    private var sourcesCard: some View {
        @Bindable var state = state
        let t = state.theme
        return VStack(alignment: .leading, spacing: 10) {
            HStack {
                SectionTitle(text: "Sources", symbol: "tray.full")
                Spacer()
                Picker("", selection: $state.slatesOnly) {
                    Text("Slate + Master Videos").tag(false)
                    Text("Standalone Slates Only").tag(true)
                }
                .pickerStyle(.segmented).labelsHidden().frame(width: 330)
            }
            PathField(label: "Slate Template (.aep)", path: $state.templatePath, files: true, types: ["aep"],
                      placeholder: "Bundled slate template (Template_006)")
            if !state.slatesOnly {
                PathField(label: "Master Videos Folder", path: $state.videosDir)
            }
        }
        .card(t)
    }

    private var queueCard: some View {
        @Bindable var state = state
        let t = state.theme
        return VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                SectionTitle(text: "Slate Queue  (\(state.rows.count))", symbol: "list.bullet.rectangle")
                Spacer()
                Button { state.importSpreadsheetWithPanel() } label: { Label("Import Sheet…", systemImage: "tablecells") }
                    .buttonStyle(AccentButtonStyle(theme: t, prominent: false))
                    .help("Load an .xlsx / .csv / .tsv slate sheet (replaces the queue)")
                Button { state.newSheetTemplate() } label: { Label("New Sheet Template…", systemImage: "doc.badge.plus") }
                    .buttonStyle(AccentButtonStyle(theme: t, prominent: false))
                    .help("Save a fresh copy of the spreadsheet template and open it")
                Menu {
                    Text("Aspects per video (none = from file name)")
                    ForEach(Aspect.allCases) { a in
                        Toggle(a.label, isOn: Binding(
                            get: { state.scanAspects.contains(a) },
                            set: { on in if on { state.scanAspects.insert(a) } else { state.scanAspects.remove(a) } }))
                    }
                    Divider()
                    Button("Build Queue From Master Videos") { state.scanVideosIntoRows() }
                } label: {
                    Label("From Videos", systemImage: "film.stack")
                }
                .menuStyle(.borderlessButton).fixedSize()
                .disabled(state.videosDir.isEmpty)
                .help("Create one row per master video (replaces the queue)")
            }
            SlateTable()
                .frame(minHeight: 140)
            HStack(spacing: 8) {
                Button { state.addRow() } label: { Label("Add Spot", systemImage: "plus") }
                    .buttonStyle(AccentButtonStyle(theme: t, prominent: false))
                Button { state.removeSelectedRows() } label: { Label("Remove", systemImage: "minus") }
                    .buttonStyle(AccentButtonStyle(theme: t, prominent: false))
                    .disabled(state.selection.isEmpty)
                Menu {
                    ForEach(Aspect.allCases) { a in
                        Button(a.label) { state.duplicateSelectedRows(as: a) }
                    }
                } label: { Label("Add Aspect Copy", systemImage: "plus.rectangle.on.rectangle") }
                    .menuStyle(.borderlessButton).fixedSize()
                    .disabled(state.selection.isEmpty)
                Spacer()
                if !state.spreadsheetPath.isEmpty {
                    Text((state.spreadsheetPath as NSString).lastPathComponent)
                        .foregroundStyle(t.textMuted).lineLimit(1).truncationMode(.middle)
                }
            }
        }
        .card(t)
        .onDrop(of: [.fileURL], isTargeted: nil) { providers in
            guard let p = providers.first else { return false }
            _ = p.loadObject(ofClass: URL.self) { url, _ in
                guard let url, ["xlsx", "csv", "tsv", "txt"].contains(url.pathExtension.lowercased()) else { return }
                Task { @MainActor in state.importSpreadsheet(url.path) }
            }
            return true
        }
    }
}

struct SlateTable: View {
    @Environment(WorkstationState.self) private var state

    var body: some View {
        @Bindable var state = state
        Table($state.rows, selection: $state.selection) {
            TableColumn("Aspect") { $row in
                Picker("", selection: Binding(get: { row.aspect }, set: { row.aspect = $0 })) {
                    ForEach(Aspect.allCases) { Text($0.rawValue).tag($0.rawValue) }
                }
                .labelsHidden()
            }
            .width(min: 70, ideal: 80, max: 90)
            TableColumn("Ad-ID") { $row in
                TextField("Ad-ID", text: Binding(get: { row.adID }, set: { row.adID = $0 }))
            }
            .width(min: 80, ideal: 110)
            TableColumn("Title") { $row in
                TextField("Title", text: Binding(get: { row.title }, set: { row.title = $0 }))
            }
            .width(min: 120, ideal: 200)
            TableColumn("TRT") { $row in
                TextField(":30", text: Binding(get: { row["trt"] }, set: { row["trt"] = $0; row["duration"] = $0 }))
            }
            .width(min: 40, ideal: 50, max: 60)
            TableColumn("Client") { $row in
                TextField("Client", text: $row.fields[key: "client"])
            }
            .width(min: 70, ideal: 100)
            TableColumn("Flame") { $row in
                Toggle("", isOn: Binding(get: { row.flame }, set: { row.flame = $0 })).labelsHidden()
            }
            .width(44)
        }
        .tableStyle(.bordered(alternatesRowBackgrounds: true))
        .scrollContentBackground(.hidden)
        .background(state.theme.recessed, in: RoundedRectangle(cornerRadius: 8))
        .overlay {
            if state.rows.isEmpty {
                VStack(spacing: 6) {
                    Image(systemName: "tablecells.badge.ellipsis").font(.system(size: 28))
                    Text("Drop a slate sheet here, import one, build from master videos, or add spots.")
                }
                .foregroundStyle(state.theme.textMuted)
                .allowsHitTesting(false)
            }
        }
    }
}

extension Dictionary where Key == String, Value == String {
    subscript(key key: String) -> String {
        get { self[key] ?? "" }
        set { self[key] = newValue }
    }
}

struct CampaignCard: View {
    @Environment(WorkstationState.self) private var state
    var body: some View {
        @Bindable var state = state
        let t = state.theme
        VStack(alignment: .leading, spacing: 10) {
            SectionTitle(text: "Campaign", symbol: "megaphone")
            LabeledField(label: "Agency", text: $state.campaign.agency, prompt: "MARTIN*")
            LabeledField(label: "Client", text: Binding(
                get: { state.campaign.client },
                set: { newClient in
                    let oldDefault = CampaignFields.defaultCopyright(for: state.campaign.client)
                    state.campaign.client = newClient
                    if state.campaign.copyright.isEmpty || state.campaign.copyright == oldDefault || state.campaign.copyright == "© 2026" {
                        state.campaign.copyright = CampaignFields.defaultCopyright(for: newClient)
                    }
                }
            ))
            HStack {
                LabeledField(label: "Date", text: $state.campaign.date, prompt: "YYYY_MM_DD (today)")
                LabeledField(label: "Audio", text: $state.campaign.audio, prompt: "STEREO")
            }
            LabeledField(label: "Workspace / Artist", text: $state.campaign.workspace)
            LabeledField(label: "Copyright", text: $state.campaign.copyright, prompt: CampaignFields.defaultCopyright(for: state.campaign.client))
            HStack {
                Toggle("Flame logo", isOn: $state.campaign.flame)
                Toggle("NFA", isOn: $state.campaign.nfa)
            }
            HStack {
                Button("Fill Blanks") { state.applyCampaignToAll(overwrite: false) }
                    .help("Copy campaign fields into rows where they are empty")
                Button("Apply to All") { state.applyCampaignToAll(overwrite: true) }
                    .help("Overwrite these fields on every row")
            }
            .buttonStyle(AccentButtonStyle(theme: t, prominent: false))
            .disabled(state.rows.isEmpty)
        }
        .card(t)
    }
}
