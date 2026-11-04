import SwiftUI

struct MarryVideosView: View {
    @Environment(WorkstationState.self) private var state

    var body: some View {
        @Bindable var state = state
        let t = state.theme
        VStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 10) {
                SectionTitle(text: "Marry Existing Slates + Master Videos", symbol: "link")
                Text("Pairs each existing slate (.mov/.png/.psd…) with its master video by Ad-ID and aspect, then builds SLATED (and optionally UNSLATED) deliveries.")
                    .foregroundStyle(t.textMuted)
                HStack(spacing: 12) {
                    PathField(label: "Existing Slates Folder", path: $state.slatesDir) { state.scanMarryPairs() }
                    PathField(label: "Master Videos Folder", path: $state.videosDir) { state.scanMarryPairs() }
                }
                PathField(label: "Slate Sheet for Naming (optional)", path: $state.marryCSV, files: true,
                          types: ["xlsx", "csv", "tsv", "txt"], placeholder: "Use file names") { state.scanMarryPairs() }
            }
            .card(t)

            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    SectionTitle(text: "Matched Pairs  (\(state.marryPairs.count))", symbol: "checklist")
                    Spacer()
                    Button { state.scanMarryPairs() } label: { Label("Rescan", systemImage: "arrow.clockwise") }
                        .buttonStyle(AccentButtonStyle(theme: t, prominent: false))
                        .disabled(state.slatesDir.isEmpty || state.videosDir.isEmpty)
                }
                Table(state.marryPairs) {
                    TableColumn("Ad-ID", value: \.adID).width(min: 70, ideal: 90)
                    TableColumn("Aspect", value: \.aspect).width(60)
                    TableColumn("Slate", value: \.slateName)
                    TableColumn("Master Video", value: \.videoName)
                    TableColumn("Output", value: \.outputName)
                }
                .tableStyle(.bordered(alternatesRowBackgrounds: true))
                .scrollContentBackground(.hidden)
                .background(t.recessed, in: RoundedRectangle(cornerRadius: 8))
            }
            .card(t)
        }
        .font(t.font(12))
        .onAppear { state.scanMarryPairs() }
    }
}

struct UnslateView: View {
    @Environment(WorkstationState.self) private var state

    var body: some View {
        @Bindable var state = state
        let t = state.theme
        VStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 10) {
                SectionTitle(text: "Un-Slate (7.0s Head Trim)", symbol: "scissors")
                Text("Removes the 5.0s slate + 2.0s black/2-pop from slated masters and writes UNSLATED/ProRes (and H.264 when enabled). Only files whose start timecode is 00:59:53:00, or with no timecode and a name ending in “Slated”, are trimmed. Everything else is skipped and listed in Unslate_Log.txt.")
                    .foregroundStyle(t.textMuted)
                    .fixedSize(horizontal: false, vertical: true)
                PathField(label: "Slated Videos Folder", path: $state.unslateDir)
            }
            .card(t)
            Spacer()
        }
        .font(t.font(12))
    }
}
