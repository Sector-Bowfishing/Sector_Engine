//
//  AlabamaPowerGenerationService.swift
//  SectorEngine
//
//  Generation for Alabama Power's 14 hydro dams on the Coosa, Tallapoosa and
//  Black Warrior rivers — the ones TVA/SWPA/USACE don't cover (Logan Martin,
//  Lay, Mitchell, Jordan, Bouldin, Weiss, Neely Henry, Harris, Martin, Yates,
//  Thurlow, Smith, Bankhead, Holt).
//
//  Source: apcshorelines.com caches APC's own "lakes API" into WordPress ACF
//  fields, served publicly at /wp-json/wp/v2/our-lakes/{id}. That carries the
//  same things TVA publishes — the forward unit SCHEDULE (units per hour, today
//  + next days), current outflow (cfs) and pool elevation — so APC dams get a
//  real schedule tile instead of an observed-only fallback. All APC dams are
//  Central time. Returns nil on any failure (the caller falls back to CWMS).
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

final class AlabamaPowerGenerationService: GenerationProvider, Sendable {
    static let shared = AlabamaPowerGenerationService()
    private init() {}

    let operatorID: GenerationOperator = .apc

    /// Per-dam reading. APC was fetched on EVERY render with no cache at all; the
    /// schedule is posted a few times a day, so 15 minutes loses nothing and
    /// concurrent renders for the same dam share one request.
    private let generationCache = SingleFlightCache<String, DamGeneration>(
        ttl: 15 * 60, failureTTL: 60, staleOnErrorTTL: 2 * 3600, maxEntries: 50)

    /// A static registry — these are fixed infrastructure. `wpId` is the
    /// WordPress post id used to fetch live data; `coord` is a reference point on
    /// the impoundment (good enough for nearest-dam resolution).
    private struct APCDam {
        let apiId: Int          // APC's own lake id (also in the id string)
        let wpId: Int           // apcshorelines.com WordPress post id
        let name: String        // display / lake name
        let river: String
        let lat: Double
        let lon: Double
        var id: String { "APC-\(apiId)" }
    }

    private static let registry: [APCDam] = [
        .init(apiId: 3,  wpId: 33,   name: "Logan Martin",  river: "Coosa",        lat: 33.551023, lon: -86.188472),
        .init(apiId: 4,  wpId: 34,   name: "Lay",           river: "Coosa",        lat: 33.116552, lon: -86.476998),
        .init(apiId: 5,  wpId: 35,   name: "Mitchell",      river: "Coosa",        lat: 32.864666, lon: -86.455105),
        .init(apiId: 6,  wpId: 36,   name: "Jordan",        river: "Coosa",        lat: 32.651104, lon: -86.302648),
        .init(apiId: 7,  wpId: 37,   name: "Walter Bouldin", river: "Coosa",       lat: 32.600699, lon: -86.289197),
        .init(apiId: 1,  wpId: 4214, name: "Weiss",         river: "Coosa",        lat: 34.198123, lon: -85.606240),
        .init(apiId: 2,  wpId: 26,   name: "Neely Henry",   river: "Coosa",        lat: 33.867656, lon: -86.066724),
        .init(apiId: 8,  wpId: 27,   name: "Harris",        river: "Tallapoosa",   lat: 33.305899, lon: -85.576060),
        .init(apiId: 9,  wpId: 28,   name: "Martin",        river: "Tallapoosa",   lat: 32.810512, lon: -85.898003),
        .init(apiId: 10, wpId: 30,   name: "Yates",         river: "Tallapoosa",   lat: 32.612738, lon: -85.895070),
        .init(apiId: 14, wpId: 29,   name: "Thurlow",       river: "Tallapoosa",   lat: 32.607053, lon: -85.894627),
        .init(apiId: 11, wpId: 24,   name: "Smith",         river: "Black Warrior", lat: 33.994404, lon: -87.150088),
        .init(apiId: 12, wpId: 25,   name: "Bankhead",      river: "Black Warrior", lat: 33.527060, lon: -87.240539),
        .init(apiId: 13, wpId: 32,   name: "Holt",          river: "Black Warrior", lat: 33.341200, lon: -87.415918),
    ]

    private static let centralTZ = TimeZone(identifier: "America/Chicago") ?? .current

    func dams() async -> [GenerationDam] {
        Self.registry.map {
            GenerationDam(id: $0.id, operatorID: .apc, name: $0.name,
                          latitude: $0.lat, longitude: $0.lon, river: $0.river,
                          lakeNameOverride: "\($0.name) Lake")
        }
    }

    func generation(for dam: GenerationDam, distanceMiles: Double) async -> DamGeneration? {
        guard let entry = Self.registry.first(where: { $0.id == dam.id }) else { return nil }
        let reading = await generationCache.value(for: dam.id) { [self] in
            await self.fetchGeneration(for: dam, wpId: entry.wpId)
        }
        return reading?.withDistance(distanceMiles)
    }

    private func fetchGeneration(for dam: GenerationDam, wpId: Int) async -> DamGeneration? {
        guard let acf = await fetchACF(wpId: wpId) else { return nil }

        let windows = Self.parseSchedule(acf["lakes_api_schedule"])
        let flow = Self.double(acf["lakes_api_flow"])
        let level = Self.double(acf["lakes_api_level"])

        // Nothing usable at all → let the caller fall back to CWMS/observed.
        guard !windows.isEmpty || flow != nil || level != nil else { return nil }

        return DamGeneration(
            dam: dam,
            distanceMiles: 0,   // per-caller; see withDistance
            windows: windows,
            dischargeCfs: flow,
            dischargeTrend12hCfs: nil,        // APC publishes a spot flow, no trend
            reservoirElevationFt: level,
            tailwaterElevationFt: nil,
            observedAt: Date(),
            history: [])
    }

    // MARK: - Fetch

    private func fetchACF(wpId: Int) async -> [String: Any]? {
        let path = "https://apcshorelines.com/wp-json/wp/v2/our-lakes/\(wpId)?_fields=acf.lakes_api_flow,acf.lakes_api_level,acf.lakes_api_units,acf.lakes_api_schedule"
        guard let url = URL(string: path) else { return nil }
        guard let result = try? await HTTP.get(url, headers: ["User-Agent": "Mozilla/5.0",
                                                              "Accept": "application/json"]),
              result.isSuccess,
              let obj = try? JSONSerialization.jsonObject(with: result.body) as? [String: Any],
              let acf = obj["acf"] as? [String: Any] else { return nil }
        return acf
    }

    // MARK: - Schedule parsing

    /// `lakes_api_schedule` is a JSON *string* of step changes:
    /// `[{"timestamp":"2026-08-14T00:00:00","units":1,"mthourstart":"1600"}, …]`.
    /// Each step's unit count holds until the next step; consecutive steps become
    /// GenerationWindows in the dam's Central zone.
    static func parseSchedule(_ raw: Any?) -> [GenerationWindow] {
        guard let s = raw as? String, let d = s.data(using: .utf8),
              let arr = try? JSONSerialization.jsonObject(with: d) as? [[String: Any]] else { return [] }

        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = centralTZ

        let steps: [(date: Date, units: Int)] = arr.compactMap { e in
            guard let ts = e["timestamp"] as? String,
                  let day = ts.split(separator: "T").first,
                  let (hh, mm) = hourMinute(e["mthourstart"]) else { return nil }
            let parts = day.split(separator: "-").compactMap { Int($0) }
            guard parts.count == 3 else { return nil }
            var c = DateComponents()
            c.year = parts[0]; c.month = parts[1]; c.day = parts[2]; c.hour = hh; c.minute = mm
            c.timeZone = centralTZ
            guard let date = cal.date(from: c) else { return nil }
            let units = intValue(e["units"]) ?? 0
            return (date, units)
        }
        .sorted { $0.date < $1.date }

        guard !steps.isEmpty else { return [] }
        var windows: [GenerationWindow] = []
        for i in steps.indices {
            let start = steps[i].date
            let end = (i + 1 < steps.count) ? steps[i + 1].date : start.addingTimeInterval(24 * 3600)
            guard end > start else { continue }
            windows.append(GenerationWindow(start: start, end: end, generators: steps[i].units,
                                            isMinimum: false, unitsAreDerived: false, timeZone: centralTZ))
        }
        return windows
    }

    /// "1600" / "0200" / "0000" → (16,0) / (2,0) / (0,0). Tolerates an Int too.
    private static func hourMinute(_ raw: Any?) -> (Int, Int)? {
        let str: String
        if let s = raw as? String { str = s }
        else if let i = raw as? Int { str = String(format: "%04d", i) }
        else { return nil }
        let padded = String(repeating: "0", count: max(0, 4 - str.count)) + str
        guard padded.count == 4, let hh = Int(padded.prefix(2)), let mm = Int(padded.suffix(2)),
              (0...23).contains(hh), (0...59).contains(mm) else { return nil }
        return (hh, mm)
    }

    private static func intValue(_ v: Any?) -> Int? {
        if let i = v as? Int { return i }
        if let d = v as? Double { return Int(d) }
        if let s = v as? String { return Int(s) }
        return nil
    }
    private static func double(_ v: Any?) -> Double? {
        if let d = v as? Double { return d }
        if let i = v as? Int { return Double(i) }
        if let s = v as? String { return Double(s) }
        return nil
    }
}
