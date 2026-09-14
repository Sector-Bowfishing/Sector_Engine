//
//  CWMSObservedService.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Observed water data for USACE projects, from the Corps' CWMS Data API:
//  https://cwms-data.usace.army.mil/cwms-data/  (open JSON, no key)
//
//  WHY THIS EXISTS
//  SWPA publishes the generation PLAN — hourly megawatts, nothing measured. So a
//  SWPA tailwater showed a release figure and nothing else: reservoir and
//  tailwater elevations came back nil and their tiles hid. CWMS carries the
//  measured side for the same dams — pool elevation, tailwater elevation,
//  tailwater temperature — so the two together give a SWPA dam the same depth
//  TVA has natively.
//
//  ⚠️ CWMS IS FEDERATED. Every district names its series differently:
//      SWL  Bull_Shoals_Dam-Headwater.Elev.Inst.1Hour.0.Decodes-rev
//      SWT  TENK-…                       (four-letter project codes)
//      LRL  Barren-…
//      SAM  Buford-…                     (Lake Lanier's project is "Buford")
//  Hardcoding a table per district would rot, and no string heuristic turns
//  "Lanier (Sidney Lanier)" into "Buford". So NOTHING here is hardcoded:
//
//    1. `cwmsOffice` comes from the lake directory, parsed from the district
//       named in Michael's research sheet ("USACE Little Rock" -> SWL).
//    2. The project is resolved by COORDINATE — nearest CWMS location to the
//       dam — because coordinates are universal and names aren't.
//    3. The series are DISCOVERED from that project's catalog by pattern, then
//       ranked (revised over raw, hourly/15-min over daily).
//
//  Everything is cached per session: the office location list is large, the
//  catalog lookup is per project, and neither changes while the app is running.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

/// The measured side of a dam, when CWMS carries it.
struct CWMSObserved: Equatable {
    let reservoirFt: Double?
    let tailwaterFt: Double?
    let tailwaterTempF: Double?
    let dischargeCfs: Double?
    let dischargeTrend12hCfs: Double?
    let observedAt: Date?
    /// Oldest → newest, for the history chart.
    let history: [GenerationObservation]
}

final class CWMSObservedService {
    static let shared = CWMSObservedService()
    private init() {}

    private let base = "https://cwms-data.usace.army.mil/cwms-data"

    /// Beyond this the nearest CWMS project isn't this dam.
    static let maxProjectMiles: Double = 8
    private static let ttl: TimeInterval = 30 * 60

    private var officeLocations: [String: [(name: String, lat: Double, lon: Double)]] = [:]
    private var resolvedSeries: [String: Series] = [:]      // key: office|base
    private var cached: [String: (value: CWMSObserved, at: Date)] = [:]

    /// Ranked candidates per metric, best first. A district can publish the same
    /// reading under several versions (USGS vs LRGS, revised vs raw) and the
    /// top-ranked one is sometimes stale while a sibling is live — so this keeps
    /// the whole ordered list and the value fetch walks it until one returns a
    /// fresh reading. Single strings couldn't express that fallback.
    private struct Series {
        var reservoir: [String] = []
        var tailwater: [String] = []
        var temp: [String] = []
        var outflow: [String] = []
        var isEmpty: Bool { reservoir.isEmpty && tailwater.isEmpty && temp.isEmpty && outflow.isEmpty }
    }

    // MARK: Entry point

    /// Observed readings for `coordinate` in `office`, or nil when CWMS has
    /// nothing usable there.
    /// `withinMiles` and `nameHint` widen this for LAKE-origin lookups. Asking
    /// from a dam, the project is right there and 8 miles is plenty. Asking from
    /// a reservoir's directory point, the dam can be 20+ miles down the lake —
    /// so the caller passes the lake's name and a wider radius, and the name
    /// wins over raw distance when a project matches it.
    func observed(office: String,
                  coordinate: CLLocationCoordinate2D,
                  withinMiles: Double = maxProjectMiles,
                  nameHint: String? = nil) async -> CWMSObserved? {
        let bases = await projectBases(office: office, coordinate: coordinate,
                                       withinMiles: withinMiles, nameHint: nameHint)
        guard !bases.isEmpty else { return nil }

        // Try candidate projects best-first. The top pick is usually right, but
        // a long reservoir's nearest CWMS location can be a river gage or a met
        // station that lists no live water reading — so if it comes back empty
        // we fall through to the next-best project rather than reporting nothing.
        for base in bases.prefix(Self.maxProjects) {
            let key = "\(office)|\(base)"
            if let hit = cached[key], Date().timeIntervalSince(hit.at) < Self.ttl { return hit.value }

            let series: Series
            if let known = resolvedSeries[key] {
                series = known
            } else {
                guard let discovered = await discover(office: office, base: base), !discovered.isEmpty else {
                    continue
                }
                resolvedSeries[key] = discovered
                series = discovered
            }

            async let resTask  = latest(series.reservoir, office: office)
            async let tailTask = latest(series.tailwater, office: office)
            async let tempTask = latest(series.temp, office: office)
            async let flowTask = history(series.outflow, office: office)

            let res = await resTask, tail = await tailTask, temp = await tempTask
            let flow = await flowTask

            let result = CWMSObserved(
                reservoirFt: res?.value,
                tailwaterFt: tail?.value,
                tailwaterTempF: temp?.value,
                dischargeCfs: flow?.points.last?.dischargeCfs,
                dischargeTrend12hCfs: flow?.trend12h,
                observedAt: [res?.at, tail?.at, flow?.points.last?.at].compactMap { $0 }.max(),
                history: flow?.points ?? [])

            // Nothing measured at this project — try the next candidate.
            guard result.reservoirFt != nil || result.tailwaterFt != nil
                    || result.dischargeCfs != nil || result.tailwaterTempF != nil else { continue }
            cached[key] = (result, Date())
            return result
        }
        return nil
    }

    // MARK: Resolve the project by coordinate

    /// How many candidate projects to try before giving up on a lake.
    private static let maxProjects = 5

    /// A project that doesn't share the lake's name is accepted only within this
    /// distance — past it, "nearest" is a different water body, not this one.
    private static let maxProximityFallbackMiles: Double = 12

    /// Candidate CWMS project prefixes for this water, best-first. Locations come
    /// back as "<base>-Turbine1", "<base>-Pool", "<base>-Dam"; the part before
    /// the first "-" is the prefix every series for that project shares.
    ///
    /// Ordering matters because a reservoir's directory point often has a river
    /// gage or met station physically closer than its own dam. The tiers:
    ///
    ///   0  the name matches EXACTLY — the district's own word for this lake
    ///   1  the name matches as a substring (e.g. "Barren" ⊂ "Barren River")
    ///   3  a substring match that looks like a gage/met station, not the dam
    ///   4  proximity only, a real project
    ///   5  proximity only, and it looks like a gage/met station
    ///
    /// Within a tier, nearer wins. The caller walks this list until a project
    /// actually returns a live reading.
    private func projectBases(office: String, coordinate: CLLocationCoordinate2D,
                              withinMiles: Double, nameHint: String?) async -> [String] {
        let locs: [(name: String, lat: Double, lon: Double)]
        if let known = officeLocations[office] {
            locs = known
        } else {
            guard let fetched = await fetchLocations(office: office) else { return [] }
            officeLocations[office] = fetched
            locs = fetched
        }
        let origin = CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude)
        let ranked = locs
            .map { ($0, origin.distance(from: CLLocation(latitude: $0.lat, longitude: $0.lon)) / 1609.34) }
            .filter { $0.1 <= withinMiles }
            .sorted { $0.1 < $1.1 }

        let want = nameHint.map(Self.projectKey) ?? ""
        var seen = Set<String>()
        var scored: [(base: String, tier: Int, miles: Double)] = []
        for (loc, miles) in ranked {
            let base = prefix(of: loc.name)
            guard seen.insert(base).inserted else { continue }
            let bk = Self.projectKey(base)
            let tier: Int
            if !want.isEmpty, bk == want {
                tier = 0
            } else if !want.isEmpty, bk.count >= 4, want.count >= 4,
                      bk.contains(want) || want.contains(bk) {
                tier = Self.looksLikeGageOrMet(base) ? 3 : 1
            } else {
                // A project that DOESN'T share this water's name is only the right
                // answer when it's genuinely on top of the point — otherwise it's
                // the next lake over. Trinity Lake's directory point resolved to
                // Shasta's dam 40 mi away and showed Shasta's pool as Trinity's.
                // Name matches keep the wide radius (a long reservoir's dam is far
                // from its midpoint); a proximity-only guess must be close.
                guard miles <= Self.maxProximityFallbackMiles else { continue }
                tier = Self.looksLikeGageOrMet(base) ? 5 : 4
            }
            scored.append((base, tier, miles))
        }
        return scored.sorted { ($0.tier, $0.miles) < ($1.tier, $1.miles) }.map(\.base)
    }

    /// A river gage or meteorological station rather than the impoundment. These
    /// sit near a lake but carry stream stage or weather, not pool/tailwater —
    /// so they're tried only after the real projects.
    private static func looksLikeGageOrMet(_ base: String) -> Bool {
        base.range(of: #"(?i)(webmet|^met|gage|_R$|_ws$|coast guard|_DS$|-DS$)"#,
                   options: .regularExpression) != nil
    }

    /// CWMS locations are "<project>-Turbine1", "<project>-Pool"; the part
    /// before the first "-" is the prefix every series for that project shares.
    private func prefix(of location: String) -> String {
        location.split(separator: "-").first.map(String.init) ?? location
    }

    /// "Bull_Shoals_Dam" and "Bull Shoals Lake" have to meet.
    private static func projectKey(_ n: String) -> String {
        var s = n.lowercased().replacingOccurrences(of: "_", with: " ")
        for w in ["dam", "lake", "reservoir", "the", "of"] {
            s = s.replacingOccurrences(of: "\\b\(w)\\b", with: " ", options: .regularExpression)
        }
        return s.filter { $0.isLetter || $0.isNumber }
    }

    private func fetchLocations(office: String) async -> [(name: String, lat: Double, lon: Double)]? {
        guard let data = await get("\(base)/locations?office=\(office)&page-size=6000") else { return nil }
        guard let raw = Self.parseJSON(data) else { return nil }
        let list: [[String: Any]]
        if let arr = raw as? [[String: Any]] { list = arr }
        else if let dict = raw as? [String: Any], let arr = dict["locations"] as? [[String: Any]] { list = arr }
        else { return nil }
        return list.compactMap {
            guard let n = $0["name"] as? String,
                  let la = $0["latitude"] as? Double,
                  let lo = $0["longitude"] as? Double else { return nil }
            return (n, la, lo)
        }
    }

    // MARK: Discover the series

    private enum Metric { case reservoir, tailwater, temp, outflow }

    /// CWMS series IDs follow one grammar — `Location.Parameter.Type.Interval.
    /// Duration.Version` — but every district names the pieces its own way
    /// (`-Headwater` here, `Elev-Pool` there, `TW-Kaskaskia` somewhere else).
    /// Matching those with a fixed regex table meant a district the table didn't
    /// anticipate went dark, which is exactly what happened to Nashville,
    /// Huntington, St. Louis and Louisville. So instead of matching spellings
    /// this parses the grammar and classifies structurally:
    ///
    ///   • reservoir  = an elevation parameter whose LOCATION isn't a tailwater
    ///   • tailwater  = an elevation parameter that IS a tailwater location
    ///   • outflow    = a flow-out parameter (never inflow)
    ///   • temp       = a water-temperature parameter
    ///
    /// Pool vs tailwater comes from the location token (`TW`, `Tail`, `Outflow`,
    /// `Downstream`), which is the one thing every district encodes. Forecast
    /// and modeled versions are dropped so a projected pool never masquerades as
    /// a reading. What survives is returned RANKED, since the top pick is
    /// occasionally stale and the fetch falls through to the next.
    private func discover(office: String, base projectBase: String) async -> Series? {
        let like = ".*\(projectBase).*".addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
        guard let data = await get("\(base)/catalog/TIMESERIES?office=\(office)&like=\(like)&page-size=1500"),
              let raw = Self.parseJSON(data) as? [String: Any],
              let entries = raw["entries"] as? [[String: Any]] else { return nil }
        let names = entries.compactMap { $0["name"] as? String }
        guard !names.isEmpty else { return nil }

        func candidates(_ metric: Metric) -> [String] {
            names.filter { Self.classify($0, as: metric) }
                 .sorted { Self.rank($0) < Self.rank($1) }
        }
        return Series(reservoir: candidates(.reservoir),
                      tailwater: candidates(.tailwater),
                      temp:      candidates(.temp),
                      outflow:   candidates(.outflow))
    }

    /// A location that sits BELOW the dam. The token appears in every district's
    /// naming; a bounded match (separator/·digit on each side) keeps it from
    /// firing inside an unrelated word.
    private static func isTailwaterLocation(_ loc: String) -> Bool {
        loc.range(of: #"(?i)(^|[ _-])(tw|tail|tailwater|outflow|downstream|below)([ _-]|\d|$)"#,
                  options: .regularExpression) != nil
    }

    /// Modeled/projected series — never a measured reading, so they must not
    /// stand in for one.
    private static func isForecast(_ id: String) -> Bool {
        id.range(of: #"(?i)(forecast|fcst|for comparison|historic|-F[FX]$|-P[FX]$|National-CWMS|smoothed|-test$|nodlb)"#,
                 options: .regularExpression) != nil
    }

    private static func classify(_ id: String, as metric: Metric) -> Bool {
        if isForecast(id) { return false }
        let parts = id.split(separator: ".").map(String.init)
        guard parts.count >= 3 else { return false }
        let loc = parts[0], param = parts[1]
        switch metric {
        case .reservoir:
            return (param == "Elev" || param == "Elev-Pool") && !isTailwaterLocation(loc)
        case .tailwater:
            // Districts name the below-dam elevation three different ways:
            // `Elev-Tail` (Nashville/Huntington), `Elev-Tailwater` (Tulsa),
            // `Elev-Downstream` (Little Rock). Plus the generic `Elev` when the
            // LOCATION itself is the tailwater. Missing the first three left
            // whole districts (SWT, SWL) showing a pool but no tailwater.
            return param == "Elev-Tail" || param == "Elev-Tailwater" || param == "Elev-Downstream"
                || (param == "Elev" && isTailwaterLocation(loc))
        case .outflow:
            return param == "Flow" || param == "Flow-Out" || param == "Flow-Turbine"
        case .temp:
            return param.hasPrefix("Temp-Water")
        }
    }

    /// Revised over raw, sub-daily over daily, shorter ID breaks ties. Lower is
    /// better. Only orders candidates of the SAME metric — the classifier has
    /// already decided what each series measures.
    private static func rank(_ id: String) -> (Int, Int, Int, Int) {
        let revised = id.range(of: #"(?i)(rev|obs)$"#, options: .regularExpression) != nil ? 0 : 1
        let raw = id.lowercased().contains("raw") ? 1 : 0
        let subDaily = (id.contains("Minutes") || id.contains("1Hour")) ? 0 : (id.contains("6Hours") ? 1 : 2)
        return (revised, raw, subDaily, id.count)
    }

    // MARK: Values

    private struct Reading { let value: Double; let at: Date }

    /// How many ranked candidates to try before giving up on a metric, and how
    /// recent a reading has to be to count as live. A district can list a
    /// reading under several versions where the best-ranked one has gone quiet,
    /// so this walks the list until one answers with a fresh value.
    private static let maxCandidates = 8
    private static let freshWindow: TimeInterval = 36 * 3600

    private func latest(_ names: [String], office: String) async -> Reading? {
        let cutoff = Date().addingTimeInterval(-Self.freshWindow)
        for name in names.prefix(Self.maxCandidates) {
            guard let pts = await points(name, office: office, hours: 48), let last = pts.last,
                  last.0 >= cutoff else { continue }
            return Reading(value: last.1, at: last.0)
        }
        return nil
    }

    private func history(_ names: [String], office: String)
        async -> (points: [GenerationObservation], trend12h: Double?)? {
        let cutoff = Date().addingTimeInterval(-Self.freshWindow)
        var pts: [(Date, Double)]?
        for name in names.prefix(Self.maxCandidates) {
            if let p = await points(name, office: office, hours: 48), let last = p.last, last.0 >= cutoff {
                pts = p; break
            }
        }
        guard let pts, !pts.isEmpty else { return nil }
        let obs = pts.map { GenerationObservation(at: $0.0, dischargeCfs: $0.1,
                                                  reservoirFt: nil, tailwaterFt: nil) }
        // Same 12-hour lookback the rest of the engine uses for a discharge trend.
        var trend: Double?
        if let last = pts.last {
            let trendCutoff = last.0.addingTimeInterval(-12 * 3600)
            if let baseline = pts.last(where: { $0.0 <= trendCutoff }), baseline.0 != last.0 {
                trend = last.1 - baseline.1
            }
        }
        return (obs, trend)
    }

    /// Values in ENGLISH units (ft / cfs / °F) — CWMS stores SI by default.
    private func points(_ name: String?, office: String, hours: Int) async -> [(Date, Double)]? {
        guard let name else { return nil }
        let now = Date()
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        var c = URLComponents(string: "\(base)/timeseries")
        c?.queryItems = [
            .init(name: "office", value: office),
            .init(name: "name", value: name),
            .init(name: "unit", value: "EN"),
            .init(name: "begin", value: f.string(from: now.addingTimeInterval(-Double(hours) * 3600))),
            .init(name: "end", value: f.string(from: now.addingTimeInterval(3600))),
            .init(name: "page-size", value: "5000"),
        ]
        guard let url = c?.url, let data = await get(url.absoluteString),
              let raw = Self.parseJSON(data) as? [String: Any],
              let values = raw["values"] as? [[Any?]] else { return nil }
        return values.compactMap { row in
            guard row.count >= 2, let ms = row[0] as? Double, let v = row[1] as? Double else { return nil }
            return (Date(timeIntervalSince1970: ms / 1000), v)
        }
    }

    // MARK: Transport

    /// CWMS's larger payloads (whole districts — SWT, MVS, SPA, NAE) carry stray
    /// non-UTF8 bytes that make `JSONSerialization` reject the entire document,
    /// which silently darkened those districts: every lake in them returned nil.
    /// A strict parse is tried first; on failure the bytes are re-read as UTF-8
    /// with the invalid units replaced (U+FFFD) and parsed again. The garbled
    /// bytes only ever land in a name string we don't key on, so nothing
    /// downstream is harmed — and SWT alone goes from 0 to 3,327 usable
    /// locations. Static so every parse site shares the one code path.
    static func parseJSON(_ data: Data) -> Any? {
        if let strict = try? JSONSerialization.jsonObject(with: data) { return strict }
        let cleaned = Data(String(decoding: data, as: UTF8.self).utf8)
        return try? JSONSerialization.jsonObject(with: cleaned)
    }

    /// CWMS occasionally emits stray non-UTF8 bytes in the locations payload, so
    /// this returns Data and callers decode leniently via `parseJSON`.
    private func get(_ urlString: String) async -> Data? {
        guard let url = URL(string: urlString) else { return nil }
        guard let result = try? await HTTP.get(url, headers: ["Accept": "application/json;version=2"]),
              result.isSuccess
        else { return nil }
        return result.body
    }
}
