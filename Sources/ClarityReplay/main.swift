//
//  ClarityReplay — Clarity Fusion Stage 2's historical replay.
//
//  Builds each arm's record from the history files (scripts/hydrology:
//  pass_history, rain_history, nwm_history, and the USGS IV pull), then, for
//  every pair of well-read passes of an arm, runs the live state engine AS OF
//  one minute before the second pass (ClarityHistory: nothing after that
//  moment is visible) and compares the direction it expected with what the
//  second pass read. Also writes each target arm's day-by-day state.
//
//  usage: ClarityReplay <passes dir> <rain_daily.json> <usgs_iv.json> <nwm_daily.json>
//                       <mrms_weights.json> <out.json> [arm ...]
//                       [--hourly rain_pass_hours.json] [--anchors DIR]
//
//  --hourly   Stage 3A: the day before each pass as HOURLY MRMS (17Z the day
//             before -> 16Z on the day), replacing that day's 24 h total, plus
//             the residual hour 16-17Z (which contains the pass and so is
//             never visible to it). Without it the replay cannot see the last
//             ~23.5 h before a pass.
//  --anchors  Stage 3A: anchors from zone_history.py (ArmAnchorFile JSON, with
//             through-water fill distances), so a weak scene is judged weak
//             the way the live product judges it.
//

import Foundation
import SectorEngine

var argv = CommandLine.arguments
func flag(_ name: String) -> String? {
    guard let i = argv.firstIndex(of: name), i + 1 < argv.count else { return nil }
    let v = argv[i + 1]; argv.removeSubrange(i...(i + 1)); return v
}
let hourlyPath = flag("--hourly")
let anchorsDir = flag("--anchors")
let args = argv
guard args.count >= 7 else {
    FileHandle.standardError.write("usage: ClarityReplay <passes dir> <rain_daily.json> <usgs_iv.json> <nwm_daily.json> <mrms_weights.json> <out.json> [arm ...]\n".data(using: .utf8)!)
    exit(2)
}
let (passDir, rainPath, usgsPath, nwmPath, weightsPath, outPath) = (args[1], args[2], args[3], args[4], args[5], args[6])
let targets = args.count > 7 ? Array(args[7...]) : ["town-creek-marshall", "south-sauty-creek", "browns-creek", "boshart-creek", "mainstem"]

func json(_ p: String) -> Any { try! JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: p))) }
let iso: (String) -> Date? = { s in
    let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime]
    if let d = f.date(from: s) { return d }
    if let dot = s.firstIndex(of: ".") {
        let tail = s[dot...].drop { $0 != "Z" && $0 != "+" && $0 != "-" }
        return f.date(from: String(s[..<dot]) + tail)
    }
    return nil
}
let day = DateFormatter(); day.locale = Locale(identifier: "en_US_POSIX"); day.timeZone = TimeZone(identifier: "UTC"); day.dateFormat = "yyyy-MM-dd"

// MARK: load

let graph = Hydrology.guntersville
let weights = (json(weightsPath) as! [String: Any])["arms"] as! [String: [String: Any]]
var anchors: [String: [SatelliteAnchor]] = [:]
if let dir = anchorsDir {
    for f in try! FileManager.default.contentsOfDirectory(atPath: dir) where f.hasSuffix(".json") {
        let file = try! JSONDecoder().decode(ArmAnchorFileReplay.self, from: Data(contentsOf: URL(fileURLWithPath: dir + "/" + f)))
        guard let t = iso(file.sceneTime) else { continue }
        for (arm, e) in file.arms.map({ ($0.key, $0.value) }) + (file.mainStem.map { [("mainstem", $0)] } ?? []) {
            guard let o = e.observedFNU, e.waterCells > 0 else { continue }
            anchors[arm, default: []].append(SatelliteAnchor(
                sceneDate: file.sceneDate, sceneTime: t, platform: file.platform, waterCells: e.waterCells,
                observedCells: e.observedCells, filledCells: e.filledCells, filledWithin500mCells: e.filledWithin500mCells,
                medianFillDistanceM: e.medianFillDistanceM,
                observedFNU: Distribution(n: o.n, p25: o.p25, p50: o.p50, p75: o.p75), allFNU: nil, source: file.source))
        }
    }
}
for f in (anchorsDir == nil ? try! FileManager.default.contentsOfDirectory(atPath: passDir) : []) where f.hasSuffix(".json") {
    let p = json(passDir + "/" + f) as! [String: Any]
    guard (p["status"] as? String) == "read", let t = (p["time"] as? String).flatMap(iso) else { continue }
    for (arm, v) in p["arms"] as! [String: [String: Any]] {
        guard let fnu = v["fnu"] as? [String: Any] else { continue }
        let w = v["waterCells"] as! Int, o = v["observedCells"] as! Int
        let dist = Distribution(n: fnu["n"] as! Int, p25: fnu["p25"] as! Double, p50: fnu["p50"] as! Double, p75: fnu["p75"] as! Double)
        anchors[arm, default: []].append(SatelliteAnchor(
            sceneDate: p["date"] as! String, sceneTime: t, platform: p["platform"] as? String, waterCells: w,
            observedCells: o, filledCells: w - o, filledWithin500mCells: nil, medianFillDistanceM: nil,
            observedFNU: dist, allFNU: nil, source: "pass_history \(p["date"]!) \(p["platform"]!)"))
    }
}
let rainDays = (json(rainPath) as! [String: Any])["days"] as! [String: Any]
let hourKey = DateFormatter(); hourKey.locale = Locale(identifier: "en_US_POSIX"); hourKey.timeZone = TimeZone(identifier: "UTC"); hourKey.dateFormat = "yyyy-MM-dd'T'HH"
let hourly = hourlyPath.map { (json($0) as! [String: Any])["hours"] as! [String: Any] } ?? [:]
func rainRecord(_ key: String, basis: String, km2: Double?) -> RainRecord {
    var steps: [RainStep] = []
    for (d, v) in rainDays {
        guard let date = day.date(from: d) else { continue }
        let end = date.addingTimeInterval(17 * 3600)
        let inches = (v as? [String: Any]).flatMap { $0[key] as? Double }
        // The day before a pass, hour by hour, where every hour was read.
        let hours = (1...23).map { end.addingTimeInterval(Double($0 - 24) * 3600) }     // valid 18Z D-1 ... 16Z D
        let vals = hours.map { h -> Double? in (hourly[hourKey.string(from: h)] as? [String: Any]).flatMap { $0[key] as? Double } }
        if !hourly.isEmpty, vals.allSatisfy({ $0 != nil }), let daily = inches {
            for (h, x) in zip(hours, vals) { steps.append(RainStep(start: h.addingTimeInterval(-3600), end: h, inches: x)) }
            let rest = max(0, daily - vals.compactMap { $0 }.reduce(0, +))
            steps.append(RainStep(start: end.addingTimeInterval(-3600), end: end, inches: rest))
            continue
        }
        steps.append(RainStep(start: end.addingTimeInterval(-86_400), end: end, inches: inches))
    }
    return RainRecord(basis: basis, drainageKm2: km2, source: hourly.isEmpty ? "MRMS 24H Pass 2 valid 17Z (daily)"
                      : "MRMS 24H Pass 2 valid 17Z (daily), 01H Pass 2 for the day before each pass", steps: steps)
}
let usgs = json(usgsPath) as! [String: [[Any]]]
var usgsSeries: [String: FlowSeries] = [:]
for (site, pts) in usgs {
    usgsSeries[site] = FlowSeries(provenance: .measuredUSGS, source: "USGS \(site)", points: pts.compactMap { p in
        guard let t = (p[0] as? String).flatMap(iso), let v = p[1] as? Double else { return nil }
        return FlowPoint(validTime: t, cfs: v)
    })
}
let nwm = json(nwmPath) as! [String: Any]
let nwmDays = nwm["days"] as! [String: Any]
func nwmSeries(_ reach: String) -> FlowSeries? {
    var pts: [FlowPoint] = []
    for (d, v) in nwmDays {
        guard let date = day.date(from: d), let x = (v as? [String: Any])?[reach] as? Double else { continue }
        pts.append(FlowPoint(validTime: date.addingTimeInterval(16 * 3600), cfs: x))
    }
    return pts.isEmpty ? nil : FlowSeries(provenance: .modeledNWM, source: "NWM reach \(reach), analysis 16Z", points: pts)
}
let byId = Dictionary(uniqueKeysWithValues: graph.arms.map { ($0.id, $0) })
var records: [String: ClarityHistory.ArmRecord] = [:]
for a in graph.arms {
    let w = weights[a.id]
    records[a.id] = ClarityHistory.ArmRecord(
        armId: a.id, armName: a.name, anchors: anchors[a.id] ?? [],
        rain: rainRecord(a.id, basis: (w?["basis"] as? String) ?? "unavailable", km2: w?["drainageKm2"] as? Double),
        flow: FlowRecord(measured: a.usgsDischargeSite.flatMap { usgsSeries[$0] }, modeled: a.nwmFeatureId.flatMap(nwmSeries)),
        parentArmName: a.parent == graph.mainStem.id ? nil : byId[a.parent]?.name)
}
let history = ClarityHistory(
    lakeId: graph.lakeId, arms: records,
    mainStem: .init(river: graph.mainStem.name, anchors: anchors["mainstem"] ?? [],
                    directRain: rainRecord("_lakeSurface", basis: "lakeSurface", km2: nil),
                    inflow: nil, outflow: nil,   // TVA publishes 48 h: no history to replay
                    inflowDamName: graph.mainStem.upstreamDam.name, outflowDamName: graph.mainStem.downstreamDam.name))

// MARK: replay

let noiseHi = 0.139, noiseLo = -0.151       // pass_pairs.py noise floor (dry pairs, p90 / p10)
func observed(_ dlog: Double) -> String { dlog > noiseHi ? "murkierThanPass" : dlog < noiseLo ? "clearerThanPass" : "sameAsPass" }
func usable(_ a: SatelliteAnchor) -> Bool { a.observedPct >= 30 && a.observedCells >= 30 }

var pairs: [[String: Any]] = []
for (id, rec) in records.sorted(by: { $0.key < $1.key }) + [("mainstem", nil)] {
    let seq = (id == "mainstem" ? history.mainStem!.anchors : rec!.anchors).filter(usable)
    for next in seq {
        let t = next.sceneTime.addingTimeInterval(-60)
        let state: (anchor: String?, fnu: Double?, runoff: RunoffState, auth: SatelliteAuthority, rain: Double?, ratio: Double?, prov: String)
        if id == "mainstem" {
            guard let x = history.mainStemInputs(asOf: t) else { continue }
            let s = ClarityStateEngine.mainStemState(x, now: t)
            state = (s.satelliteSceneDate, s.satelliteAnchorFNU, s.runoff, s.satelliteAuthority, s.directRainSincePassIn, nil, "tva unavailable")
        } else {
            guard let x = history.inputs(arm: id, asOf: t) else { continue }
            let s = ClarityStateEngine.armState(x, now: t)
            state = (s.satelliteSceneDate, s.satelliteAnchorFNU, s.runoff, s.satelliteAuthority,
                     s.divergence.rainSincePassIn, s.divergence.dischargePeakRatioToPass, s.dischargeProvenance.rawValue)
        }
        guard let a = state.anchor, let f = state.fnu, let nf = next.observedFNU?.p50,
              let prev = (id == "mainstem" ? history.mainStem!.anchors : rec!.anchors).first(where: { $0.sceneDate == a }),
              next.sceneTime.timeIntervalSince(prev.sceneTime) <= 12 * 86_400 else { continue }
        let dlog = log10(nf / f)
        pairs.append(["arm": id, "anchor": a, "next": next.sceneDate, "gapDays": next.sceneTime.timeIntervalSince(prev.sceneTime) / 86_400,
                      "anchorFNU": f, "nextFNU": nf, "dlog10": dlog, "observed": observed(dlog),
                      "expected": state.runoff.expectedDirection, "runoff": state.runoff.state.rawValue,
                      "authority": state.auth.level.rawValue, "rainSincePassIn": state.rain ?? NSNull(),
                      "flowPeakRatio": state.ratio ?? NSNull(), "flowProvenance": state.prov])
    }
}

// day-by-day for the targets
var trajectories: [String: [[String: Any]]] = [:]
let first = day.date(from: "2025-03-01")!, last = day.date(from: "2026-09-26")!
for id in targets {
    var rows: [[String: Any]] = []
    var t = first.addingTimeInterval(17 * 3600)
    while t <= last {
        if id == "mainstem", let x = history.mainStemInputs(asOf: t) {
            let s = ClarityStateEngine.mainStemState(x, now: t)
            rows.append(["t": day.string(from: t), "anchor": s.satelliteSceneDate ?? NSNull(), "strength": s.satelliteAnchorStrength.rawValue,
                         "rainSincePassIn": s.directRainSincePassIn ?? NSNull(), "runoff": s.runoff.state.rawValue,
                         "authority": s.satelliteAuthority.level.rawValue, "basis": s.currentVisibility.basis])
        } else if let x = history.inputs(arm: id, asOf: t) {
            let s = ClarityStateEngine.armState(x, now: t)
            rows.append(["t": day.string(from: t), "anchor": s.satelliteSceneDate ?? NSNull(), "strength": s.satelliteAnchorStrength.rawValue,
                         "anchorFNU": s.satelliteAnchorFNU ?? NSNull(), "rainSincePassIn": s.divergence.rainSincePassIn ?? NSNull(),
                         "flowNow": s.dischargeCurrentCfs ?? NSNull(), "flowAtPass": s.dischargeAtSatellitePassCfs ?? NSNull(),
                         "flowPeakRatio": s.divergence.dischargePeakRatioToPass ?? NSNull(), "flowProvenance": s.dischargeProvenance.rawValue,
                         "runoff": s.runoff.state.rawValue, "expected": s.runoff.expectedDirection,
                         "authority": s.satelliteAuthority.level.rawValue, "confidence": s.confidence.level,
                         "completeness": s.catchmentCompleteness.rawValue])
        }
        t = t.addingTimeInterval(86_400)
    }
    trajectories[id] = rows
}
let out: [String: Any] = ["noiseFloorDlog10": ["p10": noiseLo, "p90": noiseHi], "pairs": pairs, "trajectories": trajectories,
                          "rules": ["asOf": "one minute before the next pass; rain steps must have ended by then (daily 17Z totals, so the last ~23.5 h before a pass are not visible)",
                                    "anchor": "ClarityHistory.selectAnchor", "usablePass": ">= 30% of the arm's lake cells and >= 30 cells observed"]]
try! JSONSerialization.data(withJSONObject: out, options: [.prettyPrinted, .sortedKeys]).write(to: URL(fileURLWithPath: outPath))
print("pairs", pairs.count, "trajectories", trajectories.mapValues(\.count))

/// zone_history.py's anchor files (the engine's ArmAnchorFile is internal).
struct ArmAnchorFileReplay: Decodable {
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
    }
    struct Dist: Decodable { let n: Int; let p25: Double; let p50: Double; let p75: Double }
}
