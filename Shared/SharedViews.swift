import SwiftUI

extension EnvironmentValues {
    /// Brand palette for shared views; each app sets it at its window root.
    @Entry var brandTheme: BrandTheme = .bundleDefault
}

/// Worker log panel, shared by the slate app and the ingest companion app.
struct ConsoleView: View {
    let theme: BrandTheme
    @Binding var log: [LogLine]

    var body: some View {
        let t = theme
        VStack(spacing: 0) {
            HStack {
                Label("Worker Log", systemImage: "terminal").font(t.font(11, weight: .bold))
                Spacer()
                Button("Copy") {
                    let text = log.map(\.text).joined(separator: "\n")
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(text, forType: .string)
                }
                Button("Clear") { log.removeAll() }
            }
            .buttonStyle(.borderless)
            .padding(.horizontal, 14).padding(.vertical, 6)
            .background(t.card)
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 2) {
                        ForEach(log) { line in
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
                .onChange(of: log.count) {
                    if let last = log.last { proxy.scrollTo(last.id, anchor: .bottom) }
                }
            }
            .background(t.recessed)
        }
        .overlay(alignment: .top) { Rectangle().fill(t.border).frame(height: 1) }
    }

    private func color(_ k: LogLine.Kind) -> Color {
        switch k {
        case .info: theme.success
        case .warning: theme.highlight
        case .error: Color(hex: 0xFF6B63)
        case .output: .white.opacity(0.8)
        }
    }
}

struct SectionTitle: View {
    @Environment(\.brandTheme) private var theme
    let text: String
    var symbol: String? = nil
    var body: some View {
        HStack(spacing: 6) {
            if let symbol { Image(systemName: symbol).foregroundStyle(theme.accent) }
            Text(text.uppercased()).font(theme.font(12, weight: .bold)).kerning(1)
        }
    }
}

