//
//  LakeBrainContract.swift
//  Sector — Lake Brain (`lake-brain`): contract types and Engine-owned enums
//
//  The Lake Brain is an intelligence layer over the EXISTING lake registry
//  (the Engine directory, GET /lakes). It owns, per lake:
//    • LakeProfile   `/lakes/{k}/brain`                      slow-changing
//    • LakeState     `/lakes/{k}/states/lake` + snapshot `lakeState`
//    • presence      `/lakes/{k}/speciesPresence/{speciesId}`
//  It never owns species knowledge (Biological Brain), what fish do about the
//  level (Sector Intelligence / Conditions Score) or presentation (Sector Ops).
//
//  Spec: docs/brains/LAKE_BRAIN_INTEGRATION.md. Unknown stays unknown: every
//  optional is written as absent, never a default.
//
//  ADDITIVE: nothing in the request path (/conditions, /lakes, …) imports this.
//

import Foundation

public enum LakeBrainSpec {
    public static let brainId = "lake-brain"
    public static let displayName = "Lake Brain"
    public static let slot = "lake"
    public static let snapshotField = "lakeState"
    public static let brainVersion = "1.0.0"
    /// The classification rules (§7 of the spec). Bump on any rule change.
    public static let modelVersion = "lake-level-rules-v1"
    /// Day-of-year percentile climatology (§6 of the spec).
    public static let baselineMethod = "doy15-percentile-v1"
    public static let profileSchemaVersion = 1
    public static let stateSchemaVersion = 1
    /// A published state older than this is stale whatever the source says.
    public static let staleAfterHours = 3.0
}

// MARK: - Engine-owned enums

/// What kind of value a LakeState carries.
public enum LakeStateKind: String, Codable, Sendable, CaseIterable {
    /// An operator pool or an on-lake surface-elevation gauge.
    case observed = "OBSERVED"
    /// A nearby gage height / river stage. Trend only: never a level state, a
    /// percentile or a pool difference.
    case proxy = "PROXY"
    case unavailable = "UNAVAILABLE"
}

/// How well a lake's water level can be known (one class per lake, from its binding).
public enum LevelSourceCapability: String, Codable, Sendable, CaseIterable {
    case directOperatorPool = "DIRECT_OPERATOR_POOL"
    case directLakeGauge = "DIRECT_LAKE_GAUGE"
    case nearbyGaugeProxy = "NEARBY_GAUGE_PROXY"
    case historicalOnly = "HISTORICAL_ONLY"
    /// Reserved. Nothing is modeled in v1.
    case modeled = "MODELED"
    case noSource = "NO_SOURCE"
}

/// Whether a lake's source binding has been probed and reviewed.
public enum LevelBindingStatus: String, Codable, Sendable {
    /// Probed and reviewed; this binding drives the LakeState.
    case reviewed = "REVIEWED"
    /// Derived from directory hints only. Never used to publish a state.
    case candidate = "CANDIDATE"
}

/// Level against the OPERATOR's own zone / guide for the date (lake-specific).
public enum LakeLevelState: String, Codable, Sendable, CaseIterable {
    case belowZone = "BELOW_ZONE"
    case inZone = "IN_ZONE"
    case aboveZone = "ABOVE_ZONE"
    /// Above the operator's top of conservation (bottom of flood control).
    case floodPool = "FLOOD_POOL"
    case unknown = "UNKNOWN"
}

/// 24-hour change against this lake's own seasonal |Δ24h| distribution.
public enum LakeTrendState: String, Codable, Sendable, CaseIterable {
    case stable = "STABLE"
    case rising = "RISING"
    case falling = "FALLING"
    case risingRapidly = "RISING_RAPIDLY"
    case fallingRapidly = "FALLING_RAPIDLY"
    case unknown = "UNKNOWN"
}

/// Level against this lake's own day-of-year climatology.
public enum LakeHistoricalState: String, Codable, Sendable, CaseIterable {
    case normal = "NORMAL"
    case unusual = "UNUSUAL"
    case veryUnusual = "VERY_UNUSUAL"
    case insufficientHistory = "INSUFFICIENT_HISTORY"
}

/// Dynamic flood-pool occupancy. Different from `characteristics.floodControl`
/// (whether the reservoir HAS a flood pool).
public enum LakeFloodPoolState: String, Codable, Sendable, CaseIterable {
    case normal = "NORMAL"
    case inFloodPool = "IN_FLOOD_POOL"
    case unknown = "UNKNOWN"
}

/// How much history backs a lake's baselines.
public enum LakeBaselineStatus: String, Codable, Sendable, CaseIterable {
    /// ≥ 5 complete years.
    case sufficient = "SUFFICIENT"
    /// 2–4 complete years.
    case limited = "LIMITED"
    /// Some history, < 2 complete years.
    case insufficient = "INSUFFICIENT"
    case none = "NONE"
}

/// Per-lake readiness for `lake-brain` (shared Brain vocabulary; rule in the spec §9).
public enum LakeBrainReadiness: String, Codable, Sendable {
    case discovered = "DISCOVERED"
    case profiled = "PROFILED"
    case calibration = "CALIBRATION"
    case beta = "BETA"
    case validated = "VALIDATED"
    case production = "PRODUCTION"
    case degraded = "DEGRADED"
    case blocked = "BLOCKED"
}

/// The research presence vocabulary, verbatim (Biological Brain §10, Ops §8a).
public enum LakePresenceState: String, Codable, Sendable, CaseIterable {
    case established, reported, stocked, inRangeUnconfirmed, historical
    case failedEradicated = "failed/eradicated"
    case unknown
}

// MARK: - Shared small shapes

/// Sector_Ops `Known<T>`: unknown is the absent value, never a default.
public struct KnownValue<T: Codable & Equatable & Sendable>: Codable, Equatable, Sendable {
    public var value: T?
    public var source: String?
    public var quality: String?
    public init(_ value: T?, source: String?, quality: String?) {
        self.value = value; self.source = source; self.quality = quality
    }
}

public struct LakeLevelChange: Codable, Equatable, Sendable {
    public var h1: Double?
    public var h6: Double?
    public var h24: Double?
    public var d3: Double?
    public var d7: Double?
}

public struct LakeOperatingZone: Codable, Equatable, Sendable {
    public var bottomFt: Double
    public var topFt: Double
    public var bottomLabel: String
    public var topLabel: String
    public var source: String
}

public struct LakeOperatorLevel: Codable, Equatable, Sendable {
    public var name: String
    public var ft: Double
    public var source: String
}

public struct LakeSeasonalBand: Codable, Equatable, Sendable {
    public var p02: Double
    public var p10: Double
    public var p50: Double
    public var p90: Double
    public var p98: Double
    /// Complete years behind the band.
    public var basisYears: Int
    /// Day-of-year window (± days) the band pools.
    public var windowDays: Int
    public var sampleCount: Int
}

public struct LakeStateFreshness: Codable, Equatable, Sendable {
    public var generatedAt: String
    public var sourceObservationAt: String?
    /// observation + cadence + lag: no newer observation is expected before this.
    public var freshUntil: String?
    /// Earliest a refresh is worthwhile. Never faster than the source cadence.
    public var nextCheckAt: String
    public var stale: Bool
    public var refreshReason: String
}

// MARK: - LakeState (`/lakes/{k}/states/lake`, snapshot `lakeState`)

public struct LakeLevelStateRecord: Codable, Equatable, Sendable {
    public var lakeId: String
    public var schemaVersion: Int
    public var kind: LakeStateKind
    public var sourceCapability: LevelSourceCapability
    public var currentElevationFt: Double?
    public var unit: String?
    public var datum: String?
    public var observationTime: String?
    public var sourceAgeHours: Double?
    /// Live value minus the directory's normal full pool. Only for operator
    /// full pools that aren't low-confidence; natural-lake surfaces never.
    public var differenceFromNormalPoolFt: Double?
    public var normalPoolRef: String?
    public var guideFt: Double?
    public var differenceFromGuideFt: Double?
    public var operatingZone: LakeOperatingZone?
    public var operatorLevels: [LakeOperatorLevel]?
    public var change: LakeLevelChange?
    public var levelState: LakeLevelState
    public var trendState: LakeTrendState
    public var historicalState: LakeHistoricalState
    public var floodPoolState: LakeFloodPoolState
    /// 0–100, current value against the same-season distribution. Only when the baseline is SUFFICIENT.
    public var seasonalPercentile: Double?
    /// 0–100, |Δ24h| against the same-season |Δ24h| distribution.
    public var rateOfChangePercentile: Double?
    public var rapidChangeThresholdFt: Double?
    public var seasonalBand: LakeSeasonalBand?
    public var baselineStatus: LakeBaselineStatus
    /// Engine-authored, factual sentences in display order. No fish wording.
    public var facts: [String]?
    public var freshness: LakeStateFreshness
    public var provenance: BrainProvenance
}

// MARK: - LakeProfile (`/lakes/{k}/brain`, extends Sector_Ops `LakeBrain`)

public struct LakeBrainProfileRecord: Codable, Equatable, Sendable {
    public struct Identity: Codable, Equatable, Sendable {
        public var riverSystem: String?
        public var basin: String?
        public var lakeType: String?
        /// Pointer to the shoreline registry (LakeBindingTypes.swift); no polygon is stored here.
        public var geometry: LakeGeometryRef? = nil
    }
    public struct Hydrology: Codable, Equatable, Sendable {
        public var dam: KnownValue<String>?
        public var operation: KnownValue<String>?
    }
    public struct Characteristics: Codable, Equatable, Sendable {
        public var floodControl: KnownValue<Bool>?
        public var hydropower: KnownValue<Bool>?
        public var navigation: KnownValue<Bool>?
        public var runOfRiver: KnownValue<Bool>?
        public var controlled: KnownValue<Bool>?
        public var naturalLake: KnownValue<Bool>?
        /// Research-derived context (class, regime, region, residence time, chain, ...), each value with source and quality.
        public var context: LakeContextFeatures? = nil
    }
    public struct GuideCurveRef: Codable, Equatable, Sendable {
        public var available: Bool
        public var source: String?
        public var ref: String?
    }
    public struct OperatingPools: Codable, Equatable, Sendable {
        /// The normal full pool itself stays in the directory (GET /lakes); this names it.
        public var normalFullPoolRef: String
        public var topOfGatesFt: KnownValue<Double>?
        public var guideCurve: GuideCurveRef
        public var operatingZoneSource: String?
        public var datum: KnownValue<String>?
        /// Operator flood-pool bottom with its source (verified plan / flood evidence only).
        public var floodPoolBottom: FloodPoolBottomRef? = nil
        public var planEvidence: PlanEvidenceRef? = nil
    }
    public struct SourceRef: Codable, Equatable, Sendable {
        public var sourceId: String
        public var provider: String
        public var capability: LevelSourceCapability
        public var cadenceMin: Int
        public var lagMin: Int
        public var note: String?
    }
    public struct SourceCapability: Codable, Equatable, Sendable {
        public var level: LevelSourceCapability
        public var bindingStatus: LevelBindingStatus
        public var bindingVersion: String
        public var primary: SourceRef?
        public var fallbacks: [SourceRef]?
        public var history: [String]?
        public var proxyOnly: Bool
        public var reviewedAt: String?
        public var note: String?
    }
    public struct HistoricalCoverage: Codable, Equatable, Sendable {
        public var historyStart: String?
        public var historyEnd: String?
        public var observationCount: Int
        public var coveragePct: Double?
        public var yearsCovered: Int
        public var baselineStatus: LakeBaselineStatus
        public var baselineMethod: String
        public var baselineVersion: String?
        public var historyRef: String?
    }
    public struct PresenceSummary: Codable, Equatable, Sendable {
        public var assessedSpecies: Int
        public var recordCount: Int
        public var byState: [String: Int]?
        public var researchVersion: String
        public var ref: String
    }
    public struct TrustedSource: Codable, Equatable, Sendable {
        public var sourceId: String
        public var provider: String
        public var sourceType: String
        public var station: String
        public var status: String
        public var lastObservationAt: String?
        public var authority: String
        public var brains: [String]
    }
    /// Sector_Ops `Issue`: severity critical | warning | info.
    public struct Issue: Codable, Equatable, Sendable {
        public var id: String
        public var severity: String
        public var kind: String
        public var title: String
        public var lakeId: String
        public var brainId: String
        public var since: String
    }

    public var lakeId: String
    public var schemaVersion: Int
    /// Integer for Sector Ops (`profileVersion: number`); bumps when `profileHash` changes.
    public var profileVersion: Int
    public var profileHash: String
    public var updatedAt: String
    public var identity: Identity
    public var hydrology: Hydrology?
    public var characteristics: Characteristics?
    public var operatingPools: OperatingPools?
    public var sourceCapability: SourceCapability
    public var historicalCoverage: HistoricalCoverage?
    public var speciesPresenceSummary: PresenceSummary?
    public var trustedSources: [String: TrustedSource]?
    public var readiness: [String: String]
    public var activeIssues: [Issue]?
}

// MARK: - Presence (`/lakes/{k}/speciesPresence/{speciesId}`)

public struct LakeSpeciesPresenceRecord: Codable, Equatable, Sendable {
    public var lakeId: String
    public var speciesId: String
    public var presenceState: LakePresenceState
    public var presenceAuthority: String
    public var confidence: String?
    public var nativeStatus: String?
    public var sourceTier: String?
    public var latestRecord: String?
    public var dataGaps: String?
    public var sourceRef: String
    public var researchVersion: String
    public var discrepancyIds: [String]?
    public var updatedAt: String
}
