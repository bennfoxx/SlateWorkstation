import Foundation

struct LogLine: Identifiable {
    enum Kind { case info, warning, error, output }
    let id = UUID()
    let date = Date()
    let kind: Kind
    let text: String
}

struct AlertMessage: Identifiable {
    let id = UUID()
    let level: String
    let title: String
    let message: String
}
