//
//  ConditionsResult.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  The aggregator's output: the final score + band, the regime that shaped it,
//  a confidence signal, the per-factor breakdown (with the *active* weight that
//  varies by regime), any active gate caps, the "top reasons", and the
//  "where to look" cards. Pure value type — the UI renders it. §2.
//

import Foundation

/// One row in the breakdown sheet.
public struct FactorBreakdown: Equatable, Sendable {
    public let key: FactorKey
    public let score: Int          // 0…100 sub-score
    public let weightPct: Int      // active (renormalized) weight, %
    public let label: String       // human value, e.g. "0.6 ft viz"
    public let why: String
    /// Signed points this factor adds to the `baseline` (50) — `weight × (score −
    /// 50)`. The breakdown reconciles: baseline + Σ contribution ≈ score. This is
    /// what "did tonight" instead of static weight, so clients don't re-derive it.
    public let contribution: Double
}

/// A factor that isn't in play tonight (e.g. spawn out of season) — excluded from
/// scoring and renormalization, but surfaced so the UI can explain the dormancy.
public struct DormantFactor: Equatable, Sendable {
    public let key: FactorKey
    public let label: String       // e.g. "Out of season"
    public let reason: String      // e.g. "No run — carp spawn Apr–Jun"
}

/// An active veto/cap and why it fired.
public struct GateHit: Equatable, Sendable {
    public let reason: String
    public let cap: Int
}

/// A "where to look" card. `kind` lets the UI pick an icon/tint; the engine
/// stays framework-free.
public struct WhereToLookCard: Equatable, Sendable {
    public enum Kind: String, Equatable, Sendable { case spawn, current, wind, level, clarity, darkness, temp }
    public let kind: Kind
    public let title: String
    public let body: String
}

public struct ConditionsResult: Equatable, Sendable {
    public let score: Int
    public let band: ConditionsBand
    public let regime: ConditionsRegime

    public let confidence: Int
    public let confidenceBand: ConfidenceBand

    public let factors: [FactorBreakdown]
    public let gates: [GateHit]
    public let topReasons: [String]

    public let whereToLook: [WhereToLookCard]
    public let closingLine: String

    /// The leading spawn species (for copy/targeting), if any.
    public let spawnSpeciesName: String?
    public let spawnNeedsDisclaimer: Bool

    /// The "average night" the contributions build on (50). Score breakdown shows
    /// it as the first row so a user can add the column up.
    public let baseline: Double
    /// Factors excluded from tonight's scoring (e.g. spawn out of season), surfaced
    /// for the "not in play tonight" group.
    public let dormantFactors: [DormantFactor]

    /// True if any gate capped the score.
    public var isCapped: Bool { !gates.isEmpty }
    /// The binding cap reason (lowest cap), if capped.
    public var primaryGate: GateHit? { gates.min { $0.cap < $1.cap } }
}
