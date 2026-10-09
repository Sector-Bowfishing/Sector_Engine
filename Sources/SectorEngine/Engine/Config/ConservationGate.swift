//
//  ConservationGate.swift
//  Sector — Sector Intelligence, Phase 5A (guardrails)
//
//  L7 — THE CONSERVATION GATE, engine side.
//
//  Decides, for species × jurisdiction × purpose, whether TARGETING output may
//  name a species. It is separate from biology (SpawnFactor still computes
//  every species' spawn state), presence (SpawnSpecies.present) and legality
//  (SpeciesLegality): those are siblings, not the gate.
//
//  Mirrors the iOS gate (Sector/FishIntel/Policy/ConservationGate.swift).
//  A freshwater species with NO ratified policy (bowfin, tilapia, freshwater
//  drum, gizzard shad, striped mullet — and the already-excluded channel
//  catfish, paddlefish, American shad) FAILS CLOSED: `policyNotAssessed`,
//  internally known, public targeting suppressed. Phase 5A closeout decision.
//
//  Applied at the CANDIDATE stage of SpawnFactor: a gated species never
//  becomes the spawn leader, so it can't drive naming, the spawn regime, the
//  spawn boost, "Spawn's on" alerts, or any night of the outlook.
//

import Foundation

public enum GateOutcome: String, Codable, Comparable, Sendable {
    case allow, conditional, suppress, refuse

    private var rank: Int {
        switch self { case .allow: return 0; case .conditional: return 1
                      case .suppress: return 2; case .refuse: return 3 }
    }
    public static func < (a: Self, b: Self) -> Bool { a.rank < b.rank }

    public var permitsTargeting: Bool { self == .allow || self == .conditional }
}

public enum GateReason: String, Codable, CaseIterable, Sendable {
    case conservationSensitive, identityRisk, protectedSpecies, conservationRank
    case spawningAggregation, trophyTargetingNotPermitted, recruitmentLimited
    case presenceUnconfirmed, policyNotAssessed
}

public enum GatePurpose: String, Codable, Sendable {
    /// "Spawning now" / spawn species naming in the Conditions Score.
    case spawnTiming
    /// Trophy / size-class targeting.
    case trophyTargeting
    /// Ranking spawning runs or aggregations.
    case aggregationTargeting
    /// Informational — never blocked.
    case identification, regulations, presence, education, reporting, conservation

    var isTargeting: Bool {
        switch self {
        case .spawnTiming, .trophyTargeting, .aggregationTargeting: return true
        default: return false
        }
    }
}

public enum TargetingStance: String, Codable, Sendable { case normal, conditional, suppress, refuse }

public struct JurisdictionRule: Equatable, Sendable {
    public let outcome: GateOutcome        // .suppress or .refuse
    public let reasons: [GateReason]
}

public struct SpeciesPolicy: Equatable, Sendable {
    public let speciesId: String
    public let stance: TargetingStance
    public let trophyTargetingAllowed: Bool
    public let aggregationTargetingAllowed: Bool
    public let publicSpawnTimingAllowed: Bool
    public let isNative: Bool
    public let jurisdictions: [String: JurisdictionRule]
    public let standingReasons: [GateReason]

    init(_ id: String, stance: TargetingStance, spawnTiming: Bool = false,
         trophy: Bool = false, aggregation: Bool = false, native: Bool,
         jurisdictions: [String: JurisdictionRule] = [:], standing: [GateReason] = []) {
        speciesId = id; self.stance = stance; publicSpawnTimingAllowed = spawnTiming
        trophyTargetingAllowed = trophy; aggregationTargetingAllowed = aggregation
        isNative = native; self.jurisdictions = jurisdictions; standingReasons = standing
    }
}

public struct GateDecision: Equatable, Sendable {
    public let speciesId: String
    public let outcome: GateOutcome
    public let reasons: [GateReason]
    /// Biology is still computed and may be used internally (warnings,
    /// closures, suppression timing) even when public targeting is off.
    public let internallyKnown: Bool

    public var publicTargetingAllowed: Bool { outcome.permitsTargeting }
}

/// The ratified per-species policy (Phases 2–4). Only these species.
public enum SpeciesPolicyRegistry {

    public static func policy(_ id: String) -> SpeciesPolicy? { byId[id] }

    static let byId: [String: SpeciesPolicy] =
        Dictionary(uniqueKeysWithValues: all.map { ($0.speciesId, $0) })

    private static let rank = JurisdictionRule(outcome: .suppress, reasons: [.conservationRank])
    private static let extirpated = JurisdictionRule(outcome: .suppress,
                                                     reasons: [.conservationRank, .presenceUnconfirmed])
    private static let protected = JurisdictionRule(outcome: .suppress, reasons: [.protectedSpecies])

    public static let all: [SpeciesPolicy] = [
        SpeciesPolicy("common_carp", stance: .normal, spawnTiming: true, native: false),
        SpeciesPolicy("grass_carp", stance: .conditional, spawnTiming: true, native: false,
                      jurisdictions: ["FL": protected, "SC": protected, "TX": protected]),
        SpeciesPolicy("silver_carp", stance: .normal, spawnTiming: true, native: false,
                      standing: [.identityRisk]),
        SpeciesPolicy("bighead_carp", stance: .normal, spawnTiming: true, native: false,
                      standing: [.identityRisk]),
        SpeciesPolicy("black_carp", stance: .suppress, native: false, standing: [.identityRisk]),

        SpeciesPolicy("smallmouth_buffalo", stance: .conditional, native: true,
                      jurisdictions: ["NC": rank], standing: [.identityRisk]),
        SpeciesPolicy("bigmouth_buffalo", stance: .suppress, native: true,
                      standing: [.conservationSensitive, .recruitmentLimited]),
        SpeciesPolicy("black_buffalo", stance: .refuse, native: true,
                      standing: [.protectedSpecies, .identityRisk]),

        SpeciesPolicy("spotted_gar", stance: .conditional, spawnTiming: true, native: true,
                      jurisdictions: ["KS": rank, "OH": rank, "PA": rank, "IL": rank, "MI": rank,
                                      "NM": extirpated, "ON": protected]),
        SpeciesPolicy("longnose_gar", stance: .conditional, spawnTiming: true, native: true,
                      jurisdictions: ["NM": rank, "SD": rank, "NJ": rank]),
        SpeciesPolicy("shortnose_gar", stance: .suppress, native: true,
                      jurisdictions: ["AL": extirpated, "NY": extirpated, "PA": extirpated, "OH": rank],
                      standing: [.identityRisk]),
        SpeciesPolicy("alligator_gar", stance: .refuse, native: true,
                      standing: [.protectedSpecies, .recruitmentLimited, .identityRisk]),
    ]
}

public enum ConservationGate {

    /// Deterministic: same inputs → same decision, reasons in a stable order.
    public static func evaluate(speciesId: String, purpose: GatePurpose,
                                jurisdictions: [String]) -> GateDecision {
        func decide(_ o: GateOutcome, _ r: [GateReason]) -> GateDecision {
            var seen = Set<GateReason>()
            return GateDecision(speciesId: speciesId, outcome: o,
                                reasons: r.filter { seen.insert($0).inserted },
                                internallyKnown: true)
        }

        guard purpose.isTargeting else { return decide(.allow, []) }

        // Fail closed: a species with no ratified policy is internally known
        // (its biology still runs) but never publicly targeted.
        guard let p = SpeciesPolicyRegistry.policy(speciesId) else {
            return decide(.suppress, [.policyNotAssessed])
        }

        var outcome: GateOutcome
        switch p.stance {
        case .normal: outcome = .allow
        case .conditional: outcome = .conditional
        case .suppress: outcome = .suppress
        case .refuse: outcome = .refuse
        }
        var reasons = p.standingReasons

        // Jurisdiction can only tighten.
        for j in jurisdictions {
            guard let rule = p.jurisdictions[j.uppercased()] else { continue }
            reasons += rule.reasons
            outcome = max(outcome, rule.outcome)
        }

        switch purpose {
        case .trophyTargeting where !p.trophyTargetingAllowed:
            reasons.append(.trophyTargetingNotPermitted); outcome = .refuse
        case .aggregationTargeting where !p.aggregationTargetingAllowed:
            reasons.append(.spawningAggregation); outcome = max(outcome, .suppress)
        case .spawnTiming where !p.publicSpawnTimingAllowed:
            reasons.append(.spawningAggregation); outcome = max(outcome, .suppress)
        default: break
        }

        if p.isNative && (p.stance == .refuse || p.stance == .suppress) {
            reasons.append(.conservationSensitive)
        }
        return decide(outcome, reasons)
    }

    /// May the Conditions Score name this species' spawn here?
    public static func permitsSpawnNaming(_ species: SpawnSpecies, jurisdictions: [String]) -> Bool {
        evaluate(speciesId: species.id, purpose: .spawnTiming,
                 jurisdictions: jurisdictions).publicTargetingAllowed
    }
}
