//
//  ClarityBrainOutput.swift
//  Sector — the Water Clarity Brain's customer copy, served as the additive `clarityBrain` (Sector_Ops #53, spec §4, §5).
//
//  Reads only `customer/lakes/{k}/clarity` (schema `sector-customer-clarity-v1`), written by the Publisher. Every gate fails
//  closed to UNKNOWN with a reason; freshness is checked again on every request. With no reader (this build) every lake is
//  UNKNOWN, which means the old clarity path. Not wired into `/conditions` here: the tile flag does that.
//

import Foundation

/// `clarityBrain` (spec §4). `status`: AVAILABLE (observed), ESTIMATE (modeled) or UNKNOWN. `reason` only when UNKNOWN.
public struct ClarityBrainOutput: Codable, Equatable, Sendable {
    public let lakeId: String
    public let status: String
    public let reason: String?
    public let centralFt: Double?
    public let lowFt: Double?
    public let highFt: Double?
    public let confidence: String?
    public let observedAt: String?
    public let freshUntil: String?
    public let runner: String?
    public let publishId: String?

    static func unknown(_ lakeId: String, _ reason: String) -> ClarityBrainOutput {
        ClarityBrainOutput(lakeId: lakeId, status: LakeLevelOutput.unknown, reason: reason, centralFt: nil, lowFt: nil, highFt: nil,
                           confidence: nil, observedAt: nil, freshUntil: nil, runner: nil, publishId: nil)
    }
}

public enum ClarityBrainOutputAPI {
    public static let copySchema = "sector-customer-clarity-v1"
    public static let brainSource = "water-clarity-brain"

    public static func copyPath(_ lakeId: String) -> String { "customer/lakes/\(BrainPlatform.lakeKey(lakeId))/clarity" }

    struct CustomerCopy: Decodable {
        let schema: String
        let lakeId: String
        let status: String
        let centralFt: Double?
        let lowFt: Double?
        let highFt: Double?
        let confidence: String?
        let observedAt: String?
        let freshUntil: String?
        let runner: String?
        let publishId: String?
    }

    public static func output(lakeId: String, reader: BrainOutputReader?, now: Date = Date()) async -> ClarityBrainOutput {
        let c: CustomerCopy
        switch await BrainCopyRead.copy(CustomerCopy.self, path: copyPath(lakeId), schema: copySchema, schemaOf: \.schema, reader: reader) {
        case .failure(let f): return .unknown(lakeId, f.reason)
        case .success(let v): c = v
        }
        guard c.lakeId == lakeId else { return .unknown(lakeId, BrainCopyReason.lakeIdMismatch) }   // lake keys are lossy
        guard c.status == LakeLevelOutput.available || c.status == LakeLevelOutput.estimate else {
            return .unknown(lakeId, BrainCopyReason.noSource)
        }
        guard BrainCopyRead.date(c.observedAt) != nil, let until = BrainCopyRead.date(c.freshUntil), now <= until else {
            return .unknown(lakeId, BrainCopyReason.stale)
        }
        guard let central = BrainCopyRead.finite(c.centralFt) else { return .unknown(lakeId, BrainCopyReason.noValue) }
        return ClarityBrainOutput(lakeId: lakeId, status: c.status, reason: nil, centralFt: central, lowFt: BrainCopyRead.finite(c.lowFt),
                                  highFt: BrainCopyRead.finite(c.highFt), confidence: c.confidence, observedAt: c.observedAt,
                                  freshUntil: c.freshUntil, runner: c.runner, publishId: c.publishId)
    }
}
