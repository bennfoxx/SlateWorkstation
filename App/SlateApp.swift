import SwiftUI

@main
struct SlateApp: App {
    @State private var state = WorkstationState(theme: BrandTheme.bundleDefault)

    var body: some Scene {
        WindowGroup(state.theme.appTitle) {
            MainView()
                .environment(state)
                .environment(\.brandTheme, state.theme)
                .frame(minWidth: 1040, minHeight: 800)
                .onOpenURL { url in
                    // Slate sheets opened from Finder / dropped on the Dock icon
                    if ["xlsx", "csv", "tsv", "txt"].contains(url.pathExtension.lowercased()) {
                        state.importSpreadsheet(url.path)
                    }
                }
                // Route Finder/Dock opens to the existing window instead of opening a second
                // window onto the same shared state.
                .handlesExternalEvents(preferring: ["*"], allowing: ["*"])
                .preferredColorScheme(.dark)
        }
        .windowStyle(.hiddenTitleBar)
        .defaultSize(width: 1220, height: 900)
        .commands {
            CommandGroup(after: .newItem) {
                Button("Import Spreadsheet…") { state.importSpreadsheetWithPanel() }
                    .keyboardShortcut("o")
                Button("New Sheet Template…") { state.newSheetTemplate() }
                    .keyboardShortcut("n", modifiers: [.command, .shift])
            }
            CommandMenu("Workflow") {
                Button("Run") { state.run() }
                    .keyboardShortcut(.return, modifiers: [.command])
                    .disabled(!state.canRun)
                Button("Stop Worker") { state.cancel() }
                    .keyboardShortcut(".", modifiers: [.command])
                    .disabled(!state.isRunning)
                Divider()
                Toggle("Dry Run (write JSX only)", isOn: Bindable(state).dryRun)
            }
        }

        Settings {
            SettingsView()
                .environment(state)
                .preferredColorScheme(.dark)
        }
    }
}
