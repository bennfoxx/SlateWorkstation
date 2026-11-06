import SwiftUI
import UniformTypeIdentifiers

/// Labeled path field with Choose… button and Finder drag-and-drop.
struct PathField: View {
    @Environment(WorkstationState.self) private var state
    let label: String
    @Binding var path: String
    var files = false
    var types: [String] = []
    var placeholder = "Drop a folder here or choose…"
    var onChange: (() -> Void)? = nil
    @State private var targeted = false

    var body: some View {
        let t = state.theme
        VStack(alignment: .leading, spacing: 5) {
            Text(label.uppercased())
                .font(t.font(10, weight: .bold)).foregroundStyle(t.textMuted).kerning(0.8)
            HStack(spacing: 8) {
                Image(systemName: files ? "doc" : "folder")
                    .foregroundStyle(path.isEmpty ? t.textMuted : t.accent)
                Text(path.isEmpty ? placeholder : (path as NSString).abbreviatingWithTildeInPath)
                    .font(t.font(12))
                    .foregroundStyle(path.isEmpty ? t.textMuted : .white)
                    .lineLimit(1).truncationMode(.middle)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if !path.isEmpty {
                    Button { path = ""; onChange?() } label: { Image(systemName: "xmark.circle.fill") }
                        .buttonStyle(.plain).foregroundStyle(t.textMuted)
                        .help("Clear").accessibilityLabel("Clear")
                }
                Button("Choose…") {
                    if let url = state.pick(files: files, types: types) { path = url.path; onChange?() }
                }
                .buttonStyle(AccentButtonStyle(theme: t, prominent: false))
            }
            .padding(.leading, 10).padding(.vertical, 4).padding(.trailing, 4)
            .background(t.recessed, in: RoundedRectangle(cornerRadius: 9))
            .overlay(RoundedRectangle(cornerRadius: 9).stroke(targeted ? t.accent : t.border, lineWidth: targeted ? 2 : 1))
            .onDrop(of: [.fileURL], isTargeted: $targeted) { providers in
                guard let provider = providers.first else { return false }
                _ = provider.loadObject(ofClass: URL.self) { url, _ in
                    guard let url else { return }
                    var isDir: ObjCBool = false
                    FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir)
                    let ok = files ? (!isDir.boolValue && (types.isEmpty || types.contains(url.pathExtension.lowercased())))
                                   : isDir.boolValue
                    guard ok else { return }
                    Task { @MainActor in path = url.path; onChange?() }
                }
                return true
            }
        }
    }
}

struct LabeledField: View {
    @Environment(WorkstationState.self) private var state
    let label: String
    @Binding var text: String
    var prompt = ""
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label.uppercased()).font(state.theme.font(10, weight: .bold))
                .foregroundStyle(state.theme.textMuted).kerning(0.8)
            TextField(label, text: $text, prompt: Text(prompt))
                .textFieldStyle(.plain)
                .font(state.theme.font(13))
                .padding(.horizontal, 10).padding(.vertical, 7)
                .background(state.theme.recessed, in: RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(state.theme.border))
        }
    }
}
