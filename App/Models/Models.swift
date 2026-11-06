import Foundation

enum WorkflowMode: String, CaseIterable, Identifiable {
    case batch, marry, unslate
    var id: String { rawValue }
    var title: String {
        switch self {
        case .batch: "Build Slates"
        case .marry: "Marry Existing Slates"
        case .unslate: "Un-Slate"
        }
    }
    var symbol: String {
        switch self {
        case .batch: "rectangle.stack.badge.plus"
        case .marry: "link"
        case .unslate: "scissors"
        }
    }
}

/// Aspect keys and pixel sizes mirrored from ASPECT_RESOLUTIONS in the engine.
enum Aspect: String, CaseIterable, Identifiable {
    case r16x9 = "16x9", r1x1 = "1x1", r4x5 = "4x5", r9x16 = "9x16", r2x3 = "2x3"
    var id: String { rawValue }
    var size: (w: Int, h: Int) {
        switch self {
        case .r16x9: (1920, 1080)
        case .r1x1: (1080, 1080)
        case .r4x5: (1080, 1350)
        case .r9x16: (1080, 1920)
        case .r2x3: (1080, 1620)
        }
    }
    var label: String { "\(rawValue.replacingOccurrences(of: "x", with: ":"))  \(size.w)×\(size.h)" }
    var ratio: CGFloat { CGFloat(size.w) / CGFloat(size.h) }
}

let fpsPresets = ["23.976", "24", "25", "29.97", "30", "50", "59.94", "60"]

/// One slate row. Keys match the engine's canonical slate keys (normalize_slate_row);
/// unknown keys from a spreadsheet are kept and passed back untouched.
struct SlateRow: Identifiable, Hashable {
    let id = UUID()
    var fields: [String: String]

    subscript(_ key: String) -> String {
        get { fields[key] ?? "" }
        set { fields[key] = newValue }
    }

    var adID: String {
        get { self["id"] }
        set { self["id"] = newValue; self["ad-id"] = newValue }
    }
    var title: String {
        get { self["title"] }
        set { self["title"] = newValue; self["name"] = newValue }
    }
    var aspect: String {
        get { fields["aspect"] ?? Aspect.r16x9.rawValue }
        set { self["aspect"] = newValue; self["comp"] = newValue; self["resolution"] = "" }
    }
    var flame: Bool {
        get { ["y", "yes", "true", "1"].contains(self["flame"].lowercased()) }
        set { self["flame"] = newValue ? "y" : "n" }
    }

    init(fields: [String: String]) { self.fields = fields }

    init(any: [String: Any]) {
        var f: [String: String] = [:]
        for (k, v) in any {
            switch v {
            case let s as String: f[k] = s
            case is NSNull: continue
            default: f[k] = "\(v)"
            }
        }
        self.fields = f
    }
}

/// Campaign-wide fields applied to every row (mirrors the Tk "shared" fields).
struct CampaignFields: Codable, Equatable {
    var agency = "MARTIN*"
    var client = ""
    var date = ""
    var workspace = ""
    var audio = "STEREO"
    var copyright = ""
    var flame = false
    var nfa = false

    var json: String {
        (try? String(data: JSONEncoder().encode(self), encoding: .utf8)) ?? "{}"
    }
}

struct MarryPair: Identifiable, Hashable {
    var id: String { slatePath + "|" + videoPath }
    let adID: String
    let slateName: String
    let slatePath: String
    let videoName: String
    let videoPath: String
    let outputName: String
    let aspect: String

    init(_ d: [String: Any]) {
        adID = d["id"] as? String ?? ""
        slateName = d["slate_name"] as? String ?? ""
        slatePath = d["slate_path"] as? String ?? ""
        videoName = d["video_name"] as? String ?? ""
        videoPath = d["video_path"] as? String ?? ""
        outputName = d["output_name"] as? String ?? ""
        aspect = d["aspect"] as? String ?? ""
    }
}

struct PreviewItem: Identifiable, Hashable {
    var id: String { imagePath }
    let adID: String
    let aspect: String
    let title: String
    let imagePath: String
}
