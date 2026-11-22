//
//  LakeLevelFeedsCOOPS.swift
//  Sector — Lake Brain: read-only client for NOAA CO-OPS Great Lakes water levels (api.tidesandcurrents.noaa.gov datagetter)
//
//  Fetches only the station a binding names, on IGLD, in feet, with GMT stamps, one request at a time (CO-OPS throttles
//  per customer and asks callers to space their requests). Every request carries `application=Sector_LakeBrain` and the
//  Sector-LakeBrain User-Agent.
//
//  Traps handled (checked against the live API on 2026-11-22, Calumet Harbor 9087044):
//    • `hourly_height` and `daily_mean` are VERIFIED products: on 2026-11-22 both ended at 2026-10-31 (local). Neither is a live
//      series. Live is `water_level` (6-minute, preliminary `q:"p"` until verified).
//    • IGLD exists only at Great Lakes stations. A tidal station answers with an error, so asking for IGLD is itself the check.
//    • The API answers HTTP 200 with `{"error":{"message":…}}`. "No data was found" is an empty window, anything else a failure.
//    • Values are strings; a missing reading is an empty string. Preliminary rows whose flat-line (F) or limit (L) flag is set,
//      and daily means whose limit (L) flag is set, are dropped.
//    • `daily_mean` must be asked in `lst` (local standard time): its day is the station's standard-time date.
//    • IGLD (2020) is expected to replace IGLD (1985) in the US by 2027: a datum change will step the series (LAKE_BRAIN_PROVIDERS.md).
//

import Foundation

/// NOAA CO-OPS datagetter client. `fetch` is the transport (tests inject recorded responses); `gate` spaces the requests.
struct LakeCOOPSClient: Sendable {
    static let base = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    static let application = "Sector_LakeBrain"
    static let datum = "IGLD"
    /// The only live product: 6-minute water level (preliminary until verified).
    static let liveProduct = "water_level"
    /// Longest request per product (CO-OPS limits): 6-minute 31 days, daily means 10 years.
    static let waterLevelWindowDays = 31
    static let dailyMeanWindowYears = 10
    /// How far back the preliminary tail reaches past the last verified daily mean (verification lags about a month).
    static let tailMaxDays = 93

    var fetch: @Sendable (_ url: String) async -> LakeFeedHTTP.Response?
    var gate: HADSGate
    /// Minimum seconds between two CO-OPS requests.
    var gapSeconds: TimeInterval = 1

    static func live() -> LakeCOOPSClient {
        LakeCOOPSClient(fetch: { url in await LakeFeedHTTP.get(url, accept: "application/json", timeout: 60) }, gate: HADSGate())
    }

    /// A 7-digit CO-OPS station id.
    static func isStationId(_ s: String) -> Bool { s.count == 7 && s.allSatisfy { $0.isASCII && $0.isNumber } }

    static func url(product: String, station: String, timeZone: String, _ extra: [(String, String)]) -> String? {
        var c = URLComponents(string: base)
        var items: [URLQueryItem] = [
            .init(name: "product", value: product), .init(name: "station", value: station), .init(name: "datum", value: datum),
            .init(name: "units", value: "english"), .init(name: "time_zone", value: timeZone), .init(name: "format", value: "json"),
            .init(name: "application", value: application),
        ]
        for (k, v) in extra { items.append(URLQueryItem(name: k, value: v)) }
        c?.queryItems = items
        return c?.url?.absoluteString
    }

    static func stamp(_ d: Date) -> String {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "UTC"); f.dateFormat = "yyyyMMdd HH:mm"
        return f.string(from: d)
    }

    // MARK: parse

    enum Parsed {
        case rows([(t: String, v: Double)])
        /// "No data was found…": the window is empty (not a failure).
        case noData
        case failed(String)
    }

    /// True when the row's flags mark it unusable. Preliminary water level `O,F,R,L`: flat-line or limit. Verified water level
    /// `I,F,R,T`: flat-line. Hourly height / daily mean `I,L`: limit. Rate-of-change (R) is kept: a seiche trips it legitimately.
    static func flagged(_ f: String?, q: String?) -> Bool {
        let p = (f ?? "").split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) == "1" }
        switch p.count {
        case 4: return p[1] || (q != "v" && p[3])
        case 2: return p[1]
        default: return false
        }
    }

    static func parse(_ data: Data, station: String, product: String) -> Parsed {
        guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return .failed("CO-OPS \(station) \(product): unreadable JSON") }
        if let e = obj["error"] as? [String: Any] {
            let m = (e["message"] as? String ?? "error").trimmingCharacters(in: .whitespacesAndNewlines)
            return m.lowercased().hasPrefix("no data was found") ? .noData : .failed("CO-OPS \(station) \(product): \(m)")
        }
        if let id = (obj["metadata"] as? [String: Any])?["id"] as? String, id != station {
            return .failed("CO-OPS \(station) \(product): response is for station \(id)")
        }
        var out: [(t: String, v: Double)] = []
        for row in (obj["data"] as? [[String: Any]]) ?? [] {
            guard let t = row["t"] as? String, let s = row["v"] as? String, let v = Double(s.trimmingCharacters(in: .whitespaces)), v.isFinite,
                  !flagged(row["f"] as? String, q: row["q"] as? String) else { continue }
            out.append((t, v))
        }
        return .rows(out)
    }

    /// `"2026-11-22 06:30"` (GMT) → Date.
    static func gmt(_ t: String) -> Date? {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "UTC"); f.dateFormat = "yyyy-MM-dd HH:mm"
        return f.date(from: t)
    }

    static func observations(_ rows: [(t: String, v: Double)]) -> [LevelObservation] {
        rows.compactMap { r in gmt(r.t).map { LevelObservation(at: $0, ft: r.v) } }
    }

    private func get(_ url: String) async -> LakeFeedHTTP.Response? {
        await gate.wait(minGap: gapSeconds)
        return await fetch(url)
    }

    // MARK: live

    /// The last `hours` of 6-minute water level on IGLD. `ref.series` is the product (nil = `water_level`).
    func recent(_ ref: LevelSeriesRef, hours: Int) async -> FeedResult {
        let st = ref.station, product = ref.series ?? Self.liveProduct
        guard Self.isStationId(st) else { return .failed("CO-OPS binding needs a 7-digit station id (got \(st))") }
        guard product == Self.liveProduct else {
            return .failed("CO-OPS \(st): \(product) is not a live series (hourly_height and daily_mean are verified-only and lag weeks; bind water_level)")
        }
        guard let url = Self.url(product: product, station: st, timeZone: "gmt", [("range", String(min(max(1, hours), Self.waterLevelWindowDays * 24)))]) else {
            return .failed("CO-OPS \(st): bad request URL")
        }
        guard let r = await get(url) else { return .failed("CO-OPS \(st) unreachable") }
        guard r.isSuccess else { return .failed("CO-OPS \(st) \(product): HTTP \(r.status)") }
        switch Self.parse(r.body, station: st, product: product) {
        case .failed(let e): return .failed(e)
        case .noData: return .failed("CO-OPS \(st) \(product): no readings")
        case .rows(let rows):
            let obs = Self.observations(rows)
            return obs.isEmpty ? .failed("CO-OPS \(st) \(product): no usable readings") : FeedResult(observations: LakeLevelSeries.merge(obs), error: nil)
        }
    }

    // MARK: history

    /// Daily history on IGLD: the verified daily means (10-year chunks, newest first, stopping at the first empty chunk), then the days
    /// after the last verified one from preliminary 6-minute water level reduced to the median of each lake-local day (31-day windows,
    /// at most `tailMaxDays`). Any failed request fails the whole pull (no silent hole).
    func daily(station: String, since: String?, now: Date, timeZone: TimeZone) async -> [DailyLevel]? {
        guard Self.isStationId(station) else { return nil }
        let today = LakeLevelCalendar.dayString(now, timeZone: timeZone)
        let thisYear = Int(today.prefix(4)) ?? 2026
        let floorYear = since.flatMap { Int($0.prefix(4)) } ?? 1900
        let compact = { (d: String) in d.replacingOccurrences(of: "-", with: "") }
        var verified: [DailyLevel] = []
        var hi = thisYear
        while hi >= floorYear {
            let lo = max(floorYear, hi - Self.dailyMeanWindowYears + 1)
            let begin = max(since ?? "\(lo)-01-01", "\(lo)-01-01"), end = hi == thisYear ? today : "\(hi)-12-31"
            guard let url = Self.url(product: "daily_mean", station: station, timeZone: "lst", [("begin_date", compact(begin)), ("end_date", compact(end))]),
                  let r = await get(url), r.isSuccess else { return nil }
            var rows: [(t: String, v: Double)] = []
            switch Self.parse(r.body, station: station, product: "daily_mean") {
            case .failed: return nil
            case .noData: break
            case .rows(let x): rows = x
            }
            // The chunk holding today is empty for weeks after each month (verification lag): keep walking past it once.
            if rows.isEmpty && hi != thisYear { break }
            verified += rows.compactMap { r in
                let d = String(r.t.prefix(10))
                return LakeLevelCalendar.isDayString(d) ? DailyLevel(date: d, ft: r.v, sourceId: "coops:\(station):daily_mean") : nil
            }
            hi = lo - 1
        }
        verified = LakeDailyHistory.dedupe(verified)

        // Preliminary tail: from the day after the last verified mean (or `since`). It reaches at most tailMaxDays back: a gap older
        // than that (verification stopped, or `since` far back with no verified means) would be a silent hole, so the pull fails.
        let floorDay = LakeLevelCalendar.dayString(now.addingTimeInterval(-Double(Self.tailMaxDays) * 86_400), timeZone: timeZone)
        var startDay = verified.last.flatMap { LakeLevelCalendar.nextDay($0.date) } ?? since ?? floorDay
        if let since, since > startDay { startDay = since }
        if startDay < floorDay { return nil }
        var tail: [LevelObservation] = []
        if startDay <= today, var cursor = LakeLevelCalendar.utcBounds(day: startDay, timeZone: timeZone)?.0 {
            while cursor < now {
                let end = min(cursor.addingTimeInterval(Double(Self.waterLevelWindowDays) * 86_400), now)
                guard let url = Self.url(product: Self.liveProduct, station: station, timeZone: "gmt",
                                         [("begin_date", Self.stamp(cursor)), ("end_date", Self.stamp(end))]),
                      let r = await get(url), r.isSuccess else { return nil }
                switch Self.parse(r.body, station: station, product: Self.liveProduct) {
                case .failed: return nil
                case .noData: break
                case .rows(let x): tail += Self.observations(x)
                }
                cursor = end
            }
        }
        let tailDays = LakeFleetClients.dailyMedians(LakeLevelSeries.merge(tail), timeZone: timeZone, offsetFt: 0, src: "coops:\(station):water_level")
            .filter { $0.date >= startDay }
        return LakeDailyHistory.dedupe(verified + tailDays).filter { since == nil || $0.date >= since! }
    }
}

extension LakeLevelCalendar {
    /// `yyyy-MM-dd` → the next calendar day.
    static func nextDay(_ day: String) -> String? {
        let p = day.split(separator: "-").compactMap { Int($0) }
        guard p.count == 3 else { return nil }
        let utc = TimeZone(identifier: "UTC")!
        return dayString(date(year: p[0], month: p[1], day: p[2], timeZone: utc).addingTimeInterval(86_400), timeZone: utc)
    }
}
