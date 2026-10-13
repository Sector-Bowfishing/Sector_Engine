//
//  LakeLevelFeedsFleet.swift
//  Sector — Lake Brain: read-only clients for the fleet providers (Access2Water, RISE, NWPS) and the history / operator-level sources
//
//  Everything here is a GET against a public API, fetches only the series a binding names, and is polite:
//  one request at a time per host where the host asks for it (IEM HADS: >= 15 s apart, 429 backs off), one Access2Water
//  listing per district per run, a self-identifying User-Agent.
//
//  Traps handled (each one cost the research a false binding or a wrong history):
//    • USGS 00065 is a gage height, NOT an elevation: refused for live, and for history unless a datum offset is given.
//    • RISE writes 0.0 for a missing daily value: dropped. Daily items lag about 48 h. Modeled results are ignored.
//    • NWPS: a gauge's pedts must start with the binding's pe code (HP pool elevation vs HG stage); sentinels (-999) dropped.
//    • CWMS: asked in English units; a response that still says metres is converted.
//    • Access2Water: ONE GET per district; plain `Elev` on tailwater locations is excluded by binding the exact tsid.
//

import Foundation
import AsyncHTTPClient
import NIOCore
import NIOHTTP1

// MARK: - HTTP

enum LakeFeedHTTP {
    /// The identity every Lake Brain request carries. No personal mailbox: a role contact is added only when the operator sets
    /// `SECTOR_CONTACT` (an email or URL) in the job environment. See `userAgent(contact:)`.
    static let baseUserAgent = "Sector-LakeBrain/1.0 (io.sector.co; Rehtac Labs; read-only public data)"

    /// `baseUserAgent`, plus `; contact <value>` when `SECTOR_CONTACT` is set to a non-empty, printable, <= 120 character value.
    static func userAgent(contact: String?) -> String {
        guard let raw = contact?.trimmingCharacters(in: .whitespacesAndNewlines), !raw.isEmpty, raw.count <= 120,
              raw.unicodeScalars.allSatisfy({ $0.value >= 0x20 && $0.value < 0x7F && $0 != "(" && $0 != ")" })
        else { return baseUserAgent }
        return String(baseUserAgent.dropLast()) + "; contact \(raw))"
    }

    static let userAgent = userAgent(contact: ProcessInfo.processInfo.environment["SECTOR_CONTACT"])

    /// Process-lifetime client with a long read timeout (a HADS chunk or an Access2Water listing can take well over the
    /// engine's 8 s cap). Never shut down, like `HTTP.client`.
    static let client: HTTPClient = {
        var config = HTTPClient.Configuration()
        config.timeout = HTTPClient.Configuration.Timeout(connect: .seconds(10), read: .seconds(120))
        config.redirectConfiguration = .follow(max: 5, allowCycles: false)
        config.decompression = .enabled(limit: .size(256 * 1024 * 1024))
        return HTTPClient(eventLoopGroupProvider: .singleton, configuration: config)
    }()

    struct Response { var status: Int; var body: Data; var isSuccess: Bool { (200..<300).contains(status) } }

    static func get(_ url: String, accept: String = "application/json", timeout: TimeInterval = 60,
                    headers: [String: String] = [:]) async -> Response? {
        guard URL(string: url) != nil else { return nil }
        var request = HTTPClientRequest(url: url)
        request.method = .GET
        request.headers.add(name: "User-Agent", value: userAgent)
        request.headers.add(name: "Accept", value: accept)
        request.headers.add(name: "Accept-Encoding", value: "gzip, deflate")
        for (k, v) in headers { request.headers.replaceOrAdd(name: k, value: v) }
        do {
            let response = try await client.execute(request, timeout: .milliseconds(Int64(timeout * 1000)))
            let buffer = try await response.body.collect(upTo: 256 * 1024 * 1024)
            return Response(status: Int(response.status.code), body: Data(buffer.readableBytesView))
        } catch {
            return nil
        }
    }

    static func isoDate(_ s: String) -> Date? {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        if let d = f.date(from: s) { return d }
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f.date(from: s)
    }

    static let feetPerMetre = 3.280839895
}

// MARK: - Access2Water

/// One Access2Water location (the reporting API's `providers/{district}/locations` item), trimmed to what the Brain reads.
struct A2WLocation: Decodable, Sendable {
    struct Series: Decodable, Sendable {
        var tsid: String
        var parameter: String?
        var unit: String?
        var latest_time: String?
        var latest_value: Double?
        var delta24hr: Double?
    }
    struct Level: Decodable, Sendable {
        var label: String?
        var tsid: String?
        var parameter: String?
        var base_parameter: String?
        var units: String?
        var type: String?
        var latest_value: Double?
    }
    var provider: String
    var code: String
    var timeseries: [Series]?
    var levels: [Level]?
}

/// One listing per district and run, shared by every lake in it; concurrent callers join the same fetch.
actor A2WDistrictCache {
    private var inflight: [String: Task<[String: A2WLocation]?, Never>] = [:]
    private var done: [String: (at: Date, value: [String: A2WLocation]?)] = [:]
    private let ttl: TimeInterval
    init(ttl: TimeInterval = 15 * 60) { self.ttl = ttl }

    func district(_ slug: String, fetch: @escaping @Sendable (String) async -> [String: A2WLocation]?) async -> [String: A2WLocation]? {
        let key = slug.lowercased()
        if let d = done[key], Date().timeIntervalSince(d.at) < (d.value == nil ? 60 : ttl) { return d.value }
        if let t = inflight[key] { return await t.value }
        let t = Task { await fetch(key) }
        inflight[key] = t
        let v = await t.value
        inflight[key] = nil
        done[key] = (Date(), v)
        return v
    }
}

/// IEM asks callers to stay under about one request per 15-20 s; one gate for the whole process.
actor HADSGate {
    private var last = Date.distantPast
    func wait(minGap: TimeInterval) async {
        let wake = last.addingTimeInterval(minGap)
        let now = Date()
        if wake > now { try? await Task.sleep(nanoseconds: UInt64(wake.timeIntervalSince(now) * 1_000_000_000)) }
        last = Date()
    }
}

/// Mutable client state of `PublicLakeLevelFeeds` for the fleet providers.
final class LakeFleetClients: @unchecked Sendable {
    let a2w = A2WDistrictCache()
    let hads = HADSGate()
    /// TWDB pacing gate + transport (LakeLevelFeedsTWDB.swift).
    let twdbTransport = TWDBTransport.live()
    static let a2wBase = "https://water.usace.army.mil/cda/reporting"
    static let nwpsBase = "https://api.water.noaa.gov/nwps/v1"
    static let riseBase = "https://data.usbr.gov/rise/api"
    static let hadsBase = "https://mesonet.agron.iastate.edu/cgi-bin/request/hads.py"
    static let usgsBase = "https://waterservices.usgs.gov/nwis"
    /// Minimum seconds between two IEM requests.
    var hadsGapSeconds: TimeInterval = 15

    // MARK: Access2Water

    func a2wDistrict(_ slug: String) async -> [String: A2WLocation]? {
        await a2w.district(slug) { s in
            guard let r = await LakeFeedHTTP.get("\(Self.a2wBase)/providers/\(s)/locations", timeout: 90), r.isSuccess,
                  let locs = try? JSONDecoder().decode([A2WLocation].self, from: r.body) else { return nil }
            return Dictionary(locs.map { ($0.code, $0) }, uniquingKeysWith: { a, _ in a })
        }
    }

    /// `SWL:Beaver_Dam` → ("swl", "Beaver_Dam").
    static func a2wStation(_ station: String) -> (district: String, code: String)? {
        let p = station.split(separator: ":", maxSplits: 1).map(String.init)
        return p.count == 2 ? (p[0].lowercased(), p[1]) : nil
    }

    /// Access2Water carries the latest value and the 24 h change of each series, not a history: the reading is the latest value and,
    /// when the change is given, the value 24 h before it. That is enough for the 24 h trend; 1 h / 6 h / 3 d / 7 d changes stay unknown.
    func a2wRecent(_ ref: LevelSeriesRef) async -> FeedResult {
        guard let tsid = ref.series, let (district, code) = Self.a2wStation(ref.station) else { return .failed("a2w binding needs DISTRICT:CODE and a tsid") }
        guard let locs = await a2wDistrict(district) else { return .failed("Access2Water \(district) listing unreachable") }
        guard let loc = locs[code] else { return .failed("Access2Water \(ref.station): location not in the \(district) listing") }
        return Self.a2wReading(loc, ref: ref)
    }

    static func a2wReading(_ loc: A2WLocation, ref: LevelSeriesRef) -> FeedResult {
        guard let tsid = ref.series else { return .failed("a2w binding needs a tsid") }
        guard let s = loc.timeseries?.first(where: { $0.tsid == tsid }) else { return .failed("Access2Water \(ref.station): series \(tsid) not listed") }
        guard (s.unit ?? "ft").lowercased() == "ft" else { return .failed("Access2Water \(tsid): unit \(s.unit ?? "?") is not feet") }
        guard let t = s.latest_time, let at = LakeFeedHTTP.isoDate(t), let v = s.latest_value, v.isFinite else {
            return .failed("Access2Water \(tsid): no latest value")
        }
        var obs = [LevelObservation(at: at, ft: v)]
        if let d = s.delta24hr, d.isFinite { obs.insert(LevelObservation(at: at.addingTimeInterval(-86_400), ft: v - d), at: 0) }
        return FeedResult(observations: obs, error: nil)
    }

    /// Today's value of an Access2Water operator level.
    func a2wLevel(office: String, location: String, tsid: String) async -> Double? {
        guard let locs = await a2wDistrict(office), let l = locs[location],
              let lv = l.levels?.first(where: { $0.tsid == tsid }), (lv.units ?? "ft").lowercased() == "ft",
              let v = lv.latest_value, v.isFinite else { return nil }
        return v
    }

    // MARK: NWPS

    /// NWS NWPS gauge `/stageflow/observed`: about 30 days of hourly pool readings.
    func nwpsRecent(_ ref: LevelSeriesRef, since: Date) async -> FeedResult {
        let lid = ref.station
        guard let r = await LakeFeedHTTP.get("\(Self.nwpsBase)/gauges/\(lid)/stageflow/observed", timeout: 30) else {
            return .failed("NWPS \(lid) unreachable")
        }
        guard r.isSuccess else { return .failed("NWPS \(lid): HTTP \(r.status)") }
        return Self.parseNWPS(r.body, lid: lid, expectedPe: ref.series.map { String($0.prefix(2)) }, since: since)
    }

    static func parseNWPS(_ data: Data, lid: String, expectedPe: String?, since: Date) -> FeedResult {
        guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return .failed("NWPS \(lid): unreadable JSON") }
        if let want = expectedPe, let pedts = obj["pedts"] as? String, !pedts.hasPrefix(want) {
            return .failed("NWPS \(lid): gauge reports \(pedts), binding expects \(want) (stage is not pool elevation)")
        }
        if let u = obj["primaryUnits"] as? String, u.lowercased() != "ft" { return .failed("NWPS \(lid): primary unit \(u) is not feet") }
        var out: [LevelObservation] = []
        for row in (obj["data"] as? [[String: Any]]) ?? [] {
            guard let t = row["validTime"] as? String, let at = LakeFeedHTTP.isoDate(t), at >= since,
                  let v = (row["primary"] as? Double) ?? (row["primary"] as? Int).map(Double.init), v > -990 else { continue }
            out.append(LevelObservation(at: at, ft: v))
        }
        return out.isEmpty ? .failed("NWPS \(lid): no observed readings") : FeedResult(observations: LakeLevelSeries.merge(out), error: nil)
    }

    // MARK: RISE

    /// RISE daily `result`s of one item after `after` (yyyy-MM-dd). Follows `links.next`; returns nil if any page fails.
    func riseResults(item: String, after: String, maxPages: Int = 60) async -> [LevelObservation]? {
        var out: [LevelObservation] = []
        var page = 1
        while page <= maxPages {
            let url = "\(Self.riseBase)/result?itemId=\(item)&dateTime%5Bafter%5D=\(after)&itemsPerPage=2000&page=\(page)"
            guard let r = await LakeFeedHTTP.get(url, accept: "application/vnd.api+json", timeout: 90), r.isSuccess else { return nil }
            let (obs, hasNext) = Self.parseRISE(r.body)
            out += obs
            if !hasNext { break }
            page += 1
        }
        return out
    }

    static func parseRISE(_ data: Data) -> ([LevelObservation], hasNext: Bool) {
        guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else { return ([], false) }
        let next = ((obj["links"] as? [String: Any])?["next"] as? String).map { !$0.isEmpty } ?? false
        let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime]
        var out: [LevelObservation] = []
        for it in (obj["data"] as? [[String: Any]]) ?? [] {
            guard let a = it["attributes"] as? [String: Any], let t = a["dateTime"] as? String, let at = f.date(from: t),
                  let v = (a["result"] as? Double) ?? (a["result"] as? Int).map(Double.init), v.isFinite else { continue }
            if v <= 0 { continue }   // RISE writes 0.0 for a missing daily value
            if let ra = a["resultAttributes"] as? [String: Any], let kind = ra["resultType"] as? String, kind != "observed" { continue }
            out.append(LevelObservation(at: at, ft: v))
        }
        return (out, next)
    }

    func riseRecent(_ ref: LevelSeriesRef, hours: Int, now: Date) async -> FeedResult {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "UTC"); f.dateFormat = "yyyy-MM-dd"
        let after = f.string(from: now.addingTimeInterval(-Double(hours + 24) * 3600))
        guard let obs = await riseResults(item: ref.station, after: after, maxPages: 3) else { return .failed("RISE item \(ref.station) unreachable") }
        let merged = LakeLevelSeries.merge(obs)
        return merged.isEmpty ? .failed("RISE item \(ref.station): no usable daily values (0.0 placeholders dropped)") : FeedResult(observations: merged, error: nil)
    }

    func riseDaily(item: String, since: String?) async -> [DailyLevel]? {
        guard let obs = await riseResults(item: item, after: since ?? "1900-01-01") else { return nil }
        let utc = TimeZone(identifier: "UTC")!
        return LakeDailyHistory.dedupe(LakeLevelSeries.merge(obs).map {
            DailyLevel(date: LakeLevelCalendar.dayString($0.at, timeZone: utc), ft: $0.ft, sourceId: "rise:\(item)")
        })
    }

    // MARK: USGS history

    static let usgsElevationParams: Set<String> = ["00062", "62614", "62615", "62616", "72020", "72022"]
    /// Daily-value statistic precedence of the research (mean, then end-of-day observation, ...).
    static let usgsStatOrder = ["00003", "32400", "30800", "00001", "00002"]

    func usgsDaily(site: String, param: String, stat: String, offsetFt: Double, since: String?, now: Date,
                   timeZone: TimeZone) async -> [DailyLevel]? {
        // A gage height is a local-datum stage; it is a history only with the explicit datum offset that makes it an elevation.
        if !Self.usgsElevationParams.contains(param) && offsetFt == 0 { return nil }
        let src = "usgs:\(site):\(param):\(stat)"
        if stat == "iv" { return await usgsIVDaily(site: site, param: param, offsetFt: offsetFt, since: since, now: now, timeZone: timeZone, src: src) }
        let end = LakeLevelCalendar.dayString(now, timeZone: timeZone)
        var url = "\(Self.usgsBase)/dv/?format=json&sites=\(site)&parameterCd=\(param)&startDT=\(since ?? "1900-01-01")&endDT=\(end)&siteStatus=all"
        if stat != "dv" { url += "&statCd=\(stat)" }
        guard let r = await LakeFeedHTTP.get(url, timeout: 120) else { return nil }
        if r.status == 404 { return [] }   // USGS answers 404 for "no data"
        guard r.isSuccess else { return nil }
        return Self.parseUSGSDV(r.body, offsetFt: offsetFt, src: src)
    }

    static func parseUSGSDV(_ data: Data, offsetFt: Double, src: String) -> [DailyLevel]? {
        guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let value = obj["value"] as? [String: Any], let series = value["timeSeries"] as? [[String: Any]] else { return nil }
        var byStat: [String: [String: Double]] = [:]
        for s in series {
            let variable = s["variable"] as? [String: Any]
            let nodata = (variable?["noDataValue"] as? Double) ?? -999_999
            let stat = ((variable?["options"] as? [String: Any])?["option"] as? [[String: Any]])?.first?["optionCode"] as? String ?? "?"
            for block in (s["values"] as? [[String: Any]]) ?? [] {
                for v in (block["value"] as? [[String: Any]]) ?? [] {
                    guard let t = v["dateTime"] as? String, t.count >= 10, let x = Double((v["value"] as? String) ?? ""), x != nodata, x > -990_000 else { continue }
                    byStat[stat, default: [:]][String(t.prefix(10))] = x
                }
            }
        }
        var merged: [String: Double] = [:]
        for stat in usgsStatOrder + byStat.keys.filter({ !usgsStatOrder.contains($0) }).sorted() {
            for (d, x) in byStat[stat] ?? [:] where merged[d] == nil { merged[d] = x }
        }
        return LakeDailyHistory.dedupe(merged.map { DailyLevel(date: $0.key, ft: $0.value + offsetFt, sourceId: src) })
    }

    /// Instantaneous values reduced to the median of each lake-local day. Walks year by year back from now until two empty years.
    private func usgsIVDaily(site: String, param: String, offsetFt: Double, since: String?, now: Date, timeZone: TimeZone, src: String) async -> [DailyLevel]? {
        var out: [DailyLevel] = []
        var year = Int(LakeLevelCalendar.dayString(now, timeZone: timeZone).prefix(4)) ?? 2026
        let floor = since.flatMap { Int($0.prefix(4)) } ?? 1990
        var empty = 0
        while year >= floor && empty < 2 {
            let start = max(since ?? "\(year)-01-01", "\(year)-01-01")
            let end = year == (Int(LakeLevelCalendar.dayString(now, timeZone: timeZone).prefix(4)) ?? year)
                ? LakeLevelCalendar.dayString(now, timeZone: timeZone) : "\(year)-12-31"
            let url = "\(Self.usgsBase)/iv/?format=json&sites=\(site)&parameterCd=\(param)&startDT=\(start)&endDT=\(end)&siteStatus=all"
            guard let r = await LakeFeedHTTP.get(url, timeout: 120) else { return nil }
            if r.status == 404 { empty += 1; year -= 1; continue }
            guard r.isSuccess, let obs = Self.parseUSGSIV(r.body) else { return nil }
            empty = obs.isEmpty ? empty + 1 : 0
            out += Self.dailyMedians(obs, timeZone: timeZone, offsetFt: offsetFt, src: src)
            year -= 1
        }
        return LakeDailyHistory.dedupe(out)
    }

    static func parseUSGSIV(_ data: Data) -> [LevelObservation]? {
        guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let value = obj["value"] as? [String: Any], let series = value["timeSeries"] as? [[String: Any]] else { return nil }
        let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        var out: [LevelObservation] = []
        for s in series {
            for block in (s["values"] as? [[String: Any]]) ?? [] {
                for v in (block["value"] as? [[String: Any]]) ?? [] {
                    guard let t = v["dateTime"] as? String, let at = f.date(from: t), let x = Double((v["value"] as? String) ?? ""), x > -990_000 else { continue }
                    out.append(LevelObservation(at: at, ft: x))
                }
            }
        }
        return out
    }

    /// Median of the readings of each lake-local calendar day (robust to spikes), shifted by the datum offset.
    static func dailyMedians(_ obs: [LevelObservation], timeZone: TimeZone, offsetFt: Double, src: String) -> [DailyLevel] {
        var byDay: [String: [Double]] = [:]
        for o in obs { byDay[LakeLevelCalendar.dayString(o.at, timeZone: timeZone), default: []].append(o.ft) }
        return byDay.map { d, xs in
            let s = xs.sorted()
            let m = s.count % 2 == 1 ? s[s.count / 2] : (s[s.count / 2 - 1] + s[s.count / 2]) / 2
            return DailyLevel(date: d, ft: m + offsetFt, sourceId: src)
        }.sorted { $0.date < $1.date }
    }

    // MARK: HADS (IEM archive of the NWS DCP stream)

    /// Pool-elevation history of an NWS location id, 3-year chunks newest first, one request per `hadsGapSeconds`.
    /// A 429 backs off (60 s, doubling). The walk stops at the first empty chunk; any failed chunk fails the whole pull.
    func hadsDaily(lid: String, pe: String, offsetFt: Double, since: String?, now: Date, timeZone: TimeZone) async -> [DailyLevel]? {
        let prefix = pe.uppercased() + "IR"
        let src = "hads:\(lid):\(pe.uppercased())"
        let thisYear = Int(LakeLevelCalendar.dayString(now, timeZone: timeZone).prefix(4)) ?? 2026
        let floorYear = max(since.flatMap { Int($0.prefix(4)) } ?? 2009, 2009)
        var out: [DailyLevel] = []
        var hi = thisYear
        while hi >= floorYear {
            let lo = max(floorYear, hi - 2)
            let sts = "\(lo)-01-01T00:00Z"
            let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "UTC"); f.dateFormat = "yyyy-MM-dd'T'HH:mm'Z'"
            let ets = hi == thisYear ? f.string(from: now) : "\(hi + 1)-01-01T00:00Z"
            let url = "\(Self.hadsBase)?stations=\(lid)&sts=\(sts)&ets=\(ets)&what=txt&delim=comma"
            var body: Data?
            var wait: TimeInterval = 60
            for _ in 0..<4 {
                await hads.wait(minGap: hadsGapSeconds)
                let r = await LakeFeedHTTP.get(url, accept: "text/plain", timeout: 300)
                if let r, r.status == 429 { try? await Task.sleep(nanoseconds: UInt64(wait * 1e9)); wait *= 2; continue }
                if let r, r.isSuccess { body = r.body }
                break
            }
            guard let body else { return nil }
            let obs = Self.parseHADS(body, prefix: prefix)
            if obs.isEmpty { break }   // the archive starts about 2010-12: nothing earlier
            out += Self.dailyMedians(obs, timeZone: timeZone, offsetFt: offsetFt, src: src)
            hi = lo - 1
        }
        return LakeDailyHistory.dedupe(out).filter { since == nil || $0.date >= since! }
    }

    /// IEM `what=txt&delim=comma`: `station,utc_valid,HPIRZZZ,…`. A gauge can report its pool under several `HPIR…` columns over the years
    /// (different DCP configurations); per row the first non-empty `HPIR…` column is the pool elevation.
    static func parseHADS(_ data: Data, prefix: String) -> [LevelObservation] {
        let text = String(decoding: data, as: UTF8.self)
        var lines = text.split(whereSeparator: \.isNewline).makeIterator()
        guard let header = lines.next() else { return [] }
        let cols = header.split(separator: ",", omittingEmptySubsequences: false).map { String($0) }
        guard let tIdx = cols.firstIndex(of: "utc_valid") else { return [] }
        let vIdx = cols.indices.filter { cols[$0].hasPrefix(prefix) }
        guard !vIdx.isEmpty else { return [] }
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "UTC"); f.dateFormat = "yyyy-MM-dd HH:mm:ss"
        var out: [LevelObservation] = []
        while let line = lines.next() {
            let c = line.split(separator: ",", omittingEmptySubsequences: false)
            guard c.count > tIdx, let at = f.date(from: String(c[tIdx])) else { continue }
            for i in vIdx where i < c.count {
                if let v = Double(c[i]), v > -990 { out.append(LevelObservation(at: at, ft: v)); break }
            }
        }
        return out
    }
}

// MARK: - PublicLakeLevelFeeds: operator levels

extension PublicLakeLevelFeeds {

    /// Today's value of one operator level.
    func operatorLevelValue(_ r: OperatorLevelRef, day: String, timeZone: TimeZone) async -> Double? {
        switch r.kind {
        case .staticFt:
            return r.ft
        case .a2w:
            guard let o = r.office, let l = r.location, let id = r.id else { return nil }
            return await fleet.a2wLevel(office: o, location: l, tsid: id)
        case .cwmsLevel:
            guard let office = r.office, let id = r.id, let (start, end) = LakeLevelCalendar.utcBounds(day: day, timeZone: timeZone) else { return nil }
            let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime]
            let path = id.addingPercentEncoding(withAllowedCharacters: CharacterSet.urlPathAllowed.subtracting(CharacterSet(charactersIn: "/"))) ?? id
            let url = "\(cwmsBase)/levels/\(path)/timeseries?office=\(office)&unit=ft&begin=\(f.string(from: start.addingTimeInterval(-36 * 3600)))&end=\(f.string(from: end))"
            guard let r = await LakeFeedHTTP.get(url, accept: "application/json;version=2", timeout: 30), r.isSuccess,
                  let raw = (try? JSONSerialization.jsonObject(with: r.body)) as? [String: Any],
                  (raw["units"] as? String ?? "ft").lowercased() == "ft" else { return nil }
            var best: (Date, Double)?
            for row in (raw["values"] as? [[Any?]]) ?? [] {
                guard row.count >= 2, let ms = row[0] as? Double, let v = row[1] as? Double else { continue }
                let t = Date(timeIntervalSince1970: ms / 1000)
                if t <= end, best == nil || t > best!.0 { best = (t, v) }
            }
            return best?.1
        case .cwmsSeries:
            guard let office = r.office, let id = r.id, let (start, end) = LakeLevelCalendar.utcBounds(day: day, timeZone: timeZone) else { return nil }
            return await cwms(office: office, name: id, begin: start.addingTimeInterval(-12 * 3600), end: end).observations.last?.ft
        }
    }

    /// Operator guidance from verified levels. A zone needs both edges and a top above its bottom.
    func guide(operator o: OperatorLevels, day: String, timeZone: TimeZone) async -> LakeGuideForDay? {
        func value(_ r: OperatorLevelRef?) async -> Double? {
            guard let r else { return nil }
            return await operatorLevelValue(r, day: day, timeZone: timeZone).map { ($0 * 100).rounded() / 100 }
        }
        let gc = await value(o.guide), top = await value(o.zoneTop), bottom = await value(o.zoneBottom), flood = await value(o.floodPoolBottom)
        var levels: [LakeOperatorLevel] = []
        for (r, v) in [(o.guide, gc), (o.zoneTop, top), (o.zoneBottom, bottom), (o.floodPoolBottom, flood)] {
            if let r, let v { levels.append(.init(name: r.name, ft: v, source: r.source)) }
        }
        guard !levels.isEmpty else { return nil }
        var zone: LakeOperatingZone?
        if let t = o.zoneTop, let b = o.zoneBottom, let top, let bottom, top > bottom {
            zone = LakeOperatingZone(bottomFt: bottom, topFt: top, bottomLabel: b.name, topLabel: t.name, source: t.source)
        }
        // The same level can be both the top of the zone and the flood-pool bottom: list it once.
        var seen = Set<String>(); levels = levels.filter { seen.insert("\($0.name)|\($0.ft)").inserted }
        return LakeGuideForDay(guideFt: gc, zone: zone, levels: levels.sorted { $0.ft > $1.ft }, topOfGatesFt: nil,
                               floodPoolBottomFt: flood, source: "operator-levels:\(o.matchedProject ?? "verified")")
    }

    func fleetDaily(_ source: LakeHistorySource, since: String?, now: Date, timeZone: TimeZone) async -> [DailyLevel]? {
        switch source {
        case .usgsDaily(let site, let param, let stat, let offset):
            return await fleet.usgsDaily(site: site, param: param, stat: stat, offsetFt: offset, since: since, now: now, timeZone: timeZone)
        case .riseDaily(let item):
            return await fleet.riseDaily(item: item, since: since)
        case .hadsDaily(let lid, let pe, let offset):
            return await fleet.hadsDaily(lid: lid, pe: pe, offsetFt: offset, since: since, now: now, timeZone: timeZone)
        case .twdbDaily(let slug, let datum, let offset):
            return await fleet.twdbDaily(slug: slug, datum: datum, offsetFt: offset, since: since, now: now)
        default:
            return nil
        }
    }
}

// MARK: - Profile text for history sources

extension LakeHistorySource {
    /// One line for the profile's `sourceCapability.history`.
    var profileDescription: String {
        switch self {
        case .tvaOperatingGuide(let l): return "tva:operating-guide:\(l) (current + previous year, daily midnight)"
        case .sharedTVAArchive(let bucket, let prefix, let l): return "gs://\(bucket)/\(prefix)/\(l) (hourly, shared archive, read-only)"
        case .cwmsDaily(let o, let s): return "cwms:\(o):\(s) (daily)"
        case .usgsDaily(let site, let p, let stat, let off):
            return "usgs:\(site):\(p) (\(stat == "iv" ? "daily median of instantaneous values" : "daily values"))" + (off != 0 ? ", datum offset \(String(format: "%.2f", off)) ft" : "")
        case .riseDaily(let item): return "rise:\(item) (daily)"
        case .hadsDaily(let lid, let pe, let off):
            return "hads:\(lid):\(pe) (IEM HADS archive, daily median)" + (off != 0 ? ", datum offset \(String(format: "%.2f", off)) ft" : "")
        case .twdbDaily(let slug, let datum, let off):
            return "twdb:\(slug) (TWDB Water Data for Texas, estimated daily average, file datum \(datum))" + (off != 0 ? ", datum offset \(String(format: "%.2f", off)) ft" : "")
        }
    }
}
