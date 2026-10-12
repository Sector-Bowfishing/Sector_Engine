//
//  WaterTemperatureBrainRunner.swift
//  Sector — one fleet run of the water-temp brain → the Brain RTDB
//
//  Runs OUTSIDE the request path (the WaterTempBrainJob Cloud Run job). A Brain
//  RTDB failure fails this job only: the service never reads or writes here.
//
//  Write order (Sector_Ops BRAIN_INTEGRATION_REQUIREMENTS §0.9), per chunk of
//  lakes as ONE atomic multi-path update — states + profiles + the snapshot's
//  water-temp fields + the fleet row's water-temp fields — then the registry,
//  validation, health, sources, and activity.
//
//  Only water-temp-owned keys are written. Lake-level fleet fields shared by
//  every brain (`stale`, `issueCount`, `hasObservations`, `riverSystem`, …)
//  belong to the Lake Brain and are left alone.
//

import Foundation

public struct WaterTemperatureBrainRunOptions: Sendable {
    public var lakeIds: [String]? = nil
    public var limit: Int? = nil
    public var concurrency: Int = 6
    public var chunkSize: Int = 50
    /// Cloud Run revision / engine commit of the code that ran.
    public var processingVersion: String? = nil
    public init() {}
}

public struct WaterTemperatureBrainRunResult: Sendable {
    public var lakes = 0
    public var kindCounts: [String: Int] = [:]
    public var readinessCounts: [String: Int] = [:]
    public var modelFailures = 0
    public var staleLakes = 0
    public var health = "UNKNOWN"
    public var durationMs = 0
    public var writeError: String? = nil
    public var states: [WaterTemperatureBrain.State] = []
    public var ok: Bool { writeError == nil && health != "FAILED" }
}

public enum WaterTemperatureBrainRunner {

    public static let jobId = "water-temp-brain"

    /// Runtime health of one run — never readiness, never validation.
    static func health(lakes: Int, unavailable: Int, modelFailures: Int, writeFailed: Bool) -> String {
        if writeFailed || lakes == 0 { return "FAILED" }
        let bad = Double(max(unavailable, modelFailures)) / Double(lakes)
        if bad > 0.25 { return "DEGRADED" }
        if bad > 0.05 { return "WARNING" }
        return "HEALTHY"
    }

    public static func run(store: BrainStore?, options: WaterTemperatureBrainRunOptions = .init(),
                           now: Date = Date()) async -> WaterTemperatureBrainRunResult {
        let t0 = Date()
        var result = WaterTemperatureBrainRunResult()
        let collisions = BrainPlatform.keyCollisions(LakeDirectory.all.map(\.id))
        var lakes = LakeDirectory.all
        if let ids = options.lakeIds { lakes = lakes.filter { ids.contains($0.id) } }
        if let n = options.limit { lakes = Array(lakes.prefix(n)) }

        let previous: BrainRegistryEntry? = await {
            guard let store, let d = try? await store.get("brains/\(WaterTemperatureBrain.brainId)") else { return nil }
            return try? JSONDecoder().decode(BrainRegistryEntry.self, from: d)
        }()

        guard collisions.isEmpty else {
            result.health = "FAILED"
            result.writeError = "lake key collision: \(collisions.keys.sorted())"
            if let store { try? await writeFailure(store: store, message: result.writeError!, now: now, options: options, t0: t0) }
            return result
        }

        // ---- compute (bounded concurrency; same fetch + resolver as /conditions)
        var inputs: [WaterTemperatureBrain.LakeInputs] = []
        var i = 0
        while i < lakes.count {
            let batch = lakes[i..<min(i + max(1, options.concurrency), lakes.count)]
            await withTaskGroup(of: WaterTemperatureBrain.LakeInputs.self) { g in
                for lake in batch { g.addTask { await WaterTemperatureBrain.fetchInputs(for: lake) } }
                for await x in g { inputs.append(x) }
            }
            i += options.concurrency
        }
        inputs.sort { $0.lake.id < $1.lake.id }
        let generatedAt = Date()
        for x in inputs {
            let resolved = WaterTemperatureResolver.resolve(measurement: x.measurement, model: x.model, at: generatedAt)
            let st = WaterTemperatureBrain.state(from: x, resolved: resolved, now: generatedAt, processingVersion: options.processingVersion)
            result.states.append(st)
            result.kindCounts[st.kind, default: 0] += 1
            result.readinessCounts[st.provenance.readiness ?? "UNKNOWN", default: 0] += 1
            if x.modelFetchFailed { result.modelFailures += 1 }
            if st.stale { result.staleLakes += 1 }
        }
        result.lakes = inputs.count
        result.health = health(lakes: result.lakes, unavailable: result.kindCounts["unavailable", default: 0],
                               modelFailures: result.modelFailures, writeFailed: false)

        guard let store else {
            result.durationMs = Int(Date().timeIntervalSince(t0) * 1000)
            return result
        }

        // ---- write
        do {
            let gen = BrainPlatform.iso(generatedAt)
            for chunk in stride(from: 0, to: inputs.count, by: options.chunkSize) {
                var paths: [String: Data] = [:]
                for j in chunk..<min(chunk + options.chunkSize, inputs.count) {
                    let lake = inputs[j].lake, st = result.states[j], k = BrainPlatform.lakeKey(lake.id)
                    let stateJSON = try BrainJSON.encode(st)
                    paths["lakes/\(k)/states/\(WaterTemperatureBrain.slot)"] = stateJSON
                    paths["lakes/\(k)/profiles/\(WaterTemperatureBrain.slot)"] = try BrainJSON.encode(WaterTemperatureBrain.profile(for: lake))
                    paths["snapshots/\(k)/latest/lakeId"] = try BrainJSON.encode(lake.id)
                    paths["snapshots/\(k)/latest/generatedAt"] = try BrainJSON.encode(gen)
                    paths["snapshots/\(k)/latest/snapshotVersion"] = try BrainJSON.encode(1)
                    paths["snapshots/\(k)/latest/\(WaterTemperatureBrain.snapshotField)"] = stateJSON
                    paths["snapshots/\(k)/latest/brainVersions/\(WaterTemperatureBrain.brainId)"] = try BrainJSON.encode(WaterTemperatureBrain.brainVersion)
                    paths["lakeFleet/\(k)/lakeId"] = try BrainJSON.encode(lake.id)
                    paths["lakeFleet/\(k)/readiness/\(WaterTemperatureBrain.slot)"] = try BrainJSON.encode(st.provenance.readiness)
                    paths["lakeFleet/\(k)/modelVersions/\(WaterTemperatureBrain.slot)"] = try BrainJSON.encode(WaterTemperatureBrain.modelVersion)
                    paths["lakeFleet/\(k)/lastUpdatedAt"] = try BrainJSON.encode(gen)
                    // Per-brain fleet summary, the convention the clarity and wind brains already write.
                    paths["lakeFleet/\(k)/slots/\(WaterTemperatureBrain.slot)"] = try BrainJSON.encode(FleetSlot(
                        issueCount: (st.stale || st.kind == "unavailable") ? 1 : 0, lastUpdatedAt: gen,
                        readiness: st.provenance.readiness, stale: st.stale, stateType: st.kind))
                }
                try await store.update(paths)
            }
            // validation (documented evidence) — fleet + the protected lakes that have a real per-lake record
            var v: [String: Data] = ["validation/\(WaterTemperatureBrain.brainId)": try BrainJSON.encode(WaterTemperatureBrain.fleetValidation())]
            for p in WaterTemperatureBrain.protectedLakes where LakeDirectory.all.contains(where: { $0.id == p.lakeId }) {
                v["lakes/\(BrainPlatform.lakeKey(p.lakeId))/validation/\(WaterTemperatureBrain.brainId)"] =
                    try BrainJSON.encode(WaterTemperatureBrain.protectedLakeValidation(p))
            }
            try await store.update(v)

            let finished = Date()
            result.durationMs = Int(finished.timeIntervalSince(t0) * 1000)
            let fullFleet = options.lakeIds == nil && options.limit == nil
            // A partial run (one lake, a sample) writes per-lake nodes only; the registry,
            // health and sources describe the whole fleet and are left to full runs.
            guard fullFleet else { return result }
            let registry = registryEntry(result: result, now: finished, options: options, fullFleet: fullFleet, lastError: nil)
            var tail: [String: Data] = [
                "brains/\(WaterTemperatureBrain.brainId)": try BrainJSON.encode(registry),
                "health/brains/\(WaterTemperatureBrain.brainId)": try BrainJSON.encode(BrainHealthRecord(
                    status: result.health, lastRun: BrainPlatform.iso(t0), lastSuccess: BrainPlatform.iso(finished),
                    durationMs: result.durationMs, staleLakeCount: result.staleLakes, errorCount: result.modelFailures,
                    latestError: nil, deployedVersion: options.processingVersion)),
                "health/jobs/\(jobId)": try BrainJSON.encode(BrainJobHealth(
                    displayName: "Water Temperature Brain", kind: "cloud-run-job", schedule: WaterTemperatureBrain.schedule,
                    status: result.health, lastRun: BrainPlatform.iso(t0), lastSuccess: BrainPlatform.iso(finished),
                    durationMs: result.durationMs, latestError: nil, running: false)),
            ]
            for (id, rec) in sourceRecords(inputs: inputs, now: finished) {
                tail["sources/\(id)"] = try BrainJSON.encode(rec.0)
                tail["health/sources/\(id)"] = try BrainJSON.encode(rec.1)
            }
            for e in activity(previous: previous, current: registry, now: finished) { tail["activity/\(e.id)"] = try BrainJSON.encode(e) }
            try await store.update(tail)
            try? await pruneActivity(store: store, now: finished)
        } catch {
            result.writeError = "\(error)"
            result.health = "FAILED"
            try? await writeFailure(store: store, message: result.writeError!, now: Date(), options: options, t0: t0)
        }
        return result
    }

    // MARK: registry

    static func registryEntry(result: WaterTemperatureBrainRunResult, now: Date, options: WaterTemperatureBrainRunOptions,
                              fullFleet: Bool, lastError: BrainRegistryEntry.ErrorInfo?) -> BrainRegistryEntry {
        var sourceKind: [String: Int] = [:]
        for s in result.states { sourceKind[s.provenance.sources?.first?.sourceType ?? "none", default: 0] += 1 }
        var directoryTempSource: [String: Int] = [:]
        for l in LakeDirectory.all { directoryTempSource[l.tempSource.rawValue, default: 0] += 1 }
        return BrainRegistryEntry(
            brainId: WaterTemperatureBrain.brainId, displayName: "Water Temperature", domain: "condition",
            question: "What is the water temperature doing?", version: WaterTemperatureBrain.brainVersion,
            schemaVersion: BrainPlatform.schemaVersion, enabled: true, health: result.health,
            supportedLakeCount: LakeDirectory.all.count,
            readinessCounts: fullFleet ? result.readinessCounts : nil,
            staleLakeCount: fullFleet ? result.staleLakes : nil, staleAfterHours: WaterTemperatureBrain.staleAfterHours,
            lastSuccessfulRun: lastError == nil ? BrainPlatform.iso(now) : nil, lastError: lastError,
            deploymentVersion: options.processingVersion,
            breakdowns: fullFleet ? ["stateKind": result.kindCounts, "sourceKind": sourceKind, "directoryTempSource": directoryTempSource] : nil,
            status: "PRODUCTION",
            versions: [
                .init(version: WaterTemperatureBrain.modelVersion, date: "2026-09-23", note: "Production model (global 17-gauge calibration). Shown = scored and lake-local date since 2026-10-07 (Stage 2E).", status: "CURRENT"),
                .init(version: "V2 candidate: M0 + Stage 3C.1 Arm A KF [x,b] + operational state", date: "2026-10-11", note: "Research candidate. Frozen, NOT promoted, not running. Protected Level-4 validation blocked by insufficient truth.", status: "RESEARCH"),
                .init(version: "air-lag k=0.20", date: "2026-09-23", note: "Retired: ran 3.7 °F cold.", status: "RETIRED"),
            ],
            runsPerMinute: nil,
            activeProductionModel: .init(modelVersion: WaterTemperatureBrain.modelVersion, since: "2026-09-23",
                                         validationStatus: "GLOBAL_HOLDOUT_ONLY", assimilation: "none"),
            researchCandidate: .init(name: "Water Temp V2", description: "production M0 + Stage 3C.1 Arm A 2-state Kalman filter + operational state engine",
                                     status: "RESEARCH_NOT_PROMOTED", certified: false,
                                     blocker: "Protected truth insufficient: Wheeler 18/25, Wilson 2/25 (Stage 3C.3, 2026-10-11)"),
            readinessDefinitions: WaterTemperatureBrain.readinessDefinitions,
            stateKindDefinitions: WaterTemperatureBrain.stateKindDefinitions,
            healthRule: "FAILED: write failed or no lakes. DEGRADED: > 25 % of lakes unavailable or model fetch failed. WARNING: > 5 %. HEALTHY otherwise.",
            fleetScope: fullFleet ? "full" : "partial")
    }

    // MARK: sources (only what this run can actually observe)

    static func sourceRecords(inputs: [WaterTemperatureBrain.LakeInputs], now: Date) -> [String: (BrainDataSourceStatus, BrainSourceHealth)] {
        let at = BrainPlatform.iso(now)
        var out: [String: (BrainDataSourceStatus, BrainSourceHealth)] = [:]
        let modelFails = inputs.filter(\.modelFetchFailed).count
        let omHealth = health(lakes: inputs.count, unavailable: 0, modelFailures: modelFails, writeFailed: false)
        out["open-meteo-forecast"] = (
            BrainDataSourceStatus(sourceId: "open-meteo-forecast", provider: "Open-Meteo", type: "weather-forcing",
                                  brains: [WaterTemperatureBrain.brainId], lakeCount: inputs.count, health: omHealth,
                                  lastFetchAt: at, latestObservationAt: nil, staleThresholdHours: WaterTemperatureBrain.staleAfterHours,
                                  failures24h: nil, failuresLastRun: modelFails,
                                  provides: "daily air temperature, shortwave, wind, humidity → water-temp model forcing",
                                  notes: "Written by the water-temp brain job. Other brains also use Open-Meteo; a shared source writer should own this record once they integrate."),
            BrainSourceHealth(status: omHealth, lastFetchAt: at, failures24h: nil, failuresLastRun: modelFails))
        for (id, provider, kinds) in [("usgs-nwis-00010", "USGS", ["usgsLakeSensor"]), ("usace-cwms-water-temp", "USACE CWMS", ["cwmsLakeSensor"])] {
            let readings = inputs.compactMap(\.measurement).filter { kinds.contains($0.provider == "USACE CWMS" ? "cwmsLakeSensor" : "usgsLakeSensor") }
            let configured = inputs.filter { ($0.lake.tempSensor ?? "").hasPrefix(provider == "USGS" ? "usgs:" : "cwms:") }.count
            out[id] = (
                BrainDataSourceStatus(sourceId: id, provider: provider, type: "lake-temperature-sensor",
                                      brains: [WaterTemperatureBrain.brainId], lakeCount: readings.count, health: "UNKNOWN",
                                      lastFetchAt: at, latestObservationAt: readings.map(\.dateTime).max().map(BrainPlatform.iso),
                                      staleThresholdHours: WaterTemperatureResolver.measurementMaxAgeHours,
                                      failures24h: nil, failuresLastRun: nil,
                                      provides: "lake surface water temperature (shown as measured when ≤ 6 h old, ≤ 15 mi)",
                                      notes: "lakeCount = lakes that returned a reading this run (\(configured) lakes have this provider configured as their own sensor). Fetch errors are swallowed by the production path, so failures are not observable; health is UNKNOWN."),
                BrainSourceHealth(status: "UNKNOWN", lastFetchAt: at, failures24h: nil, failuresLastRun: nil))
        }
        return out
    }

    // MARK: activity (version / readiness / health changes, run failure)

    static func activity(previous: BrainRegistryEntry?, current: BrainRegistryEntry, now: Date) -> [BrainActivityEvent] {
        var out: [BrainActivityEvent] = []
        func ev(_ kind: String, _ title: String, _ sev: String) {
            out.append(BrainActivityEvent(id: BrainPlatform.eventKey(now.addingTimeInterval(Double(out.count) / 1000), suffix: "water-temp-\(kind)"),
                                          at: BrainPlatform.iso(now), kind: kind, title: title, brainId: WaterTemperatureBrain.brainId,
                                          lakeId: nil, severity: sev))
        }
        guard let p = previous else {
            ev("brain-registered", "Water Temperature Brain registered (v\(current.version ?? "?"), \(current.supportedLakeCount) lakes)", "info")
            return out
        }
        if p.version != current.version { ev("version-change", "Water Temperature Brain \(p.version ?? "?") → \(current.version ?? "?")", "info") }
        if p.versions?.first?.version != current.versions?.first?.version {
            ev("model-change", "Water temp production model → \(current.versions?.first?.version ?? "?")", "info")
        }
        if let pc = p.readinessCounts, let cc = current.readinessCounts, pc != cc {
            ev("readiness-change", "Water temp readiness changed: \(cc.sorted { $0.key < $1.key }.map { "\($0.key) \($0.value)" }.joined(separator: ", "))", "info")
        }
        if p.health != current.health {
            let sev = current.health == "HEALTHY" ? "success" : (current.health == "FAILED" ? "critical" : "warning")
            ev("health-change", "Water temp brain health \(p.health) → \(current.health)", sev)
        }
        return out
    }

    /// Keep ≤ 500 events and ≤ 30 days (keys are time-sortable).
    static func pruneActivity(store: BrainStore, now: Date) async throws {
        let keys = try await store.shallowKeys("activity").sorted()
        let cutoff = BrainPlatform.eventKey(now.addingTimeInterval(-30 * 86_400), suffix: "")
        var drop = Set(keys.filter { $0 < cutoff })
        if keys.count - drop.count > 500 { drop.formUnion(keys.filter { !drop.contains($0) }.prefix(keys.count - drop.count - 500)) }
        guard !drop.isEmpty else { return }
        var paths: [String: Data] = [:]
        for k in drop { paths["activity/\(k)"] = Data("null".utf8) }
        try await store.update(paths)
    }

    static func writeFailure(store: BrainStore, message: String, now: Date, options: WaterTemperatureBrainRunOptions, t0: Date) async throws {
        let at = BrainPlatform.iso(now)
        let prev = (try? await store.get("health/brains/\(WaterTemperatureBrain.brainId)")).flatMap { try? JSONDecoder().decode(BrainHealthRecord.self, from: $0) }
        try await store.update([
            "health/brains/\(WaterTemperatureBrain.brainId)": try BrainJSON.encode(BrainHealthRecord(
                status: "FAILED", lastRun: BrainPlatform.iso(t0), lastSuccess: prev?.lastSuccess, durationMs: Int(now.timeIntervalSince(t0) * 1000),
                staleLakeCount: prev?.staleLakeCount ?? 0, errorCount: (prev?.errorCount ?? 0) + 1, latestError: message,
                deployedVersion: options.processingVersion)),
            "brains/\(WaterTemperatureBrain.brainId)/health": try BrainJSON.encode("FAILED"),
            "brains/\(WaterTemperatureBrain.brainId)/lastError": try BrainJSON.encode(BrainRegistryEntry.ErrorInfo(at: at, message: message)),
            "activity/\(BrainPlatform.eventKey(now, suffix: "water-temp-run-failed"))": try BrainJSON.encode(BrainActivityEvent(
                id: BrainPlatform.eventKey(now, suffix: "water-temp-run-failed"), at: at, kind: "run-failed",
                title: "Water temp brain run failed: \(message.prefix(160))", brainId: WaterTemperatureBrain.brainId, lakeId: nil, severity: "critical")),
        ])
    }
}

/// `lakeFleet/{k}/slots/waterTemp`. issueCount = 1 when the lake's sensor has no fresh reading or no value exists.
struct FleetSlot: Codable, Equatable {
    var issueCount: Int
    var lastUpdatedAt: String
    var readiness: String?
    var stale: Bool
    var stateType: String
}

// MARK: - Registry entry (shared shell + water-temp extensions)

public struct BrainRegistryEntry: Codable, Equatable, Sendable {
    public struct ErrorInfo: Codable, Equatable, Sendable { public var at: String; public var message: String }
    public struct Version: Codable, Equatable, Sendable { public var version: String; public var date: String; public var note: String; public var status: String }
    public struct ActiveModel: Codable, Equatable, Sendable { public var modelVersion: String; public var since: String; public var validationStatus: String; public var assimilation: String }
    public struct Candidate: Codable, Equatable, Sendable { public var name: String; public var description: String; public var status: String; public var certified: Bool; public var blocker: String }

    public var brainId: String
    public var displayName: String
    public var domain: String
    public var question: String
    public var version: String?
    public var schemaVersion: Int
    public var enabled: Bool
    public var health: String
    public var supportedLakeCount: Int
    public var readinessCounts: [String: Int]?
    public var staleLakeCount: Int?
    public var staleAfterHours: Double?
    public var lastSuccessfulRun: String?
    public var lastError: ErrorInfo?
    public var deploymentVersion: String?
    public var breakdowns: [String: [String: Int]]?
    public var status: String?
    public var versions: [Version]?
    public var runsPerMinute: Double?
    public var activeProductionModel: ActiveModel?
    public var researchCandidate: Candidate?
    public var readinessDefinitions: [String: String]?
    public var stateKindDefinitions: [String: String]?
    public var healthRule: String?
    public var fleetScope: String?
}
