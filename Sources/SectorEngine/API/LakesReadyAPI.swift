//
//  LakesReadyAPI.swift
//  Sector — `GET /lakes/ready`: the lakes with real Brain data, for the app's lake picker (Sector_Engine #156, iOS_Sector #227).
//
//  A lake is "ready" when at least one of its CUSTOMER-lane copies is usable right now: status not UNKNOWN and not stale.
//  The decision is made by the existing per-copy readers (#144: ClarityBrainOutputAPI, WaterTempBrainOutputAPI and
//  LakeLevelOutputAPI), so the freshness bounds and the status rules are theirs. On top, `/lakes/ready` applies the
//  readers' 10-minute future-time bound (`BrainCopyRead.past`) to every layer's `asOf`, `level` included. Nothing
//  here reads a Brain INTERNAL path (`/lakes/*/states`, `/brains/*`); every read goes through `BrainOutputReader` and stays
//  under `customer/lakes`. Design note: docs/architecture/data/CUSTOMER_BRAIN_OUTPUT_PATH_V1.md §9.
//
//  Read pattern: ONE read of `customer/lakes` (the subtree that holds every per-lake copy), then each lake's copies are
//  evaluated by the readers against that in-memory snapshot. Reading each directory lake's three copies would be ~1,900
//  reads per request. The subtree also carries the `generationBinding` copies (customer lane too); they are not parsed.
//  The snapshot reader serves only `customer/lakes/{k}/{clarity|waterTemp|level}` and refuses any other path. The server
//  keeps the parsed snapshot for 60 s (`LakesReadySnapshotCache`); a failed read is not kept.
//
//  Gates (all default OFF / fail closed):
//    - `SECTOR_LAKES_READY_OUTPUT=1` routes the endpoint. Unset: the server registers no route (404, like `/lake/level`).
//    - `SECTOR_BRAIN_OUTPUT_READER` picks the reader (BrainOutputReaderConfig). Unset: no reader → `200` with no lakes.
//    - A failed or refused read of the subtree → `200` with no lakes (the app shows "no lakes yet").
//    - The `level` layer also needs the Lake level gates: `SECTOR_LAKE_LEVEL_OUTPUT=1` and the lake on `validatedLakeIds`.
//
//  Layers: `clarity`, `waterTemp` and `level` have CUSTOMER-lane copies. `wind` and `intelligence` have none per lake today
//  (wind's only copy is the global `customer/wind/outlookModel`, a model choice, not a lake value; Intelligence has no
//  copy), so v1 never emits them. A layer is present only when it is ready; an absent layer means "not yet for this lake".
//  Contract: contracts/phone/lakes-ready-v1.json.
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
    public let name: String
    public let centroid: ReadyLakeCentroid
    public let layers: ReadyLakeLayers
}

/// The directory coordinate (`GET /lakes` `lat`/`lon`).
public struct ReadyLakeCentroid: Codable, Equatable, Sendable {
    public let lat: Double
    public let lon: Double
}

/// Each key is present only when that layer is ready. v1 never emits `wind` or `intelligence` (no per-lake copy exists).
public struct ReadyLakeLayers: Codable, Equatable, Sendable {
    public let clarity: ReadyLayer?
    public let waterTemp: ReadyLayer?
    public let level: ReadyLayer?

    public var isEmpty: Bool { clarity == nil && waterTemp == nil && level == nil }
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
                                levelEligibility: LakeLevelEligibility = .fromEnvironment(),
                                now: Date = Date()) async -> LakesReadyResponse? {
        guard config.enabled else { return nil }
        var snapshot: CustomerLakesSnapshot?
        if let reader { snapshot = try? await fetchSnapshot(reader) }
        return await response(snapshot: snapshot, levelEligibility: levelEligibility, now: now)
    }

    /// The server's form: the snapshot comes from the cache (nil cache = no reader). nil when switched off.
    public static func response(config: LakesReadyConfig, cache: LakesReadySnapshotCache?,
                                levelEligibility: LakeLevelEligibility = .fromEnvironment(),
                                now: Date = Date()) async -> LakesReadyResponse? {
        guard config.enabled else { return nil }
        let snapshot = await cache?.snapshot()
        return await response(snapshot: snapshot, levelEligibility: levelEligibility, now: now)
    }

    /// One read of `customer/lakes`. Throws when the read fails; nil when the subtree is absent or not an object.
    static func fetchSnapshot(_ reader: BrainOutputReader) async throws -> CustomerLakesSnapshot? {
        guard let data = try await reader.get(subtreePath) else { return nil }
        return CustomerLakesSnapshot(subtree: data)
    }

    static func response(snapshot: CustomerLakesSnapshot?, levelEligibility: LakeLevelEligibility,
                         now: Date) async -> LakesReadyResponse {
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
                lakes.append(ReadyLake(lakeId: lake.id, name: lake.name,
                                       centroid: ReadyLakeCentroid(lat: lake.lat, lon: lake.lon), layers: layers))
            }
        }
        lakes.sort { $0.lakeId < $1.lakeId }
        return LakesReadyResponse(version: LakesReadyResponse.currentVersion, generatedAt: generatedAt, lakes: lakes)
    }

    /// One lake's ready layers, each decided by its own #144 reader.
    static func layers(lakeId: String, reader: BrainOutputReader, levelEligibility: LakeLevelEligibility,
                       now: Date) async -> ReadyLakeLayers {
        let c = await ClarityBrainOutputAPI.output(lakeId: lakeId, reader: reader, now: now)
        let t = await WaterTempBrainOutputAPI.output(lakeId: lakeId, reader: reader, now: now)
        let l = await LakeLevelOutputAPI.output(lakeId: lakeId, eligibility: levelEligibility, reader: reader, now: now)
        return ReadyLakeLayers(clarity: layer(c.status, c.observedAt, now: now),
                               waterTemp: layer(t.status, t.observedAt, now: now),
                               level: layer(l.status, l.observationTime, now: now))
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
        isoOut.string(from: Date(timeIntervalSince1970: d.timeIntervalSince1970.rounded(.down)))
    }

    /// Built once (expensive to create; thread-safe to use). Default options: internet date-time, UTC, no fractional seconds.
    nonisolated(unsafe) static let isoOut = ISO8601DateFormatter()

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
/// read is not kept: the next request tries again (an absent or malformed subtree is kept, as an answer).
public actor LakesReadySnapshotCache {
    private let reader: BrainOutputReader
    private let ttl: TimeInterval
    private let clock: @Sendable () -> Date
    private var entry: (at: Date, task: Task<CustomerLakesSnapshot?, Error>)?

    public init(reader: BrainOutputReader, ttl: TimeInterval = 60, clock: @escaping @Sendable () -> Date = { Date() }) {
        self.reader = reader
        self.ttl = ttl
        self.clock = clock
    }

    func snapshot() async -> CustomerLakesSnapshot? {
        let now = clock()
        let task: Task<CustomerLakesSnapshot?, Error>
        if let e = entry, now.timeIntervalSince(e.at) < ttl {
            task = e.task
        } else {
            let reader = self.reader
            task = Task { try await LakesReadyAPI.fetchSnapshot(reader) }
            entry = (now, task)
        }
        do {
            return try await task.value
        } catch {
            if let e = entry, e.task == task { entry = nil }   // never keep a failure
            return nil
        }
    }
}
