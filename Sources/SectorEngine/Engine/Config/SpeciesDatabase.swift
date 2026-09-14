//
//  SpeciesDatabase.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  The seed species table behind the spawn engine (§9). Each row carries spawn
//  temps (soft triangular edges — sources conflict ±several °F, §14), a spawn
//  calendar per region, habitat copy for "where to look", flood dependence, a
//  targeting tier, and a default-legality flag. Tier-3 species never contribute
//  to the spawn score; protected species (legalByDefault == .no) are never
//  auto-recommended (§5.2 / §9).
//
//  Pure data — meant to be tuned from logs and (later) transcribed to Android.
//

import Foundation

public enum FloodDependence: Equatable, Sendable {
    case none
    case partial
    case full      // bigmouth buffalo, alligator gar — strong year-classes only in flood years
    case river     // riverine drift spawners (Asian carps) — target staging, not the act
}

/// Default bowfishing legality before any state lookup. Per the project decision,
/// legality is a global denylist + disclaimer (no per-state table). §9.
public enum LegalDefault: Equatable, Sendable {
    case yes        // freely bowfished in most states
    case check      // seasonal/state closures exist — show a "verify local regs" disclaimer
    case no         // protected/closed by default — NEVER auto-recommend
}

/// Inclusive month range [start, end], 1 = Jan … 12 = Dec. Supports year-wrap
/// (e.g. Oct–Feb). Day granularity is approximated from month boundaries.
public struct MonthRange: Equatable, Sendable {
    public let start: Int
    public let end: Int
    public init(_ start: Int, _ end: Int) { self.start = start; self.end = end }

    private static let cumBefore = [0, 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    private static let daysIn    = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    private var startDOY: Int { Self.cumBefore[start] + 1 }
    private var endDOY: Int { Self.cumBefore[end] + Self.daysIn[end] }

    /// 1.0 inside the window, tapering linearly to 0 over `taperDays` beyond each
    /// edge — soft edges, not a hard switch (§5.2 / §14).
    public func membership(dayOfYear doy: Int, taperDays: Double) -> Double {
        let s = startDOY, e = endDOY
        let inside: Bool
        if s <= e {
            inside = doy >= s && doy <= e
        } else {                       // wraps the new year
            inside = doy >= s || doy <= e
        }
        if inside { return 1 }
        let dStart = circularDistance(doy, s)
        let dEnd = circularDistance(doy, e)
        let nearest = Double(Swift.min(dStart, dEnd))
        guard taperDays > 0 else { return 0 }
        return Swift.max(0, 1 - nearest / taperDays)
    }

    private func circularDistance(_ a: Int, _ b: Int) -> Int {
        let raw = abs(a - b)
        return Swift.min(raw, 365 - raw)
    }
}

public struct SpawnSpecies: Equatable, Sendable {
    public let name: String
    public let spawnMinF: Double
    public let spawnPeakF: Double
    public let spawnMaxF: Double
    public let southWindow: MonthRange
    public let midNorthWindow: MonthRange
    public let westWindow: MonthRange
    public let habitat: String           // "where to look" copy
    public let floodDependence: FloodDependence
    public let tier: SpeciesTier
    public let legalByDefault: LegalDefault
    /// Regions where this species actually occurs — the presence map that keeps a
    /// spawn run from being reported where the fish doesn't live (e.g. buffalo/gar/
    /// bowfin are absent from Pacific-coast drainages, tilapia can't winter in the
    /// North). Coarse by design; refine as coverage grows. §9.
    public let regions: Set<Region>
    /// Hard latitude cap (°N) for warm/tropical species that can't overwinter past
    /// it — tilapia only persist in the deep South (~≤30°N) and heated waters, so
    /// they must never show a spawn run on, say, an Alabama TVA lake. nil = no cap.
    public let presenceMaxLatitude: Double?
    /// False for cavity/nest spawners you can't sight-shoot during the spawn
    /// (channel catfish nest in undercuts/cavities, and bowfishing them is illegal
    /// in most states) — they never drive a bowfishing "spawn run".
    public let sightShootableSpawn: Bool
    /// Invasive Asian carp (silver/bighead) live in the Mississippi/Ohio/Missouri
    /// corridor — NOT the Florida peninsula, the Atlantic seaboard, or the arid
    /// West. Gates presence to a coarse basin box so they don't show in Orlando
    /// or Phoenix. (Grass carp are stocked nationwide, so they don't set this.)
    public let mississippiBasinOnly: Bool

    public init(name: String, spawnMinF: Double, spawnPeakF: Double, spawnMaxF: Double,
                southWindow: MonthRange, midNorthWindow: MonthRange, westWindow: MonthRange,
                habitat: String, floodDependence: FloodDependence, tier: SpeciesTier,
                legalByDefault: LegalDefault,
                regions: Set<Region> = [.south, .lowerMid, .north, .west],
                presenceMaxLatitude: Double? = nil,
                sightShootableSpawn: Bool = true,
                mississippiBasinOnly: Bool = false) {
        self.name = name
        self.spawnMinF = spawnMinF; self.spawnPeakF = spawnPeakF; self.spawnMaxF = spawnMaxF
        self.southWindow = southWindow; self.midNorthWindow = midNorthWindow; self.westWindow = westWindow
        self.habitat = habitat; self.floodDependence = floodDependence; self.tier = tier
        self.legalByDefault = legalByDefault; self.regions = regions
        self.presenceMaxLatitude = presenceMaxLatitude; self.sightShootableSpawn = sightShootableSpawn
        self.mississippiBasinOnly = mississippiBasinOnly
    }

    /// True if this species can be present in `region` (region-only check).
    public func present(in region: Region) -> Bool { regions.contains(region) }

    /// Region + tropical latitude cap (no longitude).
    public func present(in region: Region, latitude: Double) -> Bool {
        present(in: region, latitude: latitude, longitude: -90)
    }

    /// Fullest presence check: region + tropical latitude cap + Mississippi-basin
    /// gate for invasive Asian carp.
    public func present(in region: Region, latitude: Double, longitude: Double) -> Bool {
        guard regions.contains(region) else { return false }
        if let cap = presenceMaxLatitude, latitude > cap { return false }
        if mississippiBasinOnly, !Self.inMississippiBasin(latitude: latitude, longitude: longitude) { return false }
        return true
    }

    /// Coarse Mississippi/Ohio/Missouri corridor. Excludes the Florida peninsula,
    /// the Atlantic seaboard, and everything west of the Great Plains.
    static func inMississippiBasin(latitude: Double, longitude: Double) -> Bool {
        if latitude < 30, longitude > -85 { return false }   // Florida peninsula
        return longitude <= -80 && longitude >= -100
    }

    public func window(for region: Region) -> MonthRange {
        switch region {
        case .south:    return southWindow
        case .lowerMid, .north: return midNorthWindow
        case .west:     return westWindow
        }
    }
}

public enum SpeciesDatabase: Sendable {

    /// All species in `region`. (Region currently selects only the calendar; the
    /// full roster is the same nationwide — temperature gates do the rest.)
    public static func species(in region: Region) -> [SpawnSpecies] { all }

    public static let all: [SpawnSpecies] = [
        // ── Tier 1 — classic shallow spawn-run targets ──────────────────────────
        SpawnSpecies(name: "Common carp", spawnMinF: 59, spawnPeakF: 65, spawnMaxF: 77,
                     southWindow: MonthRange(3, 9), midNorthWindow: MonthRange(4, 7), westWindow: MonthRange(3, 9),
                     habitat: "flooded & submerged grass and weedy 1–3 ft flats — look/listen for thrashing pods",
                     floodDependence: .none, tier: .tier1, legalByDefault: .yes),
        SpawnSpecies(name: "Bigmouth buffalo", spawnMinF: 60, spawnPeakF: 65, spawnMaxF: 75,
                     southWindow: MonthRange(4, 5), midNorthWindow: MonthRange(5, 6), westWindow: MonthRange(4, 6),
                     habitat: "freshly flooded vegetated marsh grass and backwater margins",
                     floodDependence: .full, tier: .tier1, legalByDefault: .yes,
                     regions: [.south, .lowerMid, .north]),
        SpawnSpecies(name: "Smallmouth buffalo", spawnMinF: 57, spawnPeakF: 63, spawnMaxF: 70,
                     southWindow: MonthRange(3, 5), midNorthWindow: MonthRange(4, 6), westWindow: MonthRange(4, 6),
                     habitat: "submerged vegetation in slightly faster water",
                     floodDependence: .partial, tier: .tier1, legalByDefault: .yes,
                     regions: [.south, .lowerMid, .north]),
        SpawnSpecies(name: "Black buffalo", spawnMinF: 64, spawnPeakF: 70, spawnMaxF: 75,
                     southWindow: MonthRange(4, 5), midNorthWindow: MonthRange(4, 5), westWindow: MonthRange(4, 5),
                     habitat: "current edges and flooded vegetation",
                     floodDependence: .partial, tier: .tier1, legalByDefault: .yes,
                     regions: [.south, .lowerMid, .north]),
        SpawnSpecies(name: "Alligator gar", spawnMinF: 68, spawnPeakF: 73, spawnMaxF: 86,
                     southWindow: MonthRange(4, 5), midNorthWindow: MonthRange(5, 6), westWindow: MonthRange(4, 6),
                     habitat: "overbank flooded terrestrial grass by deep backwaters and oxbows",
                     floodDependence: .full, tier: .tier1, legalByDefault: .check,   // seasonal closures
                     regions: [.south, .lowerMid, .north], presenceMaxLatitude: 37),  // Deep South / lower Mississippi — not the upper Midwest/NE
        SpawnSpecies(name: "Spotted gar", spawnMinF: 70, spawnPeakF: 75, spawnMaxF: 79,
                     southWindow: MonthRange(4, 5), midNorthWindow: MonthRange(5, 6), westWindow: MonthRange(4, 6),
                     habitat: "heavily vegetated shallow sloughs and flooded backwaters",
                     floodDependence: .partial, tier: .tier1, legalByDefault: .yes,
                     regions: [.south, .lowerMid, .north], presenceMaxLatitude: 38),  // spotted gar are a southern/central fish
        SpawnSpecies(name: "Longnose gar", spawnMinF: 68, spawnPeakF: 72, spawnMaxF: 77,
                     southWindow: MonthRange(4, 5), midNorthWindow: MonthRange(5, 6), westWindow: MonthRange(4, 6),
                     habitat: "shallow gravel riffles and weedy shallows; gar roll on the surface",
                     floodDependence: .none, tier: .tier1, legalByDefault: .yes,
                     regions: [.south, .lowerMid, .north]),
        SpawnSpecies(name: "Bowfin", spawnMinF: 61, spawnPeakF: 64, spawnMaxF: 66,
                     southWindow: MonthRange(3, 5), midNorthWindow: MonthRange(4, 6), westWindow: MonthRange(4, 6),
                     habitat: "weedy shallow nests near cover",
                     floodDependence: .none, tier: .tier1, legalByDefault: .yes,
                     regions: [.south, .lowerMid, .north]),
        SpawnSpecies(name: "Tilapia", spawnMinF: 68, spawnPeakF: 78, spawnMaxF: 95,
                     southWindow: MonthRange(3, 10), midNorthWindow: MonthRange(6, 8), westWindow: MonthRange(5, 9),
                     habitat: "circular crater nests on shallow 3–5 ft flats (warmwater only)",
                     floodDependence: .none, tier: .tier1, legalByDefault: .yes,
                     regions: [.south, .west],
                     presenceMaxLatitude: 30),   // deep South / heated waters only — no AL freshwater
        SpawnSpecies(name: "Channel catfish", spawnMinF: 75, spawnPeakF: 80, spawnMaxF: 85,
                     southWindow: MonthRange(5, 7), midNorthWindow: MonthRange(6, 8), westWindow: MonthRange(6, 8),
                     habitat: "cavities — undercut banks, logs, riprap, debris",
                     floodDependence: .none, tier: .tier1, legalByDefault: .check,
                     sightShootableSpawn: false),   // cavity nester + broadly illegal to bowfish — never headline
        SpawnSpecies(name: "Gizzard shad", spawnMinF: 60, spawnPeakF: 66, spawnMaxF: 70,
                     southWindow: MonthRange(3, 4), midNorthWindow: MonthRange(5, 6), westWindow: MonthRange(4, 6),
                     habitat: "surface in shallow coves, flats and backwaters",
                     floodDependence: .none, tier: .tier1, legalByDefault: .yes),

        // ── Tier 2 — river/flood spawners: target STAGING fish, not the act ──────
        SpawnSpecies(name: "Grass carp", spawnMinF: 56, spawnPeakF: 73, spawnMaxF: 86,
                     southWindow: MonthRange(4, 9), midNorthWindow: MonthRange(5, 7), westWindow: MonthRange(5, 8),
                     habitat: "warm (>70°F) slow backwaters and side channels where they stage",
                     floodDependence: .river, tier: .tier2, legalByDefault: .yes),
        SpawnSpecies(name: "Silver carp", spawnMinF: 64, spawnPeakF: 72, spawnMaxF: 86,
                     southWindow: MonthRange(4, 7), midNorthWindow: MonthRange(5, 7), westWindow: MonthRange(5, 8),
                     habitat: "warm slow backwaters where they surface-school",
                     floodDependence: .river, tier: .tier2, legalByDefault: .yes,
                     regions: [.south, .lowerMid, .north], mississippiBasinOnly: true),   // not FL/Atlantic/arid West
        SpawnSpecies(name: "Bighead carp", spawnMinF: 64, spawnPeakF: 77, spawnMaxF: 86,
                     southWindow: MonthRange(4, 7), midNorthWindow: MonthRange(5, 7), westWindow: MonthRange(5, 8),
                     habitat: "warm slow backwaters and side channels where they stage",
                     floodDependence: .river, tier: .tier2, legalByDefault: .yes,
                     regions: [.south, .lowerMid, .north], mississippiBasinOnly: true),   // not FL/Atlantic/arid West

        // ── Tier 3 — never a warm-water spawn run (kept for legality/coverage) ───
        SpawnSpecies(name: "Freshwater drum", spawnMinF: 64, spawnPeakF: 70, spawnMaxF: 79,
                     southWindow: MonthRange(4, 5), midNorthWindow: MonthRange(5, 7), westWindow: MonthRange(5, 7),
                     habitat: "open water — not a shallow run",
                     floodDependence: .none, tier: .tier3, legalByDefault: .yes),
        SpawnSpecies(name: "Striped mullet", spawnMinF: 50, spawnPeakF: 55, spawnMaxF: 62,
                     southWindow: MonthRange(10, 2), midNorthWindow: MonthRange(10, 2), westWindow: MonthRange(10, 2),
                     habitat: "inshore flats (spawns offshore in fall — not a warming-water run)",
                     floodDependence: .none, tier: .tier3, legalByDefault: .yes),
        SpawnSpecies(name: "Paddlefish", spawnMinF: 55, spawnPeakF: 58, spawnMaxF: 65,
                     southWindow: MonthRange(3, 4), midNorthWindow: MonthRange(4, 6), westWindow: MonthRange(4, 6),
                     habitat: "river gravel bars",
                     floodDependence: .river, tier: .tier3, legalByDefault: .no),     // protected by default
        SpawnSpecies(name: "American shad", spawnMinF: 54, spawnPeakF: 65, spawnMaxF: 70,
                     southWindow: MonthRange(3, 5), midNorthWindow: MonthRange(3, 5), westWindow: MonthRange(3, 5),
                     habitat: "riverine spring run",
                     floodDependence: .none, tier: .tier3, legalByDefault: .no),      // managed gamefish
    ]
}
