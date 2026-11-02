//
//  LakeLevelOutputAPI.swift
//  Sector — the first customer path for a Brain output: Lake Brain's level and
//  trend (Sector_Ops #43, #44; design note docs/architecture/data/CUSTOMER_BRAIN_OUTPUT_PATH_V1.md).
//
//  The Engine API stays the only customer boundary: the app never reads the
//  Brain RTDB. The Engine never reads Lake's INTERNAL state either: the Publisher
//  writes a small CUSTOMER-lane copy per eligible lake
//  (`/customer/lakes/{k}/level`, schema `sector-customer-lake-level-v1`) and the
//  Engine serves that through a read-only reader. Every gate fails closed to
//  UNKNOWN. In this build the output is off, the eligible-lake list is empty and
//  the server has no reader, so every lake is UNKNOWN until the owner approves
//  each of those separately.
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

/// The Engine's gates in front of the output (design note §3). Owner-controlled; nothing here turns itself on.
/// The Publisher applies the Brain-side gates (readiness, validation, source class) before it writes the copy.
public struct LakeLevelEligibility: Sendable {
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
                      noPublication = "NO_PUBLICATION", stale = "STALE", noSource = "NO_SOURCE", nearbyGauge = "NEARBY_GAUGE"

    public static let nearbyGaugeLimitation = "Trend from a nearby gauge, not a level measured on the lake."

    /// The CUSTOMER-lane copy the Publisher writes (design note §6).
    public static let copySchema = "sector-customer-lake-level-v1"

    public static func copyPath(_ lakeId: String) -> String { "customer/lakes/\(BrainPlatform.lakeKey(lakeId))/level" }

    /// The copy, decoded only as far as the output needs. Unknown fields are ignored.
    struct CustomerCopy: Decodable {
        let schema: String
        let lakeId: String
        let status: String
        let elevationFt: Double?
        let datum: String?
        let observationTime: String?
        let sourceAgeHours: Double?
        let trend: String?
        let change24hFt: Double?
        let freshUntil: String?
    }

    public static func output(lakeId: String, eligibility: LakeLevelEligibility, reader: BrainOutputReader?,
                              now: Date = Date()) async -> LakeLevelOutput {
        guard eligibility.enabled else { return .unknown(lakeId, notEnabled) }
        guard eligibility.eligibleLakeIds.contains(lakeId) else { return .unknown(lakeId, notValidatedHere) }
        guard let reader else { return .unknown(lakeId, noReader) }

        guard let data = try? await reader.get(copyPath(lakeId)),
              let c = try? JSONDecoder().decode(CustomerCopy.self, from: data),
              c.schema == copySchema,
              c.lakeId == lakeId else { return .unknown(lakeId, noPublication) }   // lake keys are lossy: the stored id must match
        // The copy can go stale after the Publisher wrote it, so freshness is checked again on every request.
        guard let observed = c.observationTime, isoDate(observed) != nil,
              let until = c.freshUntil.flatMap(isoDate), now <= until else { return .unknown(lakeId, stale) }

        switch c.status {
        case LakeLevelOutput.available:
            guard let elevation = c.elevationFt, elevation.isFinite else { return .unknown(lakeId, stale) }
            return LakeLevelOutput(lakeId: lakeId, status: LakeLevelOutput.available, reason: nil, elevationFt: elevation,
                                   datum: c.datum, observationTime: observed, sourceAgeHours: c.sourceAgeHours, trend: c.trend,
                                   change24hFt: c.change24hFt, freshUntil: c.freshUntil, limitation: nil, brainId: "lake-brain")
        case LakeLevelOutput.estimate:
            // A nearby-gauge proxy is trend only: never a lake elevation or a lake change (Cortex lake.md LC-06).
            guard let trend = c.trend, trend != "UNKNOWN" else { return .unknown(lakeId, noSource) }
            return LakeLevelOutput(lakeId: lakeId, status: LakeLevelOutput.estimate, reason: nearbyGauge, elevationFt: nil,
                                   datum: nil, observationTime: observed, sourceAgeHours: c.sourceAgeHours, trend: trend,
                                   change24hFt: nil, freshUntil: c.freshUntil, limitation: nearbyGaugeLimitation, brainId: "lake-brain")
        default:
            return .unknown(lakeId, noSource)
        }
    }

    static func isoDate(_ s: String) -> Date? {
        let f = ISO8601DateFormatter()
        if let d = f.date(from: s) { return d }
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f.date(from: s)
    }
}
