//
//  LakeBrainRunner.swift
//  Sector — one Lake Brain run → GCS history + the Brain RTDB
//
//  Runs OUTSIDE the request path (the LakeBrainJob executable). A failure here
//  fails this run only; no other brain and no customer path is touched.
//
//  Write order (Sector_Ops BRAIN_INTEGRATION_REQUIREMENTS §0.9), per lake as ONE
//  atomic multi-path update, LEAF PATHS ONLY on shared nodes:
//    lakes/{k}/states/lake, lakes/{k}/brain, lakes/{k}/speciesPresence/{id}
//    snapshots/{k}/latest/{lakeId, lakeState, brainVersions/lake-brain}
//    lakeFleet/{k}/{lakeId, readiness/lake, slots/lake, modelVersions/lake, riverSystem}
//  then brains/lake-brain, validation/lake-brain, health, sources, activity.
//  Never another brain's slot, never /schemaVersion, never a whole /lakes/{k}.
//

import Foundation

public struct LakeBrainRunOptions: Sendable {
    public enum Scope: String, Sendable { case pilots, fleet }
    public var scope: Scope = .pilots
    /// A subset of lakes: per-lake nodes only (registry/health/sources are left to full runs).
    public var lakeIds: [String]? = nil
    /// Lakes evaluated at once. Clamped to 1...`BrainPlatform.maxConcurrency` when used (0 or a negative value used to
    /// spin the batch loop forever); read `LakeBrainRunResult.concurrency` for the value that was applied.
    public var concurrency: Int = 3
    /// Ignore plan() and recompute every lake in scope.
    public var force = false
    /// Pull full operator history (decades of CWMS daily) instead of the recent tail.
    public var backfill = false
    public var processingVersion: String? = nil
    /// Prospective prediction ledger (docs/brains/LAKE_BRAIN_PREDICTION_LEDGER.md). ON BY DEFAULT and in every production
    /// path; never affects the publish. Only the explicit `--no-ledger` job flag (dry runs, debug, replay, local tests) turns it off,
    /// and the run then records `ledger: disabled` (`LakeBrainRunResult.ledgerStatus`).
    public var ledgerEnabled = true
    /// Where the ledger object goes. Default: a live run writes to the history archive; a dry run (local RTDB store)
    /// writes under `<dry-run dir>/_ledger` and never to GCS.
    public var ledgerArchive: LakeBrainArchive? = nil
    /// Run id in the ledger object name; default is a short random id.
    public var runId: String? = nil
    /// DRY RUN ONLY (LakeBrainJob refuses it with --rtdb): evaluate CANDIDATE bindings as if reviewed. Writes local files only and
    /// marks every output `dryRunCandidate`. A normal run never sets this.
    public var includeCandidates = false
    public init() {}
}

public struct LakeBrainLakeResult: Sendable {
    public var lakeId: String
    public var plan: LakeBrainPlanDecision?
    public var state: LakeLevelStateRecord?
    public var profile: LakeBrainProfileRecord
    public var presence: [LakeSpeciesPresenceRecord]
    public var baseline: LakeLevelBaseline?
    public var historyRows: Int
    public var historyWritten: Bool
    public var errors: [String]
    /// The binding was a CANDIDATE evaluated as if reviewed (candidate dry run).
    public var dryRunCandidate = false
}

public struct LakeBrainRunResult: Sendable {
    public var lakes: [LakeBrainLakeResult] = []
    public var health = "UNKNOWN"
    public var durationMs = 0
    public var writeError: String? = nil
    public var archiveErrors: [String] = []
    public var presenceError: String? = nil
    /// Prediction ledger outcome: object path (nil when nothing was written), record count, and a warning if the write failed.
    public var ledgerObject: String? = nil
    public var ledgerRecords = 0
    public var ledgerWarning: String? = nil
    /// "enabled" or "disabled" (only `--no-ledger` / `ledgerEnabled = false` disables). Printed by the job as `ledger: …`.
    public var ledgerStatus = "enabled"
    /// The lake concurrency actually applied (after clamping).
    public var concurrency = 0
    public var ok: Bool { writeError == nil && health != "FAILED" }
}

public struct LakeBrainRegistryEntry: Codable, Equatable, Sendable {
    public struct ErrorInfo: Codable, Equatable, Sendable { public var at: String; public var message: String }
    /// Contract §13: the platform this brain publishes through.
    public var platform: BrainPlatformRef? = nil
    /// Orchestrator inputs (contract §9/§11).
    public var stalenessModel: String? = nil
    public var dependsOn: [String]? = nil
    public var schedule: [String: String]? = nil
    public struct Version: Codable, Equatable, Sendable { public var version: String; public var date: String; public var note: String; public var status: String }
    public var brainId: String
    public var displayName: String
    public var domain: String
    public var question: String
    public var version: String
    public var schemaVersion: Int
    public var enabled: Bool
    public var health: String
    public var status: String
    public var supportedLakeCount: Int
    public var directoryLakeCount: Int
    public var readinessCounts: [String: Int]?
    public var staleLakeCount: Int?
    public var staleAfterHours: Double
    public var lastSuccessfulRun: String?
    public var lastError: ErrorInfo?
    public var deploymentVersion: String?
    public var modelVersion: String
    public var baselineMethod: String
    public var bindingVersion: String
    public var breakdowns: [String: [String: Int]]?
    public var versions: [Version]
    public var readinessDefinitions: [String: String]
    public var stateKindDefinitions: [String: String]
    public var healthRule: String
    public var orchestration: LakeBrainDescriptor
    public var fleetScope: String
    /// Prospective prediction-ledger status (Ops-visible validation clock). `startedAt` is the fixed start of the prospective clock.
    public var predictionLedger: PredictionLedgerStatus? = nil
}

/// The prospective prediction ledger as Sector Ops should see it. Validation stays NOT_VALIDATED regardless of this.
public struct PredictionLedgerStatus: Codable, Equatable, Sendable {
    public var status: String
    public var startedAt: String
    public var lastObject: String?
    public var lastRecords: Int?
    public var warning: String?
    public var rulesVersion: String
    public var note: String
    /// 2026-10-13T18:53:14Z: first object `predictions/2026/10/13/185314Z-740761e4e50a.jsonl` (docs/brains/LAKE_BRAIN_PREDICTION_LEDGER.md).
    public static let startedAt = "2026-10-13T18:53:14Z"
    public static func make(status: String, lastObject: String?, lastRecords: Int, warning: String?) -> PredictionLedgerStatus {
        PredictionLedgerStatus(status: status, startedAt: startedAt, lastObject: lastObject, lastRecords: lastObject == nil ? nil : lastRecords,
                               warning: warning, rulesVersion: LakeBrainSpec.modelVersion,
                               note: "Prospective evidence only. Validation stays NOT_VALIDATED until pre-registered scoring of logged predictions supports a change.")
    }
}

public enum LakeBrainRunner {

    public static let jobId = "lake-brain"

    // MARK: per-lake compute

    static func liveHours(_ ref: LevelSeriesRef) -> Int { ref.provider == .tva ? 48 : 192 }

    static func evaluateLake(_ lake: DirectoryLake, feeds: LakeLevelFeeds, archive: LakeBrainArchive?,
                                    presence: LakePresenceIndex?, published: LakeLevelStateRecord?,
                                    previousProfile: LakeBrainProfileRecord?, options: LakeBrainRunOptions,
                                    now: Date) async -> LakeBrainLakeResult {
        var binding = LakeSourceBindings.binding(for: lake.id)
        // Candidate dry run: in-memory promotion only; nothing here is published (the job refuses --rtdb with it).
        let dryRunCandidate = options.includeCandidates && binding?.status == .candidate
        if dryRunCandidate { binding?.status = .reviewed }
        let gen = BrainPlatform.iso(now)
        var errors: [String] = []
        var state: LakeLevelStateRecord?
        var baseline: LakeLevelBaseline?
        var historyRows = 0
        var historyWritten = false
        var plan: LakeBrainPlanDecision?
        var lastMerged: [DailyLevel] = []
        var liveResults: [(ref: LevelSeriesRef, readings: [LevelObservation], error: String?)] = []

        if let binding, binding.status == .reviewed {
            let tz = TimeZone(identifier: binding.timeZone) ?? TimeZone(identifier: "UTC")!
            let p = LakeBrainPlanner.planState(lakeId: lake.id, published: published, bindingVersion: LakeSourceBindings.version,
                                               publishedBindingVersion: previousProfile?.sourceCapability.bindingVersion, now: now)
            plan = p
            if p.action == .publish || options.force {
                // Live
                for ref in binding.live {
                    let r = await feeds.recent(ref, hours: liveHours(ref), now: now)
                    liveResults.append((ref, r.observations, r.error))
                }
                var archivedHourly: [LevelObservation] = []
                for h in binding.history {
                    if case .sharedTVAArchive = h { archivedHourly += await feeds.archivedHourly(h, days: 8, now: now, timeZone: tz) }
                }
                // Guide for today
                let today = LakeLevelCalendar.dayString(now, timeZone: tz)
                let guide: LakeGuideForDay? = await binding.guide.asyncMap { await feeds.guide($0, day: today, timeZone: tz) } ?? nil
                // History: archive ∪ fresh operator daily → baseline
                var existing: [DailyLevel] = []
                if let archive, let d = try? await archive.read(LakeDailyHistory.path(lake.id)) { existing = LakeDailyHistory.decode(d) }
                var fresh: [DailyLevel] = []
                for h in binding.history {
                    switch h {
                    case .sharedTVAArchive: continue
                    case .tvaOperatingGuide:
                        if let d = await feeds.daily(h, since: nil, now: now, timeZone: tz) { fresh += d } else { errors.append("history: TVA operating guide unavailable") }
                    case .cwmsDaily, .usgsDaily, .riseDaily, .hadsDaily, .twdbDaily:
                        // Backfill (or an empty archive) pulls the whole record; otherwise the last 21 days.
                        let since: String? = (options.backfill || existing.isEmpty) ? nil
                            : existing.last.map { _ in LakeLevelCalendar.dayString(now.addingTimeInterval(-21 * 86_400), timeZone: tz) }
                        if let d = await feeds.daily(h, since: since, now: now, timeZone: tz) { fresh += d } else { errors.append("history: \(h.profileDescription) unavailable") }
                    }
                }
                let merged = LakeDailyHistory.merge(existing: existing, new: fresh)
                lastMerged = merged
                historyRows = merged.count
                if let archive, !merged.isEmpty, merged != existing {
                    do { try await archive.write(LakeDailyHistory.path(lake.id), LakeDailyHistory.encode(merged), contentType: "text/csv"); historyWritten = true }
                    catch { errors.append("history write: \(error)") }
                }
                let b = LakeBaselineBuilder.build(lakeId: lake.id, daily: merged, today: today, poolBasisIsFullPool: lake.poolBasis == .fullPool)
                baseline = b
                if let archive, b.status != .none, (try? await archive.read(LakeBaselineBuilder.path(b))) == nil {
                    do { try await archive.write(LakeBaselineBuilder.path(b), try BrainJSON.encode(b), contentType: "application/json") }
                    catch { errors.append("baseline write: \(error)") }
                }
                state = LakeLevelClassifier.evaluate(LakeLevelInputs(
                    lakeId: lake.id, binding: binding, capabilityIfUnbound: binding.capability,
                    fullPoolFt: lake.fullPoolFt, poolBasisIsFullPool: lake.poolBasis == .fullPool,
                    poolConfidenceLow: lake.poolConfidence == .low || lake.poolConfidence == nil,
                    live: liveResults, archivedHourly: archivedHourly, guide: guide, baseline: b,
                    now: now, processingVersion: options.processingVersion))
            } else {
                state = published
            }
        }

        // The baseline must come from the series the live level comes from: a history more than 15 ft off the live level is a
        // series / datum mismatch and would label the lake 'unusual' for the wrong reason.
        if let cur = state?.currentElevationFt, state?.kind == .observed, let off = historyLiveMismatch(history: lastMerged, current: cur, now: now, timeZone: binding.map { TimeZone(identifier: $0.timeZone) ?? .gmt } ?? .gmt) {
            let flag = String(format: "historyLiveMismatch:%+.1fft", off)
            var flags = state?.provenance.qualityFlags ?? []
            flags.append(flag)
            state?.provenance.qualityFlags = flags
            errors.append("history/live series mismatch: seeded history of the last year is \(String(format: "%+.1f", off)) ft from the live level")
        }
        if dryRunCandidate {
            var flags = state?.provenance.qualityFlags ?? []
            flags.append("dryRunCandidate")
            state?.provenance.qualityFlags = flags
        }
        let presenceRecords = presence?.resolveLakeSpecies(lake.id, updatedAt: gen) ?? []
        let profile = LakeBrainProfiles.build(lake: lake, binding: binding, state: state, baseline: baseline,
                                              previous: previousProfile, presence: presence, live: liveResults, now: now,
                                              archiveURI: archive?.uri, dryRunCandidate: dryRunCandidate)
        return LakeBrainLakeResult(lakeId: lake.id, plan: plan, state: state, profile: profile, presence: presenceRecords,
                                   baseline: baseline, historyRows: historyRows, historyWritten: historyWritten, errors: errors,
                                   dryRunCandidate: dryRunCandidate)
    }

    /// Median of the history of the last 365 days minus the live level, when it is more than 15 ft (and >= 30 days exist).
    static func historyLiveMismatch(history: [DailyLevel], current: Double, now: Date, timeZone: TimeZone) -> Double? {
        let cutoff = LakeLevelCalendar.dayString(now.addingTimeInterval(-365 * 86_400), timeZone: timeZone)
        let xs = history.filter { $0.date >= cutoff }.map(\.ft).sorted()
        guard xs.count >= 30 else { return nil }
        let med = xs.count % 2 == 1 ? xs[xs.count / 2] : (xs[xs.count / 2 - 1] + xs[xs.count / 2]) / 2
        return abs(med - current) > 15 ? med - current : nil
    }

    // MARK: fleet run

    static func health(_ lakes: [LakeBrainLakeResult], writeFailed: Bool) -> String {
        let reviewed = lakes.filter { LakeSourceBindings.reviewedBinding(for: $0.lakeId) != nil || $0.dryRunCandidate }
        if writeFailed || lakes.isEmpty { return "FAILED" }
        guard !reviewed.isEmpty else { return "HEALTHY" }
        let unavailable = reviewed.filter { $0.state == nil || $0.state?.kind == .unavailable }.count
        let degraded = reviewed.filter { $0.state?.freshness.stale ?? true || ($0.state?.provenance.qualityFlags?.contains { $0.hasPrefix("fallbackSource") } ?? false) }.count
        if Double(unavailable) / Double(reviewed.count) > 0.25 { return "DEGRADED" }
        if degraded > 0 || unavailable > 0 { return "WARNING" }
        return "HEALTHY"
    }

    public static func run(store: BrainStore?, feeds: LakeLevelFeeds, archive: LakeBrainArchive?,
                           presenceArchive: LakeBrainArchive?, options: LakeBrainRunOptions = .init(),
                           now: Date = Date()) async -> LakeBrainRunResult {
        let t0 = Date()
        var result = LakeBrainRunResult()
        result.ledgerStatus = options.ledgerEnabled ? "enabled" : "disabled"
        let width = BrainPlatform.clampConcurrency(options.concurrency)
        result.concurrency = width
        let ids = LakeDirectory.all.map(\.id)
        let collisions = BrainPlatform.keyCollisions(ids)
        guard collisions.isEmpty else {
            result.health = "FAILED"; result.writeError = "lake key collision: \(collisions.keys.sorted())"
            return result
        }
        let directory = Set(ids)
        for b in LakeSourceBindings.all where !directory.contains(b.lakeId) {
            result.health = "FAILED"; result.writeError = "binding for non-directory lake \(b.lakeId)"
            return result
        }

        var lakes: [DirectoryLake]
        switch options.scope {
        case .pilots:
            // The reviewed lakes; a candidate dry run adds the candidates. A normal run never touches a CANDIDATE.
            lakes = LakeDirectory.all.filter { options.includeCandidates ? LakeSourceBindings.binding(for: $0.id) != nil
                                                                         : LakeSourceBindings.reviewedBinding(for: $0.id) != nil }
        case .fleet: lakes = LakeDirectory.all
        }
        if let only = options.lakeIds { lakes = lakes.filter { only.contains($0.id) } }

        var presence: LakePresenceIndex?
        if let pa = presenceArchive {
            do { presence = try await LakePresenceIndex.load(from: pa, knownLakeIds: directory) }
            catch { result.presenceError = "\(error)" }
        }

        let previousRegistry: LakeBrainRegistryEntry? = await {
            guard let store, let d = try? await store.get("brains/\(LakeBrainSpec.brainId)") else { return nil }
            return try? JSONDecoder().decode(LakeBrainRegistryEntry.self, from: d)
        }()

        let flight = LakeBrainSingleFlight<LakeBrainLakeResult>()
        let presenceIndex = presence
        var out: [LakeBrainLakeResult] = []
        var i = 0
        while i < lakes.count {
            let batch = lakes[i..<min(i + width, lakes.count)]
            await withTaskGroup(of: LakeBrainLakeResult.self) { g in
                for lake in batch {
                    g.addTask {
                        await flight.run(lake.id) {
                            let k = BrainPlatform.lakeKey(lake.id)
                            var published: LakeLevelStateRecord?
                            var prevProfile: LakeBrainProfileRecord?
                            if let store {
                                published = (try? await store.get("lakes/\(k)/states/\(LakeBrainSpec.slot)")).flatMap { try? JSONDecoder().decode(LakeLevelStateRecord.self, from: $0) }
                                prevProfile = (try? await store.get("lakes/\(k)/brain")).flatMap { try? JSONDecoder().decode(LakeBrainProfileRecord.self, from: $0) }
                            }
                            return await evaluateLake(lake, feeds: feeds, archive: archive, presence: presenceIndex, published: published,
                                                      previousProfile: prevProfile, options: options, now: now)
                        }
                    }
                }
                for await x in g { out.append(x) }
            }
            i += width
        }
        out.sort { $0.lakeId < $1.lakeId }
        result.lakes = out
        result.archiveErrors = out.flatMap { r in r.errors.map { "\(r.lakeId): \($0)" } }
        result.health = health(out, writeFailed: false)

        guard let store else { result.durationMs = Int(Date().timeIntervalSince(t0) * 1000); return result }

        do {
            for r in out { try await store.update(try lakePaths(r, presence: presence)) }
            let finished = Date()
            result.durationMs = Int(finished.timeIntervalSince(t0) * 1000)
            guard options.lakeIds == nil else { await appendLedger(&result, lakes: lakes, store: store, archive: archive, options: options, now: now); return result }
            let registry = registryEntry(result: result, options: options, now: finished, presence: presence)
            var tail: [String: Data] = [
                "brains/\(LakeBrainSpec.brainId)": try BrainJSON.encode(registry),
                "validation/\(LakeBrainSpec.brainId)": try BrainJSON.encode(validationSummary(result: result, now: finished)),
                "health/brains/\(LakeBrainSpec.brainId)": try BrainJSON.encode(BrainHealthRecord(
                    status: result.health, lastRun: BrainPlatform.iso(t0), lastSuccess: BrainPlatform.iso(finished),
                    durationMs: result.durationMs, staleLakeCount: out.filter { $0.state?.freshness.stale == true }.count,
                    errorCount: result.archiveErrors.count, latestError: result.archiveErrors.first ?? result.presenceError,
                    deployedVersion: options.processingVersion)),
                "health/jobs/\(jobId)": try BrainJSON.encode(BrainJobHealth(
                    displayName: "Lake Brain", kind: "manual-run", schedule: nil, status: result.health,
                    lastRun: BrainPlatform.iso(t0), lastSuccess: BrainPlatform.iso(finished), durationMs: result.durationMs,
                    latestError: result.archiveErrors.first, running: false)),
            ]
            for (id, rec) in sourceRecords(out, now: finished) {
                tail["sources/\(id)"] = try BrainJSON.encode(rec.0)
                tail["health/sources/\(id)"] = try BrainJSON.encode(rec.1)
            }
            for e in activity(previous: previousRegistry, current: registry, now: finished) { tail["activity/\(e.id)"] = try BrainJSON.encode(e) }
            try await store.update(tail)
            _ = try? await BrainActivity.prune(store: store, brainId: LakeBrainSpec.brainId, now: finished)
            await appendLedger(&result, lakes: lakes, store: store, archive: archive, options: options, now: now)
        } catch {
            result.writeError = "\(error)"; result.health = "FAILED"
            let at = BrainPlatform.iso(Date())
            try? await store.update([
                "health/brains/\(LakeBrainSpec.brainId)/status": try BrainJSON.encode("FAILED"),
                "health/brains/\(LakeBrainSpec.brainId)/latestError": try BrainJSON.encode(result.writeError!),
                "health/brains/\(LakeBrainSpec.brainId)/lastRun": try BrainJSON.encode(at),
            ])
        }
        return result
    }

    // MARK: prediction ledger

    /// After the RTDB writes succeeded: append the run's prediction object. Cannot throw and cannot change `ok`/`health`:
    /// a failure is only `ledgerWarning` (and a line in `archiveErrors` so the job prints it).
    static func appendLedger(_ result: inout LakeBrainRunResult, lakes: [DirectoryLake], store: BrainStore,
                             archive: LakeBrainArchive?, options: LakeBrainRunOptions, now: Date) async {
        guard options.ledgerEnabled else { return }
        let target: LakeBrainArchive?
        if let explicit = options.ledgerArchive { target = explicit }
        else if let local = store as? LocalDirectoryStore { target = LocalLakeBrainArchive(directory: local.dir.appendingPathComponent("_ledger").path) }
        else if let rt = store as? ReadThroughDryRunStore { target = LocalLakeBrainArchive(directory: rt.writer.dir.appendingPathComponent("_ledger").path) }
        else { target = archive }
        guard let target else { return }
        var pool: [String: (Bool?, String?)] = [:]
        for l in lakes { pool[l.id] = (l.poolBasis.map { $0 == .fullPool }, l.poolBasis?.rawValue) }
        let runId = options.runId ?? String(UUID().uuidString.lowercased().replacingOccurrences(of: "-", with: "").prefix(12))
        let o = await LakePredictionLedger.append(results: result.lakes, regulated: pool, archive: target, runId: runId, now: now)
        result.ledgerObject = o.path; result.ledgerRecords = o.records; result.ledgerWarning = o.warning
        if let w = o.warning { result.archiveErrors.append(w) }
    }

    // MARK: paths

    struct FleetSlot: Codable, Equatable {
        var issueCount: Int
        var lastUpdatedAt: String
        var readiness: String
        var stale: Bool
        var stateType: String
        var levelState: String?
        var trendState: String?
        var sourceCapability: String
    }

    static func lakePaths(_ r: LakeBrainLakeResult, presence: LakePresenceIndex?) throws -> [String: Data] {
        let k = BrainPlatform.lakeKey(r.lakeId)
        let readiness = r.profile.readiness[LakeBrainSpec.slot] ?? LakeBrainReadiness.discovered.rawValue
        var p: [String: Data] = [
            "lakes/\(k)/brain": try BrainJSON.encode(r.profile),
            "lakeFleet/\(k)/lakeId": try BrainJSON.encode(r.lakeId),
            "lakeFleet/\(k)/readiness/\(LakeBrainSpec.slot)": try BrainJSON.encode(readiness),
            "lakeFleet/\(k)/modelVersions/\(LakeBrainSpec.slot)": try BrainJSON.encode(LakeBrainSpec.modelVersion),
            "lakeFleet/\(k)/slots/\(LakeBrainSpec.slot)": try BrainJSON.encode(FleetSlot(
                issueCount: r.profile.activeIssues?.count ?? 0, lastUpdatedAt: r.profile.updatedAt, readiness: readiness,
                stale: r.state?.freshness.stale ?? false, stateType: r.state?.kind.rawValue ?? "NONE",
                levelState: r.state?.levelState.rawValue, trendState: r.state?.trendState.rawValue,
                sourceCapability: r.profile.sourceCapability.level.rawValue)),
        ]
        if let river = r.profile.identity.riverSystem { p["lakeFleet/\(k)/riverSystem"] = try BrainJSON.encode(river) }
        if let s = r.state {
            let sj = try BrainJSON.encode(s)
            p["lakes/\(k)/states/\(LakeBrainSpec.slot)"] = sj
            p["snapshots/\(k)/latest/lakeId"] = try BrainJSON.encode(r.lakeId)
            p["snapshots/\(k)/latest/\(LakeBrainSpec.snapshotField)"] = sj
            p["snapshots/\(k)/latest/brainVersions/\(LakeBrainSpec.brainId)"] = try BrainJSON.encode(LakeBrainSpec.brainVersion)
        }
        // Presence replaces the lake's whole presence node (Lake-Brain-owned), so dropped rows disappear.
        if presence != nil {
            var node: [String: LakeSpeciesPresenceRecord] = [:]
            for x in r.presence { node[x.speciesId] = x }
            p["lakes/\(k)/speciesPresence"] = node.isEmpty ? Data("null".utf8) : try BrainJSON.encode(node)
        }
        return p
    }

    // MARK: registry / validation / sources / activity

    static let readinessDefinitions: [String: String] = [
        "DISCOVERED": "Directory lake; no reviewed water-level source binding yet. Profile only.",
        "PROFILED": "Reviewed binding says no usable level source.",
        "CALIBRATION": "Current level from a reviewed source; history < 5 complete years or no operator guide, so some classifications are withheld.",
        "BETA": "Current level from a reviewed source, operator guide and ≥ 5 complete years of history: every classification computed. Not yet validated.",
        "DEGRADED": "Reviewed source, but the current reading is stale or unavailable (last known value kept and flagged).",
        "VALIDATED": "Not used until classification checks exist.",
        "PRODUCTION": "Not used.",
    ]

    static let stateKindDefinitions: [String: String] = [
        "OBSERVED": "Operator pool elevation or an on-lake surface-elevation gauge.",
        "PROXY": "A nearby gage height or river stage. Trend only: never a level state, percentile or pool difference.",
        "UNAVAILABLE": "No reading from any reviewed source.",
    ]

    /// Fleet-wide binding gate, independent of what this run evaluated: how many directory lakes have a REVIEWED binding (published)
    /// and how many only a CANDIDATE (machine-verified, awaiting human acceptance, never published). `bindingStatus` above counts only
    /// the lakes this run published, so on its own it hides the candidate fleet from Sector Ops.
    static func fleetBindingBreakdown() -> [String: Int] {
        var m: [String: Int] = [:]
        for b in LakeSourceBindings.all { m[b.status.rawValue, default: 0] += 1 }
        return m
    }

    static func registryEntry(result: LakeBrainRunResult, options: LakeBrainRunOptions, now: Date,
                              presence: LakePresenceIndex?) -> LakeBrainRegistryEntry {
        var readiness: [String: Int] = [:], cap: [String: Int] = [:], base: [String: Int] = [:]
        var level: [String: Int] = [:], trend: [String: Int] = [:], hist: [String: Int] = [:], binding: [String: Int] = [:]
        for r in result.lakes {
            readiness[r.profile.readiness[LakeBrainSpec.slot] ?? "DISCOVERED", default: 0] += 1
            cap[r.profile.sourceCapability.level.rawValue, default: 0] += 1
            binding[r.profile.sourceCapability.bindingStatus.rawValue, default: 0] += 1
            if let s = r.state {
                base[s.baselineStatus.rawValue, default: 0] += 1
                level[s.levelState.rawValue, default: 0] += 1
                trend[s.trendState.rawValue, default: 0] += 1
                hist[s.historicalState.rawValue, default: 0] += 1
            }
        }
        var entry = LakeBrainRegistryEntry(
            brainId: LakeBrainSpec.brainId, displayName: LakeBrainSpec.displayName, domain: "lake",
            question: "What does Sector know about this particular lake: its water level now, against its own history and operator guide, and which fish are recorded there?",
            version: LakeBrainSpec.brainVersion, schemaVersion: BrainPlatform.schemaVersion, enabled: true,
            health: result.health, status: LakeBrainReadiness.calibration.rawValue,
            supportedLakeCount: LakeSourceBindings.reviewed.count, directoryLakeCount: LakeDirectory.all.count,
            readinessCounts: readiness, staleLakeCount: result.lakes.filter { $0.state?.freshness.stale == true }.count,
            staleAfterHours: LakeBrainSpec.staleAfterHours, lastSuccessfulRun: BrainPlatform.iso(now), lastError: nil,
            deploymentVersion: options.processingVersion, modelVersion: LakeBrainSpec.modelVersion,
            baselineMethod: LakeBrainSpec.baselineMethod, bindingVersion: LakeSourceBindings.version,
            breakdowns: ["readiness": readiness, "sourceCapability": cap, "bindingStatus": binding, "fleetBindingStatus": fleetBindingBreakdown(), "baselineStatus": base,
                         "levelState": level, "trendState": trend, "historicalState": hist],
            versions: [.init(version: "\(LakeBrainSpec.brainVersion) · \(LakeBrainSpec.modelVersion)", date: "2026-10-13",
                             note: "Rules v2 (pre-registered): history tiers gate VERY_UNUSUAL (≥ 15 years), trend from the 72 h mean (floors 0.10 / 0.05 ft), RAPID = max(seasonal p95 |Δ24h|, 0.25 ft). baselineStatus (≥ 5 years SUFFICIENT) and NOT_VALIDATED unchanged.",
                             status: "CURRENT")],
            readinessDefinitions: readinessDefinitions, stateKindDefinitions: stateKindDefinitions,
            healthRule: "FAILED: write failed or no lakes. DEGRADED: > 25 % of reviewed lakes unavailable. WARNING: any reviewed lake stale, unavailable or on a fallback source. HEALTHY otherwise.",
            orchestration: .current,
            fleetScope: options.scope.rawValue + (presence == nil ? " (no presence bundle)" : ""))
        entry.platform = BrainPlatformRef.current
        entry.predictionLedger = PredictionLedgerStatus.make(status: result.ledgerStatus, lastObject: result.ledgerObject,
                                                              lastRecords: result.ledgerRecords, warning: result.ledgerWarning)
        entry.stalenessModel = "TIME"
        entry.dependsOn = []
        entry.schedule = ["cadence": "manual (on demand; no Lake-specific cron — the Orchestrator will own cadence)", "running": "false"]
        return entry
    }

    struct ValidationSummary: Codable, Equatable {
        var brainId: String
        var modelVersion: String
        var validationVersion: String
        var status: String
        var lastRunAt: String
        var holdoutType: String
        var sampleCount: Int
        var lakeCount: Int
        var notes: [String]
    }

    static func validationSummary(result: LakeBrainRunResult, now: Date) -> ValidationSummary {
        ValidationSummary(brainId: LakeBrainSpec.brainId, modelVersion: LakeBrainSpec.modelVersion, validationVersion: "none",
                          status: "NOT_VALIDATED", lastRunAt: BrainPlatform.iso(now), holdoutType: "none", sampleCount: 0,
                          lakeCount: result.lakes.filter { $0.state != nil }.count,
                          notes: ["No classification checks exist yet; readiness is capped at BETA.",
                                  "Method cross-check (not a validation): Lake Hartwell's computed seasonal band is compared with the CWMS-published percentile series in the pilot report."])
    }

    static func sourceRecords(_ lakes: [LakeBrainLakeResult], now: Date) -> [String: (BrainDataSourceStatus, BrainSourceHealth)] {
        let at = BrainPlatform.iso(now)
        let defs: [(id: String, provider: LevelSeriesRef.Provider, name: String, type: String, provides: String)] = [
            ("tva-restapi", .tva, "TVA", "reservoir-elevation", "hourly observed reservoir elevation + 365-day operating guide (guide curve, operating zone)"),
            ("usace-cwms-pool", .cwms, "USACE CWMS", "reservoir-elevation", "pool elevation (hourly + daily since 1960 at Hartwell), guide curve, drought levels"),
            ("usgs-nwis-lake-elevation", .usgs, "USGS", "lake-surface-elevation", "on-lake surface elevation (00062/62614)"),
            ("usace-access2water", .a2w, "USACE Access2Water", "reservoir-elevation", "latest pool elevation + 24 h change and operator levels (one listing per district)"),
            ("usbr-rise", .rise, "USBR RISE", "reservoir-elevation", "daily lake/reservoir elevation (about 48 h latency; 0.0 placeholders dropped)"),
            ("nws-nwps", .nwps, "NWS NWPS", "lake-surface-elevation", "hourly pool elevation of NWS gauges (HP pe codes)"),
            ("twdb-water-data-texas", .twdb, "TWDB Water Data for Texas", "reservoir-elevation", "estimated daily average reservoir elevation of Texas lakes (a relay of USGS / USACE / USBR / IBWC / LCRA gauges; the file declares its datum)"),
        ]
        var out: [String: (BrainDataSourceStatus, BrainSourceHealth)] = [:]
        for d in defs {
            var used = 0, failed = 0, stale = 0
            var latest: String?
            for r in lakes {
                guard let b = r.dryRunCandidate ? LakeSourceBindings.binding(for: r.lakeId) : LakeSourceBindings.reviewedBinding(for: r.lakeId) else { continue }
                for ref in b.live where ref.provider == d.provider {
                    used += 1
                    let flags = r.state?.provenance.qualityFlags ?? []
                    if flags.contains("sourceError:\(ref.sourceId)") { failed += 1 }
                    if flags.contains(where: { $0.hasPrefix("primarySourceStale:\(ref.sourceId)") || $0 == "sourceStale:\(ref.sourceId)" }) { stale += 1 }
                    if let s = r.state?.provenance.sources?.first, s.sourceId == ref.sourceId, let o = s.lastObservationAt { latest = max(latest ?? "", o) }
                }
            }
            guard used > 0 else { continue }
            let h = failed == used ? "FAILED" : (failed > 0 || stale > 0) ? "WARNING" : "HEALTHY"
            out[d.id] = (BrainDataSourceStatus(sourceId: d.id, provider: d.name, type: d.type, ownerBrainId: LakeBrainSpec.brainId, brains: [LakeBrainSpec.brainId: true],
                                               lakeCount: used, health: h, lastFetchAt: at, latestObservationAt: latest,
                                               staleThresholdHours: 3, failures24h: nil, failuresLastRun: failed, provides: d.provides,
                                               notes: "Written by the Lake Brain run. \(stale) bound series stale at run time."),
                         BrainSourceHealth(status: h, lastFetchAt: at, failures24h: nil, failuresLastRun: failed))
        }
        return out
    }

    static func activity(previous: LakeBrainRegistryEntry?, current: LakeBrainRegistryEntry, now: Date) -> [BrainActivityEvent] {
        var out: [BrainActivityEvent] = []
        func ev(_ kind: String, _ title: String, _ sev: String) {
            let id = BrainActivity.eventId(at: now, brainId: LakeBrainSpec.brainId, n: out.count)   // contract §7
            out.append(BrainActivityEvent(id: id, at: BrainPlatform.iso(now), kind: kind, title: title,
                                          brainId: LakeBrainSpec.brainId, lakeId: nil, severity: sev))
        }
        guard let p = previous else {
            ev("brain.registered", "Lake Brain registered (v\(current.version), \(current.supportedLakeCount) pilot lakes)", "info")
            return out
        }
        if p.version != current.version || p.modelVersion != current.modelVersion {
            ev("brain.version", "Lake Brain \(p.version)/\(p.modelVersion) → \(current.version)/\(current.modelVersion)", "info")
        }
        if p.readinessCounts != current.readinessCounts {
            ev("readiness.changed", "Lake Brain readiness: \((current.readinessCounts ?? [:]).sorted { $0.key < $1.key }.map { "\($0.key) \($0.value)" }.joined(separator: ", "))", "info")
        }
        if p.health != current.health {
            ev("health.changed", "Lake Brain health \(p.health) → \(current.health)",
               current.health == "HEALTHY" ? "success" : current.health == "FAILED" ? "critical" : "warning")
        }
        return out
    }
}

extension Optional {
    func asyncMap<U>(_ f: (Wrapped) async -> U) async -> U? {
        guard let x = self else { return nil }
        return await f(x)
    }
}
