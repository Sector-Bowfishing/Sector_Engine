//
//  MainStem.swift
//  Sector — the Tennessee River through Guntersville, as TVA measures it
//
//  The main stem's state at its two ends: what Nickajack Dam releases into the
//  top of the reservoir, and what Guntersville Dam releases out of it, with
//  the pool and tailwater elevations and today's posted generation. All of it
//  is TVA's own hourly record (RestApi observed-data-48-hours) or TVA's posted
//  schedule (generation-releases), labelled as which.
//
//  NO CURRENT. Sector has no velocity anywhere in the reservoir, and a flow
//  rate at a dam says nothing about how fast water moves 40 km up the lake.
//  Nothing here is, or may be turned into, a current speed or a travel time.
//

import Foundation

public struct ScheduledGeneration: Codable, Equatable {
    public let start: Date
    public let end: Date
    public let units: Int
    public let unitsIsMinimum: Bool
}

public struct DamState: Codable, Equatable {
    public let dam: String
    public let name: String
    public let tva: String
    /// "measuredTVA" for the hourly record; the schedule is "scheduledTVA".
    public let provenance: String
    public let releaseCfs: Double?
    public let releaseChange12hCfs: Double?
    public let poolFt: Double?
    public let tailwaterFt: Double?
    public let observedAt: Date?
    public let history: [HistoryPoint]
    public let schedule: [ScheduledGeneration]
    public let scheduleProvenance: String

    public struct HistoryPoint: Codable, Equatable {
        public let at: Date
        public let releaseCfs: Double?
        public let poolFt: Double?
    }
}

public struct MainStemState: Codable, Equatable {
    public let river: String
    /// Nickajack's release: the main stem's inflow at the head of the reservoir.
    public let inflow: DamState?
    /// Guntersville Dam's release: the main stem's outflow.
    public let outflow: DamState?
    /// Stated, so no reader mistakes a dam release for a current.
    public let currentVelocity: String
}

public enum MainStemService {

    public static func state(for graph: HydrologyGraph) async -> MainStemState {
        let dams = await TVAGenerationService.shared.dams()
        // In turn, not as `async let` (see HydrologyAPI.computeInputs).
        let up = await damState(graph.mainStem.upstreamDam, among: dams)
        let down = await damState(graph.mainStem.downstreamDam, among: dams)
        return MainStemState(river: graph.mainStem.name, inflow: up, outflow: down,
                             currentVelocity: "unknown: not measured anywhere in the reservoir")
    }

    private static func damState(_ d: HydrologyGraph.Dam, among dams: [GenerationDam]) async -> DamState? {
        guard let dam = dams.first(where: { $0.id == d.tva || $0.id.hasSuffix(d.tva) }) else { return nil }
        guard let g = await TVAGenerationService.shared.generation(for: dam, distanceMiles: 0) else { return nil }
        return DamState(dam: d.id, name: d.name, tva: d.tva, provenance: "measuredTVA",
                        releaseCfs: g.dischargeCfs, releaseChange12hCfs: g.dischargeTrend12hCfs,
                        poolFt: g.reservoirElevationFt, tailwaterFt: g.tailwaterElevationFt,
                        observedAt: g.observedAt,
                        history: g.history.map { .init(at: $0.at, releaseCfs: $0.dischargeCfs, poolFt: $0.reservoirFt) },
                        schedule: g.windows.map { .init(start: $0.start, end: $0.end, units: $0.generators,
                                                        unitsIsMinimum: $0.isMinimum) },
                        scheduleProvenance: "scheduledTVA")
    }
}
