//
//  LakeBrainOrchestration.swift
//  Sector — Lake Brain: what it depends on and when a run is warranted
//
//  No scheduler lives here (there is no Lake-specific cron). The future Sector
//  Brain Orchestrator owns scheduling, retries and dependency ordering; this
//  answers the brain-side questions it will ask, like the Biological Brain's
//  orchestration.py: what are my inputs, what makes my state stale, and given
//  what is published now, is a run warranted?
//

import Foundation

public struct LakeBrainDescriptor: Codable, Equatable, Sendable {
    public struct Component: Codable, Equatable, Sendable {
        public var status: String
        public var inputs: [String]
        public var staleness: String
        public var recomputeWhen: [String]
    }
    public var brainId: String
    public var schedule: String
    public var components: [String: Component]

    public static let current = LakeBrainDescriptor(
        brainId: LakeBrainSpec.brainId,
        schedule: "none: run on demand, or when the future Sector Brain Orchestrator decides (no Lake-specific cron)",
        components: [
            "lakeState": .init(
                status: "ACTIVE (pilot lakes)",
                inputs: ["reviewed source bindings (\(LakeSourceBindings.version))", "TVA RestApi observed-data-48-hours + operating-guide",
                         "USACE CWMS timeseries (named series)", "USGS NWIS IV (named site/parameter)",
                         "gs://sector-water-temp-archive/water-temp/tva (shared, read-only)", "gs://sector-lake-brain/history, baselines"],
                staleness: "time-based: stale when the source is more than two cadences past due, or the published state is older than \(Int(LakeBrainSpec.staleAfterHours)) h",
                recomputeWhen: ["now ≥ published freshness.nextCheckAt", "published state is stale", "brain or rules version changed",
                                "binding version changed", "nothing published yet"]),
            "lakeProfile": .init(
                status: "ACTIVE",
                inputs: ["Engine directory (GET /lakes) — referenced, not copied", "reviewed source bindings", "baseline status", "presence researchVersion"],
                staleness: "version-based: profileHash changes",
                recomputeWhen: ["profileHash differs from the published one"]),
            "speciesPresence": .init(
                status: "ACTIVE",
                inputs: ["gs://sector-lake-brain/presence/latest.json (private)"],
                staleness: "version-based: researchVersion / fingerprint; never by age",
                recomputeWhen: ["presence researchVersion or fingerprint changed"]),
        ])
}

public struct LakeBrainPlanDecision: Codable, Equatable, Sendable {
    public enum Action: String, Codable, Sendable { case publish = "PUBLISH", skip = "SKIP" }
    public var lakeId: String
    public var component: String
    public var action: Action
    public var reasons: [String]
}

public enum LakeBrainPlanner {
    /// Pure: should the lake's state be recomputed now?
    public static func planState(lakeId: String, published: LakeLevelStateRecord?, bindingVersion: String,
                                 publishedBindingVersion: String?, now: Date) -> LakeBrainPlanDecision {
        var reasons: [String] = []
        if let p = published {
            if p.provenance.brainVersion != LakeBrainSpec.brainVersion { reasons.append("brain version \(p.provenance.brainVersion ?? "?") → \(LakeBrainSpec.brainVersion)") }
            if p.provenance.modelVersion != LakeBrainSpec.modelVersion { reasons.append("rules \(p.provenance.modelVersion ?? "?") → \(LakeBrainSpec.modelVersion)") }
            if let pb = publishedBindingVersion, pb != bindingVersion { reasons.append("binding \(pb) → \(bindingVersion)") }
            if p.freshness.stale { reasons.append("published state is stale") }
            let f = ISO8601DateFormatter()
            if let next = f.date(from: p.freshness.nextCheckAt), now >= next { reasons.append("nextCheckAt \(p.freshness.nextCheckAt) reached") }
            if let gen = f.date(from: p.freshness.generatedAt), now.timeIntervalSince(gen) > LakeBrainSpec.staleAfterHours * 3600 {
                reasons.append("published state older than \(Int(LakeBrainSpec.staleAfterHours)) h")
            }
        } else {
            reasons.append("nothing published yet")
        }
        return .init(lakeId: lakeId, component: "lakeState", action: reasons.isEmpty ? .skip : .publish,
                     reasons: reasons.isEmpty ? ["published state is current; next check \(published?.freshness.nextCheckAt ?? "?")"] : reasons)
    }
}

/// Deduplicates concurrent refreshes of the same lake inside one process: the
/// second caller awaits the first caller's result instead of fetching again.
public actor LakeBrainSingleFlight<Value: Sendable> {
    private var inflight: [String: Task<Value, Never>] = [:]
    public private(set) var joined = 0
    public init() {}

    public func run(_ key: String, _ op: @escaping @Sendable () async -> Value) async -> Value {
        if let t = inflight[key] { joined += 1; return await t.value }
        let t = Task { await op() }
        inflight[key] = t
        let v = await t.value
        inflight[key] = nil
        return v
    }
}
