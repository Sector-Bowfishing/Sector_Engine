//
//  LakeLevelFeeds.swift
//  Sector — Lake Brain: read-only clients for the water-level sources
//
//  Fetches only the NAMED series a reviewed binding points at — no nearest-site
//  search. Reuses the production parsers (TVAGenerationService's time/number
//  helpers, CWMSObservedService.parseJSON) without changing their behaviour.
//
//  ⚠️ TVA "Midnight" rows: TVA labels the hour ENDING at midnight with the day
//  it ends ("10/10/2026 Midnight CDT" sits between 10/10 11 PM and 10/11 1 AM),
//  so it is 00:00 of the NEXT day. Production's TVAGenerationService.date puts it
//  24 h early; the Lake Brain parses it correctly and leaves production alone.
//

import Foundation
import SectorEngine

public struct LevelObservation: Codable, Equatable, Sendable {
    public var at: Date
    public var ft: Double
    public init(at: Date, ft: Double) { self.at = at; self.ft = ft }
}

/// One day's operator guidance for a lake.
public struct LakeGuideForDay: Equatable, Sendable {
    public var guideFt: Double?
    public var zone: LakeOperatingZone?
    public var levels: [LakeOperatorLevel]
    public var topOfGatesFt: Double?
    /// Above this the lake is in its flood-control pool (CWMS top of conservation).
    public var floodPoolBottomFt: Double?
    public var source: String
}

/// A daily elevation (lake-local calendar date, `yyyy-MM-dd`).
public struct DailyLevel: Codable, Equatable, Sendable {
    public var date: String
    public var ft: Double
    public var sourceId: String
}

/// One hourly dam release reading (LB-09): the operator's average hourly discharge and the tailwater elevation, kept apart
/// from the pool. Either value may be missing on a given hour.
public struct ReleaseObservation: Codable, Equatable, Sendable {
    public var at: Date
    public var outflowCfs: Double?
    public var tailwaterFt: Double?
    public init(at: Date, outflowCfs: Double?, tailwaterFt: Double?) { self.at = at; self.outflowCfs = outflowCfs; self.tailwaterFt = tailwaterFt }
}

public struct FeedResult: Sendable {
    public var observations: [LevelObservation]
    public var error: String?
    /// Release readings from the same response, where the source publishes them (TVA's 48 h feed). Empty elsewhere.
    public var release: [ReleaseObservation] = []
    public static func failed(_ e: String) -> FeedResult { FeedResult(observations: [], error: e) }
}

/// Everything the Lake Brain reads from the outside world. Tests inject fakes.
public protocol LakeLevelFeeds: Sendable {
    /// Recent readings of one live series, oldest first.
    func recent(_ ref: LevelSeriesRef, hours: Int, now: Date) async -> FeedResult
    /// The operator's guidance for `day` (lake-local).
    func guide(_ source: LakeGuideSource, day: String, timeZone: TimeZone) async -> LakeGuideForDay?
    /// Daily history from one source, `since` (inclusive) to now.
    func daily(_ source: LakeHistorySource, since: String?, now: Date, timeZone: TimeZone) async -> [DailyLevel]?
    /// Archived hourly readings (shared archive), oldest first.
    func archivedHourly(_ source: LakeHistorySource, days: Int, now: Date, timeZone: TimeZone) async -> [LevelObservation]
}

// MARK: - Live implementation

public final class PublicLakeLevelFeeds: LakeLevelFeeds, @unchecked Sendable {
    let tvaBase = "https://www.tva.com/RestApi"
    let cwmsBase = "https://cwms-data.usace.army.mil/cwms-data"
    let usgsBase = "https://waterservices.usgs.gov/nwis/iv/"
    /// Read-only access to the shared TVA archive (another lane's bucket).
    let sharedArchive: (String) -> LakeBrainArchive?
    /// Access2Water / RISE / NWPS / HADS / USGS-history clients (LakeLevelFeedsFleet.swift).
    let fleet = LakeFleetClients()
    private var guideCache: [String: [TVAGuideRow]] = [:]
    private let lock = NSLock()

    public init(sharedArchive: @escaping (String) -> LakeBrainArchive? = { _ in nil }) {
        self.sharedArchive = sharedArchive
    }

    public func recent(_ ref: LevelSeriesRef, hours: Int, now: Date) async -> FeedResult {
        switch ref.provider {
        case .tva: return await tvaObserved(ref.station)
        case .cwms:
            guard let name = ref.series else { return .failed("cwms series missing") }
            return await cwms(office: ref.station, name: name,
                              begin: now.addingTimeInterval(-Double(hours) * 3600), end: now.addingTimeInterval(3600))
        case .usgs:
            guard let p = ref.series else { return .failed("usgs parameter missing") }
            // 00065 is a gage height in a local datum, not an elevation: never a lake level.
            guard LakeFleetClients.usgsElevationParams.contains(p) else { return .failed("USGS \(p) is not a lake elevation parameter (gage height is not an elevation)") }
            return await usgs(site: ref.station, parameter: p, hours: hours)
        case .a2w: return await fleet.a2wRecent(ref)
        case .rise: return await fleet.riseRecent(ref, hours: hours, now: now)
        case .nwps: return await fleet.nwpsRecent(ref, since: now.addingTimeInterval(-Double(hours) * 3600))
        }
    }

    public func guide(_ source: LakeGuideSource, day: String, timeZone: TimeZone) async -> LakeGuideForDay? {
        switch source {
        case .tvaOperatingGuide(let loc):
            guard let rows = await tvaGuideRows(loc) else { return nil }
            let md = String(day.dropFirst(5))          // MM-dd
            guard let r = rows.first(where: { $0.monthDay == md }) else { return nil }
            let src = "tva:operating-guide:\(loc)"
            var zone: LakeOperatingZone?
            if let b = r.btmOpZone, let t = r.topOpZone {
                zone = LakeOperatingZone(bottomFt: b, topFt: t, bottomLabel: "TVA operating zone bottom",
                                         topLabel: "TVA operating zone top", source: src)
            }
            return LakeGuideForDay(guideFt: r.guideCurve, zone: zone, levels: [], topOfGatesFt: r.topOfGates,
                                   floodPoolBottomFt: nil, source: src)
        case .cwms(let office, let guideSeries, let bottomSeries, let bottomLabel, let extra):
            guard let (start, end) = LakeLevelCalendar.utcBounds(day: day, timeZone: timeZone) else { return nil }
            // Daily operator series are stamped near the start of the day; widen so one value is caught.
            let b = start.addingTimeInterval(-12 * 3600), e = end
            func last(_ name: String) async -> Double? {
                await cwms(office: office, name: name, begin: b, end: e).observations.last?.ft
            }
            let gc = await last(guideSeries)
            let bottom = await last(bottomSeries)
            var levels: [LakeOperatorLevel] = []
            let src = "cwms:\(office)"
            if let gc { levels.append(.init(name: "Top of Conservation (guide curve)", ft: gc, source: "\(src):\(guideSeries)")) }
            if let bottom { levels.append(.init(name: bottomLabel, ft: bottom, source: "\(src):\(bottomSeries)")) }
            for x in extra { if let v = await last(x.series) { levels.append(.init(name: x.name, ft: v, source: "\(src):\(x.series)")) } }
            guard gc != nil || bottom != nil else { return nil }
            var zone: LakeOperatingZone?
            if let gc, let bottom {
                zone = LakeOperatingZone(bottomFt: bottom, topFt: gc, bottomLabel: bottomLabel,
                                         topLabel: "Top of Conservation (guide curve)", source: src)
            }
            return LakeGuideForDay(guideFt: gc, zone: zone, levels: levels.sorted { $0.ft > $1.ft }, topOfGatesFt: nil,
                                   floodPoolBottomFt: gc, source: "\(src):\(guideSeries)")
        case .operatorLevels(let o):
            return await guide(operator: o, day: day, timeZone: timeZone)
        }
    }

    public func daily(_ source: LakeHistorySource, since: String?, now: Date, timeZone: TimeZone) async -> [DailyLevel]? {
        switch source {
        case .tvaOperatingGuide(let loc):
            guard let rows = await tvaGuideRows(loc) else { return nil }
            return Self.tvaDaily(rows: rows, locationId: loc, now: now, timeZone: timeZone)
                .filter { since == nil || $0.date >= since! }
        case .cwmsDaily(let office, let series):
            let begin: Date = since.flatMap { LakeLevelCalendar.utcBounds(day: $0, timeZone: timeZone)?.0 }
                ?? LakeLevelCalendar.date(year: 1950, month: 1, day: 1)
            var out: [DailyLevel] = []
            var chunkStart = begin
            // Windows sized to the series interval keep each request inside the page budget (daily: 5 y; hourly: 5 y; 15 min: 1 y).
            let window = Self.cwmsWindowSeconds(series)
            while chunkStart < now {
                let chunkEnd = min(chunkStart.addingTimeInterval(window), now.addingTimeInterval(86_400))
                let r = await cwms(office: office, name: series, begin: chunkStart, end: chunkEnd)
                // A failed window would leave a silent hole in the history: fail the whole pull.
                if r.error != nil { return nil }
                out += Self.dailyMedians(r.observations, timeZone: timeZone, sourceId: "cwms:\(office):\(series)")
                chunkStart = chunkEnd
            }
            return LakeDailyHistory.dedupe(out)
        case .usgsDaily, .riseDaily, .hadsDaily:
            return await fleetDaily(source, since: since, now: now, timeZone: timeZone)
        case .sharedTVAArchive:
            return nil
        }
    }

    public func archivedHourly(_ source: LakeHistorySource, days: Int, now: Date, timeZone: TimeZone) async -> [LevelObservation] {
        guard case .sharedTVAArchive(let bucket, let prefix, let loc) = source, let store = sharedArchive(bucket) else { return [] }
        var out: [LevelObservation] = []
        for back in 0..<max(1, days) {
            let day = LakeLevelCalendar.dayString(now.addingTimeInterval(-Double(back) * 86_400), timeZone: timeZone)
            guard let d = try? await store.read("\(prefix)/\(loc)/\(day).json") else { continue }
            out += Self.parseSharedTVAArchiveDay(d)
        }
        return LakeLevelSeries.merge(out)
    }

    /// Request window for a CWMS series: ~5 years for coarse series, shrinking for sub-hourly ones (5 000 points per page, 20 pages).
    static func cwmsWindowSeconds(_ series: String) -> TimeInterval {
        let parts = series.split(separator: ".").map(String.init)
        var minutes = 1440
        if parts.count >= 6 {
            let iv = parts[3].trimmingCharacters(in: CharacterSet(charactersIn: "~"))
            if let r = iv.range(of: #"^\d+"#, options: .regularExpression), let n = Int(iv[r]) {
                if iv.contains("Minute") { minutes = n } else if iv.contains("Hour") { minutes = n * 60 } else { minutes = n * 1440 }
            }
        }
        let years = max(0.25, min(5.0, 60_000.0 / (525_960.0 / Double(max(1, minutes)))))
        return years * 365.25 * 86_400
    }

    /// One value per lake-local day: the median of the day's readings (identical to the reading itself for a daily series).
    static func dailyMedians(_ obs: [LevelObservation], timeZone: TimeZone, sourceId: String) -> [DailyLevel] {
        LakeFleetClients.dailyMedians(obs, timeZone: timeZone, offsetFt: 0, src: sourceId)
    }

    // MARK: TVA

    struct TVAGuideRow: Equatable {
        var monthDay: String   // MM-dd
        var guideCurve: Double?
        var btmOpZone: Double?
        var topOpZone: Double?
        var topOfGates: Double?
        var curYrElev: Double?
        var prevYrElev: Double?
    }

    private func tvaGuideRows(_ loc: String) async -> [TVAGuideRow]? {
        if let c = lock.withLock({ guideCache[loc] }) { return c }
        guard let data = await get("\(tvaBase)/operating-guide/\(loc)", accept: "application/json"),
              let rows = Self.parseTVAGuide(data), !rows.isEmpty else { return nil }
        lock.withLock { guideCache[loc] = rows }
        return rows
    }

    /// `/operating-guide/{id}` → rows keyed by month-day. The `Day` year is a stale
    /// template label (rows read "2025" in 2026): only month and day are used.
    /// Zero means "no value" (future days of `CurYrElev`).
    static func parseTVAGuide(_ data: Data) -> [TVAGuideRow]? {
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let items = obj["items"] as? [[String: Any]] else { return nil }
        func num(_ v: Any?) -> Double? {
            let d: Double?
            if let n = v as? Double { d = n } else if let n = v as? Int { d = Double(n) }
            else if let s = v as? String { d = TVAGenerationService.number(s) } else { d = nil }
            guard let x = d, x > 0 else { return nil }
            return x
        }
        return items.compactMap { it in
            guard let day = it["Day"] as? String else { return nil }
            let p = day.split(separator: "/")
            guard p.count == 3, let m = Int(p[0]), let dd = Int(p[1]) else { return nil }
            return TVAGuideRow(monthDay: String(format: "%02d-%02d", m, dd), guideCurve: num(it["GuideCurve"]),
                               btmOpZone: num(it["BtmOpZone"]), topOpZone: num(it["TopOpZone"]),
                               topOfGates: num(it["TopOfGates"]), curYrElev: num(it["CurYrElev"]),
                               prevYrElev: num(it["PrevYrElev"]))
        }
    }

    /// `CurYrElev` = this calendar year's elevation at 00:00 of that day (validated
    /// 2026-10-12: the last non-zero row equals `MidNightElevation` and the 48 h feed's
    /// midnight reading on all four pilot dams). `PrevYrElev` = the previous year.
    static func tvaDaily(rows: [TVAGuideRow], locationId: String, now: Date, timeZone: TimeZone) -> [DailyLevel] {
        let today = LakeLevelCalendar.dayString(now, timeZone: timeZone)
        guard let year = Int(today.prefix(4)) else { return [] }
        let src = "tva:operating-guide:\(locationId)"
        var out: [DailyLevel] = []
        for r in rows {
            if let v = r.prevYrElev { out.append(DailyLevel(date: "\(year - 1)-\(r.monthDay)", ft: v, sourceId: src)) }
            let cur = "\(year)-\(r.monthDay)"
            if let v = r.curYrElev, cur <= today { out.append(DailyLevel(date: cur, ft: v, sourceId: src)) }
        }
        return LakeDailyHistory.dedupe(out)
    }

    private func tvaObserved(_ loc: String) async -> FeedResult {
        guard let data = await get("\(tvaBase)/observed-data-48-hours/\(loc)", accept: "application/json") else {
            return .failed("TVA observed-data-48-hours/\(loc) unreachable")
        }
        let obs = Self.parseTVAObserved(data)
        return obs.isEmpty ? .failed("TVA observed-data-48-hours/\(loc) returned no readings")
            : FeedResult(observations: obs, error: nil, release: Self.parseTVARelease(data))
    }

    /// The same 48 h rows' `AverageHourlyDischarge` (cfs) and `TailwaterElevation` (ft), oldest first. Zero or blank is "no value".
    static func parseTVARelease(_ data: Data) -> [ReleaseObservation] {
        guard let rows = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] else { return [] }
        func num(_ k: String, _ r: [String: Any]) -> Double? { TVAGenerationService.number(r[k] as? String).flatMap { $0 > 0 ? $0 : nil } }
        var byTime: [Date: ReleaseObservation] = [:]
        for r in rows {
            guard let day = r["Day"] as? String, let time = r["Time"] as? String, let at = tvaTime(day: day, time: time) else { continue }
            let o = ReleaseObservation(at: at, outflowCfs: num("AverageHourlyDischarge", r), tailwaterFt: num("TailwaterElevation", r))
            if o.outflowCfs != nil || o.tailwaterFt != nil { byTime[at] = o }
        }
        return byTime.values.sorted { $0.at < $1.at }
    }

    static func parseTVAObserved(_ data: Data) -> [LevelObservation] {
        guard let rows = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] else { return [] }
        return LakeLevelSeries.merge(rows.compactMap { r in
            guard let day = r["Day"] as? String, let time = r["Time"] as? String,
                  let ft = TVAGenerationService.number(r["ReservoirElevation"] as? String), ft > 0,
                  let at = tvaTime(day: day, time: time) else { return nil }
            return LevelObservation(at: at, ft: ft)
        })
    }

    /// "10/10/2026" + "Midnight CDT" → 2026-10-11T00:00 America/Chicago (hour-ending label).
    static func tvaTime(day: String, time: String) -> Date? {
        guard let zone = TVAGenerationService.zone(from: time) else { return nil }
        let stripped = TVAGenerationService.stripZone(time)
        let isMidnight = stripped.uppercased() == "MIDNIGHT"
        guard let hour = isMidnight ? 24 : TVAGenerationService.hour(from: stripped) else { return nil }
        return TVAGenerationService.date(day: day, hour: hour, zone: zone)
    }

    /// The Water Temp lane's archive day file: `observed{localTime → {parsed{utcTime, reservoirElevationFt}}}`.
    static func parseSharedTVAArchiveDay(_ data: Data) -> [LevelObservation] {
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let observed = obj["observed"] as? [String: Any] else { return [] }
        let f = ISO8601DateFormatter()
        return observed.values.compactMap { v in
            guard let row = v as? [String: Any], let p = row["parsed"] as? [String: Any],
                  let utc = p["utcTime"] as? String, let at = f.date(from: utc),
                  let ft = (p["reservoirElevationFt"] as? Double) ?? (p["reservoirElevationFt"] as? Int).map(Double.init),
                  ft > 0 else { return nil }
            return LevelObservation(at: at, ft: ft)
        }
    }

    // MARK: CWMS

    func cwms(office: String, name: String, begin: Date, end: Date) async -> FeedResult {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        var out: [LevelObservation] = []
        var page: String? = nil
        for attempt in 0..<20 {
            var c = URLComponents(string: "\(cwmsBase)/timeseries")
            var q: [URLQueryItem] = [
                .init(name: "office", value: office), .init(name: "name", value: name), .init(name: "unit", value: "EN"),
                .init(name: "begin", value: f.string(from: begin)), .init(name: "end", value: f.string(from: end)),
                .init(name: "page-size", value: "5000"),
            ]
            if let page { q.append(.init(name: "page", value: page)) }
            c?.queryItems = q
            guard let url = c?.url?.absoluteString, let data = await get(url, accept: "application/json;version=2") else {
                return out.isEmpty ? .failed("CWMS \(office) \(name) unreachable") : FeedResult(observations: out, error: "CWMS page fetch failed")
            }
            guard let raw = CWMSObservedService.parseJSON(data) as? [String: Any] else { return .failed("CWMS \(name): unreadable JSON") }
            // Asked in English units; if a feed still answers in metres, convert.
            let k = ((raw["units"] as? String) ?? "ft").lowercased() == "m" ? LakeFeedHTTP.feetPerMetre : 1.0
            for row in (raw["values"] as? [[Any?]]) ?? [] {
                guard row.count >= 2, let ms = row[0] as? Double, let v = row[1] as? Double else { continue }
                out.append(LevelObservation(at: Date(timeIntervalSince1970: ms / 1000), ft: v * k))
            }
            guard let next = raw["next-page"] as? String, !next.isEmpty else { break }
            page = next
            if attempt == 19 { return FeedResult(observations: out, error: "CWMS \(name): page limit reached (series too dense for the window)") }
        }
        return FeedResult(observations: LakeLevelSeries.merge(out), error: nil)
    }

    // MARK: USGS (legacy WaterServices IV, the same service production reads)

    func usgs(site: String, parameter: String, hours: Int) async -> FeedResult {
        let url = "\(usgsBase)?format=json&sites=\(site)&parameterCd=\(parameter)&period=PT\(max(1, hours))H"
        guard let data = await get(url, accept: "application/json"),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let value = obj["value"] as? [String: Any],
              let series = value["timeSeries"] as? [[String: Any]] else { return .failed("USGS \(site) \(parameter) unreachable") }
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        var out: [LevelObservation] = []
        for s in series {
            for block in (s["values"] as? [[String: Any]]) ?? [] {
                for v in (block["value"] as? [[String: Any]]) ?? [] {
                    guard let t = v["dateTime"] as? String, let at = f.date(from: t),
                          let ft = Double((v["value"] as? String) ?? ""), ft > -999_990 else { continue }
                    out.append(LevelObservation(at: at, ft: ft))
                }
            }
        }
        return out.isEmpty ? .failed("USGS \(site) \(parameter): no readings") : FeedResult(observations: LakeLevelSeries.merge(out), error: nil)
    }

    private func get(_ url: String, accept: String) async -> Data? {
        guard let u = URL(string: url),
              let r = try? await HTTP.get(u, headers: ["Accept": accept]), r.isSuccess else { return nil }
        return r.body
    }
}

// MARK: - Series helpers

public enum LakeLevelSeries {
    /// Sorted, one value per timestamp (last wins).
    public static func merge(_ xs: [LevelObservation]) -> [LevelObservation] {
        var byTime: [Date: Double] = [:]
        for x in xs { byTime[x.at] = x.ft }
        return byTime.map { LevelObservation(at: $0.key, ft: $0.value) }.sorted { $0.at < $1.at }
    }

    /// The reading closest to `t` within `tolerance` seconds.
    public static func value(at t: Date, in xs: [LevelObservation], tolerance: TimeInterval) -> Double? {
        var best: (TimeInterval, Double)?
        for x in xs {
            let d = abs(x.at.timeIntervalSince(t))
            if d <= tolerance, best == nil || d < best!.0 { best = (d, x.ft) }
        }
        return best?.1
    }
}

public enum LakeLevelCalendar {
    public static func dayString(_ d: Date, timeZone: TimeZone) -> String {
        var cal = Calendar(identifier: .gregorian); cal.timeZone = timeZone
        let c = cal.dateComponents([.year, .month, .day], from: d)
        return String(format: "%04d-%02d-%02d", c.year!, c.month!, c.day!)
    }

    public static func date(year: Int, month: Int, day: Int, timeZone: TimeZone = TimeZone(identifier: "UTC")!) -> Date {
        var cal = Calendar(identifier: .gregorian); cal.timeZone = timeZone
        return cal.date(from: DateComponents(year: year, month: month, day: day))!
    }

    /// [start, end) of a lake-local day in absolute time.
    public static func utcBounds(day: String, timeZone: TimeZone) -> (Date, Date)? {
        let p = day.split(separator: "-").compactMap { Int($0) }
        guard p.count == 3 else { return nil }
        let s = date(year: p[0], month: p[1], day: p[2], timeZone: timeZone)
        var cal = Calendar(identifier: .gregorian); cal.timeZone = timeZone
        guard let e = cal.date(byAdding: .day, value: 1, to: s) else { return nil }
        return (s, e)
    }

    /// Day of year on a 365-day calendar; Feb 29 shares Feb 28's index.
    public static func doy365(_ day: String) -> Int? {
        let p = day.split(separator: "-").compactMap { Int($0) }
        guard p.count == 3, (1...12).contains(p[1]), (1...31).contains(p[2]) else { return nil }
        let cum = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
        let d = (p[1] == 2 && p[2] == 29) ? 28 : p[2]
        return cum[p[1] - 1] + d
    }

    public static func previousDay(_ day: String) -> String? {
        let p = day.split(separator: "-").compactMap { Int($0) }
        guard p.count == 3 else { return nil }
        let utc = TimeZone(identifier: "UTC")!
        return dayString(date(year: p[0], month: p[1], day: p[2], timeZone: utc).addingTimeInterval(-86_400), timeZone: utc)
    }
}
