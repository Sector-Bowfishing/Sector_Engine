//
//  BrainPlatform.swift
//  Sector — the Swift implementation of docs/brains/BRAIN_PLATFORM_CONTRACT.md
//
//  Shared by every Swift brain (Lake, Water Temperature). The dedicated Brain
//  RTDB (`sector-brain`, project sector-9393c) is written by Sector Engine jobs
//  and only read by Sector Ops. Every optional is written as absent (RTDB has no
//  stored null) — unknown stays unknown, never a default.
//
//  ADDITIVE: nothing in the request path (/conditions, /lakes, …) imports this.
//  The conformance fixtures in docs/brains/conformance/ are run against this file
//  by BrainPlatformConformanceTests; the Python package jobs/brain_platform/
//  runs the same fixtures.
//

import Foundation

public enum BrainPlatform {

    public static let schemaVersion = 1
    public static let databaseURL = "https://sector-brain.firebaseio.com"
    /// Customer-data instances: a writer refuses these URLs outright.
    public static let appDatabases = ["sector-9393c-default-rtdb", "sector-dev-1f4d0"]

    /// brainId → (slot, snapshot field, display name). Contract §2.
    public static let brains: [String: (slot: String, snapshotField: String, displayName: String)] = [
        "lake-brain": ("lake", "lakeState", "Lake Brain"),
        "water-temp": ("waterTemp", "waterTemperature", "Water Temperature"),
        "water-clarity": ("waterClarity", "waterClarity", "Water Clarity"),
        "wind": ("wind", "wind", "Wind"),
        "biological-state": ("biology", "biologicalState", "Biological Brain"),
        "sector-intelligence": ("intelligence", "sectorIntelligence", "Sector Intelligence"),
        "depth": ("depth", "depth", "Depth"),
        "vegetation": ("vegetation", "vegetation", "Vegetation"),
    ]
    public static func slot(for brainId: String) -> String? { brains[brainId]?.slot }
    public static func snapshotField(for brainId: String) -> String? { brains[brainId]?.snapshotField }

    /// RTDB key for a canonical lake id: every run of non-[A-Za-z0-9] becomes one "_".
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
        Dictionary(grouping: ids, by: lakeKey).filter { Set($0.value).count > 1 }
    }

    public static func acceptedDatabaseURL(_ url: String) -> Bool {
        url.contains("sector-brain") && !appDatabases.contains(where: { url.contains($0) })
    }

    // MARK: time

    public static func iso(_ d: Date) -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f.string(from: d)
    }

    public static func parseTime(_ s: String?) -> Date? {
        guard let s, !s.isEmpty else { return nil }
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = f.date(from: s) { return d }
        f.formatOptions = [.withInternetDateTime]
        return f.date(from: s)
    }

    /// LEGACY key format (`yyyyMMddTHHmmssSSS-<slug>`), kept only so existing records stay
    /// decodable. New events use `BrainActivity.eventId`. Never used for pruning decisions.
    public static func eventKey(_ d: Date, suffix: String) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyyMMdd'T'HHmmssSSS"
        return f.string(from: d) + "-" + lakeKey(suffix)
    }

    // MARK: key legality (contract §1)

    public struct IllegalKey: Error, CustomStringConvertible { public let description: String }

    static func isLegalKey(_ k: String) -> Bool {
        guard !k.isEmpty else { return false }
        for u in k.unicodeScalars {
            switch u.value {
            case 0x2E, 0x24, 0x23, 0x5B, 0x5D, 0x2F, 0x00...0x1F, 0x7F: return false   // . $ # [ ] / control DEL
            default: continue
            }
        }
        return true
    }

    /// Walk decoded JSON and reject any illegal node key.
    public static func checkKeys(_ value: Any, path: String = "") throws {
        if let dict = value as? [String: Any] {
            for (k, v) in dict {
                guard isLegalKey(k) else { throw IllegalKey(description: "illegal RTDB key '\(k)' at \(path.isEmpty ? "/" : path)") }
                try checkKeys(v, path: path + "/" + k)
            }
        } else if let arr = value as? [Any] {
            for (i, v) in arr.enumerated() { try checkKeys(v, path: path + "[\(i)]") }
        }
    }

    /// A multi-path update: each key is a root-relative path whose segments are node keys.
    public static func checkUpdate(_ paths: [String: Data]) throws {
        for (p, data) in paths {
            let segments = p.split(separator: "/", omittingEmptySubsequences: true).map(String.init)
            guard !segments.isEmpty else { throw IllegalKey(description: "empty path '\(p)'") }
            for s in segments where !isLegalKey(s) { throw IllegalKey(description: "illegal RTDB key '\(s)' in path '\(p)'") }
            let any = try JSONSerialization.jsonObject(with: data, options: [.fragmentsAllowed])
            try checkKeys(any, path: p)
        }
    }
}

// MARK: - Shared shapes (Sector_Ops src/types/brain.ts, contract §4, §9)

public struct BrainSourceRef: Codable, Equatable, Sendable {
    public var sourceType: String
    public var sourceId: String
    public var lastObservationAt: String?
    public init(sourceType: String, sourceId: String, lastObservationAt: String? = nil) {
        self.sourceType = sourceType; self.sourceId = sourceId; self.lastObservationAt = lastObservationAt
    }
}

public struct BrainProvenance: Codable, Equatable, Sendable {
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
    public init(brainId: String, brainVersion: String? = nil, modelVersion: String? = nil, processingVersion: String? = nil,
                generatedAt: String? = nil, sources: [BrainSourceRef]? = nil, inputAgeHours: Double? = nil,
                readiness: String? = nil, qualityFlags: [String]? = nil, validationRef: String? = nil) {
        self.brainId = brainId; self.brainVersion = brainVersion; self.modelVersion = modelVersion
        self.processingVersion = processingVersion; self.generatedAt = generatedAt; self.sources = sources
        self.inputAgeHours = inputAgeHours; self.readiness = readiness; self.qualityFlags = qualityFlags; self.validationRef = validationRef
    }
}

/// The ONE staleness envelope (contract §4). `stale` is the TIME rule; `evidenceStale` the brain's rule.
public struct BrainFreshness: Codable, Equatable, Sendable {
    public var generatedAt: String
    public var sourceObservationAt: String?
    public var freshUntil: String?
    public var nextCheckAt: String?
    public var stale: Bool
    public var evidenceStale: Bool
    public var staleReasons: [String]?
    public var refreshReason: String

    public static func envelope(generatedAt: Date, now: Date, staleAfterHours: Double, stalenessModel: String = "TIME",
                                sourceObservationAt: Date? = nil, nextCheckAt: Date? = nil,
                                evidenceStale: Bool = false, evidenceReasons: [String] = [],
                                refreshReason: String = "scheduled") -> BrainFreshness {
        precondition(BrainVocabulary.stalenessModel.contains(stalenessModel), "not a staleness model: \(stalenessModel)")
        var reasons = evidenceStale ? evidenceReasons.filter { !$0.isEmpty } : []
        var freshUntil: Date? = nil
        var stale = false
        if stalenessModel == "TIME" {
            let fu = generatedAt.addingTimeInterval(staleAfterHours * 3600)
            freshUntil = fu
            stale = now > fu
            if stale {
                let age = (now.timeIntervalSince(generatedAt) / 3600 * 10).rounded() / 10
                reasons.insert("state is \(age) h old (> \(staleAfterHours) h)", at: 0)
            }
        }
        return BrainFreshness(generatedAt: BrainPlatform.iso(generatedAt),
                              sourceObservationAt: sourceObservationAt.map(BrainPlatform.iso),
                              freshUntil: freshUntil.map(BrainPlatform.iso),
                              nextCheckAt: (nextCheckAt ?? freshUntil).map(BrainPlatform.iso),
                              stale: stale, evidenceStale: evidenceStale,
                              staleReasons: reasons.isEmpty ? nil : reasons, refreshReason: refreshReason)
    }
}

public struct BrainHealthRecord: Codable, Equatable, Sendable {
    public var status: String
    public var lastRun: String?
    public var lastSuccess: String?
    public var durationMs: Int?
    public var staleLakeCount: Int
    public var errorCount: Int
    public var latestError: String?
    public var deployedVersion: String?
    public var partial: Bool?
    public init(status: String, lastRun: String? = nil, lastSuccess: String? = nil, durationMs: Int? = nil,
                staleLakeCount: Int, errorCount: Int, latestError: String? = nil, deployedVersion: String? = nil, partial: Bool? = nil) {
        self.status = status; self.lastRun = lastRun; self.lastSuccess = lastSuccess; self.durationMs = durationMs
        self.staleLakeCount = staleLakeCount; self.errorCount = errorCount; self.latestError = latestError
        self.deployedVersion = deployedVersion; self.partial = partial
    }
}

public struct BrainJobHealth: Codable, Equatable, Sendable {
    public var displayName: String
    public var kind: String
    public var schedule: String?
    public var status: String
    public var lastRun: String?
    public var lastSuccess: String?
    public var durationMs: Int?
    public var latestError: String?
    public var running: Bool?
    public init(displayName: String, kind: String, schedule: String? = nil, status: String, lastRun: String? = nil,
                lastSuccess: String? = nil, durationMs: Int? = nil, latestError: String? = nil, running: Bool? = nil) {
        self.displayName = displayName; self.kind = kind; self.schedule = schedule; self.status = status; self.lastRun = lastRun
        self.lastSuccess = lastSuccess; self.durationMs = durationMs; self.latestError = latestError; self.running = running
    }
}

public struct BrainActivityEvent: Codable, Equatable, Sendable {
    public var id: String
    public var at: String
    public var kind: String
    public var title: String
    public var brainId: String?
    public var lakeId: String?
    public var severity: String?
    public init(id: String, at: String, kind: String, title: String, brainId: String? = nil, lakeId: String? = nil, severity: String? = nil) {
        self.id = id; self.at = at; self.kind = kind; self.title = title; self.brainId = brainId; self.lakeId = lakeId; self.severity = severity
    }
}

public struct BrainDataSourceStatus: Codable, Equatable, Sendable {
    public var sourceId: String
    public var provider: String
    public var type: String
    public var ownerBrainId: String?
    /// Map form `{brainId: true}` (contract §5): never an array, so members append without clobbering.
    public var brains: [String: Bool]
    public var lakeCount: Int
    public var health: String
    public var lastFetchAt: String?
    public var latestObservationAt: String?
    public var staleThresholdHours: Double
    /// Written only when a 24 h ledger exists; unknown is absent, never 0.
    public var failures24h: Int?
    public var failuresLastRun: Int?
    public var provides: String?
    public var notes: String?
    public init(sourceId: String, provider: String, type: String, ownerBrainId: String? = nil, brains: [String: Bool], lakeCount: Int,
                health: String, lastFetchAt: String? = nil, latestObservationAt: String? = nil, staleThresholdHours: Double,
                failures24h: Int? = nil, failuresLastRun: Int? = nil, provides: String? = nil, notes: String? = nil) {
        self.sourceId = sourceId; self.provider = provider; self.type = type; self.ownerBrainId = ownerBrainId; self.brains = brains
        self.lakeCount = lakeCount; self.health = health; self.lastFetchAt = lastFetchAt; self.latestObservationAt = latestObservationAt
        self.staleThresholdHours = staleThresholdHours; self.failures24h = failures24h; self.failuresLastRun = failuresLastRun
        self.provides = provides; self.notes = notes
    }
}

public struct BrainSourceHealth: Codable, Equatable, Sendable {
    public var status: String
    public var lastFetchAt: String?
    public var failures24h: Int?
    public var failuresLastRun: Int?
    public init(status: String, lastFetchAt: String? = nil, failures24h: Int? = nil, failuresLastRun: Int? = nil) {
        self.status = status; self.lastFetchAt = lastFetchAt; self.failures24h = failures24h; self.failuresLastRun = failuresLastRun
    }
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
