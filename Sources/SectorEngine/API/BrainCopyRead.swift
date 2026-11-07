//
//  BrainCopyRead.swift
//  Sector — shared read step for the conditions consolidation's CUSTOMER-lane copies (Sector_Ops #53, spec §5).
//
//  The same lane as Lake level (LakeLevelOutputAPI.swift, design note CUSTOMER_BRAIN_OUTPUT_PATH_V1.md): the Publisher
//  writes a small copy under `customer/`, the Engine reads it only through the read-only `BrainOutputReader`, and every
//  gate fails closed to UNKNOWN with a stable reason string. Nothing here is wired into `/conditions`.
//

import Foundation

/// Stable UNKNOWN reasons shared by the four conditions-consolidation readers. The apps map them to text; never shown raw.
public enum BrainCopyReason {
    public static let noReader = "NO_READER", noPublication = "NO_PUBLICATION", schemaMismatch = "SCHEMA_MISMATCH",
                      lakeIdMismatch = "LAKE_ID_MISMATCH", stale = "STALE", noSource = "NO_SOURCE", noValue = "NO_VALUE"
}

enum BrainCopyRead {
    /// Reads `path` and decodes it as `T`, checking the schema id. `.failure(reason)` for every way it can fail.
    static func copy<T: Decodable>(_ type: T.Type, path: String, schema: String, schemaOf: (T) -> String,
                                   reader: BrainOutputReader?) async -> Result<T, Failure> {
        guard let reader else { return .failure(Failure(BrainCopyReason.noReader)) }
        guard let data = try? await reader.get(path) else { return .failure(Failure(BrainCopyReason.noPublication)) }
        guard let c = try? JSONDecoder().decode(T.self, from: data), schemaOf(c) == schema else {
            return .failure(Failure(BrainCopyReason.schemaMismatch))
        }
        return .success(c)
    }

    struct Failure: Error { let reason: String; init(_ r: String) { reason = r } }

    static func date(_ s: String?) -> Date? { s.flatMap(LakeLevelOutputAPI.isoDate) }

    /// A source time more than this after the request time is refused: a future time never counts as fresh.
    static let maxFutureSkew: TimeInterval = 10 * 60

    /// The parsed time, or nil when it is unparseable or more than `maxFutureSkew` after `now`.
    static func past(_ s: String?, now: Date) -> Date? {
        guard let d = date(s), d <= now.addingTimeInterval(maxFutureSkew) else { return nil }
        return d
    }

    static func finite(_ x: Double?) -> Double? { x.flatMap { $0.isFinite ? $0 : nil } }
}
