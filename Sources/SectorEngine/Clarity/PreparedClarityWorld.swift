//
//  PreparedClarityWorld.swift
//  Sector — a lake's Current Clarity world, prepared by a scheduled job
//  (Clarity Fusion Stage 5)
//
//  A live build reads 45 days of hourly hydrology, every arm's gauges and the
//  chosen scenes' cells: 36–50 s, too slow for a request. The hourly job
//  (ClarityPrecompute) runs that same build and publishes
//
//      clarity/current/<slug>/world.json               this file: regions, scenes, table, overview
//      clarity/current/<slug>/composite-<etag>.bin     the map's composite (ClarityComposite.encoded)
//      clarity/current/<slug>/composite-<etag>.bin.gz  the same bytes, gzip
//      clarity/current/<slug>/changes.json             each arm's change since each recent hour
//
//  The routes read these and resolve each request at its own time: scene
//  ages and the table are the request's, the hydrology is the job's.
//
//  STALENESS. A prepared world is only as current as its hydrology:
//    ≤ 2 h old    current: served as it is
//    ≤ 12 h old   stale: served, but no drainage counts as stable or minor —
//                 it has not been re-checked — so nothing is High, and each
//                 region says when it was last checked
//    older        expired: not served; the route builds live instead
//

import Foundation

public struct PreparedClarityWorld: Codable, Equatable {
    public static let schemaId = "current-clarity-world-v1"

    public enum Freshness: String, Codable, Equatable { case current, stale, expired, live }

    public struct Provenance: Codable, Equatable {
        /// The newest hour of rain any region's record reaches.
        public let hydrologyThrough: Date?
        public let newestScene: String?
        public let oldestScene: String?
        /// The engine commit the job ran (SECTOR_ENGINE_COMMIT), if it was given one.
        public let engineCommit: String?
        public let buildSeconds: Double?
        public init(hydrologyThrough: Date?, newestScene: String?, oldestScene: String?, engineCommit: String?, buildSeconds: Double?) {
            self.hydrologyThrough = hydrologyThrough; self.newestScene = newestScene; self.oldestScene = oldestScene
            self.engineCommit = engineCommit; self.buildSeconds = buildSeconds
        }
    }
    public struct Files: Codable, Equatable {
        public let composite: String
        public let compositeGzip: String
        public let compositeBytes: Int
        public let compositeGzipBytes: Int
        public let changes: String?
        public init(composite: String, compositeGzip: String, compositeBytes: Int, compositeGzipBytes: Int, changes: String?) {
            self.composite = composite; self.compositeGzip = compositeGzip; self.compositeBytes = compositeBytes
            self.compositeGzipBytes = compositeGzipBytes; self.changes = changes
        }
    }

    public let schema: String
    public let lakeId: String
    public let builtAt: Date
    public let indexHash: UInt32
    /// The composite's ETag (CurrentClarityWorld.etag).
    public let etag: String
    public let scenes: [ClaritySceneRef]
    public let sceneForRegion: [Int?]
    public let regions: [ClarityRegionContext?]
    public let notes: [String]
    /// The table as it stood at `builtAt`, for audit; requests re-resolve it.
    public let outcomes: [[CurrentClarityResolver.Outcome]]
    public let provenance: Provenance
    public let files: Files

    /// A world the job built, ready to publish.
    public init(world: CurrentClarityWorld, provenance: Provenance, files: Files) {
        schema = Self.schemaId; lakeId = world.lakeId; builtAt = world.now; indexHash = world.index.hash
        etag = world.etag; scenes = world.composite.refs; sceneForRegion = world.composite.sceneForRegion
        regions = world.regions; notes = world.notes; outcomes = world.outcomeTable()
        self.provenance = provenance; self.files = files
    }

    public static let currentMaxAge: TimeInterval = 2 * 3600
    public static let staleMaxAge: TimeInterval = 12 * 3600

    public func freshness(at now: Date) -> Freshness {
        let age = now.timeIntervalSince(builtAt)
        return age <= Self.currentMaxAge ? .current : age <= Self.staleMaxAge ? .stale : .expired
    }

    /// The regions as a request at `now` may use them.
    public func regions(at now: Date) -> [ClarityRegionContext?] {
        freshness(at: now) == .current ? regions : regions.map { $0.map { Self.unchecked($0, since: builtAt) } }
    }

    /// A drainage last checked at `since`: whatever was stable or minor may have
    /// changed in the hours since, so it is unknown — which caps it at moderate.
    static func unchecked(_ c: ClarityRegionContext, since: Date) -> ClarityRegionContext {
        let note = "Drainage last checked \(CurrentClarityResolver.shortDateTime(since)); the hourly update is late."
        let runoff = c.runoff.state == .stable || c.runoff.state == .minorChange
            ? RunoffState(state: .unknown, expectedDirection: "unknown", magnitude: c.runoff.magnitude,
                          evidence: c.runoff.evidence + [note])
            : c.runoff
        return ClarityRegionContext(
            kind: c.kind, id: c.id, name: c.name, scene: c.scene, anchorStrength: c.anchorStrength,
            anchorNote: c.anchorNote, runoff: runoff, rainSinceSceneIn: c.rainSinceSceneIn,
            rainRecordThrough: c.rainRecordThrough, flowProvenance: c.flowProvenance, flowSource: c.flowSource,
            flowChangeRatio: c.flowChangeRatio, catchmentCompleteness: c.catchmentCompleteness,
            limitations: c.limitations + [note])
    }
}

/// Each arm's hydrologic change since each of the last hours (report freshness,
/// GET /clarity/current/change), prepared with the world.
public struct PreparedClarityChanges: Codable, Equatable {
    public static let schemaId = "current-clarity-changes-v1"
    public struct Mark: Codable, Equatable {
        public let since: Date
        public let change: HydrologicChange
    }
    public let schema: String
    public let lakeId: String
    public let builtAt: Date
    /// region id → marks, oldest first, one per whole hour.
    public let regions: [String: [Mark]]

    /// Hours back from the build that are prepared: a report is fresh for at most 12 h.
    public static let hours = 13

    /// The change since `since`, measured from the whole hour at or before it:
    /// an earlier start takes in at least as much rain and flow, never less.
    public func change(region: String, since: Date) -> HydrologicChange? {
        guard let marks = regions[region] else { return nil }
        return marks.last { $0.since <= since }?.change
    }
}
