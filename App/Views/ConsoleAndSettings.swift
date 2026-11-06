import SwiftUI

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
                Text("Leave blank to use the Python and engine embedded in the app. Set Engine folder to the repo to test unbundled changes to SuperJoy_Slating_App.py.")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
        .frame(width: 520)
        .padding()
    }
}
