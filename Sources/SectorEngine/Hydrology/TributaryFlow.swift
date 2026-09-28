//
//  TributaryFlow.swift
//  Sector — each arm's inflow, with where the number came from
//
//  EACH GAUGED ARM READS ITS OWN GAUGE. The conditions engine takes the
//  nearest USGS discharge gauge by straight line, so Browns Creek ran on Town
//  Creek's gauge 38 km away in another arm, and Town Creek's own arm ran on
//  South Sauty's. Here an arm's gauge is the active USGS discharge site on the
//  creek's own NHDPlus network (HydrologyGraph.Arm.usgsDischargeSite, found by
//  NLDI upstream navigation), or none.
//
//  MODELED IS NEVER MEASURED. An ungauged creek — or a gauged one whose gauge
//  is stale — reads the National Water Model's analysis for its own reach
//  (NOAA NWPS), labelled `modeledNWM`. On 2026-09-27 at Town Creek the gauge
//  measured 25.8 cfs and the model's analysis said 14.5: they are different
//  things and are never merged. No gauge and no matched reach: `unavailable`,
//  with the reason.
//

import Foundation

public enum FlowProvenance: String, Codable, Equatable {
    case measuredUSGS, modeledNWM, unavailable
}

public struct FlowPoint: Codable, Equatable {
    public let validTime: Date
    public let cfs: Double
    public init(validTime: Date, cfs: Double) { self.validTime = validTime; self.cfs = cfs }
}

public struct TributaryFlow: Codable, Equatable {
    public let arm: String
    public let provenance: FlowProvenance
    public let cfs: Double?
    /// Signed change over the last 12 h, same units.
    public let change12hCfs: Double?
    /// When it was measured (USGS) or the model's valid time (NWM).
    public let observedAt: Date?
    /// "USGS 03572900 TOWN CREEK NEAR GERALDINE AL" | "NWM reach 19649040, analysis and assimilation"
    public let source: String?
    /// The model's short-range forecast — only ever on a modeled value.
    public let forecast: [FlowPoint]?
    public let reason: String?

    public static func unavailable(_ arm: String, _ reason: String) -> TributaryFlow {
        TributaryFlow(arm: arm, provenance: .unavailable, cfs: nil, change12hCfs: nil,
                      observedAt: nil, source: nil, forecast: nil, reason: reason)
    }
}

public enum TributaryFlowService {

    /// A gauge reading older than this is not "now"; the arm falls to the model.
    static let maxGaugeAgeHours = 6.0

    public static func flow(for arm: HydrologyGraph.Arm, now: Date = Date()) async -> TributaryFlow {
        var gaugeNote: String?
        if let site = arm.usgsDischargeSite {
            if let m = await usgs(site: site, arm: arm.id, name: arm.usgsDischargeSiteName, now: now) {
                return m
            }
            gaugeNote = "USGS \(site) has no reading in the last \(Int(maxGaugeAgeHours)) h"
        }
        if let reach = arm.nwmFeatureId {
            if var m = await nwm(reach: reach, arm: arm.id) {
                if let gaugeNote {
                    m = TributaryFlow(arm: m.arm, provenance: .modeledNWM, cfs: m.cfs, change12hCfs: m.change12hCfs,
                                      observedAt: m.observedAt, source: m.source, forecast: m.forecast,
                                      reason: gaugeNote + "; the model stands in")
                }
                return m
            }
            return .unavailable(arm.id, (gaugeNote.map { $0 + "; " } ?? "") + "NWM reach \(reach) did not answer")
        }
        let why = arm.flags.first { $0.hasPrefix("noNHDPlus") || $0.hasPrefix("nwm") }
            .map { "no gauge on this creek and no matching NWM reach (\($0))" }
            ?? "no gauge on this creek and no matching NWM reach"
        return .unavailable(arm.id, (gaugeNote.map { $0 + "; " } ?? "") + why)
    }

    // MARK: USGS

    private struct IVResponse: Decodable {
        let value: Value
        struct Value: Decodable { let timeSeries: [Series] }
        struct Series: Decodable { let values: [Block] }
        struct Block: Decodable { let value: [Point] }
        struct Point: Decodable { let value: String; let dateTime: String }
    }

    static func parseUSGS(_ data: Data) -> [(Date, Double)] {
        guard let r = try? JSONDecoder().decode(IVResponse.self, from: data),
              let pts = r.value.timeSeries.first?.values.first?.value else { return [] }
        let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let g = ISO8601DateFormatter(); g.formatOptions = [.withInternetDateTime]
        return pts.compactMap { p in
            guard let v = Double(p.value), v >= 0,
                  let d = f.date(from: p.dateTime) ?? g.date(from: p.dateTime) else { return nil }
            return (d, v)
        }.sorted { $0.0 < $1.0 }
    }

    private static func usgs(site: String, arm: String, name: String?, now: Date) async -> TributaryFlow? {
        guard let url = URL(string: "https://waterservices.usgs.gov/nwis/iv/?format=json&sites=\(site)&parameterCd=00060&period=PT13H"),
              let r = try? await HTTP.get(url), r.isSuccess else { return nil }
        let pts = parseUSGS(r.body)
        guard let last = pts.last, now.timeIntervalSince(last.0) <= maxGaugeAgeHours * 3600 else { return nil }
        let cutoff = last.0.addingTimeInterval(-12 * 3600)
        let base = pts.last { $0.0 <= cutoff } ?? pts.first
        return TributaryFlow(arm: arm, provenance: .measuredUSGS, cfs: last.1,
                             change12hCfs: base.map { last.1 - $0.1 }, observedAt: last.0,
                             source: "USGS \(site)" + (name.map { " \($0)" } ?? ""), forecast: nil, reason: nil)
    }

    // MARK: NWM (NOAA National Water Prediction Service)

    private struct NWPSResponse: Decodable {
        let analysisAssimilation: Product?
        let shortRange: Product?
        struct Product: Decodable { let series: Series? }
        struct Series: Decodable { let units: String?; let data: [Point]? }
        struct Point: Decodable { let validTime: String; let flow: Double? }
    }

    static func parseNWPS(_ data: Data) -> (analysis: [(Date, Double)], forecast: [(Date, Double)], units: String?)? {
        guard let r = try? JSONDecoder().decode(NWPSResponse.self, from: data) else { return nil }
        let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime]
        func pts(_ p: NWPSResponse.Product?) -> [(Date, Double)] {
            (p?.series?.data ?? []).compactMap { x in
                guard let v = x.flow, v >= 0, let d = f.date(from: x.validTime) else { return nil }
                return (d, v)
            }.sorted { $0.0 < $1.0 }
        }
        return (pts(r.analysisAssimilation), pts(r.shortRange), r.analysisAssimilation?.series?.units)
    }

    private static func nwm(reach: String, arm: String) async -> TributaryFlow? {
        guard let url = URL(string: "https://api.water.noaa.gov/nwps/v1/reaches/\(reach)/streamflow"),
              let r = try? await HTTP.get(url, headers: ["Accept": "application/json"]), r.isSuccess,
              let p = parseNWPS(r.body), let last = p.analysis.last else { return nil }
        // NWPS reports ft³/s; anything else would be a changed API, not a flow
        guard (p.units ?? "ft³/s").contains("ft") else { return nil }
        let cutoff = last.0.addingTimeInterval(-12 * 3600)
        let base = p.analysis.last { $0.0 <= cutoff } ?? p.analysis.first
        return TributaryFlow(arm: arm, provenance: .modeledNWM, cfs: last.1,
                             change12hCfs: base.map { last.1 - $0.1 }, observedAt: last.0,
                             source: "NWM reach \(reach), analysis and assimilation",
                             forecast: p.forecast.map { FlowPoint(validTime: $0.0, cfs: $0.1) }, reason: nil)
    }
}
