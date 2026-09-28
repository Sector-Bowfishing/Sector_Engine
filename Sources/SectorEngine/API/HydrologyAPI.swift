//
//  HydrologyAPI.swift
//  Sector — the lake's hydrologic inputs, with provenance (Clarity Fusion Stage 1)
//
//  GET /hydrology/graph?lake=Guntersville|AL   the arm graph (static)
//  GET /hydrology?lake=Guntersville|AL         live inputs per arm and for the
//                                              main stem: flow (measuredUSGS |
//                                              modeledNWM | unavailable), rain
//                                              over the arm's drainage (MRMS, or
//                                              unavailable), TVA at both dams
//
//  EXPOSURE ONLY. Nothing scores from these yet: /conditions is unchanged.
//

import Foundation

public struct ArmInputsDTO: Codable, Equatable {
    public let id: String
    public let name: String
    public let parent: String
    public let topLevel: String
    public let receivingRegion: String?
    public let flow: TributaryFlow
    public let rainfall: CatchmentRainfall
}

public struct HydrologyInputsResponse: Codable, Equatable {
    public let lakeId: String
    public let graphVersion: Int
    public let generatedAt: Date
    public let mainStem: MainStemState
    public let arms: [ArmInputsDTO]
    public let notes: [String]
}

actor HydrologyInputsCache {
    static let shared = HydrologyInputsCache()
    private var entries: [String: (at: Date, value: HydrologyInputsResponse)] = [:]
    private var inFlight: [String: Task<HydrologyInputsResponse?, Never>] = [:]
    static let maxAge: TimeInterval = 10 * 60

    func inputs(_ lakeId: String, compute: @escaping @Sendable () async -> HydrologyInputsResponse?) async -> HydrologyInputsResponse? {
        if let e = entries[lakeId], Date().timeIntervalSince(e.at) < Self.maxAge { return e.value }
        if let t = inFlight[lakeId] { return await t.value }
        let t = Task { await compute() }
        inFlight[lakeId] = t
        let v = await t.value
        inFlight[lakeId] = nil
        if let v { entries[lakeId] = (Date(), v) }
        return v
    }
}

extension SectorEngineAPI {

    public static func hydrologyGraph(lakeId: String) -> HydrologyGraph? {
        Hydrology.graph(forLake: lakeId)
    }

    public static func hydrology(lakeId: String) async -> HydrologyInputsResponse? {
        guard let g = Hydrology.graph(forLake: lakeId) else { return nil }
        return await HydrologyInputsCache.shared.inputs(lakeId) { await computeInputs(g) }
    }

    static func computeInputs(_ g: HydrologyGraph, now: Date = Date()) async -> HydrologyInputsResponse {
        let slug = g.lakeId.map { $0.isLetter || $0.isNumber ? String($0) : "_" }.joined()
        // Awaited in turn, not as `async let`: an `async let` still pending
        // beside the task group below aborted the Linux runtime ("freed
        // pointer was not the last allocation", rev 00043).
        let main = await MainStemService.state(for: g)
        let r = await CatchmentRainfallFeed.latest(forLake: slug, arms: g.arms.map(\.id), now: now)
        // Flows eight at a time: one request per creek, and the engine runs
        // one render per instance (see deploy.sh on the 2026-09-14 outage).
        var flows: [String: TributaryFlow] = [:]
        await withTaskGroup(of: TributaryFlow.self) { group in
            var it = g.arms.makeIterator()
            for _ in 0..<8 { if let a = it.next() { group.addTask { await TributaryFlowService.flow(for: a, now: now) } } }
            for await f in group {
                flows[f.arm] = f
                if let a = it.next() { group.addTask { await TributaryFlowService.flow(for: a, now: now) } }
            }
        }
        let arms = g.arms.map { a in
            ArmInputsDTO(id: a.id, name: a.name, parent: a.parent, topLevel: a.topLevel,
                         receivingRegion: a.receivingRegion,
                         flow: flows[a.id] ?? .unavailable(a.id, "not fetched"),
                         rainfall: r[a.id] ?? .unavailable(a.id, reason: "not in the rain feed"))
        }
        return HydrologyInputsResponse(
            lakeId: g.lakeId, graphVersion: g.version, generatedAt: now, mainStem: main, arms: arms,
            notes: ["Topology and measurements only: no current velocities or travel times exist here.",
                    "measuredUSGS is a gauge on that creek; modeledNWM is the National Water Model's analysis for that creek's reach; they are never merged.",
                    "Rain is basin-mean over each arm's NHDPlus drainage, from MRMS Pass 2, once the hourly rain job runs."])
    }
}
