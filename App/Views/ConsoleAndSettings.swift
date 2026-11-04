import SwiftUI

struct ConsoleView: View {
    @Environment(WorkstationState.self) private var state

    var body: some View {
        let t = state.theme
        VStack(spacing: 0) {
            HStack {
                Label("Worker Log", systemImage: "terminal").font(t.font(11, weight: .bold))
                Spacer()
                Button("Copy") {
                    let text = state.log.map(\.text).joined(separator: "\n")
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(text, forType: .string)
                }
                Button("Clear") { state.log.removeAll() }
            }
            .buttonStyle(.borderless)
            .padding(.horizontal, 14).padding(.vertical, 6)
            .background(t.card)
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 2) {
                        ForEach(state.log) { line in
                            Text(line.text)
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundStyle(color(line.kind))
                                .textSelection(.enabled)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .id(line.id)
                        }
                    }
                    .padding(10)
                }
                .onChange(of: state.log.count) {
                    if let last = state.log.last { proxy.scrollTo(last.id, anchor: .bottom) }
                }
            }
            .background(t.recessed)
        }
        .overlay(alignment: .top) { Rectangle().fill(t.border).frame(height: 1) }
    }

    private func color(_ k: LogLine.Kind) -> Color {
        switch k {
        case .info: state.theme.success
        case .warning: state.theme.highlight
        case .error: Color(hex: 0xFF6B63)
        case .output: .white.opacity(0.8)
        }
    }
}

struct PreviewGallery: View {
    @Environment(WorkstationState.self) private var state
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        let t = state.theme
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                SectionTitle(text: "Slate Previews (\(state.previews.count))", symbol: "photo.on.rectangle")
                Spacer()
                Button("Done") { dismiss() }.keyboardShortcut(.defaultAction)
            }
            ScrollView {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 220), spacing: 12)], spacing: 12) {
                    ForEach(state.previews) { p in
                        VStack(alignment: .leading, spacing: 4) {
                            if let img = NSImage(contentsOfFile: p.imagePath) {
                                Image(nsImage: img).resizable().scaledToFit()
                                    .clipShape(RoundedRectangle(cornerRadius: 6))
                            }
                            Text("\(p.adID)  \(p.aspect)").font(t.font(11, weight: .bold))
                            Text(p.title).font(t.font(10)).foregroundStyle(t.textMuted).lineLimit(1)
                        }
                        .onTapGesture(count: 2) { NSWorkspace.shared.open(URL(fileURLWithPath: p.imagePath)) }
                    }
                }
            }
        }
        .padding(20)
        .frame(minWidth: 720, minHeight: 480)
        .background(t.background)
    }
}

struct SettingsView: View {
    @Environment(WorkstationState.self) private var state
    @AppStorage(PythonWorker.pythonOverrideKey) private var pythonPath = ""
    @AppStorage(PythonWorker.engineOverrideKey) private var engineDir = ""

    var body: some View {
        @Bindable var state = state
        Form {
            Picker("Brand theme", selection: Binding(get: { state.theme.key },
                                                     set: { state.theme = BrandTheme.named($0) })) {
                ForEach(BrandTheme.all, id: \.key) { Text($0.appTitle).tag($0.key) }
            }
            Section("Python worker") {
                TextField("python3 path", text: $pythonPath, prompt: Text(PythonWorker.resolvePython()?.path ?? "not found"))
                TextField("Engine folder", text: $engineDir, prompt: Text("App bundle Resources"))
                Text("Leave blank to use the first python3 found and the engine bundled with the app. Set Engine folder to the repo to test unbundled changes to SuperJoy_Slating_App.py.")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
        .frame(width: 520)
        .padding()
    }
}
