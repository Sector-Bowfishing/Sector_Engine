//
//  LakeSpeciesPresence.swift
//  Sector — Lake Brain: lake → species presence (the Sector Intelligence seam)
//
//  The presence DATA is private research (621 lakes × 12 species, built in the
//  private research repository and stored in gs://sector-lake-brain/presence/).
//  This public file only validates a bundle and turns it into
//  `/lakes/{k}/speciesPresence/{speciesId}` records. It contains no data.
//
//  Rules (decision 8, 2026-10-12):
//    • the research vocabulary verbatim, plus canonical overrides from the
//      Biological Brain's canonical release, recorded as discrepancy ids;
//    • only the 12 assessed species; every other species is NOT_ASSESSED (absent);
//    • `unknown` rows are not written — absent means unknown / not assessed;
//    • which states count as "relevant" is Sector Intelligence's call, not here.
//

import Foundation
import SectorEngine

public struct LakePresenceBundle: Codable, Sendable {
    public struct Row: Codable, Sendable {
        public var lakeId: String
        public var speciesId: String
        public var presenceState: String
        public var confidence: String?
        public var nativeStatus: String?
        public var sourceTier: String?
        public var latestRecord: String?
        public var dataGaps: String?
        public var discrepancyIds: [String]?
    }
    public var schemaVersion: Int
    public var kind: String
    public var researchVersion: String
    public var presenceAuthority: String
    public var assessedSpecies: [String]
    public var sourceArtifacts: [String]?
    public var rows: [Row]
}

public struct LakePresencePointer: Codable, Sendable {
    public var researchVersion: String
    public var path: String
    public var fingerprint: String
    public var rowCount: Int
}

public struct LakePresenceError: Error, CustomStringConvertible { public let description: String }

public struct LakePresenceIndex: Sendable {
    public let researchVersion: String
    public let fingerprint: String
    public let sourceRef: String
    public let assessedSpecies: [String]
    let byLake: [String: [LakePresenceBundle.Row]]
    let authority: String

    static let speciesPattern = try! NSRegularExpression(pattern: "^[a-z][a-z0-9_]{1,63}$")

    /// Validates everything or throws; a bad bundle publishes nothing.
    public init(bundle: LakePresenceBundle, fingerprint: String, sourceRef: String, knownLakeIds: Set<String>) throws {
        guard bundle.schemaVersion == 1, bundle.kind == "lake-brain-presence" else {
            throw LakePresenceError(description: "unexpected bundle kind/schema \(bundle.kind) v\(bundle.schemaVersion)")
        }
        let assessed = Set(bundle.assessedSpecies)
        guard assessed.count == bundle.assessedSpecies.count, !assessed.isEmpty else {
            throw LakePresenceError(description: "assessedSpecies empty or duplicated")
        }
        for s in assessed where Self.speciesPattern.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) == nil {
            throw LakePresenceError(description: "speciesId not snake_case: \(s)")
        }
        var seen = Set<String>()
        var byLake: [String: [LakePresenceBundle.Row]] = [:]
        for r in bundle.rows {
            guard LakePresenceState(rawValue: r.presenceState) != nil else {
                throw LakePresenceError(description: "\(r.lakeId)/\(r.speciesId): presenceState '\(r.presenceState)' is not in the research vocabulary")
            }
            guard assessed.contains(r.speciesId) else { throw LakePresenceError(description: "\(r.speciesId) is not an assessed species") }
            guard knownLakeIds.contains(r.lakeId) else { throw LakePresenceError(description: "\(r.lakeId) is not a directory lake") }
            guard seen.insert("\(r.lakeId)#\(r.speciesId)").inserted else {
                throw LakePresenceError(description: "duplicate row \(r.lakeId)/\(r.speciesId)")
            }
            if r.presenceState == LakePresenceState.unknown.rawValue { continue }
            byLake[r.lakeId, default: []].append(r)
        }
        researchVersion = bundle.researchVersion
        self.fingerprint = fingerprint
        self.sourceRef = sourceRef
        assessedSpecies = bundle.assessedSpecies.sorted()
        authority = bundle.presenceAuthority
        self.byLake = byLake.mapValues { $0.sorted { $0.speciesId < $1.speciesId } }
    }

    /// The Sector Intelligence interface: every written presence record for a lake.
    public func resolveLakeSpecies(_ lakeId: String, updatedAt: String) -> [LakeSpeciesPresenceRecord] {
        (byLake[lakeId] ?? []).map { r in
            LakeSpeciesPresenceRecord(
                lakeId: lakeId, speciesId: r.speciesId, presenceState: LakePresenceState(rawValue: r.presenceState)!,
                presenceAuthority: authority, confidence: r.confidence, nativeStatus: r.nativeStatus,
                sourceTier: r.sourceTier, latestRecord: r.latestRecord, dataGaps: r.dataGaps, sourceRef: sourceRef,
                researchVersion: researchVersion, discrepancyIds: (r.discrepancyIds?.isEmpty ?? true) ? nil : r.discrepancyIds,
                updatedAt: updatedAt)
        }
    }

    public func summary(_ lakeId: String) -> LakeBrainProfileRecord.PresenceSummary {
        var by: [String: Int] = [:]
        let rows = byLake[lakeId] ?? []
        for r in rows { by[r.presenceState, default: 0] += 1 }
        let unknown = assessedSpecies.count - rows.count
        if unknown > 0 { by[LakePresenceState.unknown.rawValue] = unknown }
        return .init(assessedSpecies: assessedSpecies.count, recordCount: rows.count, byState: by,
                     researchVersion: researchVersion,
                     ref: "/lakes/\(BrainPlatform.lakeKey(lakeId))/speciesPresence")
    }

    /// Loads `presence/latest.json` → the release it points at, and checks the fingerprint.
    public static func load(from archive: LakeBrainArchive, knownLakeIds: Set<String>) async throws -> LakePresenceIndex? {
        guard let p = try await archive.read("presence/latest.json") else { return nil }
        let pointer = try JSONDecoder().decode(LakePresencePointer.self, from: p)
        guard let d = try await archive.read(pointer.path) else {
            throw LakePresenceError(description: "presence pointer names missing \(pointer.path)")
        }
        let fp = LakeBaselineBuilder.fingerprint(String(decoding: d, as: UTF8.self))
        guard fp == pointer.fingerprint else {
            throw LakePresenceError(description: "presence fingerprint mismatch: \(fp) ≠ \(pointer.fingerprint)")
        }
        let bundle = try JSONDecoder().decode(LakePresenceBundle.self, from: d)
        guard bundle.researchVersion == pointer.researchVersion, bundle.rows.count == pointer.rowCount else {
            throw LakePresenceError(description: "presence pointer and bundle disagree")
        }
        return try LakePresenceIndex(bundle: bundle, fingerprint: fp, sourceRef: "\(archive.uri)/\(pointer.path) (private)",
                                     knownLakeIds: knownLakeIds)
    }
}
