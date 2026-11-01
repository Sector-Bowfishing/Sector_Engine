//
//  LakeLevelOutputAPI.swift
//  Sector — the first customer path for a Brain output: Lake Brain's level and
//  trend (Sector_Ops #43, design note docs/architecture/data/CUSTOMER_BRAIN_OUTPUT_PATH_V1.md).
//
//  The Engine API stays the only customer boundary: the app never reads the
//  Brain RTDB. The Engine reads Lake's published state (`/lakes/{k}/states/lake`)
//  through a read-only reader and serves a small customer projection of it.
//  Every gate fails closed to UNKNOWN. In this build the output is off, the
//  eligible-lake list is empty and the server has no reader, so every lake is
//  UNKNOWN until the owner approves each of those separately.
//

import Foundation

/// Read-only access to published Brain state. The customer server never writes.
public protocol BrainOutputReader: Sendable {
    func get(_ path: String) async throws -> Data?
}

/// What the app receives for one lake. `status` is AVAILABLE (an observed level at
/// the lake), ESTIMATE (a nearby gauge stands in for the lake) or UNKNOWN.
public struct LakeLevelOutput: Codable, Equatable, Sendable {
    public static let available = "AVAILABLE", estimate = "ESTIMATE", unknown = "UNKNOWN"

    public let lakeId: String
    public let status: String
    /// Why the output is UNKNOWN or an ESTIMATE; nil when AVAILABLE.
    public let reason: String?
    public let elevationFt: Double?
    public let datum: String?
    public let observationTime: String?
    public let sourceAgeHours: Double?
    /// Lake's trend vocabulary: STABLE, RISING, FALLING, RISING_RAPIDLY, FALLING_RAPIDLY or UNKNOWN.
    public let trend: String?
    public let change24hFt: Double?
    public let freshUntil: String?
    /// One plain sentence the app shows beside an ESTIMATE.
    public let limitation: String?
    public let brainId: String

    static func unknown(_ lakeId: String, _ reason: String) -> LakeLevelOutput {
        LakeLevelOutput(lakeId: lakeId, status: unknown, reason: reason, elevationFt: nil, datum: nil, observationTime: nil,
                        sourceAgeHours: nil, trend: nil, change24hFt: nil, freshUntil: nil, limitation: nil, brainId: "lake-brain")
    }
}

/// The gates in front of the output (design note §3). Owner-controlled; nothing here turns itself on.
public struct LakeLevelEligibility: Sendable {
    /// Readiness values on the ladder at or above BETA.
    public static let customerReadiness: Set<String> = ["BETA", "VALIDATED", "PRODUCTION"]

    public var enabled: Bool
    /// Lakes whose level and trend passed the frozen Lake Beta validation. Empty until that validation is scored
    /// and the owner approves the list.
    public var eligibleLakeIds: Set<String>

    public init(enabled: Bool, eligibleLakeIds: Set<String>) {
        self.enabled = enabled
        self.eligibleLakeIds = eligibleLakeIds
    }

    /// `SECTOR_LAKE_LEVEL_OUTPUT=1` switches the output on. The eligible list is code, not configuration, so adding a
    /// lake is a reviewed change.
    public static func fromEnvironment(_ env: [String: String] = ProcessInfo.processInfo.environment) -> LakeLevelEligibility {
        LakeLevelEligibility(enabled: env["SECTOR_LAKE_LEVEL_OUTPUT"] == "1", eligibleLakeIds: validatedLakeIds)
    }

    public static let validatedLakeIds: Set<String> = []
}

public enum LakeLevelOutputAPI {
    // UNKNOWN / ESTIMATE reasons (stable strings; the app maps them to text).
    public static let notEnabled = "NOT_ENABLED", notValidatedHere = "NOT_VALIDATED_HERE", noReader = "NO_READER",
                      notBeta = "BRAIN_NOT_BETA", noPublication = "NO_PUBLICATION", stale = "STALE",
                      noSource = "NO_SOURCE", nearbyGauge = "NEARBY_GAUGE"

    public static let nearbyGaugeLimitation = "From a nearby gauge, not a gauge on the lake."

    /// The published Lake state, decoded only as far as the projection needs. Unknown fields are ignored.
    struct PublishedState: Decodable {
        struct Change: Decodable { let h24: Double? }
        struct Freshness: Decodable { let stale: Bool; let freshUntil: String? }
        let lakeId: String
        let kind: String
        let sourceCapability: String
        let currentElevationFt: Double?
        let datum: String?
        let observationTime: String?
        let sourceAgeHours: Double?
        let change: Change?
        let trendState: String
        let freshness: Freshness
    }

    public static func output(lakeId: String, eligibility: LakeLevelEligibility, reader: BrainOutputReader?) async -> LakeLevelOutput {
        guard eligibility.enabled else { return .unknown(lakeId, notEnabled) }
        guard eligibility.eligibleLakeIds.contains(lakeId) else { return .unknown(lakeId, notValidatedHere) }
        guard let reader else { return .unknown(lakeId, noReader) }

        let readiness = (try? await reader.get("brains/lake-brain/status")).flatMap { try? JSONDecoder().decode(String.self, from: $0) }
        guard let readiness, LakeLevelEligibility.customerReadiness.contains(readiness) else { return .unknown(lakeId, notBeta) }

        let path = "lakes/\(BrainPlatform.lakeKey(lakeId))/states/lake"
        guard let data = try? await reader.get(path),
              let s = try? JSONDecoder().decode(PublishedState.self, from: data),
              s.lakeId == lakeId else { return .unknown(lakeId, noPublication) }   // lake keys are lossy: the stored id must match
        guard !s.freshness.stale, let elevation = s.currentElevationFt, let observed = s.observationTime else {
            return .unknown(lakeId, stale)
        }

        let status: String, reason: String?, limitation: String?
        switch (s.kind, s.sourceCapability) {
        case ("OBSERVED", "DIRECT_OPERATOR_POOL"), ("OBSERVED", "DIRECT_LAKE_GAUGE"):
            (status, reason, limitation) = (LakeLevelOutput.available, nil, nil)
        case ("PROXY", "NEARBY_GAUGE_PROXY"):
            (status, reason, limitation) = (LakeLevelOutput.estimate, nearbyGauge, nearbyGaugeLimitation)
        default:
            return .unknown(lakeId, noSource)
        }
        return LakeLevelOutput(lakeId: lakeId, status: status, reason: reason, elevationFt: elevation, datum: s.datum,
                               observationTime: observed, sourceAgeHours: s.sourceAgeHours, trend: s.trendState,
                               change24hFt: s.change?.h24, freshUntil: s.freshness.freshUntil, limitation: limitation,
                               brainId: "lake-brain")
    }
}
