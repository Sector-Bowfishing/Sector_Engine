//
//  ClarityHistory.swift
//  Sector — a lake's recorded past, read strictly as of a moment
//  (Clarity Fusion Stage 2, historical replay)
//
//  NO LOOK-AHEAD. `inputs(arm:asOf:)` hands the state engine only what
//  existed at `t`: scenes taken before t, rain intervals that had ENDED by t
//  (a daily total ending after t is excluded whole, not prorated), and flow
//  values valid by t. The same state engine then runs as it does live.
//

import Foundation

public struct ClarityHistory {

    public struct ArmRecord {
        public let armId: String
        public let armName: String
        public let anchors: [SatelliteAnchor]
        public let rain: RainRecord
        public let flow: FlowRecord
        public let parentArmName: String?
        public init(armId: String, armName: String, anchors: [SatelliteAnchor], rain: RainRecord,
                    flow: FlowRecord, parentArmName: String?) {
            self.armId = armId; self.armName = armName
            self.anchors = anchors.sorted { $0.sceneTime < $1.sceneTime }
            self.rain = rain; self.flow = flow; self.parentArmName = parentArmName
        }
    }

    public struct MainStemRecord {
        public let river: String
        public let anchors: [SatelliteAnchor]
        public let directRain: RainRecord
        public let inflow: ReleaseSeries?
        public let outflow: ReleaseSeries?
        public let inflowDamName: String
        public let outflowDamName: String
        public init(river: String, anchors: [SatelliteAnchor], directRain: RainRecord, inflow: ReleaseSeries?,
                    outflow: ReleaseSeries?, inflowDamName: String, outflowDamName: String) {
            self.river = river; self.anchors = anchors.sorted { $0.sceneTime < $1.sceneTime }
            self.directRain = directRain; self.inflow = inflow; self.outflow = outflow
            self.inflowDamName = inflowDamName; self.outflowDamName = outflowDamName
        }
    }

    public let lakeId: String
    public let arms: [String: ArmRecord]
    public let mainStem: MainStemRecord?

    public init(lakeId: String, arms: [String: ArmRecord], mainStem: MainStemRecord?) {
        self.lakeId = lakeId; self.arms = arms; self.mainStem = mainStem
    }

    /// The latest usable scene before `t`: the newest that anchors at least
    /// moderately, else the newest that anchors at all. A cloudy new scene does
    /// not displace a clear older one; the older one's divergence carries the
    /// change since.
    public static func selectAnchor(_ anchors: [SatelliteAnchor], asOf t: Date) -> SatelliteAnchor? {
        let before = anchors.filter { $0.sceneTime < t }
        return before.last { $0.strength.0 >= .moderate } ?? before.last { $0.strength.0 >= .weak }
    }

    static func rain(_ r: RainRecord, asOf t: Date) -> RainRecord {
        RainRecord(basis: r.basis, drainageKm2: r.drainageKm2, source: r.source, steps: r.steps.filter { $0.end <= t })
    }

    static func flow(_ s: FlowSeries?, asOf t: Date) -> FlowSeries? {
        guard let s else { return nil }
        let pts = s.points.filter { $0.validTime <= t }
        return pts.isEmpty ? nil : FlowSeries(provenance: s.provenance, source: s.source, points: pts)
    }

    public func inputs(arm id: String, asOf t: Date, baseline: BaselineVisibility? = nil) -> ArmClarityInputs? {
        guard let a = arms[id] else { return nil }
        return ArmClarityInputs(lakeId: lakeId, armId: a.armId, armName: a.armName,
                                anchor: Self.selectAnchor(a.anchors, asOf: t), rain: Self.rain(a.rain, asOf: t),
                                flow: FlowRecord(measured: Self.flow(a.flow.measured, asOf: t),
                                                 modeled: Self.flow(a.flow.modeled, asOf: t)),
                                baseline: baseline, parentArmName: a.parentArmName)
    }

    public func mainStemInputs(asOf t: Date, baseline: BaselineVisibility? = nil) -> MainStemClarityInputs? {
        guard let m = mainStem else { return nil }
        func rel(_ s: ReleaseSeries?) -> ReleaseSeries? {
            guard let s else { return nil }
            let pts = s.points.filter { $0.validTime <= t }
            return pts.isEmpty ? nil : ReleaseSeries(dam: s.dam, tva: s.tva, points: pts)
        }
        return MainStemClarityInputs(lakeId: lakeId, river: m.river, anchor: Self.selectAnchor(m.anchors, asOf: t),
                                     directRain: Self.rain(m.directRain, asOf: t), inflow: rel(m.inflow),
                                     outflow: rel(m.outflow), inflowDamName: m.inflowDamName,
                                     outflowDamName: m.outflowDamName, baseline: baseline)
    }
}
