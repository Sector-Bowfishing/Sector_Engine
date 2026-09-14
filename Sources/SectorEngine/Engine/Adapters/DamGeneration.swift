//
//  DamGeneration.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Source-agnostic dam-generation model. Started life as TVA-only; the shapes
//  turned out to be general, so they moved here when a second operator (SWPA)
//  was added. Anything TVA-specific stays in TVAGenerationService.
//
//  There is NO national dam-generation feed — coverage is federated across
//  operators and degrades in tiers: some publish a forward schedule with unit
//  counts (TVA, SWPA), some only observed release. `GenerationProvider` is the
//  seam each operator implements; `GenerationService` fans out across them and
//  returns whichever covers the water you're on.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

// MARK: - Model

/// Which operator published this dam's data. Determines what we can say about
/// it — see `GenerationProvider` for the coverage tiers.
enum GenerationOperator: String, Equatable {
    case tva = "TVA"
    case swpa = "SWPA"
    /// Observed-only tier: no published schedule, but CWMS carries the measured
    /// pool, tailwater, and outflow. Covers the USACE projects outside the
    /// TVA/SWPA marketing areas — the majority of dam lakes in the directory.
    case usace = "USACE"
    /// Alabama Power — its 14 Coosa/Tallapoosa/Black-Warrior hydro dams, with a
    /// published unit schedule + current flow/level (via apcshorelines.com).
    case apc = "APC"

    /// Shown next to the dam name in the sheet header.
    var label: String { self == .apc ? "Alabama Power" : rawValue }
}

/// A generating dam, from whichever operator publishes it.
struct GenerationDam: Equatable, Identifiable {
    /// Operator-scoped ID — TVA's NWS-style code ("NRST1"), SWPA's abbreviation
    /// ("BSD"). Prefixed by operator so IDs can't collide across sources.
    let id: String
    let operatorID: GenerationOperator
    let name: String
    let latitude: Double
    let longitude: Double
    var coordinate: CLLocationCoordinate2D { .init(latitude: latitude, longitude: longitude) }
    /// The river it sits on — the picker searches and displays it, since people
    /// think in water ("Clinch", "Cumberland") as much as in dam names.
    let river: String
    /// Set when the operator publishes the lake name outright (SWPA does).
    /// TVA doesn't, so its lakes are derived below.
    var lakeNameOverride: String? = nil

    /// The impoundment people actually search for. TVA's feed only carries the
    /// DAM name, and most lakes are just "<dam> Lake" — but enough aren't that
    /// the exceptions are listed explicitly rather than derived. The dam name is
    /// still shown as the subtitle, so nothing is lost either way.
    var lakeName: String {
        if let lakeNameOverride { return lakeNameOverride }
        if let override = Self.lakeNameOverrides[id] { return override }
        guard name.hasSuffix(" Dam") else { return name }
        return String(name.dropLast(4)) + " Lake"
    }

    private static let lakeNameOverrides: [String: String] = [
        "WLCK2": "Lake Cumberland",   // NOT "Wolf Creek Lake"
        "BARK2": "Lake Barkley",      // word order flips
        "OCAT1": "Parksville Lake",   // Ocoee No. 1 impounds Parksville
        "JPHT1": "Percy Priest Lake",
        // The other two Ocoee projects are flume diversions with no named
        // reservoir — keep the dam name rather than invent a lake.
        "OCBT1": "Ocoee No. 2 Dam",
        "OCCT1": "Ocoee No. 3 Dam",
    ]
}

/// One scheduled block: "5 PM – 6 PM EDT → 1 unit".
struct GenerationWindow: Equatable {
    let start: Date
    let end: Date
    /// Units TVA expects to run in this block.
    let generators: Int
    /// The operator said "N or more" rather than an exact count — `generators`
    /// is a floor.
    let isMinimum: Bool
    /// True when the unit count was DERIVED from published megawatts rather than
    /// stated outright. SWPA publishes MW; TVA publishes units. The number is a
    /// good estimate either way, but the sheet footnotes it so a derived count
    /// is never passed off as the operator's own figure.
    let unitsAreDerived: Bool
    /// The DAM's zone, not the device's. Times are shown the way TVA posted
    /// them, so a Central-zone dam still reads "3 PM" to someone in Eastern.
    let timeZone: TimeZone

    func contains(_ date: Date) -> Bool { date >= start && date < end }

    /// "2 units", "1 unit", "2+ units", "Off".
    var unitsLabel: String {
        guard generators > 0 else { return "Off" }
        return "\(generators)\(isMinimum ? "+" : "") unit\(generators == 1 && !isMinimum ? "" : "s")"
    }
}

/// One hour of observed record below the dam — what actually came out, as
/// opposed to what the schedule said would.
struct GenerationObservation: Equatable {
    let at: Date
    let dischargeCfs: Double?
    let reservoirFt: Double?
    let tailwaterFt: Double?
}

/// Everything the engine needs from TVA for one tailwater.
struct DamGeneration: Equatable, Identifiable {
    var id: String { dam.id }
    let dam: GenerationDam
    /// Straight-line miles from the requested coordinate to the dam.
    let distanceMiles: Double
    /// Today's schedule (plus whatever of tomorrow TVA has posted), in order.
    let windows: [GenerationWindow]
    /// The dam's OWN release — far truer than a USGS gage tens of miles off.
    let dischargeCfs: Double?
    /// Signed 12-hour change in that release, matching `WaterLevelReading.change`.
    let dischargeTrend12hCfs: Double?
    /// Pool elevation BEHIND the dam (ft). Pairs with `tailwaterElevationFt`:
    /// the difference is the head the units are running on.
    let reservoirElevationFt: Double?
    /// Water level BELOW the dam (ft) — the level you're actually standing in.
    let tailwaterElevationFt: Double?
    let observedAt: Date?
    /// The last 48 hours of observed record, oldest → newest. Pairs with
    /// `windows`: the schedule is what TVA intends, this is what the dam did.
    let history: [GenerationObservation]

    var hasSchedule: Bool { !windows.isEmpty }

    /// Units running at `date`, or nil when the schedule doesn't cover it.
    func generators(at date: Date) -> Int? {
        windows.first { $0.contains(date) }?.generators
    }

    /// The next block that actually turns water on — "generation starts at 5 PM".
    func nextGenerationStart(after date: Date) -> GenerationWindow? {
        windows.first { $0.start >= date && $0.generators > 0 }
    }

    /// The block covering `date`, for "running until 3 PM".
    func window(at date: Date) -> GenerationWindow? {
        windows.first { $0.contains(date) }
    }

    /// The first block after `date` that shuts the units off — the point the
    /// tailwater starts settling, which is the window worth shooting.
    func nextShutdown(after date: Date) -> GenerationWindow? {
        windows.first { $0.start >= date && $0.generators == 0 }
    }

    /// The dam's local zone, for formatting. Falls back to the device's.
    var timeZone: TimeZone { windows.first?.timeZone ?? .current }

    /// Only the blocks where water is actually moving. The off-periods aren't
    /// events — they're the gaps between these, and the sheet renders them as
    /// one collapsed "settled" line rather than a row apiece.
    var releases: [GenerationWindow] { windows.filter { $0.generators > 0 } }

    /// The calm stretch following `release` — from its end to the next release,
    /// or to the end of the posted schedule when it's the last one. Routinely
    /// crosses midnight, which is why it's a span and not a per-day figure.
    func settledSpan(after release: GenerationWindow) -> (start: Date, end: Date)? {
        let end = releases.first { $0.start >= release.end }?.start
            ?? windows.last?.end
        guard let end, end > release.end else { return nil }
        return (release.end, end)
    }

    /// Releases for one local day, with the total time water is moving — feeds
    /// the "2 releases · 2h running" day header.
    func daySummary(_ day: Date) -> (count: Int, running: TimeInterval) {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = timeZone
        let todays = releases.filter { cal.isDate($0.start, inSameDayAs: day) }
        return (todays.count, todays.reduce(0) { $0 + $1.end.timeIntervalSince($1.start) })
    }

    /// Windows grouped by their local day, in order. TVA posts the next day
    /// mid-afternoon, so the schedule routinely spans 2–3 calendar days — and
    /// without a divider the same clock times appear twice with no way to tell
    /// which is which.
    func windowsByDay() -> [(day: Date, windows: [GenerationWindow])] {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = timeZone
        var order: [Date] = []
        var byDay: [Date: [GenerationWindow]] = [:]
        for w in windows {
            let day = cal.startOfDay(for: w.start)
            if byDay[day] == nil { order.append(day) }
            byDay[day, default: []].append(w)
        }
        return order.map { ($0, byDay[$0] ?? []) }
    }

    /// The level the current factor scores. When TVA says the dam is OFF right
    /// now, that settles it — the water is calm and clearing regardless of what
    /// a gage miles downstream still reads from the last pulse. Otherwise fall
    /// through to the same discharge classification the USGS path uses, but fed
    /// the dam's own release instead of a distant gage's.
    func level(at date: Date = Date(),
               config: ConditionsConfig = .default) -> GenerationLevel? {
        if generators(at: date) == 0 { return .low }
        return CurrentFactor.classify(dischargeCfs: dischargeCfs,
                                      trendCfs: dischargeTrend12hCfs,
                                      cfg: config.current)
    }

    /// The same reading as seen from a different point. Adapters cache one
    /// reading per dam and hand each caller its own distance — a cached value
    /// must never carry the first caller's distance to everyone else.
    func withDistance(_ miles: Double) -> DamGeneration {
        DamGeneration(dam: dam, distanceMiles: miles, windows: windows,
                      dischargeCfs: dischargeCfs, dischargeTrend12hCfs: dischargeTrend12hCfs,
                      reservoirElevationFt: reservoirElevationFt,
                      tailwaterElevationFt: tailwaterElevationFt,
                      observedAt: observedAt, history: history)
    }
}

// MARK: - Provider seam

/// One operator's feed.
///
/// Coverage is uneven by design and that's fine — the sheet degrades. TVA and
/// SWPA both publish a forward schedule, so the hero can say "next release at
/// 5 PM". Operators that only publish observed release would return windows
/// empty, and the sheet falls back to history alone.
/// `Sendable` because every render reaches providers from its own concurrent
/// tasks: an implementation must keep no unsynchronized mutable state (cache
/// through `SingleFlightCache`).
protocol GenerationProvider: Sendable {
    var operatorID: GenerationOperator { get }
    /// Every dam this operator publishes. Cached by the implementation.
    func dams() async -> [GenerationDam]
    /// Full detail for one dam, or nil if the feed is unreachable.
    func generation(for dam: GenerationDam, distanceMiles: Double) async -> DamGeneration?
}

/// Fans out across every operator and answers "what dam governs this water".
///
/// Deliberately picks the NEAREST dam across all operators rather than
/// preferring one — a spot in north Arkansas is closer to Bull Shoals (SWPA)
/// than to anything TVA runs, and the reverse holds in Tennessee.
final class GenerationService: Sendable {
    static let shared = GenerationService()
    private init() {}

    private var providers: [GenerationProvider] {
        [TVAGenerationService.shared, SWPAGenerationService.shared, AlabamaPowerGenerationService.shared]
    }

    /// How far to look for the dam that governs this water.
    ///
    /// This was the tailwater radius (12 mi) and that was wrong for LAKES. A
    /// reservoir is the dam's impoundment but stretches tens of miles from it —
    /// Chickamauga Lake runs ~59 miles, and the directory's point for it sits
    /// 23 mi from Chickamauga Dam. Six lakes with live TVA/SWPA data resolved to
    /// nothing for exactly this reason (Wheeler, Chickamauga, Barkley, Kentucky,
    /// Eufaula, South Holston).
    ///
    /// Widening this does NOT loosen scoring: `TailwaterRegistry` still gates
    /// whether generation affects the score, with its own 12-mile radius and
    /// direction cone. This only governs which dam we can REPORT on, and pool
    /// elevation is a lake-wide fact.
    static let maxDamDistanceMiles: Double = 35

    /// Every dam from every operator, for the picker.
    func allDams() async -> [GenerationDam] {
        await withTaskGroup(of: [GenerationDam].self) { group in
            for p in providers { group.addTask { await p.dams() } }
            var out: [GenerationDam] = []
            for await d in group { out.append(contentsOf: d) }
            return out
        }
    }

    /// Nearest dam across all operators, regardless of range — lets the card
    /// stay on screen off a tailwater and name what's closest.
    ///
    /// Prefers the dam that shares this water's NAME when one is in range. On a
    /// long reservoir the nearest dam by straight line can be the wrong one —
    /// mid-Chickamauga is closer to Watts Bar than to Chickamauga Dam — and the
    /// name is the operator's own statement of which dam impounds which lake.
    func nearestDam(near coordinate: CLLocationCoordinate2D) async -> (dam: GenerationDam, miles: Double)? {
        let origin = CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude)
        let ranked = await allDams()
            .map { ($0, origin.distance(from: CLLocation(latitude: $0.latitude, longitude: $0.longitude)) / 1609.34) }
            .sorted { $0.1 < $1.1 }
        guard let nearest = ranked.first else { return nil }

        if let lake = LakeDirectory.nearest(to: coordinate, withinMiles: 40) {
            let want = Self.damKey(lake.name)
            if let named = ranked.first(where: { Self.damKey($0.0.name) == want && $0.1 <= Self.maxDamDistanceMiles }) {
                return (dam: named.0, miles: named.1)
            }
        }
        return (dam: nearest.0, miles: nearest.1)
    }

    /// Normalized so "Chickamauga Dam" and the lake "Chickamauga Lake" meet.
    private static func damKey(_ n: String) -> String {
        var s = n.lowercased()
        for w in ["dam", "lake", "reservoir", "the", "of"] {
            s = s.replacingOccurrences(of: "\\b\(w)\\b", with: " ", options: .regularExpression)
        }
        return s.filter { $0.isLetter || $0.isNumber }
    }

    /// Generation for the dam governing `coordinate`, or nil when none is close
    /// enough or every feed is down.
    func generation(near coordinate: CLLocationCoordinate2D) async -> DamGeneration? {
        if let near = await nearestDam(near: coordinate),
           near.miles <= Self.maxDamDistanceMiles,
           let g = await generation(for: near.dam, distanceMiles: near.miles) {
            return g
        }
        return await observedOnly(near: coordinate)
    }

    /// TVA and SWPA together publish 55 dams. The directory has 400 lakes with a
    /// dam on them, and most of the rest are USACE projects whose district
    /// publishes no schedule at all — so this path used to return nil and the
    /// lake showed nothing: no pool elevation, no tailwater, no outflow.
    ///
    /// CWMS carries all three for those projects. There's no schedule to be had,
    /// so `windows` stays empty and the sheet falls back to history alone, which
    /// is the degradation `GenerationProvider` was written to allow. Better an
    /// honest measured reading with no forecast than a blank screen.
    private func observedOnly(near coordinate: CLLocationCoordinate2D) async -> DamGeneration? {
        guard let lake = LakeDirectory.nearest(to: coordinate, withinMiles: Self.maxDamDistanceMiles),
              lake.hasDam,
              let office = lake.cwmsOffice,
              let obs = await CWMSObservedService.shared.observed(office: office,
                                                                  coordinate: lake.coordinate,
                                                                  withinMiles: Self.maxDamDistanceMiles,
                                                                  nameHint: lake.name)
        else { return nil }

        let dam = GenerationDam(
            id: "USACE-\(lake.id)",
            operatorID: .usace,
            name: lake.name,
            latitude: lake.lat,
            longitude: lake.lon,
            river: lake.operatorName,
            lakeNameOverride: lake.name)

        return DamGeneration(
            dam: dam,
            distanceMiles: LakeDirectory.miles(coordinate, lake.coordinate),
            windows: [],
            dischargeCfs: obs.dischargeCfs,
            dischargeTrend12hCfs: obs.dischargeTrend12hCfs,
            reservoirElevationFt: obs.reservoirFt,
            tailwaterElevationFt: obs.tailwaterFt,
            observedAt: obs.observedAt,
            history: obs.history)
    }

    /// Generation for a specific dam, routed to whichever operator owns it, then
    /// topped up with measured readings when the operator only publishes a plan.
    func generation(for dam: GenerationDam, distanceMiles: Double) async -> DamGeneration? {
        guard let provider = providers.first(where: { $0.operatorID == dam.operatorID }) else { return nil }
        guard let base = await provider.generation(for: dam, distanceMiles: distanceMiles) else { return nil }
        return await enrichedWithObserved(base)
    }

    /// SWPA publishes megawatts and nothing measured, so its dams arrived with
    /// no elevations and no history — the reservoir and tailwater tiles simply
    /// hid. CWMS carries the measured side for the same USACE projects, and the
    /// lake directory knows which CWMS office to ask (parsed from the district
    /// in the research sheet). Only fills gaps: an operator that already
    /// publishes its own readings — TVA — passes through untouched.
    private func enrichedWithObserved(_ g: DamGeneration) async -> DamGeneration {
        let needsObserved = g.reservoirElevationFt == nil
            || g.tailwaterElevationFt == nil
            || g.history.isEmpty
        guard needsObserved,
              // 35 to match `maxDamDistanceMiles`: the directory's point for a
              // long reservoir can sit 20+ miles from the dam being enriched.
              let lake = LakeDirectory.nearest(to: g.dam.coordinate, withinMiles: 35),
              let office = lake.cwmsOffice,
              let obs = await CWMSObservedService.shared.observed(office: office,
                                                                 coordinate: g.dam.coordinate)
        else { return g }

        return DamGeneration(
            dam: g.dam,
            distanceMiles: g.distanceMiles,
            windows: g.windows,
            // The operator's own release figure wins; CWMS fills in only if absent.
            dischargeCfs: g.dischargeCfs ?? obs.dischargeCfs,
            dischargeTrend12hCfs: g.dischargeTrend12hCfs ?? obs.dischargeTrend12hCfs,
            reservoirElevationFt: g.reservoirElevationFt ?? obs.reservoirFt,
            tailwaterElevationFt: g.tailwaterElevationFt ?? obs.tailwaterFt,
            observedAt: g.observedAt ?? obs.observedAt,
            history: g.history.isEmpty ? obs.history : g.history)
    }
}
