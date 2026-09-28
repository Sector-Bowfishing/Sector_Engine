//
//  CurrentClarityAPI.swift
//  Sector — the Current Clarity Engine's endpoints (Clarity Fusion Stage 4)
//
//  GET /clarity/current?lake=&lat=&lon=[&legacy=1]    one coordinate's CurrentClarityEstimate
//  GET /clarity/current/lake?lake=                    the map's summary: scenes, regions, and the
//                                                     outcome table for every kind of cell
//  GET /clarity/current/cells?lake=                   the composite, one file (ClarityComposite.encoded)
//  GET /clarity/current/change?lake=&region=&since=   a region's hydrologic change since a moment
//                                                     (a report's freshness; no coordinate is sent)
//
//  The map and a tap cannot disagree: the map colours each cell from the
//  composite and takes its confidence from the table, and the table is the
//  resolver's own decision for that kind of cell (CurrentClarityResolver.outcome).
//
//  REVIEW BUILD. Routed only where SECTOR_CURRENT_CLARITY_ROUTES=1.
//

import Foundation

public struct CurrentClarityLake: Codable, Equatable {
    public static let schemaId = "current-clarity-lake-v1"

    public struct Legend: Codable, Equatable {
        public let title: String
        public let clearLabel: String
        public let muddyLabel: String
        public let sourceLine: String
    }
    public struct Region: Codable, Equatable {
        public let index: Int
        public let kind: ClarityRegionContext.Kind
        public let id: String
        public let name: String
        public let sceneIndex: Int?
        public let anchorStrength: AnchorStrength
        public let runoffState: RunoffClass
        public let expectedDirection: String
        public let hydrologicCap: AuthorityLevel
        public let catchmentCompleteness: CatchmentCompleteness
        public let flowProvenance: String
        public let summary: String
    }
    public struct Cells: Codable, Equatable {
        public let path: String
        public let etag: String
        public let count: Int
        public let width: Int
        public let height: Int
        public let cornersLonLat: [[Double]]
        /// value: log10 FNU, 1..254 over log10 0.5..200; dist: 1 + m / 100 (254 = no path)
        public let encoding: String
    }

    public let schema: String
    public let lakeId: String
    public let generatedAt: Date
    public let legend: Legend
    public let scenes: [ClaritySceneRef]
    public let regions: [Region]
    /// Evidence keys, in `outcomes` column order: direct, filled≤500, filled≤5000,
    /// filled>5000, grass≤5000, grass>5000, none. `evidenceKey(code:dist:)` maps a cell.
    public let evidenceKeys: [String]
    /// outcomes[region][key]
    public let outcomes: [[CurrentClarityResolver.Outcome]]
    public let cells: Cells
    public let notes: [String]
    /// Stage 5. current | stale | live (see PreparedClarityWorld); nil before Stage 5.
    public let freshness: PreparedClarityWorld.Freshness?
    /// When the job prepared this world (nil for a live build).
    public let preparedAt: Date?
    /// The words for each internal confidence (two user-facing tiers, Stage 5).
    public let confidenceLabels: [String: String]?
    /// The whole lake in a few numbers, for a summary that no single point can give.
    public let overview: Overview?

    /// Share of the lake's water by what Sector can say about it now.
    public struct Overview: Codable, Equatable {
        public let waterCells: Int
        /// A current number (levels A–D).
        public let supportedPct: Double
        /// The drainage changed since the scene: only a last supported number (E).
        public let changedPct: Double
        /// No supported number: too far from a reading, no scene, or a grass bed (F).
        public let unsupportedPct: Double
        /// Grass beds, part of `unsupportedPct`.
        public let grassPct: Double
        /// Share of water by user-facing confidence among the supported.
        public let byConfidence: [String: Double]
        /// Central feet over supported water: 10th, 50th and 90th percentiles.
        public let supportedFtP10: Double?
        public let supportedFtP50: Double?
        public let supportedFtP90: Double?
        /// The scenes the regions stand on.
        public let newestObservation: Date?
        public let oldestObservation: Date?
        public let headline: String
    }

    public static let keys = ["direct", "filled<=500", "filled<=5000", "filled>5000", "grass<=5000", "grass>5000", "none"]

    /// A composite cell's column in `outcomes`.
    public static func evidenceKey(code: UInt8, dist: UInt8) -> Int {
        let d = ClarityCellCode.distanceM(dist) ?? .infinity
        switch code {
        case 255: return 0
        case 1, 2: return d <= CurrentClarityResolver.Rules.filledModerateMaxM ? 1
            : d <= CurrentClarityResolver.Rules.filledMaxM ? 2 : 3
        case 3: return d <= CurrentClarityResolver.Rules.filledMaxM ? 4 : 5
        default: return 6
        }
    }

    /// A representative cell of each key, for the resolver.
    static func representative(_ k: Int) -> ClarityCellEvidence {
        switch k {
        case 0: return ClarityCellEvidence(kind: .direct, fnu: 4, distanceToObservedM: 0)
        case 1: return ClarityCellEvidence(kind: .filled, fnu: 4, distanceToObservedM: 300, fillReason: "unreadable")
        case 2: return ClarityCellEvidence(kind: .filled, fnu: 4, distanceToObservedM: 2_000, fillReason: "unreadable")
        case 3: return ClarityCellEvidence(kind: .filled, fnu: 4, distanceToObservedM: 8_000, fillReason: "unreadable")
        case 4: return ClarityCellEvidence(kind: .grassBed, fnu: 4, distanceToObservedM: 300)
        case 5: return ClarityCellEvidence(kind: .grassBed, fnu: 4, distanceToObservedM: 8_000)
        default: return ClarityCellEvidence(kind: .none, fnu: nil, distanceToObservedM: nil)
        }
    }
}

/// Everything the endpoints need for one lake at one moment.
public struct CurrentClarityWorld {
    public let lakeId: String
    public let now: Date
    public let index: ClarityRegionsIndex
    public let composite: ClarityComposite
    /// Region index → its context (nil where the region has no water on the index).
    public let regions: [ClarityRegionContext?]
    public let notes: [String]
    /// Stage 5: whether the job prepared this world, and how fresh it is.
    public let freshness: PreparedClarityWorld.Freshness
    public let preparedAt: Date?
    /// The job's own composite files, served as they are (nil for a live build).
    public let compositeBytes: [UInt8]?
    public let compositeGzip: [UInt8]?

    public init(lakeId: String, now: Date, index: ClarityRegionsIndex, composite: ClarityComposite,
                regions: [ClarityRegionContext?], notes: [String], freshness: PreparedClarityWorld.Freshness = .live,
                preparedAt: Date? = nil, compositeBytes: [UInt8]? = nil, compositeGzip: [UInt8]? = nil) {
        self.lakeId = lakeId; self.now = now; self.index = index; self.composite = composite
        self.regions = regions; self.notes = notes; self.freshness = freshness; self.preparedAt = preparedAt
        self.compositeBytes = compositeBytes; self.compositeGzip = compositeGzip
    }

    /// The same world as a request at `now` sees it.
    public func at(_ now: Date) -> CurrentClarityWorld {
        CurrentClarityWorld(lakeId: lakeId, now: now, index: index, composite: composite, regions: regions, notes: notes,
                            freshness: freshness, preparedAt: preparedAt, compositeBytes: compositeBytes,
                            compositeGzip: compositeGzip)
    }

    public func estimate(lat: Double, lon: Double, legacy: LegacyClarityEstimate? = nil,
                         inSitu: InSituTurbidity? = nil) -> CurrentClarityEstimate {
        guard let i = index.index(lat: lat, lon: lon) else {
            return CurrentClarityResolver.estimate(lakeId: lakeId, lat: lat, lon: lon, region: nil, zone: nil,
                                                   cell: nil, legacy: legacy, now: now)
        }
        return estimate(cell: i, lat: lat, lon: lon, legacy: legacy, inSitu: inSitu)
    }

    public func estimate(cell i: Int, lat: Double, lon: Double, legacy: LegacyClarityEstimate? = nil,
                         inSitu: InSituTurbidity? = nil) -> CurrentClarityEstimate {
        let r = Int(index.region[i])
        let z = Int(index.zone[i])
        let zone = z >= 0 ? index.zones[z].map { (id: z, name: "\($0.name) (\($0.index + 1) of \($0.of))") } : nil
        return CurrentClarityResolver.estimate(lakeId: lakeId, lat: lat, lon: lon,
                                               region: r < regions.count ? regions[r] : nil, zone: zone,
                                               cell: composite.evidence(atCell: i), inSitu: inSitu,
                                               legacy: legacy, now: now)
    }

    public var etag: String {
        var h: UInt32 = 0x811C9DC5
        let key = "\(index.hash)|" + composite.sceneForRegion.map { $0.map { composite.refs[$0].date } ?? "-" }.joined(separator: ",")
        for b in key.utf8 { h ^= UInt32(b); h = h &* 0x01000193 }
        return String(format: "%08x", h)
    }

    public func lakeSummary(path: String) -> CurrentClarityLake {
        let summaries: [CurrentClarityLake.Region] = regions.enumerated().compactMap { (k, c) in
            guard let c else { return nil }
            let cap = CurrentClarityResolver.Rules.hydrologicCap(c.runoff.state)
            let when = c.scene.map { "Sentinel-2 \(CurrentClarityResolver.shortDate($0.time))" } ?? "no scene"
            let state: String = {
                switch c.runoff.state {
                case .stable: return "drainage stable since"
                case .minorChange: return "minor change since"
                case .moderateRunoff: return "runoff since"
                case .majorRunoff: return "major runoff since"
                case .recovering: return "runoff since, now receding"
                case .unknown: return "change since unknown"
                }
            }()
            return .init(index: k, kind: c.kind, id: c.id, name: c.name,
                         sceneIndex: k < composite.sceneForRegion.count ? composite.sceneForRegion[k] : nil,
                         anchorStrength: c.anchorStrength, runoffState: c.runoff.state,
                         expectedDirection: c.runoff.expectedDirection, hydrologicCap: cap,
                         catchmentCompleteness: c.catchmentCompleteness, flowProvenance: c.flowProvenance,
                         summary: "\(c.name): \(when) · \(state)")
        }
        let table = outcomeTable()
        return CurrentClarityLake(
            schema: CurrentClarityLake.schemaId, lakeId: lakeId, generatedAt: now,
            legend: .init(title: "Water Clarity", clearLabel: "Clear", muddyLabel: "Muddy",
                          sourceLine: "Sentinel-2 · latest usable observations"),
            scenes: composite.refs, regions: summaries, evidenceKeys: CurrentClarityLake.keys,
            outcomes: table,
            cells: .init(path: path, etag: etag, count: index.count, width: index.width, height: index.height,
                         cornersLonLat: index.cornersLonLat,
                         encoding: "SCCC v1: value log10 FNU 1..254 over log10(0.5)..log10(200); code 255 read, 1 unreadable, 2 cloud, 3 grass, 0 none; dist 1 + m/100, 254 no path"),
            notes: notes, freshness: freshness, preparedAt: preparedAt,
            confidenceLabels: Dictionary(uniqueKeysWithValues: [ClarityConfidence.none, .low, .moderate, .high].map { ($0.rawValue, $0.presentedLabel) }),
            overview: overview(table: table))
    }

    /// The resolver's decision for every region × kind of cell, at `now`.
    public func outcomeTable() -> [[CurrentClarityResolver.Outcome]] {
        let none = CurrentClarityResolver.Outcome(level: .none, confidence: .none, authority: .none, magnitudeSupported: false)
        return regions.map { c in
            guard let c else { return Array(repeating: none, count: CurrentClarityLake.keys.count) }
            return CurrentClarityLake.keys.indices.map {
                CurrentClarityResolver.outcome(region: c, cell: CurrentClarityLake.representative($0), now: now)
            }
        }
    }

    /// The whole lake, cell by cell through the table: what share of the
    /// water has a current number, and what those numbers are. A lake is not
    /// one point, so the dashboard reads this instead of a coordinate.
    public func overview(table: [[CurrentClarityResolver.Outcome]]) -> CurrentClarityLake.Overview {
        let n = index.count
        var supported = 0, changed = 0, grass = 0
        var byConf: [String: Int] = [:]
        var ftBins = [Int](repeating: 0, count: 301)       // 0.1 ft, 0..30 ft
        for i in 0..<n {
            let r = Int(index.region[i])
            let key = composite.scene(atCell: i) == nil ? CurrentClarityLake.keys.count - 1
                : CurrentClarityLake.evidenceKey(code: composite.code[i], dist: composite.dist[i])
            if key == 4 || key == 5 { grass += 1 }
            guard r < table.count else { continue }
            let o = table[r][key]
            if o.magnitudeSupported {
                supported += 1
                byConf[o.confidence.presentedLabel, default: 0] += 1
                if let fnu = ClarityCellCode.fnu(composite.value[i]) {
                    ftBins[min(300, Int((VisibilityModel.centralFt(fnu: fnu) * 10).rounded()))] += 1
                }
            } else if o.level == .changedHistorical {
                changed += 1
            }
        }
        func pct(_ k: Int) -> Double { n > 0 ? (Double(k) / Double(n) * 1000).rounded() / 1000 : 0 }
        func quantile(_ q: Double) -> Double? {
            let total = ftBins.reduce(0, +)
            guard total > 0 else { return nil }
            var c = 0
            for (b, k) in ftBins.enumerated() { c += k; if Double(c) >= q * Double(total) { return Double(b) / 10 } }
            return nil
        }
        let times = composite.refs.map(\.time)
        let sp = pct(supported), cp = pct(changed)
        let p10 = quantile(0.1), p50 = quantile(0.5), p90 = quantile(0.9)
        func words(_ p: Double) -> String { p > 0 && p < 0.005 ? "under 1%" : "\(Int((p * 100).rounded()))%" }
        var parts = [sp >= 0.995 ? "A current estimate for all of the water" : "\(words(sp)) of the water has a current estimate"]
        if let a = p10, let b = p90 {
            parts.append(String(format: a == b ? "about %.1f ft where known" : "%.1f–%.1f ft where known", a, b))
        }
        if cp >= 0.05 { parts.append("\(words(cp)) has changed since its last clear view") }
        return CurrentClarityLake.Overview(
            waterCells: n, supportedPct: sp, changedPct: cp, unsupportedPct: max(0, (1000 - (sp * 1000).rounded() - (cp * 1000).rounded()) / 1000),
            grassPct: pct(grass), byConfidence: byConf.mapValues(pct),
            supportedFtP10: p10, supportedFtP50: p50, supportedFtP90: p90,
            newestObservation: times.max(), oldestObservation: times.min(), headline: parts.joined(separator: " · "))
    }
}

actor CurrentClarityCache {
    static let shared = CurrentClarityCache()
    private var scenes: [String: ClaritySceneCells] = [:]
    private var worlds: [String: (at: Date, world: CurrentClarityWorld)] = [:]
    static let worldMaxAge: TimeInterval = 10 * 60

    func scene(_ key: String, load: @Sendable () async -> ClaritySceneCells?) async -> ClaritySceneCells? {
        if let s = scenes[key] { return s }
        let s = await load()
        if let s { scenes[key] = s }
        return s
    }

    func world(_ key: String, build: @Sendable () async -> CurrentClarityWorld?) async -> CurrentClarityWorld? {
        if let w = worlds[key], Date().timeIntervalSince(w.at) < Self.worldMaxAge { return w.world }
        let w = await build()
        if let w { worlds[key] = (Date(), w) }
        return w
    }
}

/// Each region's context and the scene it stands on. Pure, and shared by the
/// live world and the Stage 4 replay, so the replay tests exactly this.
public enum CurrentClarityRegions {
    public static func build(arms: [ArmClarityInputs], mainStem: MainStemClarityInputs,
                             newest: [String: SatelliteAnchor], now: Date)
        -> (contexts: [String: ClarityRegionContext], scenes: [String: SatelliteAnchor]) {
        var byId: [String: ClarityRegionContext] = [:]
        var scene: [String: SatelliteAnchor] = [:]
        for x in arms {
            let s = ClarityStateEngine.armState(x, now: now)
            if let a = x.anchor {
                scene[x.armId] = a
                byId[x.armId] = SectorEngineAPI.regionContext(s, anchor: a, note: x.anchorNote)
            } else if let a = newest[x.armId] {
                // No scene reads this arm: stand on the newest one's fill, and
                // measure the drainage from it (the cells' distances decide
                // what that fill can carry).
                scene[x.armId] = a
                let d = ClarityStateEngine.divergence(anchor: a, rain: x.rain, flow: x.flow, now: now)
                let r = ClarityStateEngine.runoff(d, hasAnchor: true)
                let c = SectorEngineAPI.regionContext(s, anchor: a, note: "No scene in the last 45 days reads this arm; its values are the \(a.sceneDate) scene's fill from readings elsewhere.")
                byId[x.armId] = ClarityRegionContext(
                    kind: .arm, id: c.id, name: c.name, scene: c.scene, anchorStrength: .none, anchorNote: c.anchorNote,
                    runoff: r, rainSinceSceneIn: d.rainSincePassIn, rainRecordThrough: d.rainValidThrough,
                    flowProvenance: d.dischargeProvenance.rawValue, flowSource: d.dischargeSource,
                    flowChangeRatio: d.dischargePeakRatioToPass, catchmentCompleteness: c.catchmentCompleteness,
                    limitations: c.limitations)
            } else {
                byId[x.armId] = SectorEngineAPI.regionContext(s, anchor: nil, note: x.anchorNote)
            }
        }
        let ms = ClarityStateEngine.mainStemState(mainStem, now: now)
        let msAnchor = mainStem.anchor ?? newest[ClarityStateLoader.mainStemKey]
        if let a = msAnchor { scene[ClarityStateLoader.mainStemKey] = a }
        byId[ClarityStateLoader.mainStemKey] = SectorEngineAPI.regionContext(ms, anchor: msAnchor)
        return (byId, scene)
    }
}

extension SectorEngineAPI {

    /// The lake's current world: the hourly job's prepared one while it is
    /// fresh enough (Stage 5), otherwise a live build of every arm's state and
    /// its chosen scene's cells. Either is resolved at the request's own time.
    public static func currentClarityWorld(lakeId: String, now: Date = Date()) async -> CurrentClarityWorld? {
        if PreparedClarityStore.enabled, let w = await PreparedClarityStore.shared.world(lakeId, now: now) { return w }
        return await CurrentClarityCache.shared.world(lakeId) { await buildCurrentClarityWorld(lakeId: lakeId, now: now) }?.at(now)
    }

    /// The live build: what the job runs, and what a route falls back to.
    public static func buildCurrentClarityWorld(lakeId: String, now: Date) async -> CurrentClarityWorld? {
        guard let graph = Hydrology.graph(forLake: lakeId), let index = ClarityRegionsIndex.forLake(lakeId) else { return nil }
        let slug = LakeSurfaceBucket.slug(lakeId)
        let inputs = await ClarityInputsCache.shared.inputs(lakeId) {
            await ClarityStateLoader.load(graph: graph, now: now, baseline: nil)
        }
        var notes = inputs.notes

        let (byId, scene) = CurrentClarityRegions.build(arms: inputs.arms, mainStem: inputs.mainStem,
                                                        newest: inputs.newest, now: now)

        // The distinct scenes chosen, and their cells.
        let dates = Array(Set(scene.values.map(\.sceneDate))).sorted()
        var cells: [ClaritySceneCells] = []
        for d in dates {
            guard let a = scene.values.first(where: { $0.sceneDate == d }) else { continue }
            let ref = ClaritySceneRef(date: d, time: a.sceneTime, platform: a.platform,
                                      source: "lakes/\(slug)/clarity/\(d).cells.bin")
            let got = await CurrentClarityCache.shared.scene("\(slug)/\(d)") {
                guard let u = LakeSurfaceBucket.url("lakes/\(slug)/clarity/\(d).cells.bin"),
                      let r = try? await HTTP.get(u), r.isSuccess else { return nil }
                return try? ClaritySceneCells(ref: ref, data: [UInt8](r.body), index: index)
            }
            if let got { cells.append(got) } else { notes.append("no cells file for the \(d) scene (lakes/\(slug)/clarity/\(d).cells.bin)") }
        }
        let position = Dictionary(uniqueKeysWithValues: cells.enumerated().map { ($1.ref.date, $0) })
        var sceneFor: [Int?] = []
        var contexts: [ClarityRegionContext?] = []
        for id in index.regionIds {
            let c = byId[id]
            let p = scene[id].flatMap { position[$0.sceneDate] }
            if c?.scene != nil && p == nil {
                // Chosen, but its cells did not load: the region has no evidence.
                contexts.append(c.map { withoutScene($0) })
            } else {
                contexts.append(c)
            }
            sceneFor.append(p)
        }
        return CurrentClarityWorld(lakeId: lakeId, now: now, index: index,
                                   composite: ClarityComposite(index: index, scenes: cells, sceneForRegion: sceneFor),
                                   regions: contexts, notes: notes)
    }

    static func withoutScene(_ c: ClarityRegionContext) -> ClarityRegionContext {
        ClarityRegionContext(kind: c.kind, id: c.id, name: c.name, scene: nil, anchorStrength: .none, anchorNote: c.anchorNote,
                             runoff: c.runoff, rainSinceSceneIn: nil, rainRecordThrough: c.rainRecordThrough,
                             flowProvenance: c.flowProvenance, flowSource: c.flowSource, flowChangeRatio: nil,
                             catchmentCompleteness: c.catchmentCompleteness,
                             limitations: c.limitations + ["The chosen scene's cells could not be read."])
    }

    /// An arm's region context: the Stage 2 state's hydrology, without its whole-arm number.
    public static func regionContext(_ s: ArmClarityState, anchor: SatelliteAnchor?, note: String?) -> ClarityRegionContext {
        let keep = s.limitations.filter {
            !$0.hasPrefix("One state for the whole arm") && !$0.hasPrefix("The scene read ") && $0 != note
        }
        return ClarityRegionContext(
            kind: .arm, id: s.armId, name: s.armName,
            scene: anchor.map { ClaritySceneRef(date: $0.sceneDate, time: $0.sceneTime, platform: $0.platform, source: $0.source) },
            anchorStrength: s.satelliteAnchorStrength, anchorNote: note, runoff: s.runoff,
            rainSinceSceneIn: s.divergence.rainSincePassIn, rainRecordThrough: s.divergence.rainValidThrough,
            flowProvenance: s.dischargeProvenance.rawValue, flowSource: s.divergence.dischargeSource,
            flowChangeRatio: s.divergence.dischargePeakRatioToPass, catchmentCompleteness: s.catchmentCompleteness,
            limitations: keep)
    }

    public static func regionContext(_ s: MainStemClarityState, anchor: SatelliteAnchor?) -> ClarityRegionContext {
        let ratio: Double? = {
            guard let a = s.inflowNow24hMeanCfs, let b = s.inflowAtPass24hMeanCfs, b > 0 else { return nil }
            return a / b
        }()
        return ClarityRegionContext(
            kind: .mainStem, id: ClarityStateLoader.mainStemKey, name: "\(s.river) main stem",
            scene: anchor.map { ClaritySceneRef(date: $0.sceneDate, time: $0.sceneTime, platform: $0.platform, source: $0.source) },
            anchorStrength: s.satelliteAnchorStrength, anchorNote: nil, runoff: s.runoff,
            rainSinceSceneIn: s.directRainSincePassIn, rainRecordThrough: nil,
            flowProvenance: s.releaseProvenance == "measuredTVA" ? "measuredTVARelease" : "unavailable",
            flowSource: s.inflowDam, flowChangeRatio: ratio, catchmentCompleteness: .complete,
            limitations: s.limitations)
    }

    public static func currentClarity(lakeId: String, lat: Double, lon: Double, withLegacy: Bool = false,
                                      now: Date = Date()) async -> CurrentClarityEstimate? {
        guard let world = await currentClarityWorld(lakeId: lakeId, now: now) else { return nil }
        var legacy: LegacyClarityEstimate?
        if withLegacy, let c = await conditions(lat: lat, lon: lon)?.clarityVisibility {
            legacy = LegacyClarityEstimate(model: c.model, centralFt: c.centralFt, source: c.provenance)
        }
        return world.estimate(lat: lat, lon: lon, legacy: legacy)
    }

    /// A region's change since `since` (a report's time): the same runoff
    /// rules, measured from that moment instead of a scene. The job's prepared
    /// marks answer while they are current; otherwise a live read.
    public static func clarityChange(lakeId: String, region id: String, since: Date,
                                     now: Date = Date()) async -> HydrologicChange? {
        if PreparedClarityStore.enabled, let c = await PreparedClarityStore.shared.change(lakeId, region: id, since: since, now: now) {
            return c
        }
        guard let graph = Hydrology.graph(forLake: lakeId) else { return nil }
        // The same 10-minute inputs as the lake's arm states: a report's
        // freshness should not wait on a fresh pull of every gauge.
        let inputs = await ClarityInputsCache.shared.inputs(lakeId) {
            await ClarityStateLoader.load(graph: graph, now: now, baseline: nil)
        }
        guard let x = inputs.arms.first(where: { $0.armId == id }) else { return nil }
        return change(x, since: since, now: now)
    }

    /// An arm's change since a moment, from its inputs.
    public static func change(_ x: ArmClarityInputs, since: Date, now: Date) -> HydrologicChange {
        let marker = SatelliteAnchor(sceneDate: ClarityTime.dayKey.string(from: since), sceneTime: since, platform: nil,
                                     waterCells: 1, observedCells: 1, filledCells: 0, filledWithin500mCells: 0,
                                     medianFillDistanceM: nil, observedFNU: nil, allFNU: nil, source: "report")
        let d = ClarityStateEngine.divergence(anchor: marker, rain: x.rain, flow: x.flow, now: now)
        let r = ClarityStateEngine.runoff(d, hasAnchor: true)
        return HydrologicChange(state: r.state, expectedDirection: r.expectedDirection, magnitude: "uncalibrated",
                                rainSinceObservationIn: d.rainSincePassIn, rainRecordThrough: d.rainValidThrough,
                                flowChangeRatio: d.dischargePeakRatioToPass, flowProvenance: d.dischargeProvenance.rawValue,
                                flowSource: d.dischargeSource,
                                authorityCap: CurrentClarityResolver.Rules.hydrologicCap(r.state), evidence: r.evidence)
    }

    /// The job's side: the lake's world and each arm's recent change marks,
    /// from one read of the inputs.
    public static func prepareCurrentClarity(lakeId: String, now: Date)
        async -> (world: CurrentClarityWorld, changes: PreparedClarityChanges)? {
        guard let graph = Hydrology.graph(forLake: lakeId),
              let world = await buildCurrentClarityWorld(lakeId: lakeId, now: now) else { return nil }
        let inputs = await ClarityInputsCache.shared.inputs(lakeId) {
            await ClarityStateLoader.load(graph: graph, now: now, baseline: nil)
        }
        let top = Date(timeIntervalSince1970: (now.timeIntervalSince1970 / 3600).rounded(.down) * 3600)
        var marks: [String: [PreparedClarityChanges.Mark]] = [:]
        for x in inputs.arms {
            marks[x.armId] = (0..<PreparedClarityChanges.hours).reversed().map { h in
                let since = top.addingTimeInterval(-Double(h) * 3600)
                return .init(since: since, change: change(x, since: since, now: now))
            }
        }
        return (world, PreparedClarityChanges(schema: PreparedClarityChanges.schemaId, lakeId: lakeId, builtAt: now, regions: marks))
    }
}

/// The hourly job's prepared worlds, read from the bucket (Stage 5).
/// SECTOR_PREPARED_CLARITY=0 turns it off (every request then builds live).
actor PreparedClarityStore {
    static let shared = PreparedClarityStore()
    static var enabled: Bool { ProcessInfo.processInfo.environment["SECTOR_PREPARED_CLARITY"] != "0" }
    /// How often world.json is re-read.
    static let recheck: TimeInterval = 60

    static let decoder: JSONDecoder = { let d = JSONDecoder(); d.dateDecodingStrategy = .iso8601; return d }()
    /// Where the prepared files are read from: the bucket, unless
    /// SECTOR_PREPARED_CLARITY_BASE points elsewhere (the Linux smoke test).
    static func url(_ slug: String, _ name: String) -> URL? {
        let base = ProcessInfo.processInfo.environment["SECTOR_PREPARED_CLARITY_BASE"] ?? LakeSurfaceBucket.base
        return URL(string: "\(base)/clarity/current/\(slug)/\(name)")
    }

    struct Entry {
        var checkedAt: Date
        var prepared: PreparedClarityWorld
        let composite: ClarityComposite
        let bytes: [UInt8]
        let gzip: [UInt8]
    }
    private var entries: [String: Entry] = [:]
    private var missingSince: [String: Date] = [:]
    private var changes: [String: (checkedAt: Date, value: PreparedClarityChanges?)] = [:]

    func world(_ lakeId: String, now: Date) async -> CurrentClarityWorld? {
        guard let index = ClarityRegionsIndex.forLake(lakeId) else { return nil }
        let due = entries[lakeId].map { now.timeIntervalSince($0.checkedAt) >= Self.recheck }
            ?? missingSince[lakeId].map { now.timeIntervalSince($0) >= Self.recheck } ?? true
        if due { await refresh(lakeId, index: index, now: now) }
        guard let e = entries[lakeId] else { return nil }
        let f = e.prepared.freshness(at: now)
        guard f != .expired else { return nil }
        var notes = e.prepared.notes
        if f == .stale {
            notes.append("The prepared world is \(Int(now.timeIntervalSince(e.prepared.builtAt) / 3600)) h old; drainage not re-checked since.")
        }
        return CurrentClarityWorld(lakeId: lakeId, now: now, index: index, composite: e.composite,
                                   regions: e.prepared.regions(at: now), notes: notes, freshness: f,
                                   preparedAt: e.prepared.builtAt, compositeBytes: e.bytes, compositeGzip: e.gzip)
    }

    func change(_ lakeId: String, region: String, since: Date, now: Date) async -> HydrologicChange? {
        guard let e = entries[lakeId], e.prepared.freshness(at: now) == .current, let path = e.prepared.files.changes else { return nil }
        if changes[lakeId].map({ now.timeIntervalSince($0.checkedAt) >= Self.recheck || $0.value?.builtAt != e.prepared.builtAt }) ?? true {
            let slug = LakeSurfaceBucket.slug(lakeId)
            var got: PreparedClarityChanges?
            if let u = Self.url(slug, path), let r = try? await HTTP.get(u), r.isSuccess {
                got = try? Self.decoder.decode(PreparedClarityChanges.self, from: r.body)
            }
            changes[lakeId] = (now, got?.schema == PreparedClarityChanges.schemaId && got?.lakeId == lakeId ? got : nil)
        }
        return changes[lakeId]?.value?.change(region: region, since: since)
    }

    private func refresh(_ lakeId: String, index: ClarityRegionsIndex, now: Date) async {
        let slug = LakeSurfaceBucket.slug(lakeId)
        func fetch(_ name: String) async -> Data? {
            guard let u = Self.url(slug, name), let r = try? await HTTP.get(u), r.isSuccess else { return nil }
            return r.body
        }
        guard let body = await fetch("world.json"),
              let p = try? Self.decoder.decode(PreparedClarityWorld.self, from: body),
              p.schema == PreparedClarityWorld.schemaId, p.lakeId == lakeId, p.indexHash == index.hash else {
            // Keep serving what was read before; look again after `recheck`.
            if entries[lakeId] != nil { entries[lakeId]!.checkedAt = now } else { missingSince[lakeId] = now }
            return
        }
        if var e = entries[lakeId], e.prepared.etag == p.etag {
            e.prepared = p; e.checkedAt = now; entries[lakeId] = e
            return
        }
        guard let bin = await fetch(p.files.composite), let gz = await fetch(p.files.compositeGzip),
              let composite = try? ClarityComposite(index: index, refs: p.scenes, sceneForRegion: p.sceneForRegion,
                                                    encoded: [UInt8](bin)) else {
            if entries[lakeId] != nil { entries[lakeId]!.checkedAt = now } else { missingSince[lakeId] = now }
            return
        }
        entries[lakeId] = Entry(checkedAt: now, prepared: p, composite: composite, bytes: [UInt8](bin), gzip: [UInt8](gz))
        missingSince[lakeId] = nil
    }
}
