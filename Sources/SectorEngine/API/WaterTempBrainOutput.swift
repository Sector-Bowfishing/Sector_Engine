//
//  WaterTempBrainOutput.swift
//  Sector — the Water Temp Brain's customer copy, served as the additive `waterTempBrain` (Sector_Ops #53, spec §4, §5).
//
//  Reads only `customer/lakes/{k}/waterTemp` (schema `sector-customer-water-temp-v1`). Every gate fails closed to UNKNOWN
//  with a reason; freshness is checked again on every request. The frozen `waterTempModel`, `waterTemp` and
//  `waterTempState` fields are never touched by this reader. Not wired into `/conditions` here.
//

import Foundation

/// `waterTempBrain` (spec §4). `status`: AVAILABLE (`kind` measured), ESTIMATE (`kind` modeled) or UNKNOWN.
public struct WaterTempBrainOutput: Codable, Equatable, Sendable {
    public let lakeId: String
    public let status: String
    public let reason: String?
    public let valueF: Double?
    /// `measured` or `modeled`.
    public let kind: String?
    public let observedAt: String?
    public let freshUntil: String?
    public let runner: String?
    public let publishId: String?

    static func unknown(_ lakeId: String, _ reason: String) -> WaterTempBrainOutput {
        WaterTempBrainOutput(lakeId: lakeId, status: LakeLevelOutput.unknown, reason: reason, valueF: nil, kind: nil, observedAt: nil,
                             freshUntil: nil, runner: nil, publishId: nil)
    }
}

public enum WaterTempBrainOutputAPI {
    public static let copySchema = "sector-customer-water-temp-v1"
    public static let brainSource = "water-temp-brain"
    public static let kinds: Set<String> = ["measured", "modeled"]

    public static func copyPath(_ lakeId: String) -> String { "customer/lakes/\(BrainPlatform.lakeKey(lakeId))/waterTemp" }

    struct CustomerCopy: Decodable {
        let schema: String
        let lakeId: String
        let status: String
        let valueF: Double?
        let kind: String?
        let observedAt: String?
        let freshUntil: String?
        let runner: String?
        let publishId: String?
    }

    public static func output(lakeId: String, reader: BrainOutputReader?, now: Date = Date()) async -> WaterTempBrainOutput {
        guard !lakeId.isEmpty else { return .unknown(lakeId, BrainCopyReason.noPublication) }
        let c: CustomerCopy
        switch await BrainCopyRead.copy(CustomerCopy.self, path: copyPath(lakeId), schema: copySchema, schemaOf: \.schema, reader: reader) {
        case .failure(let f): return .unknown(lakeId, f.reason)
        case .success(let v): c = v
        }
        guard c.lakeId == lakeId else { return .unknown(lakeId, BrainCopyReason.lakeIdMismatch) }
        guard c.status == LakeLevelOutput.available || c.status == LakeLevelOutput.estimate else {
            return .unknown(lakeId, BrainCopyReason.noSource)
        }
        guard BrainCopyRead.past(c.observedAt, now: now) != nil, let until = BrainCopyRead.date(c.freshUntil), now <= until else {
            return .unknown(lakeId, BrainCopyReason.stale)
        }
        guard let value = BrainCopyRead.finite(c.valueF), let kind = c.kind, kinds.contains(kind) else {
            return .unknown(lakeId, BrainCopyReason.noValue)
        }
        return WaterTempBrainOutput(lakeId: lakeId, status: c.status, reason: nil, valueF: value, kind: kind, observedAt: c.observedAt,
                                    freshUntil: c.freshUntil, runner: c.runner, publishId: c.publishId)
    }
}
