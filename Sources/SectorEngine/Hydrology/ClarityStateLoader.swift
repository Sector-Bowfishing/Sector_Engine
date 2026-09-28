//
//  ClarityStateLoader.swift
//  Sector — the live inputs to each arm's clarity state (Clarity Fusion Stage 2)
//
//  Everything comes from files the jobs publish, plus live flow:
//
//    lakes/<slug>/clarity/arms/latest.json   per-arm satellite anchors
//                                            (scripts/hydrology/arm_anchor.py)
//    hydrology/<slug>/hourly/<date>.json     the hourly record: rain over each
//                                            drainage, each arm's gauge and
//                                            model reach, TVA at both dams
//                                            (jobs/hydrology-hourly)
//    USGS IV / NOAA NWPS / TVA               now, and at the pass where the
//                                            record does not reach back to it
//
//  SECTOR_LAKE_SURFACE_BASE points it at a local copy of the bucket.
//

import Foundation

public enum LakeSurfaceBucket {
    public static var base: String {
        ProcessInfo.processInfo.environment["SECTOR_LAKE_SURFACE_BASE"]
            ?? "https://storage.googleapis.com/sector-lake-surface"
    }
    static func url(_ path: String) -> URL? { URL(string: "\(base)/\(path)") }
    static func slug(_ lakeId: String) -> String { lakeId.replacingOccurrences(of: "|", with: "_") }
}

enum ClarityTime {
    static func parse(_ s: String) -> Date? {
        // "2026-09-20T16:34:09.006000Z" (6 fractional digits) or plain
        let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime]
        if let d = f.date(from: s) { return d }
        if let dot = s.firstIndex(of: ".") {
            let tail = s[dot...].drop { $0 != "Z" && $0 != "+" && $0 != "-" }
            return f.date(from: String(s[..<dot]) + tail)
        }
        return nil
    }

    static let hourKey: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyy-MM-dd'T'HH"
        return f
    }()

    static let dayKey: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
}

/// arm_anchor.py's file.
struct ArmAnchorFile: Decodable {
    let sceneDate: String
    let sceneTime: String
    let platform: String?
    let source: String
    let arms: [String: Entry]
    let mainStem: Entry?

    struct Entry: Decodable {
        let waterCells: Int
        let observedCells: Int
        let filledCells: Int
        let filledWithin500mCells: Int?
        let medianFillDistanceM: Double?
        let observedFNU: Dist?
        let allFNU: Dist?
    }
    struct Dist: Decodable { let n: Int; let p25: Double; let p50: Double; let p75: Double }

    func anchor(_ e: Entry?) -> SatelliteAnchor? {
        guard let e, let t = ClarityTime.parse(sceneTime) else { return nil }
        let d: (Dist?) -> Distribution? = { $0.map { Distribution(n: $0.n, p25: $0.p25, p50: $0.p50, p75: $0.p75) } }
        return SatelliteAnchor(sceneDate: sceneDate, sceneTime: t, platform: platform, waterCells: e.waterCells,
                               observedCells: e.observedCells, filledCells: e.filledCells,
                               filledWithin500mCells: e.filledWithin500mCells, medianFillDistanceM: e.medianFillDistanceM,
                               observedFNU: d(e.observedFNU), allFNU: d(e.allFNU), source: source)
    }
}

/// jobs/hydrology-hourly's day file.
struct HourlyDayFile: Decodable {
    let rows: [String: Row]
    struct Row: Decodable {
        let rain1h: [String: Double?]?
        let flows: [String: Flow]?
        let tva: [String: TVA?]?
    }
    struct Flow: Decodable {
        let usgs: Point?
        let nwm: Point?
        struct Point: Decodable { let cfs: Double; let at: String?; let validTime: String? }
    }
    struct TVA: Decodable { let releaseCfs: Double? }
}

public struct LakeClarityInputs {
    public let arms: [ArmClarityInputs]
    public let mainStem: MainStemClarityInputs
    public let notes: [String]
}

public enum ClarityStateLoader {

    static let lakeSurfaceKey = "_lakeSurface"

    public static func load(graph: HydrologyGraph, now: Date = Date(),
                            baseline: BaselineVisibility?) async -> LakeClarityInputs {
        let slug = LakeSurfaceBucket.slug(graph.lakeId)
        var notes: [String] = []

        // 1. anchors
        var anchors: ArmAnchorFile?
        if let u = LakeSurfaceBucket.url("lakes/\(slug)/clarity/arms/latest.json"),
           let r = try? await HTTP.get(u), r.isSuccess {
            anchors = try? JSONDecoder().decode(ArmAnchorFile.self, from: r.body)
        }
        if anchors == nil { notes.append("no per-arm anchor file (lakes/\(slug)/clarity/arms/latest.json)") }
        let pass = anchors.flatMap { ClarityTime.parse($0.sceneTime) }

        // 2. the hourly record, from 7 days before the pass (or 10 days back) to now
        let from = min(pass ?? now, now.addingTimeInterval(-3 * 86_400)).addingTimeInterval(-7 * 86_400)
        var days: [Date] = []
        var d = from
        while d <= now.addingTimeInterval(3600), days.count < 45 { days.append(d); d = d.addingTimeInterval(86_400) }
        let files: [HourlyDayFile] = await withTaskGroup(of: HourlyDayFile?.self) { g in
            for day in days {
                g.addTask {
                    guard let u = LakeSurfaceBucket.url("hydrology/\(slug)/hourly/\(ClarityTime.dayKey.string(from: day)).json"),
                          let r = try? await HTTP.get(u), r.isSuccess else { return nil }
                    return try? JSONDecoder().decode(HourlyDayFile.self, from: r.body)
                }
            }
            var out: [HourlyDayFile] = []
            for await f in g { if let f { out.append(f) } }
            return out
        }
        if files.isEmpty { notes.append("no hourly hydrology record (hydrology/\(slug)/hourly/)") }
        var rain: [String: [RainStep]] = [:]
        var usgsPts: [String: [FlowPoint]] = [:], nwmPts: [String: [FlowPoint]] = [:]
        var tvaPts: [String: [FlowPoint]] = [:]
        for f in files {
            for (key, row) in f.rows {
                guard let t = ClarityTime.hourKey.date(from: key) else { continue }
                for (arm, v) in row.rain1h ?? [:] {
                    rain[arm, default: []].append(RainStep(start: t.addingTimeInterval(-3600), end: t, inches: v))
                }
                for (arm, fl) in row.flows ?? [:] {      // negative = a missing-value sentinel (-9999, -999999)
                    if let u = fl.usgs, u.cfs >= 0, let at = u.at.flatMap(ClarityTime.parse) { usgsPts[arm, default: []].append(.init(validTime: at, cfs: u.cfs)) }
                    if let n = fl.nwm, n.cfs >= 0, let at = n.validTime.flatMap(ClarityTime.parse) { nwmPts[arm, default: []].append(.init(validTime: at, cfs: n.cfs)) }
                }
                for (dam, x) in row.tva ?? [:] {
                    if let c = x?.releaseCfs { tvaPts[dam, default: []].append(.init(validTime: t, cfs: c)) }
                }
            }
        }

        // 3. live flow, and flow at the pass where the record does not reach it
        let weights = await Self.catchments(slug: slug)
        let live: [String: (FlowSeries?, FlowSeries?)] = await withTaskGroup(of: (String, FlowSeries?, FlowSeries?).self) { g in
            var running = 0
            var out: [String: (FlowSeries?, FlowSeries?)] = [:]
            for arm in graph.arms {
                if running >= 8, let r = await g.next() { out[r.0] = (r.1, r.2); running -= 1 }
                g.addTask {
                    var m: FlowSeries?, n: FlowSeries?
                    if let site = arm.usgsDischargeSite {
                        m = await Self.usgsSeries(site: site, name: arm.usgsDischargeSiteName, pass: pass, now: now)
                    }
                    if let reach = arm.nwmFeatureId { n = await Self.nwmSeries(reach: reach) }
                    return (arm.id, m, n)
                }
                running += 1
            }
            for await r in g { out[r.0] = (r.1, r.2) }
            return out
        }

        let byId = Dictionary(uniqueKeysWithValues: graph.arms.map { ($0.id, $0) })
        var armInputs: [ArmClarityInputs] = []
        for arm in graph.arms {
            let w = weights[arm.id]
            let steps = rain[arm.id] ?? []
            let record = RainRecord(basis: w?.basis ?? "unavailable", drainageKm2: w?.drainageKm2,
                                    source: "MRMS Pass 2, hourly (jobs/hydrology-hourly)", steps: steps)
            let (liveM, liveN) = live[arm.id] ?? (nil, nil)
            func merge(_ recorded: [FlowPoint]?, _ l: FlowSeries?, _ p: FlowProvenance, _ src: String?) -> FlowSeries? {
                let pts = (recorded ?? []) + (l?.points ?? [])
                guard !pts.isEmpty, let src = l?.source ?? src else { return nil }
                return FlowSeries(provenance: p, source: src, points: pts)
            }
            let measured = arm.usgsDischargeSite == nil ? nil
                : merge(usgsPts[arm.id], liveM, .measuredUSGS, arm.usgsDischargeSite.map { "USGS \($0)" })
            let modeled = arm.nwmFeatureId == nil ? nil
                : merge(nwmPts[arm.id], liveN, .modeledNWM, arm.nwmFeatureId.map { "NWM reach \($0), analysis" })
            let parent = arm.parent == graph.mainStem.id ? nil : byId[arm.parent]?.name
            armInputs.append(ArmClarityInputs(lakeId: graph.lakeId, armId: arm.id, armName: arm.name,
                                              anchor: anchors?.anchor(anchors?.arms[arm.id]), rain: record,
                                              flow: FlowRecord(measured: measured, modeled: modeled),
                                              baseline: baseline, parentArmName: parent))
        }

        // 4. the main stem
        let ms = await MainStemService.state(for: graph)
        func release(_ dam: HydrologyGraph.Dam, _ state: DamState?) -> ReleaseSeries? {
            let pts = (tvaPts[dam.tva] ?? []) + (state?.history.compactMap { h in h.releaseCfs.map { FlowPoint(validTime: h.at, cfs: $0) } } ?? [])
            return pts.isEmpty ? nil : ReleaseSeries(dam: dam.id, tva: dam.tva, points: pts)
        }
        let lakeW = weights[lakeSurfaceKey]
        let main = MainStemClarityInputs(
            lakeId: graph.lakeId, river: graph.mainStem.name, anchor: anchors?.anchor(anchors?.mainStem),
            directRain: RainRecord(basis: lakeW?.basis ?? "unavailable", drainageKm2: lakeW?.drainageKm2,
                                   source: "MRMS Pass 2 over the reservoir surface, hourly", steps: rain[lakeSurfaceKey] ?? []),
            inflow: release(graph.mainStem.upstreamDam, ms.inflow), outflow: release(graph.mainStem.downstreamDam, ms.outflow),
            inflowDamName: graph.mainStem.upstreamDam.name, outflowDamName: graph.mainStem.downstreamDam.name,
            baseline: baseline)
        return LakeClarityInputs(arms: armInputs, mainStem: main, notes: notes)
    }

    /// Each arm's catchment basis, from the rain feed the hourly job publishes.
    static func catchments(slug: String) async -> [String: (basis: String, drainageKm2: Double?)] {
        guard let u = LakeSurfaceBucket.url("rain/\(slug)/catchments.json"),
              let r = try? await HTTP.get(u), r.isSuccess,
              let f = try? JSONDecoder().decode(CatchmentRainfallFeed.Feed.self, from: r.body) else { return [:] }
        var out: [String: (basis: String, drainageKm2: Double?)] = [:]
        for (k, v) in f.arms { out[k] = (v.basis ?? "unavailable", v.drainageKm2) }
        return out
    }

    static func usgsSeries(site: String, name: String?, pass: Date?, now: Date) async -> FlowSeries? {
        var pts: [(Date, Double)] = []
        if let u = URL(string: "https://waterservices.usgs.gov/nwis/iv/?format=json&sites=\(site)&parameterCd=00060&period=PT13H"),
           let r = try? await HTTP.get(u), r.isSuccess { pts += TributaryFlowService.parseUSGS(r.body) }
        if let pass, now.timeIntervalSince(pass) > 12 * 3600 {
            let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime]
            let a = f.string(from: pass.addingTimeInterval(-3 * 3600)), b = f.string(from: pass.addingTimeInterval(3 * 3600))
            if let u = URL(string: "https://waterservices.usgs.gov/nwis/iv/?format=json&sites=\(site)&parameterCd=00060&startDT=\(a)&endDT=\(b)"),
               let r = try? await HTTP.get(u), r.isSuccess { pts += TributaryFlowService.parseUSGS(r.body) }
        }
        guard !pts.isEmpty else { return nil }
        return FlowSeries(provenance: .measuredUSGS, source: "USGS \(site)" + (name.map { " \($0)" } ?? ""),
                          points: pts.map { FlowPoint(validTime: $0.0, cfs: $0.1) })
    }

    static func nwmSeries(reach: String) async -> FlowSeries? {
        guard let u = URL(string: "https://api.water.noaa.gov/nwps/v1/reaches/\(reach)/streamflow"),
              let r = try? await HTTP.get(u, headers: ["Accept": "application/json"]), r.isSuccess,
              let p = TributaryFlowService.parseNWPS(r.body), !p.analysis.isEmpty,
              (p.units ?? "ft³/s").contains("ft") else { return nil }
        return FlowSeries(provenance: .modeledNWM, source: "NWM reach \(reach), analysis",
                          points: p.analysis.map { FlowPoint(validTime: $0.0, cfs: $0.1) })
    }
}
