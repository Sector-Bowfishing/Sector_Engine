//
//  BrainPlatform.swift
//  Sector — shared Brain Platform contract types (Sector Engine side)
//
//  The dedicated Brain RTDB (`sector-brain`, project sector-9393c) is written by
//  Sector Engine and only read by Sector Ops. Shapes follow Sector_Ops
//  docs/SECTOR_BRAIN_RTDB_SCHEMA.md and src/types/brain.ts (PROPOSED v1,
//  2026-10-12); Engine owns the enums. Every optional is written as absent
//  (RTDB has no stored null) — unknown stays unknown, never a default.
//
//  ADDITIVE: nothing in the request path (/conditions, /lakes, …) imports this.
//

import Foundation

public enum BrainPlatform {

    public static let schemaVersion = 1

    /// RTDB key for a canonical lake id: Engine's existing storage slug,
    /// `re.sub(r"[^A-Za-z0-9]+", "_", id)` (gs://sector-lake-surface/lakes/<slug>/).
    /// Lossy, so every lake-scoped node also stores `lakeId`.
    public static func lakeKey(_ lakeId: String) -> String {
        var out = ""
        var inRun = false
        for u in lakeId.unicodeScalars {
            let alnum = (u.value >= 48 && u.value <= 57) || (u.value >= 65 && u.value <= 90) || (u.value >= 97 && u.value <= 122)
            if alnum { out.unicodeScalars.append(u); inRun = false }
            else if !inRun { out += "_"; inRun = true }
        }
        return out
    }

    /// Keys of `ids` that collide after slugging (must be empty before any write).
    public static func keyCollisions(_ ids: [String]) -> [String: [String]] {
        Dictionary(grouping: ids, by: lakeKey).filter { $0.value.count > 1 }
    }

    public static func iso(_ d: Date) -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f.string(from: d)
    }

    /// Time-sortable event key: lexical order == time order (RTDB keys sort lexically).
    public static func eventKey(_ d: Date, suffix: String) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyyMMdd'T'HHmmssSSS"
        return f.string(from: d) + "-" + lakeKey(suffix)
    }
}

// MARK: - Shared shapes (Sector_Ops src/types/brain.ts)

public struct BrainSourceRef: Codable, Equatable {
    public var sourceType: String
    public var sourceId: String
    public var lastObservationAt: String?
}

public struct BrainProvenance: Codable, Equatable {
    public var brainId: String
    public var brainVersion: String?
    public var modelVersion: String?
    public var processingVersion: String?
    public var generatedAt: String?
    public var sources: [BrainSourceRef]?
    public var inputAgeHours: Double?
    public var readiness: String?
    public var qualityFlags: [String]?
    public var validationRef: String?
}

public struct BrainHealthRecord: Codable, Equatable {
    public var status: String
    public var lastRun: String?
    public var lastSuccess: String?
    public var durationMs: Int?
    public var staleLakeCount: Int
    public var errorCount: Int
    public var latestError: String?
    public var deployedVersion: String?
}

public struct BrainJobHealth: Codable, Equatable {
    public var displayName: String
    public var kind: String
    public var schedule: String?
    public var status: String
    public var lastRun: String?
    public var lastSuccess: String?
    public var durationMs: Int?
    public var latestError: String?
    public var running: Bool?
}

public struct BrainActivityEvent: Codable, Equatable {
    public var id: String
    public var at: String
    public var kind: String
    public var title: String
    public var brainId: String?
    public var lakeId: String?
    public var severity: String?
}

public struct BrainDataSourceStatus: Codable, Equatable {
    public var sourceId: String
    public var provider: String
    public var type: String
    public var brains: [String]
    public var lakeCount: Int
    public var health: String
    public var lastFetchAt: String?
    public var latestObservationAt: String?
    public var staleThresholdHours: Double
    /// Unknown (absent) unless a writer keeps 24 h history; the job does not.
    public var failures24h: Int?
    public var failuresLastRun: Int?
    public var provides: String?
    public var notes: String?
}

public struct BrainSourceHealth: Codable, Equatable {
    public var status: String
    public var lastFetchAt: String?
    public var failures24h: Int?
    /// Failures observed in the writer's last run; nil when not observable.
    public var failuresLastRun: Int?
}

// MARK: - Store (the only thing that talks to the Brain RTDB)

/// A Brain RTDB writer. `update` is one atomic multi-path update: each key is a
/// path relative to the database root, each value the JSON to SET there.
public protocol BrainStore: Sendable {
    func update(_ paths: [String: Data]) async throws
    func get(_ path: String) async throws -> Data?
    func delete(_ path: String) async throws
    /// Child keys of `path` (RTDB `?shallow=true`).
    func shallowKeys(_ path: String) async throws -> [String]
}

public enum BrainJSON {
    public static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        return e
    }()

    public static func encode<T: Encodable>(_ v: T) throws -> Data { try encoder.encode(v) }

    /// `{"path": <json>, …}` without going through Any.
    public static func multiPathBody(_ paths: [String: Data]) throws -> Data {
        var s = "{"
        for (i, k) in paths.keys.sorted().enumerated() {
            if i > 0 { s += "," }
            s += String(decoding: try encoder.encode(k), as: UTF8.self) + ":" + String(decoding: paths[k]!, as: UTF8.self)
        }
        return Data((s + "}").utf8)
    }
}
