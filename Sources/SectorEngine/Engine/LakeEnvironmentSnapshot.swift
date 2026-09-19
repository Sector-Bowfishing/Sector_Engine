//
//  LakeEnvironmentSnapshot.swift
//  SectorEngine
//
//  One environmental acquisition per LAKE per TTL, exposed as state rather than
//  as a score.
//
//  The spatial engine ranks ~6,500 shoreline segments on Guntersville. The
//  existing snapshot provider keys its cache per coordinate at ~111 x 92 m, so
//  scoring per segment would land in 5,883 distinct keys and fire roughly 53,000
//  upstream reads — at Cloud Run concurrency 1 that is not slow, it is an
//  outage. This fetches once for the whole lake and hands back normalized
//  `ConditionsInput`s that pure, local transforms derive every segment from.
//
//  WHY SAMPLES, PLURAL. It is tempting to fetch one point and call the result
//  "the lake". At 200 m spacing that is true — measured at Guntersville,
//  Open-Meteo returns identical wind and cloud at 0 m, 200 m and 1 km, changing
//  only around 5 km. But Guntersville is ~50 km end to end, which is many model
//  cells, so one sample genuinely misrepresents the far end. A short list of
//  sample points costs a handful of fetches instead of thousands and keeps the
//  claim honest; a segment reads from its nearest sample.
//
//  Nothing here scores anything. `/conditions` keeps its own path and its exact
//  current behaviour.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

// MARK: - Snapshot

public struct LakeEnvironmentSnapshot: Sendable {

    /// One environmental reading set, valid around `coordinate`.
    public struct Sample: Sendable {
        public let latitude: Double
        public let longitude: Double
        /// The normalized, scorer-ready input — the same type `/conditions`
        /// evaluates, so the spatial engine reuses the factor scorers unchanged
        /// rather than reimplementing them.
        public let input: ConditionsInput
        public let provenance: EnvironmentProvenance
    }

    /// Canonical lake identity, when the coordinate resolves to a known lake.
    public let lakeId: String?
    public let lakeName: String?
    /// The key this snapshot was cached under — lake identity where one exists,
    /// otherwise a rounded coordinate.
    public let cacheKey: String
    public let samples: [Sample]
    public let fetchedAt: Date
    public let ttl: TimeInterval

    public var isEmpty: Bool { samples.isEmpty }

    public func isFresh(at now: Date = Date()) -> Bool {
        now.timeIntervalSince(fetchedAt) < ttl
    }

    /// The sample nearest a point — how a shoreline segment picks up its
    /// lake-wide values without touching the network.
    public func sample(nearLatitude lat: Double, longitude lon: Double) -> Sample? {
        samples.min { a, b in
            Self.squaredDegrees(a, lat, lon) < Self.squaredDegrees(b, lat, lon)
        }
    }

    private static func squaredDegrees(_ s: Sample, _ lat: Double, _ lon: Double) -> Double {
        let dLat = s.latitude - lat
        // Longitude degrees shrink with latitude; at 34°N the factor is ~0.83.
        let dLon = (s.longitude - lon) * cos(lat * .pi / 180)
        return dLat * dLat + dLon * dLon
    }
}

// MARK: - Cache

/// Where lake snapshots live between requests.
///
/// Behind a protocol on purpose. Today it is one actor per Cloud Run instance,
/// which means two phones hitting different instances can see readings taken
/// minutes apart — tolerable for one lake-wide number, much less tolerable once
/// the product ranks segments and two people in the same boat get a different
/// first spot. Swapping in Memorystore later must not touch call sites.
public protocol LakeEnvironmentCache: Sendable {
    func load(key: String, now: Date) async -> LakeEnvironmentSnapshot?
    func store(_ snapshot: LakeEnvironmentSnapshot, key: String) async
}

public actor InProcessLakeEnvironmentCache: LakeEnvironmentCache {
    private var entries: [String: LakeEnvironmentSnapshot] = [:]
    /// Far above the number of lakes anyone fishes in one TTL.
    private let maxEntries: Int

    public init(maxEntries: Int = 200) { self.maxEntries = maxEntries }

    public func load(key: String, now: Date) async -> LakeEnvironmentSnapshot? {
        guard let hit = entries[key], hit.isFresh(at: now) else { return nil }
        return hit
    }

    public func store(_ snapshot: LakeEnvironmentSnapshot, key: String) async {
        entries[key] = snapshot
        guard entries.count > maxEntries else { return }
        let overflow = entries.count - maxEntries
        for k in entries.sorted(by: { $0.value.fetchedAt < $1.value.fetchedAt })
            .prefix(overflow).map(\.key) {
            entries.removeValue(forKey: k)
        }
    }
}

// MARK: - Provider

public actor LakeEnvironmentProvider {

    public static let shared = LakeEnvironmentProvider()

    /// Matches the existing snapshot and response caches: these inputs move on
    /// the order of an hour, and a lake's conditions barely shift in five
    /// minutes.
    public static let defaultTTL: TimeInterval = 5 * 60

    /// How far a coordinate can sit from a directory lake and still be treated
    /// as on it. Matches `/conditions`' own resolution radius.
    ///
    /// This is a radius from a single directory coordinate, which is a poor fit
    /// for a long reservoir: Guntersville runs ~31 miles from the dam to
    /// Bridgeport, so its upper end falls outside its own 25-mile radius and
    /// resolves to no lake at all. Verified — a point at 34.73/−85.98, which is
    /// unambiguously Guntersville water, came back unresolved and minted its own
    /// acquisition.
    ///
    /// For scoring that is a minor mislabel. For Fish Intelligence it is the
    /// whole fan-out problem returning: every upper-lake segment would key
    /// separately. So a caller that already knows which lake it is scoring
    /// passes `lakeId` and bypasses the geometry question entirely.
    public static let lakeMatchMiles: Double = 25

    private let cache: LakeEnvironmentCache
    private var inFlight: [String: Task<LakeEnvironmentSnapshot?, Never>] = [:]

    public init(cache: LakeEnvironmentCache = InProcessLakeEnvironmentCache()) {
        self.cache = cache
    }

    /// The lake's environment, fetched once per TTL and shared by every caller.
    ///
    /// - Parameter samplePoints: extra coordinates to read, for a reservoir long
    ///   enough that one sample misrepresents the far end. The requested
    ///   coordinate is always sampled. Keep this to a handful — the whole point
    ///   is that it does not scale with segment count.
    /// - Parameter lakeId: the directory id (`"Name|ST"`) when the caller
    ///   already knows the waterbody. Fish Intelligence always does — it is
    ///   scoring one named lake's segments — and passing it guarantees every
    ///   segment shares one acquisition regardless of how long the reservoir is.
    public func snapshot(latitude: Double, longitude: Double,
                         lakeId: String? = nil,
                         samplePoints: [(latitude: Double, longitude: Double)] = [],
                         force: Bool = false,
                         now: Date = Date()) async -> LakeEnvironmentSnapshot? {
        let coord = CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
        let lake = lakeId.flatMap { id in LakeDirectory.all.first { $0.id == id } }
            ?? LakeDirectory.nearest(to: coord, withinMiles: Self.lakeMatchMiles)
        let key = Self.cacheKey(lake: lake, latitude: latitude, longitude: longitude)

        if let running = inFlight[key] { return await running.value }
        if !force, let hit = await cache.load(key: key, now: now) { return hit }

        let points = Self.dedupe([(latitude, longitude)] + samplePoints)
        let task = Task<LakeEnvironmentSnapshot?, Never> { [cache] in
            var samples: [LakeEnvironmentSnapshot.Sample] = []
            for p in points {
                let c = CLLocationCoordinate2D(latitude: p.latitude, longitude: p.longitude)
                let snap = await ConditionsSnapshotProvider.shared.snapshot(for: c, force: force)
                guard snap.hasAnyLiveInput else { continue }
                let built = ConditionsInputBuilder.buildDetailed(
                    coordinate: c, date: now,
                    weather: snap.weather, water: snap.water, discharge: snap.discharge,
                    waterTempC: snap.waterTemp,
                    modeledWaterTempF: snap.waterTempModel?.currentF,
                    turbidity: snap.turbidity, generation: snap.generation,
                    alertWindFloorMph: snap.alertWindFloorMph,
                    severeWarningLabel: snap.severeWarningLabel,
                    rainWatershed72hIn: snap.mrms?.watershed72hIn)
                samples.append(.init(latitude: p.latitude, longitude: p.longitude,
                                     input: built.input, provenance: built.provenance))
            }
            guard !samples.isEmpty else { return nil }
            let result = LakeEnvironmentSnapshot(
                lakeId: lake?.id, lakeName: lake?.name, cacheKey: key,
                samples: samples, fetchedAt: now, ttl: Self.defaultTTL)
            await cache.store(result, key: key)
            return result
        }
        inFlight[key] = task
        let result = await task.value
        inFlight[key] = nil
        return result
    }

    /// Lake identity where one exists, so every point on one reservoir shares a
    /// single acquisition. Off-lake it falls back to a rounded coordinate — a
    /// river spot must not collide with the next one downstream.
    static func cacheKey(lake: DirectoryLake?, latitude: Double, longitude: Double) -> String {
        if let lake { return "lake:\(lake.id)" }
        return String(format: "pt:%.3f,%.3f", latitude, longitude)
    }

    /// Drop sample points that land in the same ~1 km cell — they would return
    /// the same model grid values and cost a fetch to prove it.
    static func dedupe(_ points: [(latitude: Double, longitude: Double)])
        -> [(latitude: Double, longitude: Double)] {
        var seen = Set<String>()
        var out: [(latitude: Double, longitude: Double)] = []
        for p in points {
            let k = String(format: "%.2f,%.2f", p.latitude, p.longitude)
            if seen.insert(k).inserted { out.append(p) }
        }
        return out
    }
}
