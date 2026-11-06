import Foundation

/// One camera card / roll found by ingest_worker.py `scan`. The raw worker dictionary is kept
/// so the full scan (with the user's Cam / Roll edits) can be sent back for reports.
struct IngestRoll: Identifiable {
    let id: String
    var cam: String
    var roll: String
    let raw: [String: Any]
    let clips: [IngestClip]

    init(any d: [String: Any]) {
        raw = d
        id = d["id"] as? String ?? UUID().uuidString
        cam = d["cam"] as? String ?? ""
        roll = d["roll"] as? String ?? ""
        clips = (d["clips"] as? [[String: Any]] ?? []).enumerated().map { IngestClip(any: $1, index: $0) }
    }

    private func s(_ k: String) -> String { raw[k] as? String ?? "" }
    var date: String { s("date") }
    var kind: String { s("kind") }
    var root: String { s("root") }
    var camera: String { s("camera_model") }
    var format: String { s("format") }
    var clipCount: Int { raw["clip_count"] as? Int ?? clips.count }
    var bytes: Int64 { (raw["bytes"] as? NSNumber)?.int64Value ?? 0 }
    var duration: Double { (raw["duration"] as? NSNumber)?.doubleValue ?? 0 }
    var codecs: String { (raw["codecs"] as? [String] ?? []).joined(separator: ", ") }
    var gammas: String { (raw["gammas"] as? [String] ?? []).joined(separator: ", ") }
    var foundReports: [String] { raw["found_reports"] as? [String] ?? [] }
    var importedReports: [String] { raw["imported_reports"] as? [String] ?? [] }

    var kindLabel: String {
        switch kind {
        case "sony_xavc": "Sony XAVC"
        case "sony_xdcam": "Sony XDCAM"
        case "red": "RED"
        default: "Folder"
        }
    }

    var reportStatus: String {
        if !importedReports.isEmpty { return "Imported" }
        if !foundReports.isEmpty { return "Found (\(foundReports.count))" }
        return "None"
    }

    /// Raw dictionary with the user's edits applied, for sending back to the worker.
    var edited: [String: Any] {
        var d = raw
        d["cam"] = cam.trimmingCharacters(in: .whitespaces).uppercased()
        d["roll"] = roll.trimmingCharacters(in: .whitespaces).uppercased()
        return d
    }
}

struct IngestClip: Identifiable {
    let id: String
    let name: String
    let timecode: String
    let duration: Double
    let fps: String
    let resolution: String
    let codec: String
    let gamma: String
    let bytes: Int64
    let scene: String
    let take: String
    let notes: String
    let path: String
    let problem: String

    init(any d: [String: Any], index: Int) {
        let info = d["info"] as? [String: Any] ?? [:]
        let rep = d["report"] as? [String: Any] ?? [:]
        name = d["name"] as? String ?? ""
        id = "\(index)-\(name)"
        timecode = info["timecode"] as? String ?? ""
        duration = (info["duration"] as? NSNumber)?.doubleValue ?? 0
        fps = (info["fps"] as? NSNumber).map { "\($0)" } ?? ""
        if let w = info["width"] as? Int, let h = info["height"] as? Int { resolution = "\(w)×\(h)" } else { resolution = "" }
        codec = info["codec"] as? String ?? ""
        gamma = info["gamma"] as? String ?? ""
        bytes = (d["bytes"] as? NSNumber)?.int64Value ?? 0
        scene = rep["scene"] as? String ?? ""
        take = rep["take"] as? String ?? ""
        notes = rep["notes"] as? String ?? ""
        path = (d["paths"] as? [String])?.first ?? ""
        problem = info["probe_error"] as? String ?? ""
    }
}

enum IngestFormat {
    static func bytes(_ n: Int64) -> String {
        ByteCountFormatter.string(fromByteCount: n, countStyle: .file)
    }

    static func duration(_ s: Double) -> String {
        guard s > 0 else { return "" }
        let t = Int(s.rounded())
        return String(format: "%d:%02d:%02d", t / 3600, t / 60 % 60, t % 60)
    }
}
