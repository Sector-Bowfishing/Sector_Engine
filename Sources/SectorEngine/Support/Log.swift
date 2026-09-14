//
//  Log.swift
//  SectorEngine
//
//  Structured, one-line JSON logs for Cloud Logging.
//
//  The engine used bare `print` with no severity, and stdout was block-buffered
//  on Cloud Run: deadline and slow-fetch lines arrived minutes late and were
//  lost entirely when an instance crashed or froze — exactly the moments they
//  explain. Upstream failures were swallowed by `try?` and never logged at all.
//
//  Cloud Logging parses a JSON object written on one stdout line: `severity`
//  sets the log level and `message` the summary; every other key is queryable
//  (jsonPayload.host, jsonPayload.status…) and usable in log-based metrics and
//  alerts. The server line-buffers stdout at startup (main.swift), and `print`
//  locks stdout per call, so concurrent renders never interleave a line.
//

import Foundation

enum LogValue: Sendable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
    case strings([String])

    fileprivate var json: Any {
        switch self {
        case let .string(s): return s
        case let .int(i): return i
        // Through a decimal so JSON shows 8.011, not binary noise (8.0109999999999992).
        case let .double(d): return d.isFinite ? NSDecimalNumber(string: String(format: "%.3f", d)) : String(describing: d)
        case let .bool(b): return b
        case let .strings(a): return a
        }
    }
}

extension LogValue: ExpressibleByStringLiteral, ExpressibleByIntegerLiteral,
                    ExpressibleByFloatLiteral, ExpressibleByBooleanLiteral {
    init(stringLiteral value: String) { self = .string(value) }
    init(integerLiteral value: Int) { self = .int(value) }
    init(floatLiteral value: Double) { self = .double(value) }
    init(booleanLiteral value: Bool) { self = .bool(value) }
}

enum Log {
    enum Severity: String, Sendable {
        case debug = "DEBUG", info = "INFO", notice = "NOTICE", warning = "WARNING", error = "ERROR"
    }

    static func info(_ message: String, _ fields: [String: LogValue] = [:]) { write(.info, message, fields) }
    static func notice(_ message: String, _ fields: [String: LogValue] = [:]) { write(.notice, message, fields) }
    static func warning(_ message: String, _ fields: [String: LogValue] = [:]) { write(.warning, message, fields) }
    static func error(_ message: String, _ fields: [String: LogValue] = [:]) { write(.error, message, fields) }

    static func write(_ severity: Severity, _ message: String, _ fields: [String: LogValue]) {
        var object: [String: Any] = ["severity": severity.rawValue, "message": message, "component": "engine"]
        for (key, value) in fields where object[key] == nil { object[key] = value.json }
        guard let data = try? JSONSerialization.data(withJSONObject: object, options: [.sortedKeys, .withoutEscapingSlashes]),
              let line = String(data: data, encoding: .utf8) else {
            print("{\"severity\":\"\(severity.rawValue)\",\"message\":\"log encode failed\"}")
            return
        }
        print(line)
    }
}
