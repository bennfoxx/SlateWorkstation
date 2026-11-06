import SwiftUI

/// MSTR-SL8R Ingest: companion app to MSTR-SL8R. Scans drives / cards / network folders
/// read-only, proposes Date / Cam / Roll organisation, and imports or generates camera reports.
@main
struct IngestApp: App {
    @State private var state = IngestState(theme: BrandTheme.bundleDefault)

    var body: some Scene {
        WindowGroup("MSTR-SL8R Ingest") {
            IngestRootView()
                .environment(state)
                .environment(\.brandTheme, state.theme)
                .frame(minWidth: 1040, minHeight: 760)
                .preferredColorScheme(.dark)
        }
        .windowStyle(.hiddenTitleBar)
        .defaultSize(width: 1280, height: 880)
        .commands {
            CommandGroup(after: .newItem) {
                Button("Add Source…") { state.addSourcesWithPanel() }
                    .keyboardShortcut("o")
                    .disabled(state.busy)
            }
            CommandMenu("Ingest") {
                Button("Scan") { state.scan() }
                    .keyboardShortcut(.return, modifiers: [.command])
                    .disabled(!state.canScan)
                Button("Import Camera Report…") { state.importCameraReportWithPanel() }
                    .keyboardShortcut("i", modifiers: [.command, .shift])
                    .disabled(state.rolls.isEmpty || state.busy)
                Button("Generate Camera Reports…") { state.generateCameraReportsWithPanel(selectedOnly: false) }
                    .keyboardShortcut("r", modifiers: [.command, .shift])
                    .disabled(state.rolls.isEmpty || state.busy)
                Divider()
                Button("Stop") { state.cancel() }
                    .keyboardShortcut(".", modifiers: [.command])
                    .disabled(!state.busy)
            }
        }
    }
}

struct IngestRootView: View {
    @Environment(IngestState.self) private var state

    var body: some View {
        @Bindable var state = state
        let t = state.theme
        VStack(spacing: 0) {
            HStack(alignment: .center, spacing: 12) {
                ZStack {
                    Circle().fill(t.accent).frame(width: 34, height: 34)
                    Image(systemName: "externaldrive.fill").font(.system(size: 15, weight: .bold))
                        .foregroundStyle(t.onAccent)
                }
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Text(t.headerBold).font(t.font(22, weight: .heavy))
                        Text("INGEST").font(t.font(22, weight: .light)).foregroundStyle(t.textMuted)
                    }
                    Text("Read-only card scan  •  Date / Cam / Roll  •  Camera reports")
                        .font(t.font(11)).foregroundStyle(t.textMuted).lineLimit(1)
                }
                Spacer()
            }
            .padding(.horizontal, 20).padding(.top, 30).padding(.bottom, 12)

            IngestView()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .padding(.horizontal, 20)
            IngestBar()
            if state.showConsole {
                ConsoleView(theme: t, log: $state.log)
                    .frame(height: 190)
                    .transition(.move(edge: .bottom))
            }
        }
        .background(t.background)
        .foregroundStyle(.white)
        .tint(t.accent)
        .animation(.easeOut(duration: 0.18), value: state.showConsole)
        .alert(item: $state.alert) { a in
            Alert(title: Text(a.title), message: Text(a.message), dismissButton: .default(Text("OK")))
        }
    }
}
