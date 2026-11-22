//
//  LakeLevelFeedsCDEC.swift
//  Sector — Lake Brain: read-only client for California DWR CDEC (California Data Exchange Center) reservoir elevation
//
//  Endpoint: `https://cdec.water.ca.gov/dynamicapp/req/JSONDataServlet?Stations=SHA&SensorNums=6&dur_code=H&Start=yyyy-MM-dd&End=yyyy-MM-dd`
//  Answer: a JSON array, one object per reading:
//    {"stationId":"SHA","durCode":"H","SENSOR_NUM":6,"sensorType":"RES ELE","date":"2026-11-20 13:00","obsDate":"2026-11-20 13:00",
//     "value":1012.34,"dataFlag":" ","units":"FEET"}
//
//  Traps handled (LAKE_BRAIN_PROVIDERS.md §2):
//    • Only sensor 6 (RES ELE, reservoir elevation, feet) is a lake level. Sensor 15 is storage in acre-feet and sensor 1 a river stage:
//      both are refused before any request, and a response whose units are not feet is refused as a whole.
//    • `-9999` is the missing-value sentinel and it is a NUMBER, not null (often a third of the rows): dropped, with anything <= -9000.
//      A value of exactly 0 is a mechanical error on CDEC (seen on storage series), never a pool: dropped.
//    • Timestamps carry no offset. They are Pacific wall-clock time (`cdecTimeZone`, America/Los_Angeles, daylight saving applied).
//      If CDEC in fact stamps fixed PST all year, this reads summer readings one hour OLDER than they are, never fresher (conservative).
//    • Daily (`D`) rows are stamped 00:00 of the day they describe: the history day is the date in the stamp, not a time-zone conversion.
//    • The datum is not published per series (most projects report in their historical datum, typically NGVD29): a binding carries it,
//      and `datumOffsetFt` when it differs.
//
//  No CDEC rate limit or quota is published; history is pulled in windows sized to the duration, one request at a time.
//

import Foundation

extension LakeFleetClients {
    static let cdecBase = "https://cdec.water.ca.gov/dynamicapp/req/JSONDataServlet"

    /// CDEC stamps are Pacific wall-clock time without an offset.
    static let cdecTimeZone = TimeZone(identifier: "America/Los_Angeles")!

    /// The only CDEC sensor that is a lake level: 6, reservoir elevation (ft).
    static let cdecElevationSensors: Set<String> = ["6"]

    /// One CDEC reading: the Pacific calendar date of its stamp, the instant, and the value.
    struct CDECRow: Equatable, Sendable {
        var day: String
        var at: Date
        var ft: Double
    }

    /// A binding's `series` for CDEC: `"6"` (hourly) or `"6:H"`, `"6:E"` (event), `"6:D"` (daily). nil if malformed.
    static func cdecSeries(_ series: String?) -> (sensor: String, dur: String)? {
        let p = (series ?? "6").split(separator: ":", omittingEmptySubsequences: false).map { $0.trimmingCharacters(in: .whitespaces) }
        guard (1...2).contains(p.count), !p[0].isEmpty, p[0].allSatisfy({ $0.isASCII && $0.isNumber }) else { return nil }
        let dur = p.count == 2 ? p[1].uppercased() : "H"
        guard ["E", "H", "D"].contains(dur) else { return nil }
        return (p[0], dur)
    }

    /// CDEC station ids are short alphanumeric codes (`SHA`, `ORO`, `FOL`).
    static func cdecStationIsValid(_ s: String) -> Bool {
        (2...6).contains(s.count) && s.allSatisfy { $0.isASCII && ($0.isLetter || $0.isNumber) }
    }

    static func cdecURL(station: String, sensor: String, dur: String, start: String, end: String) -> String {
        "\(cdecBase)?Stations=\(station.uppercased())&SensorNums=\(sensor)&dur_code=\(dur)&Start=\(start)&End=\(end)"
    }

    /// "2026-11-20 13:00" (or with seconds) as Pacific wall-clock time. A stamp inside the spring-forward gap moves forward by the
    /// calendar's rule; a repeated fall-back hour resolves to one instant (both readings then merge, last wins).
    static func cdecDate(_ s: String) -> (day: String, at: Date)? {
        let parts = s.trimmingCharacters(in: .whitespaces).split(separator: " ")
        guard let d = parts.first else { return nil }
        let ymd = d.split(separator: "-").compactMap { Int($0) }
        guard ymd.count == 3, (1...12).contains(ymd[1]), (1...31).contains(ymd[2]) else { return nil }
        var hms = [0, 0, 0]
        if parts.count >= 2 {
            let t = parts[1].split(separator: ":").compactMap { Int($0) }
            guard (2...3).contains(t.count), (0...23).contains(t[0]), (0...59).contains(t[1]) else { return nil }
            hms = [t[0], t[1], t.count == 3 ? t[2] : 0]
        }
        var cal = Calendar(identifier: .gregorian); cal.timeZone = cdecTimeZone
        guard let at = cal.date(from: DateComponents(year: ymd[0], month: ymd[1], day: ymd[2], hour: hms[0], minute: hms[1], second: hms[2])) else { return nil }
        return (String(format: "%04d-%02d-%02d", ymd[0], ymd[1], ymd[2]), at)
    }

    /// Parses a JSONDataServlet answer for one sensor. Rows of another sensor, another station or (when `dur` is given) another
    /// duration are ignored; units other than feet fail the whole answer.
    static func parseCDEC(_ data: Data, station: String, sensor: String, dur: String? = nil) -> (rows: [CDECRow], error: String?) {
        guard let arr = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]] else {
            return ([], "CDEC \(station): unreadable JSON")
        }
        func str(_ v: Any?) -> String? { (v as? String) ?? (v as? Int).map(String.init) ?? (v as? Double).map { String(Int($0)) } }
        var out: [CDECRow] = []
        for r in arr {
            if let sn = str(r["SENSOR_NUM"] ?? r["sensorNum"]), sn != sensor { continue }
            if let sid = (r["stationId"] as? String)?.trimmingCharacters(in: .whitespaces), !sid.isEmpty, sid.uppercased() != station.uppercased() { continue }
            if let dur, let dc = (r["durCode"] as? String)?.trimmingCharacters(in: .whitespaces), !dc.isEmpty, dc.uppercased() != dur.uppercased() { continue }
            guard let v = (r["value"] as? Double) ?? (r["value"] as? Int).map(Double.init), v.isFinite else { continue }
            if v <= -9000 || v == 0 { continue }   // -9999 sentinel; 0 is a mechanical error, never a pool
            if let u = (r["units"] as? String)?.trimmingCharacters(in: .whitespaces), !u.isEmpty, !["FEET", "FT"].contains(u.uppercased()) {
                return ([], "CDEC \(station) sensor \(sensor): unit \(u) is not feet")
            }
            guard let t = (r["date"] as? String) ?? (r["obsDate"] as? String), let (day, at) = cdecDate(t) else { continue }
            out.append(CDECRow(day: day, at: at, ft: v))
        }
        return (out, nil)
    }

    /// Request window of one CDEC history call: about 10 years of daily rows, 1 year of hourly, 60 days of event (15 min) rows.
    static func cdecWindowSeconds(dur: String) -> TimeInterval {
        switch dur {
        case "D": return 10 * 365.25 * 86_400
        case "H": return 365.25 * 86_400
        default: return 60 * 86_400
        }
    }

    // MARK: live

    func cdecRecent(_ ref: LevelSeriesRef, hours: Int, now: Date) async -> FeedResult {
        let st = ref.station
        guard Self.cdecStationIsValid(st) else { return .failed("CDEC station \(st) is not a CDEC station id") }
        guard let (sensor, dur) = Self.cdecSeries(ref.series) else { return .failed("CDEC \(st): series \(ref.series ?? "") is not SENSOR[:E|H|D]") }
        guard Self.cdecElevationSensors.contains(sensor) else {
            return .failed("CDEC \(st) sensor \(sensor) is not reservoir elevation (only sensor 6 is; 15 is storage in acre-feet)")
        }
        let since = now.addingTimeInterval(-Double(max(1, hours)) * 3600)
        let tz = Self.cdecTimeZone
        // Whole Pacific days; the dates are inclusive, so ask one day either side and filter.
        let url = Self.cdecURL(station: st, sensor: sensor, dur: dur,
                               start: LakeLevelCalendar.dayString(since.addingTimeInterval(-86_400), timeZone: tz),
                               end: LakeLevelCalendar.dayString(now.addingTimeInterval(86_400), timeZone: tz))
        guard let r = await transport(url, "application/json", 60) else { return .failed("CDEC \(st) unreachable") }
        guard r.isSuccess else { return .failed("CDEC \(st): HTTP \(r.status)") }
        return Self.cdecLive(r.body, station: st, sensor: sensor, since: since, dur: dur)
    }

    static func cdecLive(_ data: Data, station: String, sensor: String, since: Date, dur: String? = nil) -> FeedResult {
        let (rows, error) = parseCDEC(data, station: station, sensor: sensor, dur: dur)
        if let error { return .failed(error) }
        let obs = LakeLevelSeries.merge(rows.filter { $0.at >= since }.map { LevelObservation(at: $0.at, ft: $0.ft) })
        return obs.isEmpty ? .failed("CDEC \(station) sensor \(sensor): no readings (-9999 sentinels dropped)") : FeedResult(observations: obs, error: nil)
    }

    // MARK: history

    /// Daily levels from CDEC, windows newest first. Stops after two empty windows in a row or at `since`; any failed window fails the
    /// whole pull (no silent hole). Daily rows keep their own date; hourly and event rows become the median of each lake-local day.
    func cdecDaily(station: String, sensor: String, dur: String, offsetFt: Double, since: String?, now: Date, timeZone: TimeZone) async -> [DailyLevel]? {
        guard Self.cdecStationIsValid(station), Self.cdecElevationSensors.contains(sensor), ["E", "H", "D"].contains(dur) else { return nil }
        let src = "cdec:\(station):\(sensor):\(dur)"
        let tz = Self.cdecTimeZone
        let floor = since.flatMap { LakeLevelCalendar.utcBounds(day: $0, timeZone: tz)?.0 } ?? LakeLevelCalendar.date(year: 1900, month: 1, day: 1, timeZone: tz)
        var out: [DailyLevel] = []
        var hi = now.addingTimeInterval(86_400)
        var empty = 0
        while hi >= floor && empty < 2 {
            let lo = max(floor, hi.addingTimeInterval(-Self.cdecWindowSeconds(dur: dur)))
            let url = Self.cdecURL(station: station, sensor: sensor, dur: dur,
                                   start: LakeLevelCalendar.dayString(lo, timeZone: tz), end: LakeLevelCalendar.dayString(hi, timeZone: tz))
            guard let r = await transport(url, "application/json", 120), r.isSuccess else { return nil }
            let (rows, error) = Self.parseCDEC(r.body, station: station, sensor: sensor, dur: dur)
            if error != nil { return nil }
            empty = rows.isEmpty ? empty + 1 : 0
            out += Self.cdecDailyLevels(rows, dur: dur, timeZone: timeZone, offsetFt: offsetFt, src: src)
            hi = lo.addingTimeInterval(-86_400)
        }
        return LakeDailyHistory.dedupe(out).filter { since == nil || $0.date >= since! }
    }

    /// `D` rows: one value per stamped date (+ offset). `H` / `E` rows: the median of each lake-local day (+ offset).
    static func cdecDailyLevels(_ rows: [CDECRow], dur: String, timeZone: TimeZone, offsetFt: Double, src: String) -> [DailyLevel] {
        if dur == "D" {
            var byDay: [String: Double] = [:]
            for r in rows { byDay[r.day] = r.ft }
            return byDay.map { DailyLevel(date: $0.key, ft: $0.value + offsetFt, sourceId: src) }.sorted { $0.date < $1.date }
        }
        return dailyMedians(rows.map { LevelObservation(at: $0.at, ft: $0.ft) }, timeZone: timeZone, offsetFt: offsetFt, src: src)
    }
}
