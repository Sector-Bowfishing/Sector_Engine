//
//  BrainContract.swift
//  Sector — vocabularies, activity, health, ownership and the failure path of
//  docs/brains/BRAIN_PLATFORM_CONTRACT.md (sections 3, 5, 6, 7, 10).
//
//  Pure functions. Mirrors jobs/brain_platform/sector_brain_platform/{enums,activity,health,ownership,failure}.py
//  and must stay fixture-equal with it (BrainPlatformConformanceTests).
//

import Foundation

// MARK: - §3 vocabularies

public enum BrainVocabulary {
    public static let health = ["HEALTHY", "WARNING", "DEGRADED", "FAILED", "UNKNOWN", "NOT_CONFIGURED"]
    public static let readiness = ["DISCOVERED", "PROFILED", "CALIBRATION", "BETA", "VALIDATED", "PRODUCTION", "DEGRADED", "BLOCKED"]
    public static let readinessLadder = ["DISCOVERED", "PROFILED", "CALIBRATION", "BETA", "VALIDATED", "PRODUCTION"]
    public static let brainStatus = readinessLadder
    public static let modelLifecycle = ["RESEARCH", "CANDIDATE", "SHADOW", "REVIEW", "PRODUCTION", "RETIRED"]
    public static let versionStatus = ["CURRENT", "SHADOW", "CANDIDATE", "RETIRED"]
    public static let stateKind = ["measured", "modeled", "observed", "proxy", "analysis", "forecast", "evaluated", "not_evaluated", "unavailable"]
    public static let stalenessModel = ["TIME", "VERSION", "FINGERPRINT"]
    public static let severity = ["info", "success", "warning", "critical"]
    public static let activityKind = ["brain.registered", "brain.version", "brain.updated", "run.failed", "run.degraded", "health.changed",
                                      "readiness.promoted", "readiness.changed", "model.changed", "source.changed", "score.changed"]

    private static let legacyLifecycle = ["ACTIVE_PRODUCTION": "PRODUCTION", "RESEARCH_CANDIDATE": "CANDIDATE", "PRODUCTION_EVIDENCE": "PRODUCTION"]
    private static let legacyKind = ["OBSERVED": "observed", "PROXY": "proxy", "UNAVAILABLE": "unavailable", "MEASURED": "measured",
                                     "MODELED": "modeled", "NOT_EVALUATED": "not_evaluated"]

    /// True only for an upward move on the ladder; off-ladder values are changes, not promotions.
    public static func isPromotion(from: String?, to: String?) -> Bool {
        guard let f = from, let t = to, let fi = readinessLadder.firstIndex(of: f), let ti = readinessLadder.firstIndex(of: t) else { return false }
        return ti > fi
    }

    public static func normalizeModelLifecycle(_ v: String) -> String? {
        let n = legacyLifecycle[v] ?? v
        return modelLifecycle.contains(n) ? n : nil
    }

    public static func normalizeStateKind(_ v: String) -> String? {
        let n = legacyKind[v] ?? v.lowercased()
        return stateKind.contains(n) ? n : nil
    }
}

// MARK: - §3 run health

public enum BrainHealth {
    /// FAILED: aborted. UNKNOWN: nothing attempted. DEGRADED: publish failed or > 25 % unavailable.
    /// WARNING: 5–25 % unavailable or a partial run. HEALTHY otherwise.
    public static func runHealth(attempted: Int, ok: Int, failed: Int, aborted: Bool = false, partial: Bool = false,
                                 publishFailed: Bool = false) -> String {
        if aborted { return "FAILED" }
        if attempted <= 0 { return "UNKNOWN" }
        if publishFailed { return "DEGRADED" }
        let unavailable = Double(failed) / Double(attempted)
        if unavailable > 0.25 { return "DEGRADED" }
        if unavailable >= 0.05 || partial { return "WARNING" }
        return "HEALTHY"
    }
}

// MARK: - §7 activity

public enum BrainActivity {
    public static let keepPerBrain = 80
    public static let maxAgeDays = 30

    /// `{ms13}-{brainId}-{nnn}`: lexical order == time order across brains.
    public static func eventId(atMs ms: Int64, brainId: String, n: Int) -> String {
        String(format: "%013lld-%@-%03d", ms, brainId, n)
    }
    public static func eventId(at: Date, brainId: String, n: Int) -> String {
        eventId(atMs: Int64((at.timeIntervalSince1970 * 1000).rounded(.down)), brainId: brainId, n: n)
    }

    public static func event(at: Date, brainId: String, n: Int, kind: String, title: String, severity: String,
                             lakeId: String? = nil) -> BrainActivityEvent {
        precondition(BrainVocabulary.activityKind.contains(kind), "not an activity kind: \(kind)")
        precondition(BrainVocabulary.severity.contains(severity), "not a severity: \(severity)")
        return BrainActivityEvent(id: eventId(at: at, brainId: brainId, n: n), at: BrainPlatform.iso(at), kind: kind,
                                  title: title, brainId: brainId, lakeId: lakeId, severity: severity)
    }

    /// Keys to delete for THIS brain's old events only, decided by the `at` field, never by key.
    /// `activity` is the decoded `/activity` node (`[eventId: event]`). Events without a parseable
    /// `at` are kept; other brains' and brain-less legacy events are never touched.
    public static func pruneKeys(activity: [String: Any], brainId: String, now: Date,
                                 keep: Int = keepPerBrain, maxAgeDays: Int = maxAgeDays) -> [String] {
        var dated: [(key: String, at: Date)] = []
        for (k, v) in activity {
            guard let e = v as? [String: Any], (e["brainId"] as? String) == brainId else { continue }
            if let at = BrainPlatform.parseTime(e["at"] as? String) { dated.append((k, at)) }
        }
        let cutoff = now.addingTimeInterval(-Double(maxAgeDays) * 86_400)
        var drop = Set(dated.filter { $0.at < cutoff }.map(\.key))
        let sorted = dated.sorted { $0.at < $1.at }
        if sorted.count > keep { drop.formUnion(sorted.prefix(sorted.count - keep).map(\.key)) }
        return drop.sorted()
    }

    /// Convenience over a store: read `/activity`, compute, delete in one update.
    public static func prune(store: BrainStore, brainId: String, now: Date) async throws -> [String] {
        guard let data = try await store.get("activity"),
              let tree = try JSONSerialization.jsonObject(with: data) as? [String: Any] else { return [] }
        let keys = pruneKeys(activity: tree, brainId: brainId, now: now)
        guard !keys.isEmpty else { return [] }
        var paths: [String: Data] = [:]
        for k in keys { paths["activity/\(k)"] = Data("null".utf8) }
        try await store.update(paths)
        return keys
    }
}

// MARK: - §5/§6 ownership

public enum BrainOwnership {
    public struct Violation: Error, CustomStringConvertible { public let description: String }

    public static let sourceOwners: [String: String] = [
        "tva-restapi": "lake-brain",
        "usace-cwms-pool": "lake-brain",
        "usgs-nwis-lake-elevation": "lake-brain",
        "usace-access2water": "lake-brain",            // fleet/candidate scopes (Lake Brain is the only acquirer)
        "usbr-rise": "lake-brain",
        "nws-nwps": "lake-brain",
        "usgs-nwis-00010": "water-temp",
        "usace-cwms-water-temp": "water-temp",
        "open-meteo-forecast": "water-temp",
        "sentinel-2-l2a": "water-clarity",
        "usgs-nwis-turbidity": "water-clarity",
        "noaa-mrms": "water-clarity",
        "noaa-nbm-v5": "wind",
        "noaa-rtma-ru": "wind",
        "iem-metar-wind": "wind",
    ]
    static let rollupFleet: Set<String> = ["lastUpdatedAt", "stale", "issueCount", "hasObservations"]
    static let rollupSnapshot: Set<String> = ["generatedAt", "snapshotVersion", "evaluationTime"]
    static let lakeBrainOnlyFleet: Set<String> = ["riverSystem", "lakeType"]
    static let platformOnly: Set<String> = ["schemaVersion", "access", "validationOps", "engine", "control", "scores", "jobs"]
    /// The Engine's own publisher (scores, engine health); not a brain.
    public static let platformWriter = "brain-platform"

    public static func sourceOwner(_ sourceId: String) -> String? { sourceOwners[sourceId] }

    /// May `brainId` write `path` (root-relative, no leading slash)?
    public static func pathAllowed(_ brainId: String, _ path: String) -> Bool {
        let p = path.split(separator: "/", omittingEmptySubsequences: true).map(String.init)
        guard let root = p.first else { return false }
        if brainId == platformWriter {
            // @external-admin families (Cortex 3.1 registry): access lists and the owner's execution-control document are never a platform write.
            if root == "access" || (root == "control" && p.count >= 2 && p[1] == "executionControlV1") { return false }
            if platformOnly.contains(root) || (root == "health" && p.count >= 2 && (p[1] == "engine" || p[1] == "rtdb")) { return true }
            if root == "activity" { return p.count == 2 && p[1].contains("-\(platformWriter)-") }
            return false
        }
        guard let slot = BrainPlatform.slot(for: brainId), let field = BrainPlatform.snapshotField(for: brainId) else { return false }
        if platformOnly.contains(root) || (root == "health" && p.count > 1 && (p[1] == "engine" || p[1] == "rtdb")) { return false }
        switch root {
        case "lakeFleet":
            guard p.count >= 3 else { return false }
            let f = p[2]
            if f == "lakeId" { return true }
            if rollupFleet.contains(f) { return false }
            if lakeBrainOnlyFleet.contains(f) { return brainId == "lake-brain" }
            if ["readiness", "modelVersions", "slots"].contains(f) { return p.count >= 4 && p[3] == slot }
            return false
        case "lakes":
            guard p.count >= 3 else { return false }
            switch p[2] {
            case "brain", "speciesPresence": return brainId == "lake-brain"
            case "states", "profiles": return p.count >= 4 && p[3] == slot
            case "validation": return p.count >= 4 && p[3] == brainId
            default: return false
            }
        case "snapshots":
            guard p.count >= 4, p[2] == "latest" else { return false }
            let f = p[3]
            if f == "lakeId" { return true }
            if rollupSnapshot.contains(f) { return false }
            if f == "brainVersions" { return p.count >= 5 && p[4] == brainId }
            return f == field
        case "species": return brainId == "biological-state" && p.count >= 2     // never the whole /species root (Cortex 3.1 FD-03: a whole-node write erases every other record)
        case "brains", "validation":
            // Cortex 3.1 SC-04 / FD-15: the /brains/{id}/score(s) mirrors are the shared scorer's fields; /brains/wind/scores is the one registered LEGACY Wind family.
            if root == "brains", p.count >= 3, p[2] == "score" || p[2] == "scores", !(brainId == "wind" && p[2] == "scores") { return false }
            return p.count >= 2 && p[1] == brainId
        case "health":
            guard p.count >= 3 else { return false }
            switch p[1] {
            case "brains": return p[2] == brainId
            case "jobs": return true
            case "sources": return sourceOwner(p[2]).map { $0 == brainId } ?? true
            default: return false
            }
        case "sources":
            guard p.count >= 2 else { return false }
            if p.count >= 4, p[2] == "brains", p[3] == brainId { return true }
            return sourceOwner(p[1]).map { $0 == brainId } ?? true
        case "activity":
            return p.count == 2 && p[1].contains("-\(brainId)-")
        default: return false
        }
    }

    public static func check(_ paths: [String: Data], brainId: String) throws {
        let bad = paths.keys.filter { !pathAllowed(brainId, $0) }.sorted()
        if !bad.isEmpty { throw Violation(description: "\(brainId) may not write: \(bad.prefix(5))\(bad.count > 5 ? " …" : "")") }
    }
}

// MARK: - §10 failure path

public enum BrainFailure {
    /// One unit: health leaves, registry health + lastError, and a `run.failed` event.
    public static func writes(brainId: String, message: String, now: Date, started: Date? = nil, errorCount: Int = 1,
                              jobId: String? = nil) throws -> [String: Data] {
        let at = BrainPlatform.iso(now)
        let msg = String(message.prefix(500))
        let ev = BrainActivity.event(at: now, brainId: brainId, n: 0, kind: "run.failed",
                                     title: "\(brainId) run failed: \(message.prefix(160))", severity: "critical")
        struct LastError: Encodable { let at: String; let message: String }
        var out: [String: Data] = [
            "health/brains/\(brainId)/status": try BrainJSON.encode("FAILED"),
            "health/brains/\(brainId)/lastRun": try BrainJSON.encode(at),
            "health/brains/\(brainId)/latestError": try BrainJSON.encode(msg),
            "health/brains/\(brainId)/errorCount": try BrainJSON.encode(errorCount),
            "brains/\(brainId)/health": try BrainJSON.encode("FAILED"),
            "brains/\(brainId)/lastError": try BrainJSON.encode(LastError(at: at, message: msg)),
            "activity/\(ev.id)": try BrainJSON.encode(ev),
        ]
        if let started { out["health/brains/\(brainId)/durationMs"] = try BrainJSON.encode(Int(now.timeIntervalSince(started) * 1000)) }
        if let jobId {
            out["health/jobs/\(jobId)/status"] = try BrainJSON.encode("FAILED")
            out["health/jobs/\(jobId)/lastRun"] = try BrainJSON.encode(at)
            out["health/jobs/\(jobId)/latestError"] = try BrainJSON.encode(msg)
            out["health/jobs/\(jobId)/running"] = try BrainJSON.encode(false)
        }
        return out
    }
}
