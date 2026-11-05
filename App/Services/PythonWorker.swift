import Foundation

/// Runs slate_worker.py (bundled in Contents/Resources) and streams its JSON-lines events.
/// The worker is the only code that talks to After Effects / Media Encoder.
enum WorkerEvent {
    case log(String)
    case alert(level: String, title: String, message: String)
    case previews([[String: Any]])
    case stderr(String)
    case result([String: Any])
}

struct WorkerError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

final class PythonWorker: @unchecked Sendable {
    static let pythonOverrideKey = "pythonPath"
    static let engineOverrideKey = "engineDirectory"

    private let lock = NSLock()
    private var process: Process?

    /// Writing a job to a worker that already exited must not kill the app with SIGPIPE.
    private static let ignoreSIGPIPE: Void = { signal(SIGPIPE, SIG_IGN) }()
    init() { _ = Self.ignoreSIGPIPE }

    /// Python interpreter: user override, else the embedded runtime, else a system python3.
    static func resolvePython() -> URL? {
        let fm = FileManager.default
        if let custom = UserDefaults.standard.string(forKey: pythonOverrideKey), !custom.isEmpty,
           fm.isExecutableFile(atPath: custom) {
            return URL(fileURLWithPath: custom)
        }
        // Embedded runtime (scripts/embed_python_runtime.sh), so the app needs no system Python.
        if let bundled = Bundle.main.resourceURL?.appendingPathComponent("python/bin/python3"),
           fm.isExecutableFile(atPath: bundled.path) {
            return bundled
        }
        var candidates = ["/opt/homebrew/bin/python3", "/usr/local/bin/python3"]
        // /usr/bin/python3 is a shim that prompts to install the Command Line Tools if
        // no developer directory exists, so only use it when one does.
        if fm.fileExists(atPath: "/Library/Developer/CommandLineTools/usr/bin/python3")
            || fm.fileExists(atPath: "/Applications/Xcode.app/Contents/Developer/usr/bin/python3") {
            candidates.append("/usr/bin/python3")
        }
        return candidates.first { fm.isExecutableFile(atPath: $0) }.map { URL(fileURLWithPath: $0) }
    }

    /// Folder holding slate_worker.py + SuperJoy_Slating_App.py + presets/templates.
    /// Defaults to the app bundle's Resources; a developer can point it at the repo.
    static func resolveEngineDirectory() -> URL? {
        let fm = FileManager.default
        if let custom = UserDefaults.standard.string(forKey: engineOverrideKey), !custom.isEmpty,
           fm.fileExists(atPath: (custom as NSString).appendingPathComponent("slate_worker.py")) {
            return URL(fileURLWithPath: custom)
        }
        guard let res = Bundle.main.resourceURL,
              fm.fileExists(atPath: res.appendingPathComponent("slate_worker.py").path) else { return nil }
        return res
    }

    private func setProcess(_ p: Process?) { lock.withLock { process = p } }

    func cancel() {
        let p = lock.withLock { process }
        if let p, p.isRunning { p.terminate() }
    }

    /// Runs one worker command. `onEvent` is called on the main actor for every event.
    /// Returns the final "result" payload (or throws if the worker could not run).
    func run(arguments: [String], stdin: Data? = nil,
             onEvent: @escaping @MainActor (WorkerEvent) -> Void) async throws -> [String: Any] {
        guard let python = Self.resolvePython() else {
            throw WorkerError(message: "No Python runtime found: the embedded one is missing from the app and no python3 is installed. Rebuild the app, or set a python3 path in Settings.")
        }
        guard let engine = Self.resolveEngineDirectory() else {
            throw WorkerError(message: "slate_worker.py is missing from the app bundle.")
        }

        let p = Process()
        p.executableURL = python
        // -I: isolated (ignore PYTHON* env + user site); -B: never write __pycache__ into the signed bundle.
        p.arguments = ["-I", "-B", engine.appendingPathComponent("slate_worker.py").path] + arguments
        p.currentDirectoryURL = FileManager.default.homeDirectoryForCurrentUser
        var env = ProcessInfo.processInfo.environment
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        p.environment = env

        let outPipe = Pipe(), errPipe = Pipe(), inPipe = Pipe()
        p.standardOutput = outPipe
        p.standardError = errPipe
        p.standardInput = inPipe

        // Only workflow runs are cancellable; scans (e.g. Marry rescans while a run is going)
        // must not replace or clear the process that Stop terminates.
        let cancellable = arguments.first == "run"
        if cancellable { setProcess(p) }
        defer { if cancellable { setProcess(nil) } }

        try p.run()
        if let stdin { try? inPipe.fileHandleForWriting.write(contentsOf: stdin) }
        try? inPipe.fileHandleForWriting.close()

        let errTask = Task.detached { () -> String in
            var collected = ""
            for try await line in errPipe.fileHandleForReading.bytes.lines {
                collected += line + "\n"
                await onEvent(.stderr(line))
            }
            return collected
        }

        var result: [String: Any]?
        for try await line in outPipe.fileHandleForReading.bytes.lines {
            guard let data = line.data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let kind = obj["event"] as? String else {
                await onEvent(.stderr(line))
                continue
            }
            switch kind {
            case "log": await onEvent(.log(obj["message"] as? String ?? ""))
            case "alert":
                await onEvent(.alert(level: obj["level"] as? String ?? "info",
                                     title: obj["title"] as? String ?? "",
                                     message: obj["message"] as? String ?? ""))
            case "previews": await onEvent(.previews(obj["items"] as? [[String: Any]] ?? []))
            case "result":
                result = obj
                await onEvent(.result(obj))
            default: await onEvent(.log(line))
            }
        }
        p.waitUntilExit()
        let stderrText = (try? await errTask.value) ?? ""

        if let result { return result }
        if p.terminationReason == .uncaughtSignal {
            throw WorkerError(message: "Worker stopped.")
        }
        let tail = stderrText.split(separator: "\n").suffix(6).joined(separator: "\n")
        throw WorkerError(message: "Worker exited with code \(p.terminationStatus) without a result.\n\(tail)")
    }
}
