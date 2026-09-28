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

    public init(lakeId: String, now: Date, index: ClarityRegionsIndex, composite: ClarityComposite,
                regions: [ClarityRegionContext?], notes: [String]) {
        self.lakeId = lakeId; self.now = now; self.index = index; self.composite = composite
        self.regions = regions; self.notes = notes
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
        let key = "\(index.hash)|" + composite.sceneForRegion.map { $0.map { composite.scenes[$0].ref.date } ?? "-" }.joined(separator: ",")
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
        let none = CurrentClarityResolver.Outcome(level: .none, confidence: .none, authority: .none, magnitudeSupported: false)
        let table: [[CurrentClarityResolver.Outcome]] = regions.map { c in
            guard let c else { return Array(repeating: none, count: CurrentClarityLake.keys.count) }
            return CurrentClarityLake.keys.indices.map {
                CurrentClarityResolver.outcome(region: c, cell: CurrentClarityLake.representative($0), now: now)
            }
        }
        return CurrentClarityLake(
            schema: CurrentClarityLake.schemaId, lakeId: lakeId, generatedAt: now,
            legend: .init(title: "Water Clarity", clearLabel: "Clear", muddyLabel: "Muddy",
                          sourceLine: "Sentinel-2 · latest usable observations"),
            scenes: composite.scenes.map(\.ref), regions: summaries, evidenceKeys: CurrentClarityLake.keys,
            outcomes: table,
            cells: .init(path: path, etag: etag, count: index.count, width: index.width, height: index.height,
                         cornersLonLat: index.cornersLonLat,
                         encoding: "SCCC v1: value log10 FNU 1..254 over log10(0.5)..log10(200); code 255 read, 1 unreadable, 2 cloud, 3 grass, 0 none; dist 1 + m/100, 254 no path"),
            notes: notes)
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

    /// The lake's current world: every arm's state, its chosen scene's cells.
    public static func currentClarityWorld(lakeId: String, now: Date = Date()) async -> CurrentClarityWorld? {
        await CurrentClarityCache.shared.world(lakeId) { await buildCurrentClarityWorld(lakeId: lakeId, now: now) }
    }

    static func buildCurrentClarityWorld(lakeId: String, now: Date) async -> CurrentClarityWorld? {
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
    /// rules, measured from that moment instead of a scene.
    public static func clarityChange(lakeId: String, region id: String, since: Date,
                                     now: Date = Date()) async -> HydrologicChange? {
        guard let graph = Hydrology.graph(forLake: lakeId) else { return nil }
        // The same 10-minute inputs as the lake's arm states: a report's
        // freshness should not wait on a fresh pull of every gauge.
        let inputs = await ClarityInputsCache.shared.inputs(lakeId) {
            await ClarityStateLoader.load(graph: graph, now: now, baseline: nil)
        }
        guard let x = inputs.arms.first(where: { $0.armId == id }) else { return nil }
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
}
