import SwiftUI

/// Schematic preview of a row's slate fields at the row's aspect ratio.
/// The rendered slate comes from the After Effects template; this only checks the data.
struct SlatePreviewCard: View {
    @Environment(WorkstationState.self) private var state
    let row: SlateRow?

    var body: some View {
        let t = state.theme
        let aspect = Aspect(rawValue: row?.aspect ?? "") ?? .r16x9
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                SectionTitle(text: "Slate Data", symbol: "eye")
                Spacer()
                Text(aspect.label).font(t.font(10, weight: .semibold)).foregroundStyle(t.textMuted)
            }
            ZStack {
                RoundedRectangle(cornerRadius: 6).fill(t.recessed)
                if let row {
                    VStack(alignment: .leading, spacing: 3) {
                        line("AGENCY", row["agency"])
                        line("CLIENT", row["client"])
                        line("TITLE", row.title)
                        line("AD-ID", row.adID, emphasis: true)
                        line("TRT", row["trt"])
                        line("DATE", row["date"])
                        line("AUDIO", row["audio"])
                        if !row["workspace"].isEmpty { line("ARTIST", row["workspace"]) }
                        if !row["copyright"].isEmpty { line("©", row["copyright"]) }
                        HStack(spacing: 6) {
                            if row.flame { tag("FLAME", t.accent) }
                            if !row["nfa"].isEmpty { tag(row["nfa"], t.highlight) }
                        }
                    }
                    .font(t.font(10))
                    .padding(10)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                    .minimumScaleFactor(0.5)
                } else {
                    Text("Select a row").foregroundStyle(t.textMuted)
                }
            }
            .aspectRatio(aspect.ratio, contentMode: .fit)
            .frame(maxWidth: .infinity, maxHeight: 340)
            .overlay(RoundedRectangle(cornerRadius: 6).stroke(t.border))
            Text("Shows the row's data only. The actual slate layout comes from the AE template.")
                .font(t.font(10)).foregroundStyle(t.textMuted)
        }
        .card(t)
    }

    private func line(_ k: String, _ v: String, emphasis: Bool = false) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 6) {
            Text(k).foregroundStyle(state.theme.textMuted).frame(width: 52, alignment: .leading)
            Text(v.isEmpty ? "—" : v)
                .fontWeight(emphasis ? .bold : .regular)
                .foregroundStyle(emphasis ? state.theme.highlight : .white)
                .lineLimit(1)
        }
    }

    private func tag(_ s: String, _ c: Color) -> some View {
        Text(s).font(state.theme.font(9, weight: .bold))
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(c.opacity(0.2), in: Capsule()).foregroundStyle(c)
    }
}
