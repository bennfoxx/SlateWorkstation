import SwiftUI

struct MainView: View {
    @Environment(WorkstationState.self) private var state

    var body: some View {
        @Bindable var state = state
        let t = state.theme
        VStack(spacing: 0) {
            HeaderView()
            ModeTabBar()
                .padding(.horizontal, 20).padding(.bottom, 12)
            Group {
                switch state.mode {
                case .batch: BatchBuilderView()
                case .marry: MarryVideosView()
                case .unslate: UnslateView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .padding(.horizontal, 20)
            RunBar()
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
        .sheet(isPresented: $state.showPreviews) { PreviewGallery() }
    }
}

struct HeaderView: View {
    @Environment(WorkstationState.self) private var state
    var body: some View {
        let t = state.theme
        HStack(alignment: .center, spacing: 12) {
            ZStack {
                Circle().fill(t.accent).frame(width: 34, height: 34)
                Circle().stroke(t.highlight, lineWidth: 3).frame(width: 22, height: 22)
            }
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(t.headerBold).font(t.font(22, weight: .heavy))
                    Text(t.headerSub).font(t.font(22, weight: .light)).foregroundStyle(t.textMuted)
                }
                Text(t.tagline).font(t.font(11)).foregroundStyle(t.textMuted).lineLimit(1)
            }
            Spacer()
            if state.dryRun {
                Label("DRY RUN", systemImage: "doc.text.magnifyingglass")
                    .font(t.font(11, weight: .bold))
                    .padding(.horizontal, 10).padding(.vertical, 5)
                    .background(t.highlight.opacity(0.18), in: Capsule())
                    .foregroundStyle(t.highlight)
                    .help("Workflows write the generated JSX to disk instead of running After Effects")
            }
        }
        .padding(.horizontal, 20).padding(.top, 30).padding(.bottom, 12)
    }
}

struct ModeTabBar: View {
    @Environment(WorkstationState.self) private var state
    var body: some View {
        let t = state.theme
        HStack(spacing: 6) {
            ForEach(WorkflowMode.allCases) { m in
                let active = state.mode == m
                Button { state.mode = m } label: {
                    Label(m.title, systemImage: m.symbol)
                        .font(t.font(13, weight: active ? .bold : .medium))
                        .padding(.horizontal, 16).padding(.vertical, 8)
                        .frame(maxWidth: .infinity)
                        .foregroundStyle(active ? t.onAccent : t.textMuted)
                        .background(active ? t.accent : .clear, in: Capsule())
                        .contentShape(Capsule())
                }
                .buttonStyle(.plain)
                .disabled(state.isRunning)
            }
        }
        .padding(4)
        .background(t.recessed, in: Capsule())
        .overlay(Capsule().stroke(t.border))
    }
}

/// Global render settings shared by every workflow, plus the Run button.
struct RunBar: View {
    @Environment(WorkstationState.self) private var state
    var body: some View {
        @Bindable var state = state
        let t = state.theme
        VStack(spacing: 10) {
            HStack(alignment: .bottom, spacing: 14) {
                PathField(label: "Output Folder (optional)", path: $state.outputDir,
                          placeholder: "Default: next to the source media")
                if state.mode == .batch && state.slatesOnly {
                    VStack(alignment: .leading, spacing: 5) {
                        Text("SLATE CODEC").font(t.font(10, weight: .bold)).foregroundStyle(t.textMuted)
                        Picker("", selection: $state.slateCodec) {
                            ForEach(SlateCodec.allCases) { Text($0.label).tag($0) }
                        }
                        .labelsHidden().frame(width: 175)
                    }
                }
                VStack(alignment: .leading, spacing: 5) {
                    Text("FRAME RATE").font(t.font(10, weight: .bold)).foregroundStyle(t.textMuted)
                    Picker("", selection: $state.fps) {
                        ForEach(fpsPresets, id: \.self) { Text($0).tag($0) }
                    }
                    .labelsHidden().frame(width: 96)
                }
                VStack(alignment: .leading, spacing: 5) {
                    Text("DEFAULT ASPECT").font(t.font(10, weight: .bold)).foregroundStyle(t.textMuted)
                    Picker("", selection: $state.aspect) {
                        ForEach(Aspect.allCases) { Text($0.label).tag($0) }
                    }
                    .labelsHidden().frame(width: 150)
                }
            }
            HStack(spacing: 18) {
                Toggle("Also make H.264 + UNSLATED versions", isOn: $state.autoTranscode)
                    .disabled(state.mode == .batch && state.slatesOnly)
                Toggle("Dry run (write JSX only)", isOn: $state.dryRun)
                Spacer()
                Button {
                    state.showConsole.toggle()
                } label: {
                    Label(state.showConsole ? "Hide Log" : "Show Log", systemImage: "terminal")
                }
                .buttonStyle(AccentButtonStyle(theme: t, prominent: false))
                if state.isRunning {
                    ProgressView().controlSize(.small)
                    Button("Stop") { state.cancel() }
                        .buttonStyle(AccentButtonStyle(theme: t, prominent: false))
                }
                Button {
                    state.run()
                } label: {
                    Label(state.isRunning ? "Processing…" : runTitle, systemImage: "play.fill")
                        .frame(minWidth: 190)
                }
                .buttonStyle(AccentButtonStyle(theme: t))
                .disabled(!state.canRun)
                .help("Run (⌘↩)")
            }
            .font(t.font(12))
        }
        .card(t)
        .padding(.horizontal, 20).padding(.vertical, 12)
    }

    private var runTitle: String {
        switch state.mode {
        case .batch: state.slatesOnly ? "Build Standalone Slates" : "Slate & Queue in AME"
        case .marry: "Marry & Queue in AME"
        case .unslate: "Un-Slate & Queue in AME"
        }
    }
}
