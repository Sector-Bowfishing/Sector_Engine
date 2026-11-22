//
//  LakeLevelFeedsHydromet.swift
//  Sector — Lake Brain: read-only client for Reclamation Hydromet reservoir elevation (Pacific Northwest and Great Plains / Missouri Basin)
//
//  Hydromet is Reclamation's regional real-time network. RISE (`rise`, already supported) carries daily values for many Reclamation
//  reservoirs but not every Pacific Northwest one; Hydromet is the region's own record, with 15-minute instant data.
//
//  Endpoints (LAKE_BRAIN_PROVIDERS.md, "Reclamation Hydromet" section):
//    PN instant  https://www.usbr.gov/pn-bin/instant.pl?list=GCL%20FB&back=24&format=csv&flags=false&description=false
//    PN daily    https://www.usbr.gov/pn-bin/daily.pl?station=GCL&format=csv&year=2026&month=1&day=1&year=2026&month=11&day=21&pcode=FB
//    GP instant  https://www.usbr.gov/gp-bin/webdaycsv.pl?parameter=CAFE%20FB&syer=2026&smnth=11&sdy=20&eyer=2026&emnth=11&edy=22&format=2
//    GP daily    https://www.usbr.gov/gp-bin/webarccsv.pl?parameter=CAFE%20FB&syer=2016&smnth=1&sdy=1&eyer=2026&emnth=11&edy=21&format=2
//  Answer: comma-separated text, a header whose first column is the date (`DATE`, `DateTime`) and one column per `SITE PCODE`, sometimes
//  wrapped in HTML and (GP) between `BEGIN DATA` / `END DATA` lines. Stamps are `MM/dd/yyyy[ HH:mm]` (or `yyyy-MM-dd[ HH:mm]`), no offset.
//
//  Traps handled:
//    • Only `FB` (reservoir water surface / forebay elevation, feet) is a lake level. `AF` is storage in acre-feet, `GH` a gage height,
//      `Q` a flow: all refused before any request.
//    • `998877` is the Hydromet missing-value sentinel (a number); `MISSING` / `NO RECORD` / blank cells and values <= 0 are dropped.
//    • Stamps carry no offset and are the site's local wall-clock time (Hydromet's own documentation). The site's IANA zone is part of
//      the binding (`REGION:SITE:Area/City`) because a region spans zones (PN: Pacific and Mountain; GP: Mountain and Central). A live
//      binding without it fails closed.
//    • Daily `FB` is the midnight reading of the day it is dated (PN parameter list): the history day is the date in the stamp.
//    • The vertical datum is the project datum (Reclamation does not state it per series): a binding carries `datumOffsetFt` (live)
//      / `offsetFt` (history) when it differs from the lake's pool reference.
//

import Foundation

extension LakeFleetClients {
    static let hydrometHost = "https://www.usbr.gov"

    /// The Hydromet parameter codes that are a lake level: `FB`, reservoir water surface elevation (ft).
    static let hydrometElevationParams: Set<String> = ["FB"]

    /// Hydromet's missing-value sentinel.
    static let hydrometMissing = 998_877.0

    enum HydrometRegion: String, Sendable {
        /// Pacific Northwest (`/pn-bin/`).
        case pn = "PN"
        /// Great Plains / Missouri Basin (`/gp-bin/`).
        case gp = "GP"
    }

    /// A binding's station for Hydromet: `REGION:SITE` or `REGION:SITE:Area/City` (the site's time zone, required for live readings).
    struct HydrometStation: Equatable, Sendable {
        var region: HydrometRegion
        var site: String
        var timeZone: TimeZone?
    }

    static func hydrometStation(_ s: String) -> HydrometStation? {
        let p = s.split(separator: ":", maxSplits: 2, omittingEmptySubsequences: false).map { $0.trimmingCharacters(in: .whitespaces) }
        guard (2...3).contains(p.count), let region = HydrometRegion(rawValue: p[0].uppercased()), hydrometSiteIsValid(p[1]) else { return nil }
        var tz: TimeZone?
        if p.count == 3 {
            guard let z = TimeZone(identifier: p[2]) else { return nil }
            tz = z
        }
        return HydrometStation(region: region, site: p[1].uppercased(), timeZone: tz)
    }

    /// Hydromet site codes are short alphanumeric codes (`GCL`, `MLAW`, `CAFE`, `PUER`).
    static func hydrometSiteIsValid(_ s: String) -> Bool {
        (2...8).contains(s.count) && s.allSatisfy { $0.isASCII && ($0.isLetter || $0.isNumber) }
    }

    /// The parameter of a binding's `series` (default `FB`), upper-cased; nil unless it is a reservoir elevation.
    static func hydrometParam(_ series: String?) -> String? {
        let p = (series ?? "FB").trimmingCharacters(in: .whitespaces).uppercased()
        return hydrometElevationParams.contains(p) ? p : nil
    }

    fileprivate static func ymd(_ day: String) -> (Int, Int, Int)? {
        let p = day.split(separator: "-").compactMap { Int($0) }
        return p.count == 3 ? (p[0], p[1], p[2]) : nil
    }

    /// GP `syer…edy` query (the scripts expect this order).
    fileprivate static func gpRange(_ start: String, _ end: String) -> String? {
        guard let (sy, sm, sd) = ymd(start), let (ey, em, ed) = ymd(end) else { return nil }
        return "syer=\(sy)&smnth=\(sm)&sdy=\(sd)&eyer=\(ey)&emnth=\(em)&edy=\(ed)"
    }

    /// Instant (15 min) data: PN by `back` hours; GP by whole site-local days `start`...`end` (yyyy-MM-dd, inclusive).
    static func hydrometInstantURL(_ st: HydrometStation, param: String, hours: Int, start: String, end: String) -> String? {
        switch st.region {
        case .pn:
            return "\(hydrometHost)/pn-bin/instant.pl?list=\(st.site)%20\(param)&back=\(max(1, hours))&format=csv&flags=false&description=false"
        case .gp:
            guard let r = gpRange(start, end) else { return nil }
            return "\(hydrometHost)/gp-bin/webdaycsv.pl?parameter=\(st.site)%20\(param)&\(r)&format=2"
        }
    }

    /// Daily (archive) data for `start`...`end` (yyyy-MM-dd, inclusive).
    static func hydrometDailyURL(region: HydrometRegion, site: String, param: String, start: String, end: String) -> String? {
        guard let (sy, sm, sd) = ymd(start), let (ey, em, ed) = ymd(end) else { return nil }
        switch region {
        case .pn:
            return "\(hydrometHost)/pn-bin/daily.pl?station=\(site)&format=csv&year=\(sy)&month=\(sm)&day=\(sd)&year=\(ey)&month=\(em)&day=\(ed)&pcode=\(param)"
        case .gp:
            return "\(hydrometHost)/gp-bin/webarccsv.pl?parameter=\(site)%20\(param)&syer=\(sy)&smnth=\(sm)&sdy=\(sd)&eyer=\(ey)&emnth=\(em)&edy=\(ed)&format=2"
        }
    }

    /// One Hydromet reading: the date in its stamp, the site-local wall-clock time (nil for a daily row), and the value.
    struct HydrometRow: Equatable, Sendable {
        var day: String
        var hour: Int?
        var minute: Int
        var ft: Double

        /// The instant of a timed row in the site's zone (hour 24 is 00:00 of the next day).
        func at(_ tz: TimeZone) -> Date? {
            guard let (y, m, d) = LakeFleetClients.ymd(day) else { return nil }
            var cal = Calendar(identifier: .gregorian); cal.timeZone = tz
            guard let start = cal.date(from: DateComponents(year: y, month: m, day: d)) else { return nil }
            return cal.date(byAdding: DateComponents(hour: hour ?? 0, minute: minute), to: start)
        }
    }

    /// `MM/dd/yyyy[ HH:mm[:ss]]` or `yyyy-MM-dd[ HH:mm[:ss]]` → (yyyy-MM-dd, hour?, minute).
    static func hydrometStamp(_ s: String) -> (day: String, hour: Int?, minute: Int)? {
        let parts = s.trimmingCharacters(in: .whitespaces).split(separator: " ", omittingEmptySubsequences: true)
        guard let d = parts.first else { return nil }
        var y = 0, m = 0, dd = 0
        if d.contains("/") {
            let p = d.split(separator: "/").compactMap { Int($0) }
            guard p.count == 3 else { return nil }
            (m, dd, y) = (p[0], p[1], p[2])
        } else {
            let p = d.split(separator: "-").compactMap { Int($0) }
            guard p.count == 3 else { return nil }
            (y, m, dd) = (p[0], p[1], p[2])
        }
        guard y >= 1800, (1...12).contains(m), (1...31).contains(dd) else { return nil }
        let day = String(format: "%04d-%02d-%02d", y, m, dd)
        guard parts.count >= 2 else { return (day, nil, 0) }
        let t = parts[1].split(separator: ":").compactMap { Int($0) }
        guard (2...3).contains(t.count), (0...24).contains(t[0]), (0...59).contains(t[1]), t[0] < 24 || t[1] == 0 else { return nil }
        return (day, t[0], t[1])
    }

    /// Parses a Hydromet CSV answer for one `SITE PCODE` column. A missing header or a missing column fails the whole answer.
    static func parseHydromet(_ data: Data, site: String, param: String) -> (rows: [HydrometRow], error: String?) {
        let label = "Hydromet \(site) \(param)"
        let text = String(decoding: data, as: UTF8.self)
        var lines = text.components(separatedBy: .newlines)
            .map { $0.replacingOccurrences(of: "<[^>]*>", with: "", options: .regularExpression).trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        // GP wraps the table in BEGIN DATA / END DATA; keep only what is between them when they are there.
        if let b = lines.firstIndex(where: { $0.uppercased() == "BEGIN DATA" }) {
            let rest = Array(lines[(b + 1)...])
            lines = Array(rest.prefix(while: { $0.uppercased() != "END DATA" }))
        }
        func cells(_ l: String) -> [String] { l.split(separator: ",", omittingEmptySubsequences: false).map { $0.trimmingCharacters(in: .whitespaces) } }
        guard let h = lines.firstIndex(where: { l in
            let c = cells(l); return c.count >= 2 && c[0].lowercased().contains("date")
        }) else { return ([], "\(label): no data header (not a Hydromet table)") }
        let header = cells(lines[h])
        let want = (site + param).uppercased()
        func norm(_ s: String) -> String { s.uppercased().filter { $0.isLetter || $0.isNumber } }
        let col: Int
        if let i = header.indices.dropFirst().first(where: { norm(header[$0]) == want }) {
            col = i
        } else if header.count == 2 {
            col = 1
        } else {
            return ([], "\(label): column \(site) \(param) not in the answer (\(header.dropFirst().joined(separator: ", ")))")
        }
        var out: [HydrometRow] = []
        for l in lines[(h + 1)...] {
            let c = cells(l)
            guard c.count > col, let (day, hour, minute) = hydrometStamp(c[0]) else { continue }
            guard let v = Double(c[col]), v.isFinite, v > 0, abs(v - hydrometMissing) >= 1 else { continue }   // blank, MISSING, NO RECORD, 998877
            out.append(HydrometRow(day: day, hour: hour, minute: minute, ft: v))
        }
        return (out, nil)
    }

    // MARK: live

    func hydrometRecent(_ ref: LevelSeriesRef, hours: Int, now: Date) async -> FeedResult {
        guard let st = Self.hydrometStation(ref.station) else {
            return .failed("Hydromet station \(ref.station) is not REGION:SITE[:TimeZone] (region PN or GP)")
        }
        guard let tz = st.timeZone else {
            return .failed("Hydromet \(st.region.rawValue):\(st.site): the binding needs the site time zone (REGION:SITE:Area/City); stamps carry no offset")
        }
        guard let param = Self.hydrometParam(ref.series) else {
            return .failed("Hydromet \(st.site) \(ref.series ?? ""): not a reservoir elevation parameter (only FB; AF is storage, GH a gage height)")
        }
        let since = now.addingTimeInterval(-Double(max(1, hours)) * 3600)
        guard let url = Self.hydrometInstantURL(st, param: param, hours: hours + 2,
                                                start: LakeLevelCalendar.dayString(since.addingTimeInterval(-86_400), timeZone: tz),
                                                end: LakeLevelCalendar.dayString(now.addingTimeInterval(86_400), timeZone: tz)) else {
            return .failed("Hydromet \(st.site): bad request URL")
        }
        guard let r = await LakeFeedHTTP.get(url, accept: "text/csv, text/plain, text/html", timeout: 60) else {
            return .failed("Hydromet \(st.region.rawValue) \(st.site) unreachable")
        }
        guard r.isSuccess else { return .failed("Hydromet \(st.region.rawValue) \(st.site): HTTP \(r.status)") }
        return Self.hydrometLive(r.body, site: st.site, param: param, timeZone: tz, since: since)
    }

    static func hydrometLive(_ data: Data, site: String, param: String, timeZone: TimeZone, since: Date) -> FeedResult {
        let (rows, error) = parseHydromet(data, site: site, param: param)
        if let error { return .failed(error) }
        let obs = rows.compactMap { r -> LevelObservation? in
            guard r.hour != nil, let at = r.at(timeZone), at >= since else { return nil }
            return LevelObservation(at: at, ft: r.ft)
        }
        let merged = LakeLevelSeries.merge(obs)
        return merged.isEmpty ? .failed("Hydromet \(site) \(param): no readings (998877 / MISSING dropped)") : FeedResult(observations: merged, error: nil)
    }

    // MARK: history

    /// Daily levels from the Hydromet archive in 10-year windows, newest first. Stops after two empty windows in a row or at `since`;
    /// any failed window fails the whole pull (no silent hole). Daily rows keep their own date; a timed row becomes the median of its
    /// lake-local day.
    func hydrometDaily(region: String, site: String, param: String, offsetFt: Double, since: String?, now: Date,
                       timeZone: TimeZone) async -> [DailyLevel]? {
        guard let reg = HydrometRegion(rawValue: region.uppercased()), Self.hydrometSiteIsValid(site),
              let p = Self.hydrometParam(param) else { return nil }
        let s = site.uppercased()
        let src = "hydromet:\(reg.rawValue):\(s):\(p)"
        let utc = TimeZone(identifier: "UTC")!
        let floor = since.flatMap { LakeLevelCalendar.utcBounds(day: $0, timeZone: utc)?.0 } ?? LakeLevelCalendar.date(year: 1900, month: 1, day: 1)
        var out: [DailyLevel] = []
        var hi = now
        var empty = 0
        while hi >= floor && empty < 2 {
            let lo = max(floor, hi.addingTimeInterval(-10 * 365.25 * 86_400))
            guard let url = Self.hydrometDailyURL(region: reg, site: s, param: p, start: LakeLevelCalendar.dayString(lo, timeZone: timeZone),
                                                  end: LakeLevelCalendar.dayString(hi, timeZone: timeZone)),
                  let r = await LakeFeedHTTP.get(url, accept: "text/csv, text/plain, text/html", timeout: 120), r.isSuccess else { return nil }
            let (rows, error) = Self.parseHydromet(r.body, site: s, param: p)
            if error != nil { return nil }
            empty = rows.isEmpty ? empty + 1 : 0
            out += Self.hydrometDailyLevels(rows, timeZone: timeZone, offsetFt: offsetFt, src: src)
            hi = lo.addingTimeInterval(-86_400)
        }
        return LakeDailyHistory.dedupe(out).filter { since == nil || $0.date >= since! }
    }

    /// Daily rows: one value per stamped date (+ offset). Timed rows: the median of each lake-local day (+ offset).
    static func hydrometDailyLevels(_ rows: [HydrometRow], timeZone: TimeZone, offsetFt: Double, src: String) -> [DailyLevel] {
        var byDay: [String: Double] = [:]
        var timed: [LevelObservation] = []
        for r in rows {
            if r.hour == nil { byDay[r.day] = r.ft } else if let at = r.at(timeZone) { timed.append(LevelObservation(at: at, ft: r.ft)) }
        }
        let daily = byDay.map { DailyLevel(date: $0.key, ft: $0.value + offsetFt, sourceId: src) }
        return (daily + dailyMedians(timed, timeZone: timeZone, offsetFt: offsetFt, src: src)).sorted { $0.date < $1.date }
    }
}
