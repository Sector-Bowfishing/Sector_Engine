//
//  TVAGenerationService.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Live TVA generation: WHEN the units run and HOW MANY. Backs the current
//  factor (§5.7) on Tennessee Valley tailwaters, replacing the "classify from a
//  distant USGS gage" fallback with the operator's own schedule and release.
//
//  Source is TVA's own REST API at https://www.tva.com/RestApi — undocumented
//  but public and unauthenticated; it's what tva.com's Lake Levels pages call.
//  ⚠️ It serves JSON ONLY when asked: without `Accept: application/json` the
//  same URL returns a 20 KB HTML API-explorer page with a 200 status, which
//  then fails to decode. That header is load-bearing.
//
//  Endpoints used:
//    /locations                     — 43 dams; we keep the 37 that generate
//    /generation-releases/{id}      — time windows + generator counts
//    /observed-data-48-hours/{id}   — hourly tailwater elev + discharge (cfs)
//
//  NOT routed through `GenerationForecastProvider`: that protocol's contract is
//  forecast *discharge* (cfs) per hour, and TVA publishes generator COUNTS per
//  window. Converting would need per-unit hydraulic capacity, which this API
//  doesn't expose — so we'd be inventing numbers. The richer `DamGeneration`
//  below is returned as-is and the engine reads what TVA actually said. The
//  protocol stays for a future TVA/USACE cfs feed.
//
//  Undocumented means it can change without notice: every failure path returns
//  nil, and the builder falls straight back to the USGS discharge trend.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

// MARK: - Service

final class TVAGenerationService: GenerationProvider, Sendable {
    let operatorID: GenerationOperator = .tva

    static let shared = TVAGenerationService()
    private init() {}

    private let base = "https://www.tva.com/RestApi"

    /// Beyond this the dam's release isn't your water. Matches the tailwater
    /// radius the registry uses so the two can't disagree about "below a dam".
    static let maxDamDistanceMiles: Double = TailwaterRegistry.tailwaterRadiusMiles

    /// Schedules get revised through the day (and next-day posts land ~6 PM
    /// local), so this can't be a session cache — but it also can't be per-call.
    private static let generationTTL: TimeInterval = 15 * 60

    /// The dam roster is effectively static — held a day. A failed roster fetch
    /// is remembered for a minute so a TVA outage costs one timeout per minute,
    /// not one per render.
    private let rosterCache = SingleFlightCache<String, [GenerationDam]>(
        ttl: 24 * 3600, failureTTL: 60, maxEntries: 1)
    /// Per-dam generation, keyed by dam id and shared by concurrent renders.
    private let generationCache = SingleFlightCache<String, DamGeneration>(
        ttl: TVAGenerationService.generationTTL, failureTTL: 60, maxEntries: 200)

    // MARK: Public

    /// Live generation for the TVA dam nearest `coordinate`, or nil when there
    /// isn't one in range or TVA is unreachable.
    func generation(near coordinate: CLLocationCoordinate2D) async -> DamGeneration? {
        guard let dams = await hydroDams() else { return nil }

        let origin = CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude)
        let nearest = dams
            .map { ($0, origin.distance(from: CLLocation(latitude: $0.latitude, longitude: $0.longitude)) / 1609.34) }
            .min { $0.1 < $1.1 }
        guard let (dam, miles) = nearest, miles <= Self.maxDamDistanceMiles else { return nil }

        return await generation(for: dam, distanceMiles: miles)
    }

    /// The whole roster, for the picker — someone outside tailwater range still
    /// wants to look a lake up by name.
    func dams() async -> [GenerationDam] { await hydroDams() ?? [] }

    /// Generation for a SPECIFIC dam, chosen rather than resolved by proximity.
    func generation(for dam: GenerationDam, distanceMiles: Double) async -> DamGeneration? {
        let reading = await generationCache.value(for: dam.id) { [self] in
            await self.fetchGeneration(for: dam)
        }
        return reading?.withDistance(distanceMiles)
    }

    private func fetchGeneration(for dam: GenerationDam) async -> DamGeneration? {
        async let windowsTask = fetchWindows(damID: dam.id)
        async let observedTask = fetchObserved(damID: dam.id)
        let windows = await windowsTask
        let observed = await observedTask

        // Nothing usable came back — the caller falls back to USGS. Remembered
        // only for the cache's short failure window, not the full TTL.
        guard windows?.isEmpty == false || observed != nil else { return nil }

        return DamGeneration(dam: dam,
                             distanceMiles: 0,   // per-caller; see withDistance
                             windows: windows ?? [],
                             dischargeCfs: observed?.dischargeCfs,
                             dischargeTrend12hCfs: observed?.trend12hCfs,
                             reservoirElevationFt: observed?.reservoirFt,
                             tailwaterElevationFt: observed?.tailwaterFt,
                             observedAt: observed?.at,
                             history: observed?.series ?? [])
    }

    /// Nearest generating dam REGARDLESS of range, with its distance. Lets the
    /// dashboard card stay on screen off a tailwater and say what's true —
    /// "nearest is Norris, 31 mi" — instead of vanishing with no explanation.
    func nearestDam(near coordinate: CLLocationCoordinate2D) async -> (dam: GenerationDam, miles: Double)? {
        guard let dams = await hydroDams() else { return nil }
        let origin = CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude)
        return dams
            .map { ($0, origin.distance(from: CLLocation(latitude: $0.latitude, longitude: $0.longitude)) / 1609.34) }
            .min { $0.1 < $1.1 }
            .map { (dam: $0.0, miles: $0.1) }
    }

    // MARK: Fetch

    private func hydroDams() async -> [GenerationDam]? {
        await rosterCache.value(for: "roster") { [self] in await self.fetchHydroDams() }
    }

    private func fetchHydroDams() async -> [GenerationDam]? {
        guard let dtos: [LocationDTO] = await get("\(base)/locations") else { return nil }
        // ⚠️ `DamType` is NOT a reliable "does it generate" flag. TVA means it as
        // "is this a TVA hydropower project", so all 8 USACE Cumberland dams —
        // Barkley, Wolf Creek, Cheatham, Cordell Hull, Dale Hollow, Center Hill,
        // Old Hickory, Percy Priest — are tagged `Non-hydropower` despite having
        // powerhouses and publishing full schedules through this same API.
        // Filtering on the label alone dropped them, and a spot on Lake Barkley
        // then resolved to Kentucky Dam 2.6 mi away on a different river.
        //
        // Ownership is the honest discriminator: every `Cumberland` project
        // publishes a schedule, and every TVA-owned non-hydro dam (Tellico, the
        // Bear Creek group, Normandy, Cedar Creek) publishes none — verified
        // against all 14 non-hydro entries.
        let dams = dtos
            .filter {
                $0.damType.caseInsensitiveCompare("Hydropower") == .orderedSame
                    || $0.ownership.caseInsensitiveCompare("Cumberland") == .orderedSame
            }
            .map { GenerationDam(id: $0.id, operatorID: .tva, name: $0.name,
                                 latitude: $0.latitude, longitude: $0.longitude,
                                 river: ($0.river == "None" ? "" : $0.river) ?? "") }
        guard !dams.isEmpty else { return nil }
        return dams
    }

    private func fetchWindows(damID: String) async -> [GenerationWindow]? {
        guard let dtos: [ReleaseDTO] = await get("\(base)/generation-releases/\(damID)") else { return nil }
        return dtos
            .compactMap { Self.parseWindow(day: $0.day, time: $0.time, generators: $0.generators) }
            .sorted { $0.start < $1.start }
    }

    private struct Observed {
        let dischargeCfs: Double?
        let trend12hCfs: Double?
        let reservoirFt: Double?
        let tailwaterFt: Double?
        let at: Date
        let series: [GenerationObservation]
    }

    private func fetchObserved(damID: String) async -> Observed? {
        guard let dtos: [ObservedDTO] = await get("\(base)/observed-data-48-hours/\(damID)") else { return nil }

        let points: [(at: Date, cfs: Double?, reservoir: Double?, tailwater: Double?)] = dtos.compactMap { dto in
            guard let zone = Self.zone(from: dto.time),
                  let hour = Self.hour(from: Self.stripZone(dto.time)),
                  let at = Self.date(day: dto.day, hour: hour, zone: zone) else { return nil }
            return (at, Self.number(dto.averageHourlyDischarge),
                    Self.number(dto.reservoirElevation), Self.number(dto.tailwaterElevation))
        }.sorted { $0.at < $1.at }

        guard let latest = points.last else { return nil }

        // Same 12-hour lookback WaterLevelReading.change uses, so the trend the
        // engine sees means the same thing whichever source fed it.
        let cutoff = latest.at.addingTimeInterval(-12 * 3600)
        let baseline = points.last(where: { $0.at <= cutoff }) ?? points.first
        let trend: Double? = {
            guard let now = latest.cfs, let then = baseline?.cfs, baseline?.at != latest.at else { return nil }
            return now - then
        }()

        return Observed(dischargeCfs: latest.cfs,
                        trend12hCfs: trend,
                        reservoirFt: latest.reservoir,
                        tailwaterFt: latest.tailwater,
                        at: latest.at,
                        series: points.map {
                            GenerationObservation(at: $0.at, dischargeCfs: $0.cfs,
                                           reservoirFt: $0.reservoir, tailwaterFt: $0.tailwater)
                        })
    }

    /// One GET, decoded. Returns nil on any failure — TVA is a bonus source,
    /// never a hard dependency.
    private func get<T: Decodable>(_ urlString: String) async -> T? {
        guard let url = URL(string: urlString) else { return nil }
        // The Accept header is load-bearing: without it TVA serves an HTML
        // explorer page, status 200.
        guard let result = try? await HTTP.get(url, headers: ["Accept": "application/json"]),
              result.isSuccess else { return nil }
        return try? JSONDecoder().decode(T.self, from: result.body)
    }
}

// MARK: - Parsing

extension TVAGenerationService {

    /// TVA writes times as prose — "Midnight - 1 AM CDT", "2 AM - 3 PM CDT",
    /// "1 AM - Midnight EDT" — with the zone only on the tail.
    static func parseWindow(day: String, time: String, generators: String) -> GenerationWindow? {
        guard let zone = zone(from: time),
              let (count, isMinimum) = parseGenerators(generators) else { return nil }

        let parts = stripZone(time).components(separatedBy: "-")
        guard parts.count == 2,
              let startHour = hour(from: parts[0]),
              let rawEndHour = hour(from: parts[1]) else { return nil }

        // "1 AM - Midnight" and "Midnight - Midnight" both end on the NEXT day.
        let endHour = rawEndHour > startHour ? rawEndHour : rawEndHour + 24

        guard let start = date(day: day, hour: startHour, zone: zone),
              let end = date(day: day, hour: endHour, zone: zone) else { return nil }

        return GenerationWindow(start: start, end: end,
                                generators: count, isMinimum: isMinimum,
                                // TVA states unit counts outright.
                                unitsAreDerived: false, timeZone: zone)
    }

    /// "0" → (0, false); "2 or more" → (2, true).
    static func parseGenerators(_ text: String) -> (count: Int, isMinimum: Bool)? {
        let trimmed = text.trimmingCharacters(in: .whitespaces)
        let digits = trimmed.prefix { $0.isNumber }
        guard let count = Int(digits) else { return nil }
        return (count, trimmed.lowercased().contains("or more"))
    }

    /// "Midnight" → 0, "Noon" → 12, "5 AM" → 5, "3 PM" → 15.
    static func hour(from token: String) -> Int? {
        let t = token.trimmingCharacters(in: .whitespaces).uppercased()
        if t == "MIDNIGHT" { return 0 }
        if t == "NOON" { return 12 }
        let parts = t.split(separator: " ")
        guard parts.count == 2, let n = Int(parts[0]), (1...12).contains(n) else { return nil }
        switch parts[1] {
        case "AM": return n == 12 ? 0 : n
        case "PM": return n == 12 ? 12 : n + 12
        default:   return nil
        }
    }

    /// Zone lives on the tail of the string and VARIES BY DAM — Eastern for the
    /// upper Tennessee/Holston/Clinch, Central for Guntersville, Wheeler,
    /// Wilson, Pickwick, Nickajack and Kentucky. Never assume device-local.
    static func zone(from text: String) -> TimeZone? {
        let t = text.uppercased()
        if t.hasSuffix("EDT") || t.hasSuffix("EST") { return TimeZone(identifier: "America/New_York") }
        if t.hasSuffix("CDT") || t.hasSuffix("CST") { return TimeZone(identifier: "America/Chicago") }
        return nil
    }

    static func stripZone(_ text: String) -> String {
        var t = text.trimmingCharacters(in: .whitespaces)
        for abbr in ["EDT", "EST", "CDT", "CST"] where t.uppercased().hasSuffix(abbr) {
            t = String(t.dropLast(abbr.count)).trimmingCharacters(in: .whitespaces)
            break
        }
        return t
    }

    /// "08/03/2026" + an hour in the dam's zone. `hour` may be 24+ so a window
    /// can run past midnight into the next day.
    static func date(day: String, hour: Int, zone: TimeZone) -> Date? {
        let parts = day.split(separator: "/").compactMap { Int($0) }
        guard parts.count == 3 else { return nil }
        var components = DateComponents()
        components.year = parts[2]; components.month = parts[0]; components.day = parts[1]
        components.hour = 0
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = zone
        guard let midnight = calendar.date(from: components) else { return nil }
        return calendar.date(byAdding: .hour, value: hour, to: midnight)
    }

    /// TVA sends numbers as comma-grouped strings — "32,614".
    static func number(_ text: String?) -> Double? {
        guard let text else { return nil }
        return Double(text.replacingOccurrences(of: ",", with: ""))
    }
}

// MARK: - DTOs

private struct LocationDTO: Decodable {
    let id: String
    let name: String
    let latitude: Double
    let longitude: Double
    let damType: String
    let ownership: String
    let river: String?

    enum CodingKeys: String, CodingKey {
        case id = "LocationID", name = "Name"
        case latitude = "Lat", longitude = "Long"
        case damType = "DamType", ownership = "Ownership"
        case river = "River"
    }
}

private struct ReleaseDTO: Decodable {
    let day: String
    let time: String
    let generators: String

    enum CodingKeys: String, CodingKey {
        case day = "Day", time = "Time", generators = "Generators"
    }
}

private struct ObservedDTO: Decodable {
    let day: String
    let time: String
    let reservoirElevation: String?
    let tailwaterElevation: String?
    let averageHourlyDischarge: String?

    enum CodingKeys: String, CodingKey {
        case day = "Day", time = "Time"
        case reservoirElevation = "ReservoirElevation"
        case tailwaterElevation = "TailwaterElevation"
        case averageHourlyDischarge = "AverageHourlyDischarge"
    }
}
