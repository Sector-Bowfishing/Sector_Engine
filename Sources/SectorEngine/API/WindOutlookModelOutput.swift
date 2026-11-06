//
//  WindOutlookModelOutput.swift
//  Sector — the Wind Brain's outlook-model decision (Sector_Ops #53, spec §1 Wind outlook model, §5).
//
//  Reads only `customer/wind/outlookModel` (schema `sector-customer-wind-outlook-model-v1`). It is the Brain-owned
//  replacement for the env `SECTOR_WIND_FORECAST_MODEL` (#125). Every gate fails closed to UNKNOWN, which means the env
//  path. Tonight always stays `best_match` (WS-5); a copy that says otherwise is refused. A decision is stale 14 days
//  after its `updatedAt`. Not wired into `/conditions` here.
//

import Foundation

public struct WindOutlookModelOutput: Codable, Equatable, Sendable {
    /// AVAILABLE or UNKNOWN.
    public let status: String
    public let reason: String?
    public let tonight: String?
    public let nights2to7: String?
    public let decidedBy: String?
    public let evidence: String?
    public let updatedAt: String?

    static func unknown(_ reason: String) -> WindOutlookModelOutput {
        WindOutlookModelOutput(status: LakeLevelOutput.unknown, reason: reason, tonight: nil, nights2to7: nil, decidedBy: nil, evidence: nil,
                               updatedAt: nil)
    }
}

public enum WindOutlookModelOutputAPI {
    public static let copySchema = "sector-customer-wind-outlook-model-v1"
    public static let copyPath = "customer/wind/outlookModel"
    public static let brainSource = "wind-brain"
    /// A decision older than this is stale (spec: windModel stale after 14 days).
    public static let maxAge: TimeInterval = 14 * 24 * 3600
    public static let tonightModel = "best_match"
    public static let models: Set<String> = ["best_match", "ncep_nbm_conus"]

    struct CustomerCopy: Decodable {
        let schema: String
        let status: String?
        let tonight: String?
        let nights2to7: String?
        let decidedBy: String?
        let evidence: String?
        let updatedAt: String?
    }

    public static func output(reader: BrainOutputReader?, now: Date = Date()) async -> WindOutlookModelOutput {
        let c: CustomerCopy
        switch await BrainCopyRead.copy(CustomerCopy.self, path: copyPath, schema: copySchema, schemaOf: \.schema, reader: reader) {
        case .failure(let f): return .unknown(f.reason)
        case .success(let v): c = v
        }
        guard c.status == nil || c.status == LakeLevelOutput.available else { return .unknown(BrainCopyReason.noSource) }
        guard let updated = BrainCopyRead.date(c.updatedAt), now <= updated.addingTimeInterval(maxAge) else {
            return .unknown(BrainCopyReason.stale)
        }
        guard c.tonight == tonightModel, let later = c.nights2to7, models.contains(later), let by = c.decidedBy, !by.isEmpty else {
            return .unknown(BrainCopyReason.noValue)
        }
        return WindOutlookModelOutput(status: LakeLevelOutput.available, reason: nil, tonight: tonightModel, nights2to7: later, decidedBy: by,
                                      evidence: c.evidence, updatedAt: c.updatedAt)
    }
}
