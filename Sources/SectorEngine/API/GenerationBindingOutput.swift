//
//  GenerationBindingOutput.swift
//  Sector — the Lake Brain's dam binding for a lake (Sector_Ops #53, spec §1 Generation, §5).
//
//  Reads only `customer/lakes/{k}/generationBinding` (schema `sector-customer-generation-binding-v1`). It says WHICH dam
//  feeds a lake's generation tile; the live generation fetch stays in the Engine. Every gate fails closed to UNKNOWN, which
//  means the Engine's own `TailwaterRegistry` binding. A binding has no `freshUntil`: it is reviewed configuration, so
//  there is no staleness gate. Not wired into `/conditions` here.
//

import Foundation

public struct GenerationBindingOutput: Codable, Equatable, Sendable {
    public let lakeId: String
    /// AVAILABLE or UNKNOWN.
    public let status: String
    public let reason: String?
    public let operatorId: String?
    public let damId: String?
    public let damName: String?
    public let cwmsOffice: String?
    public let tvaCode: String?
    public let updatedAt: String?

    static func unknown(_ lakeId: String, _ reason: String) -> GenerationBindingOutput {
        GenerationBindingOutput(lakeId: lakeId, status: LakeLevelOutput.unknown, reason: reason, operatorId: nil, damId: nil, damName: nil,
                                cwmsOffice: nil, tvaCode: nil, updatedAt: nil)
    }
}

public enum GenerationBindingOutputAPI {
    public static let copySchema = "sector-customer-generation-binding-v1"
    public static let bindingSource = "lake-brain"

    public static func copyPath(_ lakeId: String) -> String { "customer/lakes/\(BrainPlatform.lakeKey(lakeId))/generationBinding" }

    struct CustomerCopy: Decodable {
        let schema: String
        let lakeId: String
        /// Absent on a live binding; `UNKNOWN` when the Publisher withdrew it.
        let status: String?
        let operatorId: String?
        let damId: String?
        let damName: String?
        let cwmsOffice: String?
        let tvaCode: String?
        let updatedAt: String?
    }

    public static func output(lakeId: String, reader: BrainOutputReader?, now: Date = Date()) async -> GenerationBindingOutput {
        let c: CustomerCopy
        switch await BrainCopyRead.copy(CustomerCopy.self, path: copyPath(lakeId), schema: copySchema, schemaOf: \.schema, reader: reader) {
        case .failure(let f): return .unknown(lakeId, f.reason)
        case .success(let v): c = v
        }
        guard c.lakeId == lakeId else { return .unknown(lakeId, BrainCopyReason.lakeIdMismatch) }
        guard c.status == nil || c.status == LakeLevelOutput.available else { return .unknown(lakeId, BrainCopyReason.noSource) }
        guard let op = c.operatorId, !op.isEmpty, let dam = c.damId, !dam.isEmpty, let name = c.damName, !name.isEmpty,
              BrainCopyRead.date(c.updatedAt) != nil else { return .unknown(lakeId, BrainCopyReason.noValue) }
        return GenerationBindingOutput(lakeId: lakeId, status: LakeLevelOutput.available, reason: nil, operatorId: op, damId: dam,
                                       damName: name, cwmsOffice: c.cwmsOffice, tvaCode: c.tvaCode, updatedAt: c.updatedAt)
    }
}
