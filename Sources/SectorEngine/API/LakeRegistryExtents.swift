//
//  LakeRegistryExtents.swift
//  Sector — each lake's extent (bbox) for `GET /lakes/ready` (Sector_Engine #158), from the Lake Registry index.
//
//  Source: `registry/lakes.v1.json` in the public bucket `gs://sector-lake-registry` (contract
//  docs/brains/LAKE_REGISTRY_GEOMETRY_CONTRACT.md; builder jobs/lake-geometry/). The registry is lake geometry identity
//  (USGS NHD shorelines, public domain), not a Brain output: it is neither `/lakes/*/states` nor `/brains/*`, it needs no
//  credential (public read) and no IAM change. The Engine already reads its sibling bucket `sector-lake-surface` the same way.
//
//  An entry gives an extent only when every check passes, otherwise the lake is listed without one (never a guessed box):
//    - `geometry` is published (not null: 31 lakes at v1 have none, e.g. the held Great Lakes);
//    - `geometryConfidence.level` is HIGH or MEDIUM (LOW includes "the directory point or the lake is wrong");
//    - `pointFlag` is not `identity-risk`;
//    - `bbox` is four finite numbers [west, south, east, north] with west < east and south < north, inside lon/lat range.
//
//  The index is ~1.5 MB (0.22 MB gzip). It is fetched at most once per `ttl` (30 min; the bucket says max-age 300, but the
//  geometry is versioned and changes only with a registry rebuild), at the same time as the customer/lakes snapshot. A failed
//  fetch is kept `failureTTL` (60 s) and means "no extents", never "no lakes". `SECTOR_LAKE_REGISTRY_INDEX_URL` points it
//  elsewhere (a local copy, a test fixture). The outline (`geometry.displayUrl`) is not served yet.
//

import Foundation

/// A lake's extent. Only `bbox` today; an outline may be added later as a new optional key.
public struct ReadyLakeExtent: Codable, Equatable, Sendable {
    public let bbox: ReadyLakeBBox
    /// The registry's `geometryConfidence.level` for the shoreline the box comes from: `HIGH` or `MEDIUM`.
    public let confidence: String
}

/// Degrees, WGS84. `west < east`, `south < north`.
public struct ReadyLakeBBox: Codable, Equatable, Sendable {
    public let west: Double
    public let south: Double
    public let east: Double
    public let north: Double
}

public enum LakeRegistryExtents {
    public static let defaultIndexURL = "https://storage.googleapis.com/sector-lake-registry/registry/lakes.v1.json"
    public static let envKey = "SECTOR_LAKE_REGISTRY_INDEX_URL"
    public static let schema = "sector.lake-registry/v1"
    static let usableLevels: Set<String> = ["HIGH", "MEDIUM"]

    public static func indexURL(_ env: [String: String] = ProcessInfo.processInfo.environment) -> URL? {
        URL(string: env[envKey].flatMap { $0.isEmpty ? nil : $0 } ?? defaultIndexURL)
    }

    /// `[lakeId: extent]` for the usable entries. nil when the document is not a v1 registry index.
    public static func parse(_ data: Data) -> [String: ReadyLakeExtent]? {
        guard let doc = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              doc["schema"] as? String == schema, let lakes = doc["lakes"] as? [Any] else { return nil }
        var out: [String: ReadyLakeExtent] = [:]
        for case let e as [String: Any] in lakes {
            if let id = e["lakeId"] as? String, !id.isEmpty, let x = extent(e) { out[id] = x }
        }
        return out
    }

    static func extent(_ e: [String: Any]) -> ReadyLakeExtent? {
        guard e["geometry"] is [String: Any],
              let level = (e["geometryConfidence"] as? [String: Any])?["level"] as? String, usableLevels.contains(level) else {
            return nil
        }
        let flags = [e["pointFlag"], (e["location"] as? [String: Any])?["pointFlag"]].compactMap { $0 as? String }
        guard !flags.contains("identity-risk") else { return nil }
        guard let raw = e["bbox"] as? [Any], raw.count == 4 else { return nil }
        let v = raw.compactMap { ($0 as? NSNumber).map(\.doubleValue) }.filter(\.isFinite)
        guard v.count == 4 else { return nil }
        let (w, s, east, n) = (v[0], v[1], v[2], v[3])
        guard -180 <= w, w < east, east <= 180, -90 <= s, s < n, n <= 90 else { return nil }
        return ReadyLakeExtent(bbox: ReadyLakeBBox(west: w, south: s, east: east, north: n), confidence: level)
    }
}

/// The parsed registry index, fetched at most once per `ttl` and one fetch at a time. A failure (transport, non-2xx, or
/// a document that is not the index) gives no extents and is kept only `failureTTL`.
public actor LakeRegistryExtentCache {
    public typealias Fetch = @Sendable (URL) async throws -> Data

    private let url: URL
    private let ttl: TimeInterval
    private let failureTTL: TimeInterval
    private let fetch: Fetch
    private let clock: @Sendable () -> Date
    private var entry: (at: Date, task: Task<[String: ReadyLakeExtent]?, Never>, failed: Bool)?

    public init(url: URL, ttl: TimeInterval = 1800, failureTTL: TimeInterval = 60,
                fetch: @escaping Fetch = LakeRegistryExtentCache.httpFetch,
                clock: @escaping @Sendable () -> Date = { Date() }) {
        self.url = url
        self.ttl = ttl
        self.failureTTL = failureTTL
        self.fetch = fetch
        self.clock = clock
    }

    /// The Engine's HTTP client, bounded to 5 s. A non-2xx status is a failure.
    public static let httpFetch: Fetch = { url in
        let r = try await HTTP.get(url, timeout: 5)
        guard r.isSuccess else { throw BrainStoreError("lake registry index: HTTP \(r.status)") }
        return r.body
    }

    func extents() async -> [String: ReadyLakeExtent] {
        let now = clock()
        let task: Task<[String: ReadyLakeExtent]?, Never>
        if let e = entry, now.timeIntervalSince(e.at) < (e.failed ? failureTTL : ttl) {
            task = e.task
        } else {
            let fetch = self.fetch, url = self.url
            task = Task {
                guard let data = try? await fetch(url) else { return nil }
                return LakeRegistryExtents.parse(data)
            }
            entry = (now, task, false)
        }
        guard let v = await task.value else {
            // Keep the failure only briefly, and only if no newer fetch has replaced it meanwhile.
            if let e = entry, e.task == task, !e.failed { entry = (clock(), task, true) }
            return [:]
        }
        return v
    }
}
