import SwiftUI

/// Brand palettes mirrored from THEMES in SuperJoy_Slating_App.py.
struct BrandTheme: Equatable {
    let key: String
    let appTitle: String
    let headerBold: String
    let headerSub: String
    let tagline: String
    let background: Color
    let card: Color
    let recessed: Color
    let border: Color
    let accent: Color
    let accentHover: Color
    let highlight: Color
    let textMuted: Color
    let success: Color
    let fontName: String

    static let superjoy = BrandTheme(
        key: "superjoy",
        appTitle: "SuperJoy Slating Workstation",
        headerBold: "SUPERJOY",
        headerSub: "SLATING WORKSTATION",
        tagline: "Broadcast Slate Automation  •  ProRes 422 HQ + H.264 (25Mbps)  •  SLATED & UNSLATED Delivery",
        background: Color(hex: 0x222538), card: Color(hex: 0x2A2E44), recessed: Color(hex: 0x181B29),
        border: Color(hex: 0x383D59), accent: Color(hex: 0xE8453C), accentHover: Color(hex: 0xF45B52),
        highlight: Color(hex: 0xF3E052), textMuted: Color(hex: 0x9BA3C2), success: Color(hex: 0x2E9E44),
        fontName: "Avenir Next")

    static let mstrSl8r = BrandTheme(
        key: "mstr_sl8r",
        appTitle: "MSTR-SL8R",
        headerBold: "MSTR-SL8R",
        headerSub: "BROADCAST WORKSTATION",
        tagline: "Broadcast Slate Automation  •  ProRes 422 HQ + H.264 (25Mbps)  •  SLATED & UNSLATED Delivery",
        background: Color(hex: 0x0A0A0C), card: Color(hex: 0x151418), recessed: Color(hex: 0x000000),
        border: Color(hex: 0x2A272D), accent: Color(hex: 0x13F1D5), accentHover: Color(hex: 0x01D4FB),
        highlight: Color(hex: 0xE5C8FF), textMuted: Color(hex: 0xA9A4AD), success: Color(hex: 0xA8E8C5),
        fontName: "Futura")

    static let all = [superjoy, mstrSl8r]

    static func named(_ key: String) -> BrandTheme {
        all.first { $0.key == key } ?? .superjoy
    }

    /// Theme chosen by the build target (SW_DEFAULT_THEME → Info.plist SWDefaultTheme).
    static var bundleDefault: BrandTheme {
        named(Bundle.main.object(forInfoDictionaryKey: "SWDefaultTheme") as? String ?? "superjoy")
    }

    /// Text drawn on top of the accent color (MSTR-SL8R's aqua needs dark text).
    var onAccent: Color { key == "mstr_sl8r" ? .black : .white }

    func font(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        if NSFont(name: fontName, size: size) != nil {
            return .custom(fontName, size: size).weight(weight)
        }
        return .system(size: size, weight: weight)
    }
}

extension Color {
    init(hex: UInt32) {
        self.init(.sRGB,
                  red: Double((hex >> 16) & 0xFF) / 255,
                  green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255,
                  opacity: 1)
    }
}

/// Rounded card surface used throughout the UI.
struct CardBackground: ViewModifier {
    let theme: BrandTheme
    func body(content: Content) -> some View {
        content
            .padding(16)
            .background(theme.card, in: RoundedRectangle(cornerRadius: 14))
            .overlay(RoundedRectangle(cornerRadius: 14).stroke(theme.border, lineWidth: 1))
    }
}

extension View {
    func card(_ theme: BrandTheme) -> some View { modifier(CardBackground(theme: theme)) }
}

struct AccentButtonStyle: ButtonStyle {
    let theme: BrandTheme
    var prominent = true
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(theme.font(13, weight: .semibold))
            .padding(.horizontal, 16).padding(.vertical, 8)
            .foregroundStyle(prominent ? theme.onAccent : .white)
            .background(
                RoundedRectangle(cornerRadius: 9)
                    .fill(prominent ? (configuration.isPressed ? theme.accentHover : theme.accent) : theme.recessed)
            )
            .overlay(RoundedRectangle(cornerRadius: 9).stroke(prominent ? .clear : theme.border))
            .opacity(isEnabled ? 1 : 0.45)
            .contentShape(Rectangle())
    }
}
