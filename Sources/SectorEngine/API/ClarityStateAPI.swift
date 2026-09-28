//
//  ClarityStateAPI.swift
//  Sector — "what does Sector believe this water's clarity is, and why?"
//  (Clarity Fusion Stage 2)
//
//  GET /clarity/state?lake=Guntersville|AL&lat=&lon=   the coordinate's arm (or
//                                                      the main stem) and its state
//  GET /clarity/states?lake=Guntersville|AL            every arm and the main stem
//
//  REVIEW BUILD. Read-only; /conditions does not use it, and it is not routed
//  in production until Stage 2 is reviewed.
//

import Foundation

public struct ClarityStateResponse: Codable, Equatable {
    public let lakeId: String
    public let lat: Double
    public let lon: Double
    /// arm | mainStem | notWater | outsideGraph
    public let membership: String
    public let armId: String?
    public let arm: ArmClarityState?
    public let mainStem: MainStemClarityState?
    public let debug: [String]
    public let notes: [String]
    public let generatedAt: Date
}

public struct ClarityStatesResponse: Codable, Equatable {
    public let lakeId: String
    public let generatedAt: Date
    public let baselineAt: [Double]?
    public let mainStem: MainStemClarityState
    public let arms: [ArmClarityState]
    public let debug: [String: [String]]
    public let notes: [String]
}

actor ClarityInputsCache {
    static let shared = ClarityInputsCache()
    private var entries: [String: (at: Date, value: LakeClarityInputs)] = [:]
    static let maxAge: TimeInterval = 10 * 60

    func inputs(_ key: String, compute: @Sendable () async -> LakeClarityInputs) async -> LakeClarityInputs {
        if let e = entries[key], Date().timeIntervalSince(e.at) < Self.maxAge { return e.value }
        let v = await compute()
        entries[key] = (Date(), v)
        return v
    }
}

extension SectorEngineAPI {

    /// The engine's own clarity number at a point, as the baseline.
    static func baselineVisibility(lat: Double, lon: Double) async -> BaselineVisibility? {
        guard let c = await conditions(lat: lat, lon: lon)?.clarityVisibility else { return nil }
        return BaselineVisibility(centralFt: c.centralFt, lowFt: c.lowFt, highFt: c.highFt, model: c.model,
                                  source: "/conditions at \(String(format: "%.4f, %.4f", lat, lon)): \(c.provenance)")
    }

    public static func currentClarityState(lakeId: String, lat: Double, lon: Double,
                                           now: Date = Date()) async -> ClarityStateResponse? {
        guard let graph = Hydrology.graph(forLake: lakeId) else { return nil }
        let grid = Hydrology.guntersvilleGrid
        let member = grid.membership(lat: lat, lon: lon)
        func empty(_ m: String, _ note: String) -> ClarityStateResponse {
            ClarityStateResponse(lakeId: lakeId, lat: lat, lon: lon, membership: m, armId: nil, arm: nil, mainStem: nil,
                                 debug: [], notes: [note], generatedAt: now)
        }
        guard let member else { return empty("outsideGraph", "outside the lake's frame") }
        if member == .notWater { return empty("notWater", "not on the lake's water") }
        let baseline = await baselineVisibility(lat: lat, lon: lon)
        let inputs = await ClarityStateLoader.load(graph: graph, now: now, baseline: baseline)
        switch member {
        case .arm(let id):
            guard let x = inputs.arms.first(where: { $0.armId == id }) else { return empty("arm", "arm \(id) has no inputs") }
            let s = ClarityStateEngine.armState(x, now: now)
            return ClarityStateResponse(lakeId: lakeId, lat: lat, lon: lon, membership: "arm", armId: id, arm: s,
                                        mainStem: nil, debug: ClarityStateDebug.lines(s), notes: inputs.notes, generatedAt: now)
        default:
            let s = ClarityStateEngine.mainStemState(inputs.mainStem, now: now)
            return ClarityStateResponse(lakeId: lakeId, lat: lat, lon: lon, membership: "mainStem", armId: nil, arm: nil,
                                        mainStem: s, debug: ClarityStateDebug.lines(s), notes: inputs.notes, generatedAt: now)
        }
    }

    /// Every arm and the main stem. The baseline is the engine's number at
    /// the lake's centre (one render, not 69).
    public static func clarityStates(lakeId: String, now: Date = Date()) async -> ClarityStatesResponse? {
        guard let graph = Hydrology.graph(forLake: lakeId) else { return nil }
        let center = graph.mainStem.regions[graph.mainStem.regions.count / 2].center
        let baseline = await baselineVisibility(lat: center[0], lon: center[1])
        let inputs = await ClarityInputsCache.shared.inputs(lakeId) {
            await ClarityStateLoader.load(graph: graph, now: now, baseline: baseline)
        }
        let arms = inputs.arms.map { ClarityStateEngine.armState($0, now: now) }
        let main = ClarityStateEngine.mainStemState(inputs.mainStem, now: now)
        var debug = Dictionary(uniqueKeysWithValues: arms.map { ($0.armId, ClarityStateDebug.lines($0)) })
        debug["mainStem"] = ClarityStateDebug.lines(main)
        return ClarityStatesResponse(lakeId: lakeId, generatedAt: now, baselineAt: center, mainStem: main, arms: arms,
                                     debug: debug, notes: inputs.notes + ["baseline: the engine's clarity at the lake's centre"])
    }
}

/// The provenance read-out (Stage 2 item 11): every value from the state.
public enum ClarityStateDebug {
    static func ft(_ v: Double?) -> String { v.map { String(format: "%.1f", $0) } ?? "?" }
    static func inch(_ v: Double?) -> String { v.map { String(format: "%.2f in", $0) } ?? "unknown" }

    public static func lines(_ s: ArmClarityState) -> [String] {
        let d = s.divergence
        var out: [String] = ["\(s.armName) (\(s.armId))"]
        if let date = s.satelliteSceneDate {
            out.append(String(format: "Satellite: %@ · %.0f%% observed, %.0f%% filled", date, s.satelliteObservedPct ?? 0, s.satelliteFilledPct ?? 0)
                       + (s.medianFillDistanceM.map { String(format: " (median %.0f m from a reading)", $0) } ?? "")
                       + " · anchor \(s.satelliteAnchorStrength.rawValue)")
            if let v = s.satelliteAnchorVisibility, let f = s.satelliteAnchorFNU {
                out.append(String(format: "At-pass visibility: ~%.1f ft (likely %.1f–%.1f) from %.1f FNU median", v.centralFt, v.lowFt, v.highFt, f))
            }
        } else {
            out.append("Satellite: no scene of this arm")
        }
        out.append("Rain since pass: \(inch(d.rainSincePassIn)) over the \(s.catchmentCompleteness.rawValue) catchment"
                   + (d.rainValidThrough.map { " (record to \(ClarityTime.hourKey.string(from: $0))Z)" } ?? ""))
        let flow: String = {
            switch s.dischargeProvenance {
            case .unavailable: return "Flow: unavailable"
            case .measuredUSGS, .modeledNWM:
                let kind = s.dischargeProvenance == .measuredUSGS ? "measured" : "modeled NWM"
                return "Flow: \(ft(s.dischargeCurrentCfs)) cfs \(kind)" + (d.dischargeSource.map { " (\($0))" } ?? "")
                    + (s.dischargeAtSatellitePassCfs.map { String(format: ", %.1f cfs at the pass", $0) } ?? ", at the pass not reconstructable")
                    + ", \(s.dischargeTrend)"
            }
        }()
        out.append(flow)
        out.append("Antecedent: \(inch(s.antecedent7dIn)) in the 7 days before the pass")
        out.append("Runoff state: \(s.runoff.state.rawValue) (\(s.runoff.expectedDirection), magnitude \(s.runoff.magnitude))")
        out.append("Satellite authority: \(s.satelliteAuthority.level.rawValue) — \(s.satelliteAuthority.reason)")
        let v = s.currentVisibility
        switch v.basis {
        case "satelliteAnchor":
            out.append(String(format: "Current magnitude: satellite-supported, ~%@ ft (%@–%@)", ft(v.centralFt), ft(v.lowFt), ft(v.highFt)))
        case "baseline":
            out.append("Current magnitude: baseline ~\(ft(v.centralFt)) ft, not adjusted (\(v.baselineSource ?? "baseline"))")
            if let w = v.warning { out.append("Warning: \(w)") }
        default:
            out.append("Current magnitude: none" + (v.warning.map { " — \($0)" } ?? ""))
        }
        out.append("Confidence: \(s.confidence.level) (\(s.confidence.reasons.joined(separator: "; ")))")
        out.append("Limitations: " + s.limitations.joined(separator: " "))
        return out
    }

    public static func lines(_ s: MainStemClarityState) -> [String] {
        var out = ["\(s.river) main stem"]
        if let date = s.satelliteSceneDate {
            out.append(String(format: "Satellite: %@ · %.0f%% observed · anchor %@", date, s.satelliteObservedPct ?? 0, s.satelliteAnchorStrength.rawValue))
            if let v = s.satelliteAnchorVisibility, let f = s.satelliteAnchorFNU {
                out.append(String(format: "At-pass visibility: ~%.1f ft (likely %.1f–%.1f) from %.1f FNU median", v.centralFt, v.lowFt, v.highFt, f))
            }
        }
        out.append("Direct rain since pass: \(inch(s.directRainSincePassIn)) on the reservoir surface")
        out.append("\(s.inflowDam) release: \(ft(s.inflowNow24hMeanCfs)) cfs (24 h mean), \(ft(s.inflowAtPass24hMeanCfs)) at the pass, \(s.inflowTrend) · \(s.releaseProvenance)")
        out.append("\(s.outflowDam) release: \(ft(s.outflowNow24hMeanCfs)) cfs (24 h mean), \(s.outflowTrend)")
        out.append("Current: \(s.currentVelocity)")
        out.append("Runoff state: \(s.runoff.state.rawValue) (\(s.runoff.expectedDirection))")
        out.append("Satellite authority: \(s.satelliteAuthority.level.rawValue) — \(s.satelliteAuthority.reason)")
        let v = s.currentVisibility
        out.append(v.basis == "satelliteAnchor"
                   ? "Current magnitude: satellite-supported, ~\(ft(v.centralFt)) ft (\(ft(v.lowFt))–\(ft(v.highFt)))"
                   : "Current magnitude: \(v.basis) ~\(ft(v.centralFt)) ft, not adjusted" + (v.warning.map { " — \($0)" } ?? ""))
        out.append("Confidence: \(s.confidence.level) (\(s.confidence.reasons.joined(separator: "; ")))")
        out.append("Limitations: " + s.limitations.joined(separator: " "))
        return out
    }
}
