//
//  LakeLevelFeedsUSGSWaterData.swift
//  Sector — Lake Brain: the USGS Water Data API (OGC API, v1) readers behind a switch that defaults to the legacy WaterServices path
//
//  Legacy WaterServices (`waterservices.usgs.gov/nwis/*`) adds a delay to every request from 2026-11-16 (2 s, then 10 s from
//  2027-01-11, beyond the readers' timeouts) and shuts down on 2027-02-22. This file reads the same Lake Brain series from
//  `api.waterdata.usgs.gov/ogcapi/v1` (`continuous`, `daily`, `time-series-metadata`, `monitoring-locations`).
//
//  Switch: `LAKE_USGS_API` = `legacy` (default, also for an unset, empty or unknown value) | `v1` | `shadow`.
//    • legacy: the WaterServices readers, unchanged.
//    • v1:     the Water Data API readers below.
//    • shadow: both are read; the LEGACY answer is the one returned, the v1 answer is only compared and logged
//              (`[usgs-shadow] ...`, one line per read). Nothing else is written.
//  Optional key: `USGS_API_KEY` is sent as the `X-Api-Key` header (never in the URL, never logged). Without it the API rate-limits
//  by IP; a 429 is retried after a pause.
//
//  The differences from WaterServices that are handled explicitly (each has a test):
//    D1 Several series per site and parameter come back flat (one `time_series_id` each). The series that matches the binding is
//       selected: a single series, or else the one `time-series-metadata` marks Primary; when that does not settle it, the read is
//       refused. Series are never merged (WaterServices' reader merged them last-wins). The gage-height reader keeps its stricter
//       rule: more than one series is refused.
//    D2 Times are UTC without fractional seconds (`2026-10-07T08:30:00+00:00`); both that and the legacy form are parsed.
//    D3 Daily statistics: `statistic_id` per feature, merged with the legacy precedence (00003 > 32400 > 30800 > 00001 > 00002). A
//       binding that names one statistic (32400, 30800, ...) is refused when the API does not serve a daily series of it.
//    D4 "No data" is a 200 with zero features (not a 404); a `null` value (and the legacy -999999) is skipped.
//    D10 A non-JSON body (the blackout notice page) is a failure, never data.
//

import Foundation

// MARK: - Switch

public enum LakeUSGSAPIMode: String, Sendable, CaseIterable {
    case legacy, v1, shadow

    public static let environmentKey = "LAKE_USGS_API"

    /// `legacy` unless the variable says `v1` or `shadow` (case-insensitive).
    public static func fromEnvironment(_ env: [String: String] = ProcessInfo.processInfo.environment) -> LakeUSGSAPIMode {
        let raw = (env[environmentKey] ?? "").trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return LakeUSGSAPIMode(rawValue: raw) ?? .legacy
    }
}

/// Runs a read the way the switch says. In `shadow` the legacy answer is returned unchanged and the v1 answer is only compared.
enum LakeUSGSRouting {
    static func run<T, U>(_ mode: LakeUSGSAPIMode,
                          legacy: () async -> T,
                          v1: () async -> U,
                          adopt: (U) -> T,
                          compare: (T, U) -> String,
                          log: (String) -> Void) async -> T {
        switch mode {
        case .legacy:
            return await legacy()
        case .v1:
            return adopt(await v1())
        case .shadow:
            let l = await legacy()
            let o = await v1()
            log(compare(l, o))
            return l
        }
    }
}

// MARK: - v1 client

/// One live read from the v1 API, with the qualifiers it carried (logged in shadow so ice-affected values are visible).
struct LakeUSGSV1Read: Sendable {
    var result: FeedResult
    var qualifiers: [String: Int] = [:]
}

struct LakeUSGSWaterDataClient: Sendable {
    static let base = "https://api.waterdata.usgs.gov/ogcapi/v1/collections"
    static let apiKeyEnvironmentKey = "USGS_API_KEY"
    static let pageLimit = 10_000
    static let observationProperties =
        "time_series_id,monitoring_location_id,parameter_code,statistic_id,time,value,unit_of_measure,approval_status,qualifier"
    static let metadataProperties = "monitoring_location_id,parameter_code,statistic_id,computation_period_identifier,primary,sublocation_identifier"

    typealias Transport = @Sendable (_ url: String, _ headers: [String: String], _ timeout: TimeInterval) async -> LakeFeedHTTP.Response?

    var transport: Transport
    /// Sent as `X-Api-Key` when set.
    var apiKey: String?
    /// `rel=next` pages followed before a read is refused as incomplete (a silent truncation would be a hole in the history).
    var maxPages = 20
    /// Retries after a 429, each after `pause(attempt)`.
    var retries429 = 2
    var pause: @Sendable (_ attempt: Int) async -> Void

    static func live(env: [String: String] = ProcessInfo.processInfo.environment) -> LakeUSGSWaterDataClient {
        let key = (env[apiKeyEnvironmentKey] ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        return LakeUSGSWaterDataClient(
            transport: { url, headers, timeout in await LakeFeedHTTP.get(url, accept: "application/json", timeout: timeout, headers: headers) },
            apiKey: key.isEmpty ? nil : key,
            pause: { attempt in _ = try? await Task.sleep(nanoseconds: UInt64(10 * attempt) * 1_000_000_000) })
    }

    var headers: [String: String] { apiKey.map { ["X-Api-Key": $0] } ?? [:] }

    static func locationId(_ site: String) -> String { "USGS-\(site)" }

    // MARK: URLs

    static func url(_ collection: String, _ items: [(String, String)]) -> String {
        var c = URLComponents(string: "\(base)/\(collection)/items")
        c?.queryItems = [URLQueryItem(name: "f", value: "json")] + items.map { URLQueryItem(name: $0.0, value: $0.1) }
        return c?.url?.absoluteString ?? ""
    }

    static func continuousURL(site: String, parameter: String, time: String) -> String {
        url("continuous", [("monitoring_location_id", locationId(site)), ("parameter_code", parameter), ("time", time),
                           ("limit", String(pageLimit)), ("properties", observationProperties)])
    }

    static func dailyURL(site: String, parameter: String, statistics: [String], time: String) -> String {
        url("daily", [("monitoring_location_id", locationId(site)), ("parameter_code", parameter),
                      ("statistic_id", statistics.joined(separator: ",")), ("time", time),
                      ("limit", String(pageLimit)), ("properties", observationProperties)])
    }

    static func metadataURL(ids: [String]) -> String {
        url("time-series-metadata", [("id", ids.joined(separator: ",")), ("limit", String(max(1, ids.count))), ("properties", metadataProperties)])
    }

    static func metadataURL(site: String, parameter: String, statistic: String) -> String {
        url("time-series-metadata", [("monitoring_location_id", locationId(site)), ("parameter_code", parameter),
                                     ("statistic_id", statistic), ("limit", "100"), ("properties", metadataProperties)])
    }

    static func locationURL(site: String) -> String {
        "\(base)/monitoring-locations/items/\(locationId(site))?f=json"
    }

    /// `[start, end]` as the OGC `time` interval, UTC with `Z`.
    static func interval(_ start: Date, _ end: Date) -> String {
        let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime]
        return "\(f.string(from: start))/\(f.string(from: end))"
    }

    // MARK: HTTP

    enum Fetched { case ok(Data), failed(String) }

    func fetch(_ url: String, timeout: TimeInterval) async -> Fetched {
        var attempt = 0
        while true {
            guard let r = await transport(url, headers, timeout) else { return .failed("unreachable") }
            if r.status == 429 && attempt < retries429 {
                attempt += 1
                await pause(attempt)
                continue
            }
            guard r.isSuccess else { return .failed("HTTP \(r.status)") }
            return .ok(r.body)
        }
    }

    /// Every feature of a paged `items` answer, following `rel=next`. Zero features on a 200 is an empty answer (D4).
    func paged(_ first: String, timeout: TimeInterval) async -> Result<[Row], ReadFailure> {
        var rows: [Row] = []
        var next: String? = first
        var pages = 0
        while let url = next {
            if pages == maxPages { return .failure(ReadFailure("more than \(maxPages) pages (answer too large for one read)")) }
            let data: Data
            switch await fetch(url, timeout: timeout) {
            case .failed(let why): return .failure(ReadFailure(why))
            case .ok(let d): data = d
            }
            // D10: a non-JSON body (the legacy blackout notice, a proxy error page) is a failure, never an empty answer.
            guard let page = Self.parsePage(data) else { return .failure(ReadFailure("unreadable JSON (not a FeatureCollection)")) }
            rows += page.rows
            pages += 1
            next = page.features == 0 ? nil : page.next
        }
        return .success(rows)
    }

    struct ReadFailure: Error, Equatable { var why: String; init(_ w: String) { why = w } }

    // MARK: Wire format

    /// One observation (one feature of `continuous` or `daily`).
    struct Row: Equatable, Sendable {
        var seriesId: String
        var location: String
        var parameter: String
        var statistic: String?
        var time: String
        /// nil for a JSON `null` (D4), an unreadable value or the legacy -999999 sentinel.
        var value: Double?
        var unit: String?
        var qualifiers: [String]
        var approval: String?
    }

    static func number(_ x: Any?) -> Double? {
        guard let x else { return nil }
        switch x {
        case let s as String: return Double(s.trimmingCharacters(in: .whitespaces))
        case let n as NSNumber: return n.doubleValue
        default: return nil
        }
    }

    static func strings(_ x: Any?) -> [String] {
        guard let x else { return [] }
        switch x {
        case let a as [Any]: return a.compactMap { $0 as? String }
        case let s as String: return s.isEmpty ? [] : [s]
        default: return []
        }
    }

    static func parsePage(_ data: Data) -> (rows: [Row], features: Int, next: String?)? {
        guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let features = obj["features"] as? [[String: Any]] else { return nil }
        var rows: [Row] = []
        for f in features {
            guard let p = f["properties"] as? [String: Any], let t = p["time"] as? String else { continue }
            var v = number(p["value"])
            if let x = v, !x.isFinite || x <= -990_000 { v = nil }
            rows.append(Row(seriesId: (p["time_series_id"] as? String) ?? "?", location: (p["monitoring_location_id"] as? String) ?? "",
                            parameter: (p["parameter_code"] as? String) ?? "", statistic: p["statistic_id"] as? String,
                            time: t, value: v, unit: p["unit_of_measure"] as? String,
                            qualifiers: strings(p["qualifier"]), approval: p["approval_status"] as? String))
        }
        let links = (obj["links"] as? [[String: Any]]) ?? []
        let next = links.first(where: { ($0["rel"] as? String) == "next" }).flatMap { $0["href"] as? String }
        return (rows, features.count, next)
    }

    /// One `time-series-metadata` feature.
    struct SeriesMeta: Equatable, Sendable {
        var id: String
        var statistic: String?
        var computationPeriod: String?
        var primary: String?
        var sublocation: String?
    }

    static func parseMetadata(_ data: Data) -> [SeriesMeta]? {
        guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let features = obj["features"] as? [[String: Any]] else { return nil }
        return features.compactMap { f -> SeriesMeta? in
            guard let id = f["id"] as? String else { return nil }
            let p = (f["properties"] as? [String: Any]) ?? [:]
            return SeriesMeta(id: id, statistic: p["statistic_id"] as? String, computationPeriod: p["computation_period_identifier"] as? String,
                              primary: p["primary"] as? String, sublocation: p["sublocation_identifier"] as? String)
        }
    }

    private static let isoPlain: ISO8601DateFormatter = { let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime]; return f }()
    private static let isoFraction: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]; return f
    }()

    /// D2: `2026-10-07T08:30:00+00:00` / `...Z` (v1) and `2026-10-07T03:30:00.000-05:00` (legacy).
    static func parseTime(_ s: String) -> Date? { isoPlain.date(from: s) ?? isoFraction.date(from: s) }

    // MARK: Series selection (D1)

    enum Pick { case primary, single }

    /// The rows of the one series of `parameter` at `site` the binding means. `.single`: more than one series is refused.
    /// `.primary`: one series, else the single series `time-series-metadata` marks Primary, else refused. Never merged.
    func select(_ rows: [Row], site: String, parameter: String, pick: Pick, label: String, timeout: TimeInterval) async -> Result<[Row], ReadFailure> {
        let mine = rows.filter { $0.parameter == parameter && ($0.location.isEmpty || $0.location == Self.locationId(site)) }
        let ids = Array(Set(mine.map(\.seriesId))).sorted()
        if ids.count <= 1 { return .success(mine) }
        if pick == .single {
            return .failure(ReadFailure("\(ids.count) \(label) series at this site (sub-locations); the binding cannot tell which is the lake"))
        }
        guard case .ok(let data) = await fetch(Self.metadataURL(ids: ids), timeout: timeout), let meta = Self.parseMetadata(data) else {
            return .failure(ReadFailure("\(ids.count) series at this site and time-series-metadata unreadable; refused rather than merged"))
        }
        let primaries = meta.filter { ids.contains($0.id) && $0.primary == "Primary" }.map(\.id)
        guard primaries.count == 1, let chosen = primaries.first else {
            return .failure(ReadFailure("\(ids.count) series at this site, \(primaries.count) marked Primary; ambiguous, refused rather than merged"))
        }
        return .success(mine.filter { $0.seriesId == chosen })
    }

    static func observations(_ rows: [Row]) -> [LevelObservation] {
        rows.compactMap { r in
            guard let v = r.value, let at = parseTime(r.time) else { return nil }
            return LevelObservation(at: at, ft: v)
        }
    }

    static func qualifierCounts(_ rows: [Row]) -> [String: Int] {
        var out: [String: Int] = [:]
        for r in rows { for q in r.qualifiers { out[q, default: 0] += 1 } }
        return out
    }

    // MARK: Live lake elevation (legacy `/nwis/iv/?period=PT{h}H`)

    func recentLevel(site: String, parameter: String, hours: Int) async -> LakeUSGSV1Read {
        let url = Self.continuousURL(site: site, parameter: parameter, time: "PT\(max(1, hours))H")
        switch await paged(url, timeout: 60) {
        case .failure(let e): return LakeUSGSV1Read(result: .failed("USGS \(site) \(parameter) unreachable (Water Data API: \(e.why))"))
        case .success(let rows):
            switch await select(rows, site: site, parameter: parameter, pick: .primary, label: parameter, timeout: 60) {
            case .failure(let e): return LakeUSGSV1Read(result: .failed("USGS \(site) \(parameter): \(e.why)"))
            case .success(let picked):
                let obs = Self.observations(picked)
                let result: FeedResult = obs.isEmpty ? .failed("USGS \(site) \(parameter): no readings")
                    : FeedResult(observations: LakeLevelSeries.merge(obs), error: nil)
                return LakeUSGSV1Read(result: result, qualifiers: Self.qualifierCounts(picked))
            }
        }
    }

    // MARK: Gage height (legacy `/nwis/iv/?parameterCd=00065`), raw: the stage client adds the altitude

    func recentStage(site: String, hours: Int) async -> Result<[LevelObservation], ReadFailure> {
        let p = LakeUSGSStageClient.gageHeight
        switch await paged(Self.continuousURL(site: site, parameter: p, time: "PT\(max(1, hours))H"), timeout: 60) {
        case .failure(let e): return .failure(ReadFailure("unreachable (Water Data API: \(e.why))"))
        case .success(let rows):
            switch await select(rows, site: site, parameter: p, pick: .single, label: "gage-height", timeout: 60) {
            case .failure(let e): return .failure(e)
            case .success(let picked):
                if let u = picked.compactMap(\.unit).first(where: { $0.lowercased() != "ft" }) {
                    return .failure(ReadFailure("unit \(u) is not feet"))
                }
                return .success(Self.observations(picked))
            }
        }
    }

    // MARK: Site altitude (legacy site service `alt_va` / `alt_datum_cd`)

    static func parseLocation(_ data: Data, site: String) -> USGSSiteDatumResult {
        guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else {
            return .refused("USGS \(site): monitoring-locations answer unreadable")
        }
        let id = (obj["id"] as? String) ?? ((obj["properties"] as? [String: Any])?["id"] as? String)
        guard id == locationId(site), let p = obj["properties"] as? [String: Any] else { return .refused("USGS \(site): site record not found") }
        guard let alt = number(p["altitude"]), alt.isFinite else {
            return .refused("USGS \(site): no published altitude (monitoring-locations altitude); gage height is not an elevation")
        }
        let datum = ((p["vertical_datum"] as? String) ?? "").trimmingCharacters(in: .whitespaces)
        guard !datum.isEmpty else { return .refused("USGS \(site): altitude \(alt) has no published datum (monitoring-locations vertical_datum)") }
        return .ok(USGSSiteDatum(site: site, name: p["monitoring_location_name"] as? String, siteType: p["site_type_code"] as? String,
                                 altitudeFt: alt, accuracyFt: number(p["altitude_accuracy"]), datum: datum))
    }

    func siteDatum(_ site: String) async -> USGSSiteDatumResult {
        switch await fetch(Self.locationURL(site: site), timeout: 60) {
        case .failed(let why) where why == "HTTP 404": return .refused("USGS \(site): site record not found")
        case .failed(let why): return .refused("USGS \(site): monitoring-locations \(why)")
        case .ok(let data): return Self.parseLocation(data, site: site)
        }
    }

    // MARK: History (legacy `/nwis/dv/` and the year-by-year `/nwis/iv/` walk)

    /// Daily values: `stat` "dv" merges the statistics with the legacy precedence; a statistic code takes only that statistic and is
    /// refused when the API serves no daily series of it (D3). nil = refused or unreachable.
    func daily(site: String, param: String, stat: String, offsetFt: Double, since: String?, now: Date, timeZone: TimeZone,
               src: String, singleSeries: Bool) async -> [DailyLevel]? {
        if stat == "iv" {
            return await ivDaily(site: site, param: param, offsetFt: offsetFt, since: since, now: now, timeZone: timeZone, src: src,
                                 singleSeries: singleSeries)
        }
        let end = LakeLevelCalendar.dayString(now, timeZone: timeZone)
        let stats = stat == "dv" ? LakeFleetClients.usgsStatOrder : [stat]
        guard case .success(let rows) = await paged(Self.dailyURL(site: site, parameter: param, statistics: stats,
                                                                  time: "\(since ?? "1900-01-01")/\(end)"), timeout: 120) else { return nil }
        var byStat: [String: [String: Double]] = [:]
        for s in stats {
            let ofStat = rows.filter { ($0.statistic ?? "") == s }
            guard case .success(let picked) = await select(ofStat, site: site, parameter: param, pick: singleSeries ? .single : .primary,
                                                           label: "\(param)/\(s)", timeout: 120) else { return nil }
            for r in picked { if let v = r.value, r.time.count >= 10 { byStat[s, default: [:]][String(r.time.prefix(10))] = v } }
        }
        if stat != "dv" && (byStat[stat] ?? [:]).isEmpty {
            // Empty: a statistic the API does not serve is refused, never substituted; a full-history pull that is empty is refused too.
            guard since != nil, await servesDaily(site: site, param: param, stat: stat) else { return nil }
            return []
        }
        var merged: [String: Double] = [:]
        for s in stats { for (d, x) in byStat[s] ?? [:] where merged[d] == nil { merged[d] = x } }
        return LakeDailyHistory.dedupe(merged.map { DailyLevel(date: $0.key, ft: $0.value + offsetFt, sourceId: src) })
    }

    /// Whether `time-series-metadata` lists a daily series of `stat` for the site and parameter.
    func servesDaily(site: String, param: String, stat: String) async -> Bool {
        guard case .ok(let data) = await fetch(Self.metadataURL(site: site, parameter: param, statistic: stat), timeout: 60),
              let meta = Self.parseMetadata(data) else { return false }
        return meta.contains { $0.statistic == stat && ($0.computationPeriod == nil || $0.computationPeriod?.lowercased() == "daily") }
    }

    /// Instantaneous values reduced to the median of each lake-local day, year by year back from now until two empty years
    /// (a 200 with no features is an empty year, D4). Each window is one lake-local calendar year or less (the API allows ≤ 3 years).
    func ivDaily(site: String, param: String, offsetFt: Double, since: String?, now: Date, timeZone: TimeZone, src: String,
                 singleSeries: Bool) async -> [DailyLevel]? {
        var out: [DailyLevel] = []
        let today = LakeLevelCalendar.dayString(now, timeZone: timeZone)
        let thisYear = Int(today.prefix(4)) ?? 2026
        var year = thisYear
        let floor = since.flatMap { Int($0.prefix(4)) } ?? 1990
        var empty = 0
        while year >= floor && empty < 2 {
            let start = max(since ?? "\(year)-01-01", "\(year)-01-01")
            let end = year == thisYear ? today : "\(year)-12-31"
            guard let s = LakeLevelCalendar.utcBounds(day: start, timeZone: timeZone)?.0,
                  let e = LakeLevelCalendar.utcBounds(day: end, timeZone: timeZone)?.1 else { return nil }
            let url = Self.continuousURL(site: site, parameter: param, time: Self.interval(s, e.addingTimeInterval(-1)))
            guard case .success(let rows) = await paged(url, timeout: 120),
                  case .success(let picked) = await select(rows, site: site, parameter: param, pick: singleSeries ? .single : .primary,
                                                           label: param, timeout: 120) else { return nil }
            let obs = Self.observations(picked)
            empty = obs.isEmpty ? empty + 1 : 0
            out += LakeFleetClients.dailyMedians(obs, timeZone: timeZone, offsetFt: offsetFt, src: src)
            year -= 1
        }
        return LakeDailyHistory.dedupe(out)
    }
}

// MARK: - Shadow comparison (agreement rule fixed in the migration plan §5, before any run)

enum LakeUSGSShadow {
    struct Verdict: Equatable {
        var verdict: String          // agree | disagree | legacy-unavailable
        var reason: String
        var legacyN: Int
        var ogcN: Int
        var maxAbsDelta: Double?
        var tsDelta: Double?
    }

    static func line(site: String, param: String, kind: String, _ v: Verdict, qualifiers: [String: Int] = [:]) -> String {
        var s = "[usgs-shadow] site=\(site) param=\(param) kind=\(kind) verdict=\(v.verdict) reason=\(v.reason) legacyN=\(v.legacyN) ogcN=\(v.ogcN)"
        s += " maxAbsDelta=" + (v.maxAbsDelta.map { String(format: "%.3f", $0) } ?? "-")
        s += " tsDelta=" + (v.tsDelta.map { String(Int($0)) } ?? "-")
        if !qualifiers.isEmpty { s += " ogcQualifiers=" + qualifiers.sorted { $0.key < $1.key }.map { "\($0.key):\($0.value)" }.joined(separator: ",") }
        return s
    }

    /// Live series: same latest timestamp or OGC newer by ≤ 2 h; the value at legacy's latest timestamp within `tolerance`; ≥ 99 % of
    /// common timestamps within `tolerance`. A failed legacy read never counts against OGC.
    static func compareLive(legacy: FeedResult, ogc: FeedResult, tolerance: Double = 0.01) -> Verdict {
        let l = legacy.observations, o = ogc.observations
        guard let ll = l.last else { return Verdict(verdict: "legacy-unavailable", reason: "legacy-failed", legacyN: 0, ogcN: o.count) }
        guard let ol = o.last else { return Verdict(verdict: "disagree", reason: "ogc-failed", legacyN: l.count, ogcN: 0) }
        let ts = ol.at.timeIntervalSince(ll.at)
        let ov = Dictionary(o.map { ($0.at, $0.ft) }, uniquingKeysWith: { _, b in b })
        let common = l.compactMap { x in ov[x.at].map { abs($0 - x.ft) } }
        let maxD = common.max()
        func v(_ verdict: String, _ reason: String) -> Verdict {
            Verdict(verdict: verdict, reason: reason, legacyN: l.count, ogcN: o.count, maxAbsDelta: maxD, tsDelta: ts)
        }
        if ts < 0 { return v("disagree", "ogc-older") }
        if ts > 2 * 3600 { return v("disagree", "ogc-newer-over-2h") }
        guard let atLatest = ov[ll.at] else { return v("disagree", "legacy-latest-missing-in-ogc") }
        if abs(atLatest - ll.ft) > tolerance + 1e-9 { return v("disagree", "latest-delta") }
        let within = common.filter { $0 <= tolerance + 1e-9 }.count
        if Double(within) < 0.99 * Double(common.count) { return v("disagree", "common-points") }
        return v("agree", ts == 0 ? "-" : "ogc-newer")
    }

    /// Daily: ≥ 99.5 % of common dates within 0.01 ft; dates present in only one series (up to the earlier last date) ≤ 1 per 365;
    /// last date equal or OGC newer by ≤ 1 day.
    static func compareDaily(legacy: [DailyLevel]?, ogc: [DailyLevel]?, tolerance: Double = 0.01) -> Verdict {
        guard let l = legacy else { return Verdict(verdict: "legacy-unavailable", reason: "legacy-failed", legacyN: 0, ogcN: ogc?.count ?? 0) }
        guard let o = ogc else { return Verdict(verdict: "disagree", reason: "ogc-failed", legacyN: l.count, ogcN: 0) }
        if l.isEmpty && o.isEmpty { return Verdict(verdict: "agree", reason: "both-empty", legacyN: 0, ogcN: 0) }
        let lm = Dictionary(l.map { ($0.date, $0.ft) }, uniquingKeysWith: { _, b in b })
        let om = Dictionary(o.map { ($0.date, $0.ft) }, uniquingKeysWith: { _, b in b })
        let deltas = lm.compactMap { d, x in om[d].map { abs($0 - x) } }
        let maxD = deltas.max()
        let lLast = lm.keys.max() ?? "", oLast = om.keys.max() ?? ""
        var days: Double?
        if let a = LakeLevelCalendar.utcBounds(day: lLast, timeZone: TimeZone(identifier: "UTC")!)?.0,
           let b = LakeLevelCalendar.utcBounds(day: oLast, timeZone: TimeZone(identifier: "UTC")!)?.0 {
            days = (b.timeIntervalSince(a) / 86_400).rounded()
        }
        func v(_ verdict: String, _ reason: String) -> Verdict {
            Verdict(verdict: verdict, reason: reason, legacyN: l.count, ogcN: o.count, maxAbsDelta: maxD, tsDelta: days.map { $0 * 86_400 })
        }
        guard let d = days else { return v("disagree", l.isEmpty ? "legacy-empty" : "ogc-empty") }
        if d < 0 { return v("disagree", "ogc-older") }
        if d > 1 { return v("disagree", "ogc-newer-over-1d") }
        let horizon = min(lLast, oLast)
        let onlyOne = Set(lm.keys).symmetricDifference(Set(om.keys)).filter { $0 <= horizon }.count
        let union = Set(lm.keys).union(Set(om.keys)).filter { $0 <= horizon }.count
        if onlyOne > max(1, Int((Double(union) / 365).rounded(.up))) { return v("disagree", "missing-dates") }
        let within = deltas.filter { $0 <= tolerance + 1e-9 }.count
        if Double(within) < 0.995 * Double(deltas.count) { return v("disagree", "common-dates") }
        return v("agree", d == 0 ? "-" : "ogc-newer")
    }

    /// Site altitude: equal to 0.01 ft and the datum code equal after upper-casing and trimming. Any difference is a hard fail.
    static func compareSite(legacy: USGSSiteDatumResult, ogc: USGSSiteDatumResult) -> Verdict {
        switch (legacy, ogc) {
        case (.refused(let why), _) where why.contains("unreachable") || why.contains("HTTP "):
            return Verdict(verdict: "legacy-unavailable", reason: "legacy-failed", legacyN: 0, ogcN: 0)
        case (.refused, .refused):
            return Verdict(verdict: "agree", reason: "both-refused", legacyN: 0, ogcN: 0)
        case (.ok, .refused):
            return Verdict(verdict: "disagree", reason: "ogc-refused", legacyN: 1, ogcN: 0)
        case (.refused, .ok):
            return Verdict(verdict: "disagree", reason: "legacy-refused", legacyN: 0, ogcN: 1)
        case (.ok(let a), .ok(let b)):
            let d = abs(a.altitudeFt - b.altitudeFt)
            let norm = { (s: String) in s.trimmingCharacters(in: .whitespaces).uppercased() }
            if norm(a.datum) != norm(b.datum) {
                return Verdict(verdict: "disagree", reason: "datum-\(norm(a.datum))-vs-\(norm(b.datum))", legacyN: 1, ogcN: 1, maxAbsDelta: d)
            }
            if d > 0.01 + 1e-9 { return Verdict(verdict: "disagree", reason: "altitude", legacyN: 1, ogcN: 1, maxAbsDelta: d) }
            return Verdict(verdict: "agree", reason: "-", legacyN: 1, ogcN: 1, maxAbsDelta: d)
        }
    }
}
