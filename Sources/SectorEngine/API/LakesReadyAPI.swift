//
//  LakesReadyAPI.swift
//  Sector — `GET /lakes/ready`: the lakes with real Brain data, for the app's lake picker (Sector_Engine #156, #158;
//  iOS_Sector #227).
//
//  A lake is "ready" when at least one of its CUSTOMER-lane copies is usable right now: status not UNKNOWN and not stale.
//  The decision is made by the existing per-copy readers (#144: ClarityBrainOutputAPI, WaterTempBrainOutputAPI and
//  LakeLevelOutputAPI), so the freshness bounds and the status rules are theirs. On top, `/lakes/ready` applies the
//  readers' 10-minute future-time bound (`BrainCopyRead.past`) to every layer's `asOf`, `level` included. Nothing
//  here reads a Brain INTERNAL path (`/lakes/*/states`, `/brains/*`); every Brain read goes through `BrainOutputReader` and
//  stays under `customer/lakes`. Design note: docs/architecture/data/CUSTOMER_BRAIN_OUTPUT_PATH_V1.md §9.
//
//  Read pattern: ONE read of `customer/lakes` (the subtree that holds every per-lake copy), then each lake's copies are
//  evaluated by the readers against that in-memory snapshot. Reading each directory lake's three copies would be ~1,900
//  reads per request. The subtree also carries the `generationBinding` copies (customer lane too); they are not parsed.
//  The snapshot reader serves only `customer/lakes/{k}/{clarity|waterTemp|level}` and refuses any other path. The server
//  keeps the parsed snapshot for 60 s (`LakesReadySnapshotCache`); a failed read is not kept.
//
//  Per lake (#158): `directoryId` (the app's "Name|ST", equal to `lakeId`) next to `brainKey` (the RTDB lake key); each
//  ready layer's lake-wide value from the same copy that made it ready (clarity `valueFt`, water temp `valueF`); and
//  `extent.bbox` from the Lake Registry index (LakeRegistryExtents.swift: public, versioned lake geometry identity, not a
//  Brain output), present only for a registry entry with a published shoreline at HIGH or MEDIUM confidence.
//
//  Gates (all default OFF / fail closed):
//    - `SECTOR_LAKES_READY_OUTPUT=1` routes the endpoint. Unset: the server registers no route (404, like `/lake/level`).
//    - `SECTOR_BRAIN_OUTPUT_READER` picks the reader (BrainOutputReaderConfig). Unset: no reader → `200` with no lakes.
//    - A failed or refused read of the subtree → `200` with no lakes (the app shows "no lakes yet").
//    - A failed registry read → the last good index is served; with none, the lakes are listed without `extent`.
//    - The `level` layer also needs the Lake level gates: `SECTOR_LAKE_LEVEL_OUTPUT=1` and the lake on `validatedLakeIds`.
//
//  Layers: `clarity`, `waterTemp` and `level` have CUSTOMER-lane copies. `wind` and `intelligence` have none per lake today
//  (wind's only copy is the global `customer/wind/outlookModel`, a model choice, not a lake value; Intelligence has no
//  copy), so they are never emitted. A layer is present only when it is ready; an absent layer means "not yet for this lake".
//  Contract: contracts/phone/lakes-ready-v1.json (1.1.0: additive).
//

import Foundation

/// The `GET /lakes/ready` body (contract `sector-phone-lakes-ready-v1`). Additive evolution only.
public struct LakesReadyResponse: Codable, Equatable, Sendable {
    public static let currentVersion = 1

    /// The response's shape version: 1. Bumped only for a breaking change, which needs a new contract.
    public let version: Int
    /// When the Engine evaluated the copies, ISO 8601 UTC, seconds precision.
    public let generatedAt: String
    /// Ready lakes, sorted by `lakeId`. Empty when nothing is ready (or no reader): not an error.
    public let lakes: [ReadyLake]
}

public struct ReadyLake: Codable, Equatable, Sendable {
    /// The lake directory id ("Name|ST"), the same `id` `GET /lakes` serves.
    public let lakeId: String
    /// The app's directory id ("Name|ST", as `LakeDirectory` and My Lakes use it). Always equal to `lakeId` (#158).
    public let directoryId: String
    /// The Brain RTDB lake key (`BrainPlatform.lakeKey`, "Guntersville_AL"). Lossy: match lakes on `directoryId`, never on this.
    public let brainKey: String
    public let name: String
    public let centroid: ReadyLakeCentroid
    /// The lake's extent from the Lake Registry. Absent when the registry has no usable shoreline for it or could not be read.
    public let extent: ReadyLakeExtent?
    public let layers: ReadyLakeLayers

    public init(lakeId: String, name: String, centroid: ReadyLakeCentroid, extent: ReadyLakeExtent?, layers: ReadyLakeLayers) {
        self.lakeId = lakeId
        self.directoryId = lakeId
        self.brainKey = BrainPlatform.lakeKey(lakeId)
        self.name = name
        self.centroid = centroid
        self.extent = extent
        self.layers = layers
    }
}

/// The directory coordinate (`GET /lakes` `lat`/`lon`).
public struct ReadyLakeCentroid: Codable, Equatable, Sendable {
    public let lat: Double
    public let lon: Double
}

/// Each key is present only when that layer is ready. `wind` and `intelligence` are never emitted (no per-lake copy exists).
public struct ReadyLakeLayers: Codable, Equatable, Sendable {
    public let clarity: ReadyClarityLayer?
    public let waterTemp: ReadyWaterTempLayer?
    public let level: ReadyLayer?

    public var isEmpty: Bool { clarity == nil && waterTemp == nil && level == nil }
}

/// The clarity layer: the copy's lake-wide clarity in feet (the Brain's clarityFt), with its range when the copy carries one that brackets it.
public struct ReadyClarityLayer: Codable, Equatable, Sendable {
    public let status: String
    public let asOf: String
    /// The copy's `centralFt`: the lake-wide value.
    public let valueFt: Double
    public let lowFt: Double?
    public let highFt: Double?
}

/// The water temp layer: the copy's lake-wide surface temperature, °F.
public struct ReadyWaterTempLayer: Codable, Equatable, Sendable {
    public let status: String
    public let asOf: String
    /// The copy's `valueF`.
    public let valueF: Double
}

public struct ReadyLayer: Codable, Equatable, Sendable {
    /// `LIVE` (the copy's AVAILABLE: observed) or `ESTIMATE` (the copy's ESTIMATE: modeled, or a nearby-gauge trend).
    public static let live = "LIVE", estimate = "ESTIMATE"

    public let status: String
    /// The source's own observation time (never a run or write time), ISO 8601 UTC, seconds precision.
    public let asOf: String
}

/// `SECTOR_LAKES_READY_OUTPUT=1` routes `GET /lakes/ready`. Off by default.
public struct LakesReadyConfig: Sendable, Equatable {
    public static let envKey = "SECTOR_LAKES_READY_OUTPUT"
    public var enabled: Bool

    public init(enabled: Bool) { self.enabled = enabled }

    public static func fromEnvironment(_ env: [String: String] = ProcessInfo.processInfo.environment) -> LakesReadyConfig {
        LakesReadyConfig(enabled: env[envKey] == "1")
    }
}

public enum LakesReadyAPI {
    /// The only path this endpoint reads: the parent of every per-lake CUSTOMER-lane copy.
    public static let subtreePath = "customer/lakes"
    /// The per-lake copies evaluated (node names under `customer/lakes/{k}`).
    static let copyLayers = ["clarity", "waterTemp", "level"]

    /// The response, or nil when the endpoint is switched off (the server then has no route: 404).
    public static func response(config: LakesReadyConfig, reader: BrainOutputReader?,
                                extents: [String: ReadyLakeExtent] = [:],
                                levelEligibility: LakeLevelEligibility = .fromEnvironment(),
                                now: Date = Date()) async -> LakesReadyResponse? {
        guard config.enabled else { return nil }
        var snapshot: CustomerLakesSnapshot?
        if let reader { snapshot = try? await fetchSnapshot(reader) }
        return await response(snapshot: snapshot, extents: extents, levelEligibility: levelEligibility, now: now)
    }

    /// The server's form: the snapshot comes from the cache (nil cache = no reader), the extents from the registry cache
    /// (nil = no extents). Both are fetched at the same time. nil when switched off.
    public static func response(config: LakesReadyConfig, cache: LakesReadySnapshotCache?,
                                extents: LakeRegistryExtentCache? = nil,
                                levelEligibility: LakeLevelEligibility = .fromEnvironment(),
                                now: Date = Date()) async -> LakesReadyResponse? {
        guard config.enabled else { return nil }
        async let snapshot = cache?.snapshot()
        async let byLake = extents?.extents()
        let (s, e) = await (snapshot, byLake)
        return await response(snapshot: s, extents: e ?? [:], levelEligibility: levelEligibility, now: now)
    }

    /// One read of `customer/lakes`. Throws when the read fails; nil when the subtree is absent or not an object.
    static func fetchSnapshot(_ reader: BrainOutputReader) async throws -> CustomerLakesSnapshot? {
        guard let data = try await reader.get(subtreePath) else { return nil }
        return CustomerLakesSnapshot(subtree: data)
    }

    static func response(snapshot: CustomerLakesSnapshot?, extents: [String: ReadyLakeExtent],
                         levelEligibility: LakeLevelEligibility, now: Date) async -> LakesReadyResponse {
        let generatedAt = iso(now)
        guard let snapshot else {
            return LakesReadyResponse(version: LakesReadyResponse.currentVersion, generatedAt: generatedAt, lakes: [])
        }

        var lakes: [ReadyLake] = []
        for key in snapshot.lakeKeys {
            // Lake keys are lossy: every directory lake with this key is tried; the readers keep only a copy whose stored
            // `lakeId` matches. A copy for a lake that is not in the directory is never listed (no name, no centroid).
            for lake in directoryByKey[key] ?? [] {
                let layers = await layers(lakeId: lake.id, reader: snapshot, levelEligibility: levelEligibility, now: now)
                guard !layers.isEmpty else { continue }
                lakes.append(ReadyLake(lakeId: lake.id, name: lake.name, centroid: ReadyLakeCentroid(lat: lake.lat, lon: lake.lon),
                                       extent: extents[lake.id], layers: layers))
            }
        }
        lakes.sort { $0.lakeId < $1.lakeId }
        return LakesReadyResponse(version: LakesReadyResponse.currentVersion, generatedAt: generatedAt, lakes: lakes)
    }

    /// One lake's ready layers, each decided by its own #144 reader. A layer's value comes from the same copy; the readers
    /// already refuse a copy without a finite value (`NO_VALUE`), so a ready clarity or water temp layer always has one.
    static func layers(lakeId: String, reader: BrainOutputReader, levelEligibility: LakeLevelEligibility,
                       now: Date) async -> ReadyLakeLayers {
        let c = await ClarityBrainOutputAPI.output(lakeId: lakeId, reader: reader, now: now)
        let t = await WaterTempBrainOutputAPI.output(lakeId: lakeId, reader: reader, now: now)
        let l = await LakeLevelOutputAPI.output(lakeId: lakeId, eligibility: levelEligibility, reader: reader, now: now)
        var clarity: ReadyClarityLayer?
        if let r = layer(c.status, c.observedAt, now: now), let v = BrainCopyRead.finite(c.centralFt) {
            // The range is served only when it brackets the value (low <= value <= high); a bound on the wrong side drops both.
            var low = BrainCopyRead.finite(c.lowFt), high = BrainCopyRead.finite(c.highFt)
            if (low.map { $0 > v } ?? false) || (high.map { $0 < v } ?? false) { low = nil; high = nil }
            clarity = ReadyClarityLayer(status: r.status, asOf: r.asOf, valueFt: v, lowFt: low, highFt: high)
        }
        var waterTemp: ReadyWaterTempLayer?
        if let r = layer(t.status, t.observedAt, now: now), let v = BrainCopyRead.finite(t.valueF) {
            waterTemp = ReadyWaterTempLayer(status: r.status, asOf: r.asOf, valueF: v)
        }
        return ReadyLakeLayers(clarity: clarity, waterTemp: waterTemp, level: layer(l.status, l.observationTime, now: now))
    }

    /// AVAILABLE → LIVE, ESTIMATE → ESTIMATE, anything else (UNKNOWN) → not ready. A time that does not parse, or lies more
    /// than the readers' future-skew bound ahead, is not ready either.
    static func layer(_ status: String, _ observedAt: String?, now: Date) -> ReadyLayer? {
        let mapped: String
        switch status {
        case LakeLevelOutput.available: mapped = ReadyLayer.live
        case LakeLevelOutput.estimate: mapped = ReadyLayer.estimate
        default: return nil
        }
        guard let t = BrainCopyRead.past(observedAt, now: now) else { return nil }
        return ReadyLayer(status: mapped, asOf: iso(t))
    }

    /// ISO 8601 UTC with no fractional seconds ("2026-11-10T12:00:00Z"), as the phone contract requires.
    static func iso(_ d: Date) -> String {
        // A Sendable value-type style (no shared formatter object): UTC, "Z", no fractional seconds.
        Date(timeIntervalSince1970: d.timeIntervalSince1970.rounded(.down)).formatted(.iso8601)
    }

    /// Directory lakes by their RTDB lake key, built once (the directory changes only with a deploy).
    static let directoryByKey: [String: [DirectoryLake]] =
        Dictionary(grouping: LakeDirectory.all, by: { BrainPlatform.lakeKey($0.id) })
}

/// The `customer/lakes` subtree held in memory and served as a `BrainOutputReader` to the per-copy readers. It answers only
/// `customer/lakes/{k}/{clarity|waterTemp|level}`; every other path is refused.
struct CustomerLakesSnapshot: BrainOutputReader, Sendable {
    private let copies: [String: Data]
    let lakeKeys: [String]

    /// nil when `subtree` is not a JSON object (a missing subtree, `null`, is the reader's nil and never gets here).
    init?(subtree: Data) {
        guard let tree = (try? JSONSerialization.jsonObject(with: subtree)) as? [String: Any] else { return nil }
        var copies: [String: Data] = [:]
        for (key, node) in tree {
            guard let lake = node as? [String: Any] else { continue }
            for layer in LakesReadyAPI.copyLayers {
                guard let copy = lake[layer] as? [String: Any],
                      let bytes = try? JSONSerialization.data(withJSONObject: copy) else { continue }
                copies["\(LakesReadyAPI.subtreePath)/\(key)/\(layer)"] = bytes
            }
        }
        self.copies = copies
        self.lakeKeys = tree.keys.sorted()
    }

    func get(_ path: String) async throws -> Data? {
        let parts = path.split(separator: "/", omittingEmptySubsequences: false)
        guard parts.count == 4, parts[0] == "customer", parts[1] == "lakes", !parts[2].isEmpty,
              LakesReadyAPI.copyLayers.contains(String(parts[3])) else {
            throw BrainStoreError("refusing to read \(path): only customer/lakes/{k}/{clarity|waterTemp|level}")
        }
        return copies[path]
    }
}

/// The parsed `customer/lakes` snapshot, kept for `ttl` seconds and fetched once at a time, so a burst of picker opens
/// costs one RTDB read and one parse per minute. Statuses and freshness are still evaluated on every request. A failed
/// read is kept only `failureTTL` seconds (an empty list meanwhile), so an outage neither pins "no lakes" for a minute nor
/// makes every request wait on a new read. An absent or malformed subtree is an answer and is kept the full `ttl`.
public actor LakesReadySnapshotCache {
    private let reader: BrainOutputReader
    private let ttl: TimeInterval
    private let failureTTL: TimeInterval
    private let clock: @Sendable () -> Date
    private var entry: (at: Date, task: Task<CustomerLakesSnapshot?, Error>, failed: Bool)?

    public init(reader: BrainOutputReader, ttl: TimeInterval = 60, failureTTL: TimeInterval = 5,
                clock: @escaping @Sendable () -> Date = { Date() }) {
        self.reader = reader
        self.ttl = ttl
        self.failureTTL = failureTTL
        self.clock = clock
    }

    func snapshot() async -> CustomerLakesSnapshot? {
        let now = clock()
        let task: Task<CustomerLakesSnapshot?, Error>
        if let e = entry, now.timeIntervalSince(e.at) < (e.failed ? failureTTL : ttl) {
            task = e.task
        } else {
            let reader = self.reader
            task = Task { try await LakesReadyAPI.fetchSnapshot(reader) }
            entry = (now, task, false)
        }
        do {
            return try await task.value
        } catch {
            // Keep the failure only briefly, and only if no newer read has replaced it meanwhile.
            if let e = entry, e.task == task, !e.failed { entry = (clock(), task, true) }
            return nil
        }
    }
}
