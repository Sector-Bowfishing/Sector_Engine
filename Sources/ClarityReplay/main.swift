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
//

import Foundation
import SectorEngine

let args = CommandLine.arguments
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
for f in try! FileManager.default.contentsOfDirectory(atPath: passDir) where f.hasSuffix(".json") {
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
func rainRecord(_ key: String, basis: String, km2: Double?) -> RainRecord {
    var steps: [RainStep] = []
    for (d, v) in rainDays {
        guard let date = day.date(from: d) else { continue }
        let end = date.addingTimeInterval(17 * 3600)
        let inches = (v as? [String: Any]).flatMap { $0[key] as? Double }
        steps.append(RainStep(start: end.addingTimeInterval(-86_400), end: end, inches: inches))
    }
    return RainRecord(basis: basis, drainageKm2: km2, source: "MRMS 24H Pass 2 valid 17Z (daily)", steps: steps)
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
