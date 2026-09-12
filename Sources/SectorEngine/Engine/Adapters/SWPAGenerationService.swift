//
//  SWPAGenerationService.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Southwestern Power Administration — the federal marketer for USACE hydro in
//  Arkansas, Oklahoma, Missouri and Kansas. Covers the water TVA doesn't:
//  Bull Shoals, Norfork, Beaver, Table Rock, Greers Ferry, Dardanelle, Ozark,
//  Tenkiller, Eufaula and the rest of the Southwestern fleet.
//
//  Source is SWPA's daily generation schedule, one fixed-width page per weekday:
//    https://www.energy.gov/swpa/mon.htm … sun.htm
//
//  The page carries two things we need:
//    1. A 24 x 18 grid of PROJECTED MEGAWATTS — hour (rows) by project (cols).
//    2. A PROJECT TABLE giving, per project: number of units, total plant
//       capacity (MW) and approximate full-power discharge (CFS).
//
//  ⚠️ SWPA publishes MEGAWATTS, not unit counts — unlike TVA, which states the
//  units outright. We derive units as `MW / (plantMW / units)` and flag every
//  window `unitsAreDerived`, so the sheet can footnote it rather than pass a
//  derived figure off as the operator's own. Real units aren't identically
//  sized, so treat the count as a close estimate, not gospel.
//
//  "Hour ending" format: the row labelled 14 is the release from 1 PM to 2 PM.
//
//  No observed feed here — SWPA publishes the plan, not the record. `history`
//  and the elevations come back empty and those sheet sections hide themselves.
//

import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif
#if canImport(CoreLocation)
import CoreLocation
#endif

final class SWPAGenerationService: GenerationProvider {
    static let shared = SWPAGenerationService()
    private init() {}

    let operatorID: GenerationOperator = .swpa

    /// Schedules are revised through the day; re-read hourly.
    private static let ttl: TimeInterval = 60 * 60

    private var cached: (day: String, value: [String: [Int]], at: Date)?
    private var cachedGeneration: [String: (value: DamGeneration, at: Date)] = [:]

    // MARK: Roster

    /// SWPA's projects, from the PROJECT TABLE printed on every schedule page.
    /// Static because the fleet doesn't change — and because it lets the picker
    /// populate without a network round trip.
    ///
    /// `units` / `plantMW` / `fullPowerCfs` are SWPA's own published figures;
    /// coordinates are the dam sites.
    struct Project {
        let abbr: String        // column key on the schedule grid
        let name: String
        let lake: String
        let river: String
        let latitude: Double
        let longitude: Double
        let units: Int
        let plantMW: Double
        let fullPowerCfs: Double
        /// Local zone. The whole Southwestern fleet sits in US Central.
        var timeZone: TimeZone { TimeZone(identifier: "America/Chicago") ?? .current }
    }

    static let projects: [Project] = [
        Project(abbr: "BBD", name: "Broken Bow Dam",       lake: "Broken Bow Lake",   river: "Mountain Fork",
                latitude: 34.1467, longitude: -94.6875, units: 2, plantMW: 115, fullPowerCfs: 7_900),
        Project(abbr: "DEN", name: "Denison Dam",          lake: "Lake Texoma",       river: "Red",
                latitude: 33.8172, longitude: -96.5678, units: 2, plantMW: 100, fullPowerCfs: 10_400),
        Project(abbr: "KEY", name: "Keystone Dam",         lake: "Keystone Lake",     river: "Arkansas",
                latitude: 36.1503, longitude: -96.2506, units: 2, plantMW: 80,  fullPowerCfs: 12_000),
        Project(abbr: "FGD", name: "Fort Gibson Dam",      lake: "Fort Gibson Lake",  river: "Grand",
                latitude: 35.8783, longitude: -95.2306, units: 4, plantMW: 50,  fullPowerCfs: 10_900),
        Project(abbr: "WFD", name: "Webbers Falls Dam",    lake: "Webbers Falls Lake", river: "Arkansas",
                latitude: 35.5514, longitude: -95.1758, units: 3, plantMW: 69,  fullPowerCfs: 35_000),
        Project(abbr: "TKD", name: "Tenkiller Ferry Dam",  lake: "Tenkiller Lake",    river: "Illinois",
                latitude: 35.5981, longitude: -95.0472, units: 2, plantMW: 45,  fullPowerCfs: 4_100),
        Project(abbr: "EUF", name: "Eufaula Dam",          lake: "Lake Eufaula",      river: "Canadian",
                latitude: 35.3025, longitude: -95.3572, units: 3, plantMW: 103, fullPowerCfs: 15_100),
        Project(abbr: "RSK", name: "Robert S. Kerr Dam",   lake: "Robert S. Kerr Lake", river: "Arkansas",
                latitude: 35.3517, longitude: -94.7817, units: 4, plantMW: 126, fullPowerCfs: 45_000),
        Project(abbr: "OZK", name: "Ozark Dam",            lake: "Ozark Lake",        river: "Arkansas",
                latitude: 35.4506, longitude: -93.8100, units: 5, plantMW: 115, fullPowerCfs: 75_000),
        Project(abbr: "DAD", name: "Dardanelle Dam",       lake: "Lake Dardanelle",   river: "Arkansas",
                latitude: 35.2597, longitude: -93.1789, units: 4, plantMW: 148, fullPowerCfs: 50_000),
        Project(abbr: "BEV", name: "Beaver Dam",           lake: "Beaver Lake",       river: "White",
                latitude: 36.4200, longitude: -93.8467, units: 2, plantMW: 128, fullPowerCfs: 8_800),
        Project(abbr: "TRD", name: "Table Rock Dam",       lake: "Table Rock Lake",   river: "White",
                latitude: 36.5958, longitude: -93.3114, units: 4, plantMW: 230, fullPowerCfs: 15_100),
        Project(abbr: "BSD", name: "Bull Shoals Dam",      lake: "Bull Shoals Lake",  river: "White",
                latitude: 36.3639, longitude: -92.5769, units: 8, plantMW: 391, fullPowerCfs: 26_400),
        Project(abbr: "NFD", name: "Norfork Dam",          lake: "Norfork Lake",      river: "North Fork",
                latitude: 36.2506, longitude: -92.2408, units: 2, plantMW: 92,  fullPowerCfs: 7_200),
        Project(abbr: "GFD", name: "Greers Ferry Dam",     lake: "Greers Ferry Lake", river: "Little Red",
                latitude: 35.5192, longitude: -91.9989, units: 2, plantMW: 110, fullPowerCfs: 7_900),
        Project(abbr: "STD", name: "Stockton Dam",         lake: "Stockton Lake",     river: "Sac",
                latitude: 37.6672, longitude: -93.7639, units: 1, plantMW: 52,  fullPowerCfs: 8_300),
        Project(abbr: "HST", name: "Harry S Truman Dam",   lake: "Truman Lake",       river: "Osage",
                latitude: 38.2650, longitude: -93.4008, units: 6, plantMW: 184, fullPowerCfs: 65_000),
        Project(abbr: "CAN", name: "Clarence Cannon Dam",  lake: "Mark Twain Lake",   river: "Salt",
                latitude: 39.5314, longitude: -91.6431, units: 2, plantMW: 70,  fullPowerCfs: 12_900),
    ]

    func dams() async -> [GenerationDam] {
        Self.projects.map {
            GenerationDam(id: "SWPA-\($0.abbr)", operatorID: .swpa, name: $0.name,
                          latitude: $0.latitude, longitude: $0.longitude,
                          river: $0.river, lakeNameOverride: $0.lake)
        }
    }

    // MARK: Generation

    func generation(for dam: GenerationDam, distanceMiles: Double) async -> DamGeneration? {
        guard let project = Self.projects.first(where: { "SWPA-\($0.abbr)" == dam.id }) else { return nil }

        if let hit = cachedGeneration[dam.id], Date().timeIntervalSince(hit.at) < Self.ttl {
            return hit.value
        }
        guard let grid = await schedule(), let mw = grid[project.abbr] else { return nil }

        let windows = Self.windows(fromHourlyMW: mw, project: project)
        guard !windows.isEmpty else { return nil }

        // "Release" for the stat row = this hour's scheduled discharge. It's the
        // plan, not a gage reading — SWPA has no observed feed — so it's derived
        // from MW against the project's full-power figures.
        let now = Date()
        let nowMW = Self.megawatts(at: now, hourly: mw, zone: project.timeZone)
        let cfs = nowMW.map { $0 / project.plantMW * project.fullPowerCfs }

        let result = DamGeneration(dam: dam, distanceMiles: distanceMiles, windows: windows,
                                   dischargeCfs: cfs, dischargeTrend12hCfs: nil,
                                   reservoirElevationFt: nil, tailwaterElevationFt: nil,
                                   observedAt: nil, history: [])
        cachedGeneration[dam.id] = (result, Date())
        return result
    }

    // MARK: Fetch + parse

    /// Today's grid, keyed by project abbreviation → 24 hourly megawatt values.
    private func schedule() async -> [String: [Int]]? {
        let day = Self.pageName(for: Date())
        if let cached, cached.day == day, Date().timeIntervalSince(cached.at) < Self.ttl {
            return cached.value
        }
        guard let url = URL(string: "https://www.energy.gov/swpa/\(day).htm") else { return nil }
        var request = URLRequest(url: url)
        request.timeoutInterval = 12
        // energy.gov serves the schedule inside a normal page; a browsery UA
        // avoids the bot-challenge variant.
        request.setValue("Mozilla/5.0 (compatible; Sector/1.0)", forHTTPHeaderField: "User-Agent")

        guard let (data, response) = try? await Net.session.data(for: request),
              let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode),
              let html = String(data: data, encoding: .utf8) ?? String(data: data, encoding: .isoLatin1)
        else { return nil }

        guard let grid = Self.parseGrid(html: html) else { return nil }
        cached = (day, grid, Date())
        return grid
    }

    /// "mon" … "sun" — SWPA keys pages by weekday, not date.
    static func pageName(for date: Date) -> String {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "America/Chicago") ?? .current
        let names = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
        return names[(cal.component(.weekday, from: date) - 1) % 7]
    }

    /// Pull the fixed-width grid out of the page: a header row of project
    /// abbreviations, then 24 rows of hour + megawatts.
    static func parseGrid(html: String) -> [String: [Int]]? {
        let text = strippedText(html)
        let lines = text.components(separatedBy: .newlines)

        // Header row starts with "HR" and lists the project columns.
        guard let headerIdx = lines.firstIndex(where: {
            $0.trimmingCharacters(in: .whitespaces).hasPrefix("HR ")
        }) else { return nil }
        let abbrs = lines[headerIdx].split(whereSeparator: \.isWhitespace).dropFirst().map(String.init)
        guard !abbrs.isEmpty else { return nil }

        var grid: [String: [Int]] = [:]
        for a in abbrs { grid[a] = [] }

        for line in lines[(headerIdx + 1)...] {
            let parts = line.split(whereSeparator: \.isWhitespace).map(String.init)
            // Rows are "<hour> <mw> <mw> …"; stop at TOTAL or anything ragged.
            guard let hour = Int(parts.first ?? ""), (1...24).contains(hour),
                  parts.count == abbrs.count + 1 else {
                if parts.first?.uppercased() == "TOT" || parts.first?.uppercased() == "TOTAL" { break }
                continue
            }
            for (i, a) in abbrs.enumerated() {
                grid[a]?.append(Int(parts[i + 1]) ?? 0)
            }
            if grid[abbrs[0]]?.count == 24 { break }
        }
        // Only trust a complete day.
        guard grid.values.allSatisfy({ $0.count == 24 }) else { return nil }
        return grid
    }

    /// Crude but sufficient tag strip — the schedule is plain text inside <pre>.
    static func strippedText(_ html: String) -> String {
        var s = html
        for tag in ["script", "style"] {
            while let open = s.range(of: "<\(tag)", options: .caseInsensitive),
                  let close = s.range(of: "</\(tag)>", options: .caseInsensitive, range: open.lowerBound..<s.endIndex) {
                s.removeSubrange(open.lowerBound..<close.upperBound)
            }
        }
        s = s.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
        return s.replacingOccurrences(of: "&nbsp;", with: " ")
                .replacingOccurrences(of: "&amp;", with: "&")
    }

    // MARK: Deriving units + windows

    /// Units running for a given megawatt figure, from the project's own plant
    /// capacity and unit count. Approximate — units aren't identically sized.
    static func units(forMW mw: Int, project: Project) -> Int {
        guard mw > 0, project.units > 0 else { return 0 }
        let perUnit = project.plantMW / Double(project.units)
        guard perUnit > 0 else { return 0 }
        return Swift.min(Swift.max(Int((Double(mw) / perUnit).rounded()), 1), project.units)
    }

    /// Megawatts scheduled for the hour containing `date`.
    static func megawatts(at date: Date, hourly: [Int], zone: TimeZone) -> Double? {
        var cal = Calendar(identifier: .gregorian); cal.timeZone = zone
        let h = cal.component(.hour, from: date)      // 0…23
        guard hourly.indices.contains(h) else { return nil }
        return Double(hourly[h])
    }

    /// Collapse 24 hourly megawatt readings into contiguous windows of equal
    /// unit count — the same shape TVA publishes directly.
    static func windows(fromHourlyMW hourly: [Int], project: Project,
                        on day: Date = Date()) -> [GenerationWindow] {
        guard hourly.count == 24 else { return [] }
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = project.timeZone
        let midnight = cal.startOfDay(for: day)

        var out: [GenerationWindow] = []
        var runStart = 0
        var runUnits = units(forMW: hourly[0], project: project)

        func flush(endHour: Int) {
            guard let s = cal.date(byAdding: .hour, value: runStart, to: midnight),
                  let e = cal.date(byAdding: .hour, value: endHour, to: midnight) else { return }
            out.append(GenerationWindow(start: s, end: e, generators: runUnits,
                                        isMinimum: false, unitsAreDerived: true,
                                        timeZone: project.timeZone))
        }

        for h in 1..<24 {
            let u = units(forMW: hourly[h], project: project)
            if u != runUnits {
                flush(endHour: h)
                runStart = h
                runUnits = u
            }
        }
        flush(endHour: 24)
        return out
    }
}
