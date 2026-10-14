//
//  LakeLevelFeedsTWDB.swift
//  Sector — Lake Brain: read-only client for the Texas Water Development Board "Water Data For Texas" reservoir CSVs
//
//  Contract (research 2026-10-13, docs/brains/LAKE_BRAIN_PROVIDERS.md section 4):
//    GET https://www.waterdatafortexas.org/reservoirs/individual/{slug}.csv         full daily record (1 to 2 MB, 0.5 to 13 s)
//    GET https://www.waterdatafortexas.org/reservoirs/individual/{slug}-1year.csv   last year
//    GET https://www.waterdatafortexas.org/reservoirs/individual/{slug}-30day.csv   last 30 days (about 5 KB)
//  Documented by TWDB at /reservoirs/download. Public, no key, no documented rate limit or licence beyond a no-warranty disclaimer.
//
//  TERMS GATE (read before enabling): https://www.waterdatafortexas.org/robots.txt says `User-agent: *` / `Disallow: *.csv`, while the
//  download page /reservoirs/download publishes exactly these .csv links for download. TWDB states no licence and no rate limit. Until
//  TWDB (waterdatafortexas@twdb.texas.gov, the contact on its site) or Michael settles that, the live transport is DISABLED: it makes
//  no request and every read fails with a named error. Set SECTOR_TWDB_TERMS_OK=1 to open it. See docs/brains/LAKE_BRAIN_PROVIDERS.md
//  section 4. Tests inject their own transport and are unaffected.
//
//  What the file says about itself (and what the adapter therefore enforces):
//    • `# Vertical datum(s) used:` + one line (NGVD29 for 13 of 16 matched lakes, `NAVD88 +0.26`, `NAVD88 +0.6`, `NGVD29 -43.3` for the
//      others): the binding names the datum label it was verified against (`series` = `water_level@<label>`); a file that says something
//      else is refused, never silently accepted.
//    • `# Units:` `water_level: feet above vertical datum`: anything but feet is refused.
//    • "Estimated daily average data": ONE value per day (the average of the polls so far for today), polled about every 6 h. A reading
//      is stamped at 12:00 America/Chicago of its date (a daily-average has no instant), so a binding is cadence 1440 / lag 1440.
//    • TWDB is a RELAY of USGS / USACE / USBR / IBWC / LCRA gauges. It is never independent corroboration of its own origin.
//
//  Traps handled (all seen in the 16 matched lakes' real files):
//    • blank water_level on days with storage only (pre-impoundment years, gauge outages) and 0.0 placeholders: dropped.
//    • isolated glitches of 1 to 3 days (Amistad 790 ft among 1118 ft, Elephant Butte 3 148 to 3 964 ft among 4 275 ft, Travis
//      +33 ft for one day, Caddo -16 ft): a run of up to 3 consecutive days whose every value is more than 15 ft from BOTH the day
//      before and the day after, when those two agree within 15 ft, is dropped. 15 ft is the same figure as the history/live mismatch
//      rule. A trailing run that cannot be confirmed yet (no day after it) and jumps more than 15 ft from the day before is held back
//      until the next day, so one bad latest day never becomes the live level.
//    • HTML or JSON bodies on HTTP 200, 404 for an unknown slug, 429 / 503: mapped to named errors; 429 / 503 back off and retry.
//

import Foundation
import AsyncHTTPClient
import NIOCore
import NIOHTTP1

// MARK: - HTTP

/// One process-wide pacing gate (TWDB documents no rate limit; the files are generated on request, so stay at one request every few seconds).
actor TWDBGate {
    private var last = Date.distantPast
    func wait(minGap: TimeInterval) async {
        let wake = last.addingTimeInterval(minGap)
        let now = Date()
        if wake > now { try? await Task.sleep(nanoseconds: UInt64(wake.timeIntervalSince(now) * 1_000_000_000)) }
        last = Date()
    }
}

struct TWDBResponse: Sendable {
    var status: Int
    var body: Data
    /// `Retry-After` in seconds, when the server sent one.
    var retryAfter: TimeInterval?
}

/// Everything the TWDB client needs from the world; tests inject fakes.
struct TWDBTransport: Sendable {
    var fetch: @Sendable (_ url: String) async -> TWDBResponse?
    var sleep: @Sendable (_ seconds: TimeInterval) async -> Void
    var gate: TWDBGate
    var minGapSeconds: TimeInterval
    /// False = no request is ever made (see the terms gate in the file header).
    var enabled = true
    static let disabledMessage = "TWDB disabled: robots.txt disallows *.csv for all agents and TWDB states no licence or rate limit (set SECTOR_TWDB_TERMS_OK=1 once TWDB or Michael has cleared it; docs/brains/LAKE_BRAIN_PROVIDERS.md section 4)"

    static let base = "https://www.waterdatafortexas.org/reservoirs/individual"

    /// `Sector-LakeBrain/1.0 (io.sector.co; Rehtac Labs; read-only public data)`, plus ` contact: <SECTOR_CONTACT>` when the env var is set.
    /// No mailbox is ever invented or embedded here.
    static func userAgent(env: [String: String] = ProcessInfo.processInfo.environment) -> String {
        var ua = "Sector-LakeBrain/1.0 (io.sector.co; Rehtac Labs; read-only public data)"
        if let c = env["SECTOR_CONTACT"]?.trimmingCharacters(in: .whitespacesAndNewlines), !c.isEmpty { ua += " contact: \(c)" }
        return ua
    }

    static func termsCleared(env: [String: String] = ProcessInfo.processInfo.environment) -> Bool {
        env["SECTOR_TWDB_TERMS_OK"] == "1"
    }

    static func live(minGapSeconds: TimeInterval = 2, env: [String: String] = ProcessInfo.processInfo.environment) -> TWDBTransport {
        TWDBTransport(
            fetch: { url in
                var request = HTTPClientRequest(url: url)
                request.method = .GET
                request.headers.add(name: "User-Agent", value: userAgent())
                request.headers.add(name: "Accept", value: "text/csv, text/plain")
                request.headers.add(name: "Accept-Encoding", value: "gzip, deflate")
                do {
                    let response = try await LakeFeedHTTP.client.execute(request, timeout: .seconds(60))
                    let buffer = try await response.body.collect(upTo: 64 * 1024 * 1024)
                    let ra = response.headers.first(name: "Retry-After").flatMap { Double($0) }
                    return TWDBResponse(status: Int(response.status.code), body: Data(buffer.readableBytesView), retryAfter: ra)
                } catch {
                    return nil
                }
            },
            sleep: { s in try? await Task.sleep(nanoseconds: UInt64(max(0, s) * 1_000_000_000)) },
            gate: TWDBGate(), minGapSeconds: minGapSeconds, enabled: termsCleared(env: env))
    }
}

// MARK: - Parsed file

struct TWDBSeries: Equatable, Sendable {
    /// The reservoir name in `# Estimated daily average data for <name>`.
    var reservoir: String?
    /// The single `# Vertical datum(s) used:` label, trimmed.
    var datum: String
    /// (yyyy-MM-dd, feet) with blanks, non-finite and non-positive values already dropped, oldest first.
    var days: [(date: String, ft: Double)]
    /// The file carried no `#` comment block (seen on the full-record file of Possum Kingdom on 2026-10-13, minutes after the same URL
    /// returned the block): datum and unit are then unknown and `datum` is empty. Only `TWDBClient.daily` accepts such a file, and only
    /// after corroborating it against the `-1year` file of the same reservoir.
    var headerless = false

    static func == (a: TWDBSeries, b: TWDBSeries) -> Bool {
        a.reservoir == b.reservoir && a.datum == b.datum && a.headerless == b.headerless && a.days.count == b.days.count
            && zip(a.days, b.days).allSatisfy { $0.date == $1.date && $0.ft == $1.ft }
    }
}

enum TWDBParseError: Error, Equatable, CustomStringConvertible {
    case notCSV, noDatum, ambiguousDatum([String]), datumMismatch(file: String, binding: String), unitNotFeet(String), noWaterLevelColumn, noUsableDays
    var description: String {
        switch self {
        case .notCSV: return "response is not a TWDB CSV"
        case .noDatum: return "file declares no vertical datum"
        case .ambiguousDatum(let d): return "file declares several vertical datums (\(d.joined(separator: ", ")))"
        case .datumMismatch(let f, let b): return "file datum '\(f)' is not the binding's datum '\(b)'"
        case .unitNotFeet(let u): return "water_level unit '\(u)' is not feet"
        case .noWaterLevelColumn: return "no water_level column"
        case .noUsableDays: return "no usable daily values (blank and 0.0 placeholders dropped)"
        }
    }
}

enum TWDB {
    /// Same figure as the history/live mismatch rule (LakeBrainRunner.historyLiveMismatch).
    static let glitchFt = 15.0
    static let maxGlitchRunDays = 3
    static let tz = TimeZone(identifier: "America/Chicago")!

    /// `water_level@NGVD29` -> `NGVD29`; nil when the binding does not name a datum (it must).
    static func bindingDatum(_ series: String?) -> String? {
        guard let s = series, let r = s.range(of: "@") else { return nil }
        let d = s[r.upperBound...].trimmingCharacters(in: .whitespaces)
        return s[..<r.lowerBound] == "water_level" && !d.isEmpty ? d : nil
    }

    static func validSlug(_ slug: String) -> Bool {
        !slug.isEmpty && slug.count <= 64 && slug.allSatisfy { ($0 >= "a" && $0 <= "z") || ($0 >= "0" && $0 <= "9") || $0 == "-" }
    }

    /// Parse one `individual/{slug}[-1year|-30day].csv`. `expectedDatum` nil skips the datum comparison (the dry-run tooling reads the label).
    static func parse(_ data: Data, expectedDatum: String?, allowHeaderless: Bool = false) -> Result<TWDBSeries, TWDBParseError> {
        let text = String(decoding: data, as: UTF8.self)
        var reservoir: String?
        var datums: [String] = []
        var inDatum = false
        var unitFeet: Bool?
        var unitText = ""
        var header: [String]?
        var rows: [Substring] = []
        for line in text.split(whereSeparator: \.isNewline) {
            if line.hasPrefix("#") {
                let body = line.dropFirst().trimmingCharacters(in: .whitespaces)
                if body.hasPrefix("Estimated daily average data for ") { reservoir = String(body.dropFirst("Estimated daily average data for ".count)) }
                if body.hasPrefix("Vertical datum(s) used:") { inDatum = true; continue }
                if inDatum {
                    if body.isEmpty || body.hasPrefix("Units:") { inDatum = false } else { datums.append(body) }
                }
                if body.hasPrefix("water_level:") {
                    unitText = String(body.dropFirst("water_level:".count)).trimmingCharacters(in: .whitespaces)
                    unitFeet = unitText.lowercased().hasPrefix("feet")
                }
                continue
            }
            if header == nil {
                header = line.split(separator: ",", omittingEmptySubsequences: false).map { $0.trimmingCharacters(in: .whitespaces) }
                continue
            }
            rows.append(line)
        }
        guard let header, header.first == "date" else { return .failure(.notCSV) }
        guard let wIdx = header.firstIndex(of: "water_level") else { return .failure(.noWaterLevelColumn) }
        let headerless = allowHeaderless && datums.isEmpty && unitText.isEmpty && reservoir == nil
        if datums.isEmpty && !headerless { return .failure(.noDatum) }
        if datums.count > 1 { return .failure(.ambiguousDatum(datums)) }
        if !headerless {
            if unitFeet != true { return .failure(.unitNotFeet(unitText.isEmpty ? "missing" : unitText)) }
            if let e = expectedDatum, e.caseInsensitiveCompare(datums[0]) != .orderedSame {
                return .failure(.datumMismatch(file: datums[0], binding: e))
            }
        }
        var days: [(String, Double)] = []
        var seen = Set<String>()
        for r in rows {
            let c = r.split(separator: ",", omittingEmptySubsequences: false)
            guard c.count > wIdx, LakeLevelCalendar.isDayString(String(c[0])),
                  let v = Double(c[wIdx].trimmingCharacters(in: .whitespaces)), v.isFinite, v > 0 else { continue }
            let d = String(c[0])
            if seen.insert(d).inserted { days.append((d, v)) }
        }
        days.sort { $0.0 < $1.0 }
        guard !days.isEmpty else { return .failure(.noUsableDays) }
        return .success(TWDBSeries(reservoir: reservoir, datum: datums.first ?? "", days: despike(days), headerless: headerless))
    }

    /// Drops glitch runs (see the header). Pure and deterministic; the dry-run tooling has an identical Python twin.
    static func despike(_ days: [(String, Double)]) -> [(date: String, ft: Double)] {
        func ordinal(_ d: String) -> Int? {
            guard let t = LakeLevelCalendar.utcBounds(day: d, timeZone: TimeZone(identifier: "UTC")!)?.0 else { return nil }
            return Int((t.timeIntervalSince1970 / 86_400).rounded())
        }
        let ord = days.map { ordinal($0.0) ?? Int.min }
        var drop = Set<Int>()
        var i = 1
        while i < days.count {
            var matched = false
            for run in 1...maxGlitchRunDays {
                let j = i + run          // index of the day after the run
                guard i >= 1, j < days.count else { break }
                // run days, the day before and the day after are all consecutive calendar days
                guard ord[j] - ord[i - 1] == run + 1 else { continue }
                let p = days[i - 1].1, n = days[j].1
                guard abs(p - n) <= glitchFt else { continue }
                if (i..<j).allSatisfy({ abs(days[$0].1 - p) > glitchFt && abs(days[$0].1 - n) > glitchFt }) {
                    for k in i..<j { drop.insert(k) }
                    i = j
                    matched = true
                    break
                }
            }
            if !matched { i += 1 }
        }
        var kept = days.enumerated().filter { !drop.contains($0.offset) }.map { (date: $0.element.0, ft: $0.element.1) }
        // Trailing points that jump more than glitchFt from the day before cannot be confirmed yet: hold them back (at most 3).
        var held = 0
        while held < maxGlitchRunDays, kept.count >= 2, abs(kept[kept.count - 1].ft - kept[kept.count - 2].ft) > glitchFt,
              let a = ordinal(kept[kept.count - 2].date), let b = ordinal(kept[kept.count - 1].date), b - a <= 1 {
            kept.removeLast(); held += 1
        }
        return kept
    }

    /// A headerless record agrees with the declared `-1year` file: at least 200 shared days, and 99 % of them equal to 0.005 ft.
    static func corroborates(_ full: [(date: String, ft: Double)], _ year: [(date: String, ft: Double)]) -> Bool {
        let f = Dictionary(full.map { ($0.date, $0.ft) }, uniquingKeysWith: { a, _ in a })
        let shared = year.filter { f[$0.date] != nil }
        guard shared.count >= 200 else { return false }
        let equal = shared.filter { abs(f[$0.date]! - $0.ft) <= 0.005 }.count
        return Double(equal) >= 0.99 * Double(shared.count)
    }

    /// 12:00 America/Chicago of a TWDB date: a daily average has no instant.
    static func stamp(_ day: String) -> Date? {
        guard let start = LakeLevelCalendar.utcBounds(day: day, timeZone: tz)?.0 else { return nil }
        return start.addingTimeInterval(12 * 3600)
    }

    static func fileName(slug: String, since: String?, now: Date) -> String {
        guard let since, let s = LakeLevelCalendar.utcBounds(day: since, timeZone: TimeZone(identifier: "UTC")!)?.0 else { return slug }
        let days = now.timeIntervalSince(s) / 86_400
        if days <= 27 { return slug + "-30day" }
        if days <= 360 { return slug + "-1year" }
        return slug
    }
}

// MARK: - Client

struct TWDBFailure: Error, Equatable, Sendable {
    var message: String
    init(_ m: String) { message = m }
}

struct TWDBClient: Sendable {
    var transport: TWDBTransport
    var maxAttempts = 4

    /// GET one file with pacing and back-off. Errors are strings the profile shows.
    func fetch(slug: String, file: String) async -> Result<Data, TWDBFailure> {
        guard transport.enabled else { return .failure(TWDBFailure(TWDBTransport.disabledMessage)) }
        guard TWDB.validSlug(slug) else { return .failure(TWDBFailure("TWDB: invalid reservoir slug '\(slug)'")) }
        let url = "\(TWDBTransport.base)/\(file).csv"
        var wait: TimeInterval = 30
        for attempt in 1...maxAttempts {
            await transport.gate.wait(minGap: transport.minGapSeconds)
            guard let r = await transport.fetch(url) else {
                if attempt == maxAttempts { return .failure(TWDBFailure("TWDB \(slug) unreachable")) }
                await transport.sleep(wait); wait *= 2
                continue
            }
            switch r.status {
            case 200..<300:
                return .success(r.body)
            case 404:
                return .failure(TWDBFailure("TWDB \(slug): not found (HTTP 404; the reservoir page was renamed or removed)"))
            case 429, 503:
                if attempt == maxAttempts { return .failure(TWDBFailure("TWDB \(slug): \(r.status == 429 ? "rate limited (HTTP 429)" : "service unavailable (HTTP 503)") after \(maxAttempts) attempts")) }
                let pause = min(120, max(r.retryAfter ?? 0, wait))
                await transport.sleep(pause); wait *= 2
            default:
                return .failure(TWDBFailure("TWDB \(slug): HTTP \(r.status)"))
            }
        }
        return .failure(TWDBFailure("TWDB \(slug) unreachable"))
    }

    func series(slug: String, file: String, datum: String?, allowHeaderless: Bool = false) async -> Result<TWDBSeries, TWDBFailure> {
        switch await fetch(slug: slug, file: file) {
        case .failure(let e): return .failure(e)
        case .success(let body):
            switch TWDB.parse(body, expectedDatum: datum, allowHeaderless: allowHeaderless) {
            case .success(let s): return .success(s)
            case .failure(let e): return .failure(TWDBFailure("TWDB \(slug): \(e)"))
            }
        }
    }

    /// Live reading: the last 30 days (or the last year for a longer window), oldest first. The classifier applies cadence / lag to the stamps.
    func recent(_ ref: LevelSeriesRef, hours: Int, now: Date) async -> FeedResult {
        guard let datum = TWDB.bindingDatum(ref.series) else {
            return .failed("TWDB \(ref.station): binding must name the parameter and datum as water_level@<datum>")
        }
        let file = hours > 27 * 24 ? ref.station + "-1year" : ref.station + "-30day"
        switch await series(slug: ref.station, file: file, datum: datum) {
        case .failure(let e): return .failed(e.message)
        case .success(let s):
            let obs = s.days.compactMap { d in TWDB.stamp(d.date).map { LevelObservation(at: $0, ft: d.ft) } }
                .filter { $0.at >= now.addingTimeInterval(-Double(hours) * 3600) }
            return obs.isEmpty ? .failed("TWDB \(ref.station): no usable daily values in the last \(hours) h") : FeedResult(observations: LakeLevelSeries.merge(obs), error: nil)
        }
    }

    /// Daily history from `since` (inclusive). The datum offset puts the file's datum on the binding's.
    func daily(slug: String, datum: String, offsetFt: Double, since: String?, now: Date) async -> [DailyLevel]? {
        let file = TWDB.fileName(slug: slug, since: since, now: now)
        guard case .success(var s) = await series(slug: slug, file: file, datum: datum, allowHeaderless: file == slug) else { return nil }
        if s.headerless {
            // No datum / unit block: accept the rows only if the `-1year` file of the same reservoir (which declares NGVD29 or whatever the
            // binding names) agrees with them on the overlapping year.
            guard case .success(let year) = await series(slug: slug, file: slug + "-1year", datum: datum) else { return nil }
            guard TWDB.corroborates(s.days, year.days) else { return nil }
            s.datum = year.datum
        }
        let src = "twdb:\(slug)"
        return s.days.filter { since == nil || $0.date >= since! }
            .map { DailyLevel(date: $0.date, ft: $0.ft + offsetFt, sourceId: src) }
    }
}

// MARK: - Wiring into the fleet clients

extension LakeFleetClients {
    func twdbRecent(_ ref: LevelSeriesRef, hours: Int, now: Date) async -> FeedResult {
        await TWDBClient(transport: twdbTransport).recent(ref, hours: hours, now: now)
    }
    func twdbDaily(slug: String, datum: String, offsetFt: Double, since: String?, now: Date) async -> [DailyLevel]? {
        await TWDBClient(transport: twdbTransport).daily(slug: slug, datum: datum, offsetFt: offsetFt, since: since, now: now)
    }
}
