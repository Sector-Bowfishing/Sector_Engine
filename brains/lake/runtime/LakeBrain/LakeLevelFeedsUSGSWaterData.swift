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
//    • shadow: both are read concurrently; the LEGACY answer is the one returned, the v1 answer is only compared and logged
//              (`[usgs-shadow] ...`, one line per read). Shadow time is bounded (`LakeUSGSShadowGovernor`): a per-read deadline,
//              a per-run budget of extra waiting, and shadow turns itself off (logged once) after repeated 429s without a key.
//  Optional key: `USGS_API_KEY` is sent as the `X-Api-Key` header, only to https://api.waterdata.usgs.gov (dropped on a `next` link
//  or a redirect to any other host), never in a URL or a log. Without it the API rate-limits by IP; a 429 is retried after a pause.
//
//  The differences from WaterServices that are handled explicitly (each has a test):
//    D1 Several series per site and parameter come back flat (one `time_series_id` each). The series that matches the binding is
//       selected: a single series, or else the one `time-series-metadata` marks Primary; when that does not settle it, the read is
//       refused. Series are never merged (WaterServices' reader merged them last-wins). The gage-height reader keeps its stricter
//       rule: more than one series is refused.
//    D2 Times are UTC without fractional seconds (`2026-10-07T08:30:00+00:00`); both that and the legacy form are parsed.
//    D3 Daily statistics: `statistic_id` per feature, merged with the legacy precedence (00003 > 32400 > 30800 > 00001 > 00002,
//       then any other statistic in code order — legacy's fallback, matched by asking `daily` for every statistic when the binding
//       says `dv`). Each statistic is selected on its own: an ambiguous statistic is dropped (and named in the shadow line), the
//       unambiguous ones are kept; a metadata read that fails (429, unreachable, 5xx, unreadable) refuses the whole read. A binding
//       that names one statistic (32400, 30800, ...) is refused when the API does not serve a daily series of it.
//    D4 "No data" is a 200 with zero features (not a 404); a `null` value (and the legacy -999999) is skipped.
//    D10 A non-JSON body (the blackout notice page) is a failure, never data.
//  Every v1 failure carries a code and a reason (`ReadFailure`), and the shadow line reports both.
//

import Foundation
import AsyncHTTPClient
import NIOCore
import NIOHTTP1

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

// MARK: - Shadow time bounds

/// Where shadow routing reads the time and sleeps while it waits for v1. Always `.system` in production; a test injects a clock
/// that records exact waits, so budget accounting does not depend on how late a busy machine wakes a sleeping task.
struct LakeUSGSShadowClock: Sendable {
    let now: @Sendable () -> Date
    let sleep: @Sendable (TimeInterval) async -> Void

    static let system = LakeUSGSShadowClock(now: { Date() },
                                            sleep: { try? await Task.sleep(nanoseconds: UInt64($0 * 1_000_000_000)) })
}

/// Bounds what `shadow` may cost a run. The Lake Brain job evaluates up to 3 lakes at a time (`LakeBrainRunOptions.concurrency`), each
/// lake's reads one after another, under the Cloud Run task timeout of 60 min (`brains/lake/deploy/deploy-job.sh`); there is no
/// in-process wall-clock limit. In shadow the v1 read runs concurrently with the legacy one; once legacy has answered, the run waits
/// for v1 at most until the per-read deadline and only while the per-run budget of such waiting lasts. Without `USGS_API_KEY`,
/// repeated 429s turn shadow off for the rest of the run. Each "off" reason is logged once.
final class LakeUSGSShadowGovernor: @unchecked Sendable {
    static let perReadKey = "LAKE_USGS_SHADOW_READ_SECONDS"
    static let budgetKey = "LAKE_USGS_SHADOW_BUDGET_SECONDS"

    /// Longest a shadow read may run, from its start.
    let perReadSeconds: TimeInterval
    /// Total extra waiting for v1, after legacy has answered, per run.
    let budgetSeconds: TimeInterval
    let hasKey: Bool
    /// 429s (retries included) without a key after which shadow is off.
    let rateLimitThreshold: Int
    /// Measures the time spent waiting for v1 (`LakeUSGSRouting.run`).
    let clock: LakeUSGSShadowClock

    private let lock = NSLock()
    private var waited: TimeInterval = 0
    private var rateLimited = 0
    private var announced: Set<String> = []
    /// Detached comparisons (kind=site) still running; the job drains them before it exits.
    let detachedShadows = LakeUSGSDetachedShadows()

    init(perReadSeconds: TimeInterval = 20, budgetSeconds: TimeInterval = 300, hasKey: Bool, rateLimitThreshold: Int = 3,
         clock: LakeUSGSShadowClock = .system) {
        self.perReadSeconds = perReadSeconds
        self.budgetSeconds = budgetSeconds
        self.hasKey = hasKey
        self.rateLimitThreshold = rateLimitThreshold
        self.clock = clock
    }

    static func fromEnvironment(_ env: [String: String] = ProcessInfo.processInfo.environment) -> LakeUSGSShadowGovernor {
        func seconds(_ k: String, _ d: TimeInterval) -> TimeInterval {
            guard let v = env[k].flatMap({ TimeInterval($0.trimmingCharacters(in: .whitespaces)) }), v.isFinite, v >= 0 else { return d }
            return v
        }
        let key = (env[LakeUSGSWaterDataClient.apiKeyEnvironmentKey] ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        return LakeUSGSShadowGovernor(perReadSeconds: seconds(perReadKey, 20), budgetSeconds: seconds(budgetKey, 300), hasKey: !key.isEmpty)
    }

    /// One per process: a Lake Brain job execution is one run.
    static let shared = LakeUSGSShadowGovernor.fromEnvironment()

    func note429() { lock.lock(); rateLimited += 1; lock.unlock() }
    var rateLimitedCount: Int { lock.lock(); defer { lock.unlock() }; return rateLimited }
    var waitedSeconds: TimeInterval { lock.lock(); defer { lock.unlock() }; return waited }

    /// nil = run the shadow read; otherwise why it is off.
    func skipReason() -> String? {
        lock.lock(); defer { lock.unlock() }
        if waited >= budgetSeconds - 0.001 { return "budget-exhausted" }
        if !hasKey && rateLimited >= rateLimitThreshold { return "rate-limited-no-key" }
        return nil
    }

    /// True the first time a reason is seen (so it is logged once).
    func firstTime(_ reason: String) -> Bool { lock.lock(); defer { lock.unlock() }; return announced.insert(reason).inserted }

    /// How long to wait for v1 now that legacy has answered, `elapsed` after the shadow read started.
    func allowedWait(elapsed: TimeInterval) -> TimeInterval {
        lock.lock(); defer { lock.unlock() }
        let w = min(perReadSeconds - elapsed, budgetSeconds - waited)
        return w < 0.001 ? 0 : w
    }

    func spend(_ t: TimeInterval) { lock.lock(); waited += max(0, t); lock.unlock() }
}

/// A value a detached task delivers, awaited with a deadline: the caller never waits past it, whatever the task does.
final class LakeUSGSPending<U: Sendable>: @unchecked Sendable {
    private let lock = NSLock()
    private var value: U?
    private var waiter: CheckedContinuation<U?, Never>?
    private var settled = false

    func fulfil(_ v: U) {
        lock.lock()
        value = v
        let w = settled ? nil : waiter
        if w != nil { settled = true; waiter = nil }
        lock.unlock()
        w?.resume(returning: v)
    }

    private func expire() {
        lock.lock()
        let w = settled ? nil : waiter
        if w != nil { settled = true; waiter = nil }
        lock.unlock()
        w?.resume(returning: nil)
    }

    func wait(seconds: TimeInterval, sleep: @escaping @Sendable (TimeInterval) async -> Void = LakeUSGSShadowClock.system.sleep) async -> U? {
        lock.lock()
        if let v = value { settled = true; lock.unlock(); return v }
        lock.unlock()
        guard seconds > 0 else { return nil }
        return await withCheckedContinuation { (c: CheckedContinuation<U?, Never>) in
            lock.lock()
            if let v = value { settled = true; lock.unlock(); c.resume(returning: v); return }
            waiter = c
            lock.unlock()
            Task { [weak self] in
                await sleep(seconds)
                self?.expire()
            }
        }
    }
}

/// The detached shadow comparisons of a run (kind=site): registered when started, finished when their line is logged. The job waits
/// for the pending ones before it exits (`LakeUSGSShadowDrain`), at most until the last one's per-read deadline plus `grace`, so a
/// comparison still running is not killed without a trace. Nothing is registered in `legacy` or `v1`.
final class LakeUSGSDetachedShadows: @unchecked Sendable {
    struct Summary: Equatable, Sendable {
        /// v1 answered and the comparison was logged.
        var completed = 0
        /// v1 missed its deadline and `reason=ogc-timeout` was logged.
        var timedOut = 0
        /// Still running when the drain gave up (no line logged before exit).
        var dropped = 0
        var registered: Int { completed + timedOut + dropped }
    }

    private let lock = NSLock()
    private var nextId = 0
    private var pending: [Int: Date] = [:]
    private var completed = 0
    private var timedOut = 0

    /// Registers a comparison whose v1 read must answer by `deadline`; returns its id.
    func register(deadline: Date) -> Int {
        lock.lock(); defer { lock.unlock() }
        nextId += 1
        pending[nextId] = deadline
        return nextId
    }

    func finish(_ id: Int, answered: Bool) {
        lock.lock(); defer { lock.unlock() }
        guard pending.removeValue(forKey: id) != nil else { return }
        if answered { completed += 1 } else { timedOut += 1 }
    }

    var pendingCount: Int { lock.lock(); defer { lock.unlock() }; return pending.count }
    var registeredCount: Int { lock.lock(); defer { lock.unlock() }; return nextId }

    private func snapshot() -> (summary: Summary, lastDeadline: Date?) {
        lock.lock(); defer { lock.unlock() }
        return (Summary(completed: completed, timedOut: timedOut, dropped: pending.count), pending.values.max())
    }

    /// Waits until nothing is pending or the last pending deadline plus `grace` has passed; the comparisons left are `dropped`.
    func drain(grace: TimeInterval = 1, poll: TimeInterval = 0.05) async -> Summary {
        while true {
            let (s, last) = snapshot()
            guard let last, s.dropped > 0, Date() < last.addingTimeInterval(grace) else { return s }
            try? await Task.sleep(nanoseconds: UInt64(poll * 1_000_000_000))
        }
    }
}

/// What the Lake Brain job calls before it exits: in `shadow`, waits for the detached comparisons still running (bounded by their
/// per-read deadline) and logs one summary line. In `legacy` and `v1` it returns at once and logs nothing.
public enum LakeUSGSShadowDrain {
    public static func beforeExit(mode: LakeUSGSAPIMode = .fromEnvironment(), log: (String) -> Void = { print($0) }) async {
        await beforeExit(mode: mode, governor: .shared, log: log)
    }

    static func beforeExit(mode: LakeUSGSAPIMode, governor: LakeUSGSShadowGovernor, grace: TimeInterval = 1,
                           log: (String) -> Void) async {
        guard mode == .shadow else { return }
        let start = Date()
        let s = await governor.detachedShadows.drain(grace: grace)
        log("[usgs-shadow] detached kind=site completed=\(s.completed) timedOut=\(s.timedOut) dropped=\(s.dropped)"
            + " drainedMs=\(Int(Date().timeIntervalSince(start) * 1000))")
    }
}

/// Runs a read the way the switch says. In `shadow` the legacy answer is returned unchanged and the v1 answer, read concurrently and
/// bounded by the governor, is only compared (`compare` gets nil when v1 missed its deadline).
enum LakeUSGSRouting {
    static func run<T: Sendable, U: Sendable>(_ mode: LakeUSGSAPIMode,
                                              governor: LakeUSGSShadowGovernor,
                                              legacy: () async -> T,
                                              v1: @escaping @Sendable () async -> U,
                                              adopt: (U) -> T,
                                              compare: (T, U?) -> String,
                                              log: (String) -> Void) async -> T {
        switch mode {
        case .legacy:
            return await legacy()
        case .v1:
            return adopt(await v1())
        case .shadow:
            if shadowOff(governor: governor, log: log) { return await legacy() }
            let clock = governor.clock
            let start = clock.now()
            let pending = LakeUSGSPending<U>()
            let task = Task { pending.fulfil(await v1()) }
            let l = await legacy()
            let legacyDone = clock.now()
            let o = await pending.wait(seconds: governor.allowedWait(elapsed: legacyDone.timeIntervalSince(start)), sleep: clock.sleep)
            governor.spend(clock.now().timeIntervalSince(legacyDone))
            if o == nil { task.cancel() }
            log(compare(l, o))
            return l
        }
    }

    /// True when the governor has turned shadow off (the reason is logged the first time it is seen).
    static func shadowOff(governor: LakeUSGSShadowGovernor, log: (String) -> Void) -> Bool {
        guard let why = governor.skipReason() else { return false }
        if governor.firstTime(why) {
            log("[usgs-shadow] shadow-off reason=\(why) rateLimited=\(governor.rateLimitedCount) apiKey=\(governor.hasKey ? "set" : "unset")"
                + " waitedSeconds=\(Int(governor.waitedSeconds)) (logged once; legacy continues)")
        }
        return true
    }

    /// A shadow comparison nobody waits for: `v1` runs in a detached task with the per-read deadline, and `compare` is logged when it
    /// answers or the deadline passes (nil). It spends none of the run's waiting budget, because the run does not wait.
    static func detached<U: Sendable>(governor: LakeUSGSShadowGovernor,
                                      v1: @escaping @Sendable () async -> U,
                                      compare: @escaping @Sendable (U?) async -> String,
                                      log: @escaping @Sendable (String) -> Void) {
        if shadowOff(governor: governor, log: log) { return }
        let deadline = governor.perReadSeconds
        let shadows = governor.detachedShadows
        let id = shadows.register(deadline: Date().addingTimeInterval(deadline))
        Task.detached {
            let pending = LakeUSGSPending<U>()
            let read = Task { pending.fulfil(await v1()) }
            let o = await pending.wait(seconds: deadline)
            if o == nil { read.cancel() }
            log(await compare(o))
            shadows.finish(id, answered: o != nil)
        }
    }
}

// MARK: - v1 client

/// Why a v1 read failed: a code for the shadow line and the human reason.
struct LakeUSGSReadFailure: Error, Equatable, Sendable {
    enum Code: String, Sendable {
        case rateLimited = "rate-limited", http, unreachable, redirect, nonJSON = "non-json", html = "html-page", pageLimit = "page-limit"
        case ambiguousPrimary = "ambiguous-primary", metadataUnreadable = "metadata-unreadable", severalSeries = "several-series"
        case statisticNotServed = "statistic-not-served", emptyHistory = "empty-history", unit, noReadings = "no-readings"
        case siteRefused = "site-refused", badRequest = "bad-request"
    }
    var code: Code
    var why: String
    init(_ code: Code, _ why: String) { self.code = code; self.why = why }
}

/// One live read from the v1 API, with the qualifiers it carried (logged in shadow so ice-affected values are visible).
struct LakeUSGSV1Read: Sendable {
    var result: FeedResult
    var qualifiers: [String: Int] = [:]
    var failure: LakeUSGSReadFailure?

    static func failed(_ f: LakeUSGSReadFailure, _ message: String) -> LakeUSGSV1Read {
        LakeUSGSV1Read(result: .failed(message), failure: f)
    }
}

/// One history read from the v1 API. `levels` nil = refused or failed (`failure` says why). `droppedStatistics`: statistics of a
/// `dv` read left out because their series were ambiguous (statistic → reason); the others were kept.
///
/// `DailyLevel` does not carry the statistic of each date (its `sourceId` names the binding's `stat`, e.g. `dv`), so the plan §5
/// "same statistic chosen per date" check cannot be made from the published history; the shadow line reports the dropped
/// statistics instead, and a statistic difference shows as a value or missing-dates difference.
struct LakeUSGSV1Daily: Sendable {
    var levels: [DailyLevel]?
    var failure: LakeUSGSReadFailure?
    var droppedStatistics: [String: String] = [:]

    static func failed(_ f: LakeUSGSReadFailure) -> LakeUSGSV1Daily { LakeUSGSV1Daily(levels: nil, failure: f) }
}

/// The v1 client's HTTP: no automatic redirects, so the API key is never carried to another host (`fetch` follows them itself).
enum LakeUSGSWaterDataHTTP {
    static let client: HTTPClient = {
        var config = HTTPClient.Configuration()
        config.timeout = HTTPClient.Configuration.Timeout(connect: .seconds(10), read: .seconds(120))
        config.redirectConfiguration = .disallow
        config.decompression = .enabled(limit: .size(256 * 1024 * 1024))
        return HTTPClient(eventLoopGroupProvider: .singleton, configuration: config)
    }()

    static func get(_ url: String, headers: [String: String], timeout: TimeInterval) async -> LakeFeedHTTP.Response? {
        guard URL(string: url) != nil else { return nil }
        var request = HTTPClientRequest(url: url)
        request.method = .GET
        request.headers.add(name: "User-Agent", value: LakeFeedHTTP.userAgent)
        request.headers.add(name: "Accept", value: "application/json")
        request.headers.add(name: "Accept-Encoding", value: "gzip, deflate")
        for (k, v) in headers { request.headers.replaceOrAdd(name: k, value: v) }
        do {
            let response = try await client.execute(request, timeout: .milliseconds(Int64(timeout * 1000)))
            let buffer = try await response.body.collect(upTo: 256 * 1024 * 1024)
            return LakeFeedHTTP.Response(status: Int(response.status.code), body: Data(buffer.readableBytesView),
                                         location: response.headers.first(name: "Location"))
        } catch {
            return nil
        }
    }
}

struct LakeUSGSWaterDataClient: Sendable {
    static let host = "api.waterdata.usgs.gov"
    static let base = "https://api.waterdata.usgs.gov/ogcapi/v1/collections"
    static let apiKeyEnvironmentKey = "USGS_API_KEY"
    static let pageLimit = 10_000
    static let observationProperties =
        "time_series_id,monitoring_location_id,parameter_code,statistic_id,time,value,unit_of_measure,approval_status,qualifier"
    static let metadataProperties = "monitoring_location_id,parameter_code,statistic_id,computation_period_identifier,primary,sublocation_identifier"

    typealias Transport = @Sendable (_ url: String, _ headers: [String: String], _ timeout: TimeInterval) async -> LakeFeedHTTP.Response?
    typealias ReadFailure = LakeUSGSReadFailure

    var transport: Transport
    /// Sent as `X-Api-Key` when set, only to `host` over https.
    var apiKey: String?
    /// `rel=next` pages followed before a read is refused as incomplete (a silent truncation would be a hole in the history).
    var maxPages = 20
    /// Retries after a 429, each after `pause(attempt)`.
    var retries429 = 2
    var pause: @Sendable (_ attempt: Int) async -> Void
    /// Told of every 429 (retries included); the shadow governor counts them.
    var onRateLimited: @Sendable () -> Void = {}

    static func live(env: [String: String] = ProcessInfo.processInfo.environment,
                     governor: LakeUSGSShadowGovernor = .shared) -> LakeUSGSWaterDataClient {
        let key = (env[apiKeyEnvironmentKey] ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        return LakeUSGSWaterDataClient(
            transport: { url, headers, timeout in await LakeUSGSWaterDataHTTP.get(url, headers: headers, timeout: timeout) },
            apiKey: key.isEmpty ? nil : key,
            pause: { attempt in _ = try? await Task.sleep(nanoseconds: UInt64(10 * attempt) * 1_000_000_000) },
            onRateLimited: { governor.note429() })
    }

    /// A client that never reaches the network (every request fails as unreachable).
    static func unreachable() -> LakeUSGSWaterDataClient {
        LakeUSGSWaterDataClient(transport: { _, _, _ in nil }, apiKey: nil, pause: { _ in })
    }

    /// Whether the key may go to `url`: https and the Water Data API host only.
    static func sendsKey(to url: String) -> Bool {
        guard let u = URL(string: url) else { return false }
        return u.scheme?.lowercased() == "https" && u.host?.lowercased() == host
    }

    func headers(for url: String) -> [String: String] {
        guard let apiKey, Self.sendsKey(to: url) else { return [:] }
        return ["X-Api-Key": apiKey]
    }

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

    /// `statistics` nil = every statistic (legacy `dv` without `statCd`).
    static func dailyURL(site: String, parameter: String, statistics: [String]?, time: String) -> String {
        var items = [("monitoring_location_id", locationId(site)), ("parameter_code", parameter)]
        if let statistics { items.append(("statistic_id", statistics.joined(separator: ","))) }
        items += [("time", time), ("limit", String(pageLimit)), ("properties", observationProperties)]
        return url("daily", items)
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

    enum Fetched { case ok(Data), failed(ReadFailure) }

    func fetch(_ first: String, timeout: TimeInterval) async -> Fetched {
        var url = first
        var attempt = 0
        var hops = 0
        while true {
            guard let r = await transport(url, headers(for: url), timeout) else { return .failed(ReadFailure(.unreachable, "unreachable")) }
            if r.status == 429 {
                onRateLimited()
                if attempt < retries429 {
                    attempt += 1
                    await pause(attempt)
                    continue
                }
                return .failed(ReadFailure(.rateLimited, "HTTP 429 after \(attempt) retries" + (apiKey == nil ? " (no USGS_API_KEY)" : "")))
            }
            if [301, 302, 303, 307, 308].contains(r.status) {
                guard hops < 5, let loc = r.location, let next = URL(string: loc, relativeTo: URL(string: url))?.absoluteURL.absoluteString else {
                    return .failed(ReadFailure(.redirect, "HTTP \(r.status) redirect without a usable Location"))
                }
                hops += 1
                url = next
                continue
            }
            guard r.isSuccess else { return .failed(ReadFailure(r.status == 400 ? .badRequest : .http, "HTTP \(r.status)")) }
            return .ok(r.body)
        }
    }

    /// Every feature of a paged `items` answer, following `rel=next`. Zero features on a 200 is an empty answer (D4).
    func paged(_ first: String, timeout: TimeInterval) async -> Result<[Row], ReadFailure> {
        var rows: [Row] = []
        var next: String? = first
        var pages = 0
        while let url = next {
            if pages == maxPages { return .failure(ReadFailure(.pageLimit, "more than \(maxPages) pages (answer too large for one read)")) }
            let data: Data
            switch await fetch(url, timeout: timeout) {
            case .failed(let f): return .failure(f)
            case .ok(let d): data = d
            }
            // D10: a non-JSON body (the legacy blackout notice, a proxy error page) is a failure, never an empty answer.
            guard let page = Self.parsePage(data) else { return .failure(Self.unreadable(data)) }
            rows += page.rows
            pages += 1
            next = page.features == 0 ? nil : page.next
        }
        return .success(rows)
    }

    static func unreadable(_ data: Data) -> ReadFailure {
        let head = String(decoding: data.prefix(512), as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if head.hasPrefix("<") || head.contains("<html") {
            return ReadFailure(.html, "an HTML page, not JSON (blackout or error page)")
        }
        return ReadFailure(.nonJSON, "unreadable JSON (not a FeatureCollection)")
    }

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
            return .failure(ReadFailure(.severalSeries, "\(ids.count) \(label) series at this site (sub-locations); the binding cannot tell which is the lake"))
        }
        let data: Data
        switch await fetch(Self.metadataURL(ids: ids), timeout: timeout) {
        case .failed(let f):
            return .failure(ReadFailure(.metadataUnreadable, "\(ids.count) \(label) series at this site and time-series-metadata failed (\(f.code.rawValue): \(f.why)); refused rather than merged"))
        case .ok(let d): data = d
        }
        guard let meta = Self.parseMetadata(data) else {
            let inner = Self.unreadable(data)
            return .failure(ReadFailure(.metadataUnreadable, "\(ids.count) \(label) series at this site and time-series-metadata unreadable (\(inner.code.rawValue): \(inner.why)); refused rather than merged"))
        }
        let primaries = meta.filter { ids.contains($0.id) && $0.primary == "Primary" }.map(\.id)
        guard primaries.count == 1, let chosen = primaries.first else {
            return .failure(ReadFailure(.ambiguousPrimary, "\(ids.count) \(label) series at this site, \(primaries.count) marked Primary; ambiguous, refused rather than merged"))
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
        case .failure(let e): return .failed(e, "USGS \(site) \(parameter) unreachable (Water Data API: \(e.why))")
        case .success(let rows):
            switch await select(rows, site: site, parameter: parameter, pick: .primary, label: parameter, timeout: 60) {
            case .failure(let e): return .failed(e, "USGS \(site) \(parameter): \(e.why)")
            case .success(let picked):
                let obs = Self.observations(picked)
                guard !obs.isEmpty else { return .failed(ReadFailure(.noReadings, "no readings"), "USGS \(site) \(parameter): no readings") }
                return LakeUSGSV1Read(result: FeedResult(observations: LakeLevelSeries.merge(obs), error: nil), qualifiers: Self.qualifierCounts(picked))
            }
        }
    }

    // MARK: Gage height (legacy `/nwis/iv/?parameterCd=00065`), raw: the stage client adds the altitude

    func recentStage(site: String, hours: Int) async -> Result<(obs: [LevelObservation], qualifiers: [String: Int]), ReadFailure> {
        let p = LakeUSGSStageClient.gageHeight
        switch await paged(Self.continuousURL(site: site, parameter: p, time: "PT\(max(1, hours))H"), timeout: 60) {
        case .failure(let e): return .failure(ReadFailure(e.code, "unreachable (Water Data API: \(e.why))"))
        case .success(let rows):
            switch await select(rows, site: site, parameter: p, pick: .single, label: "gage-height", timeout: 60) {
            case .failure(let e): return .failure(e)
            case .success(let picked):
                if let u = picked.compactMap(\.unit).first(where: { $0.lowercased() != "ft" }) {
                    return .failure(ReadFailure(.unit, "unit \(u) is not feet"))
                }
                return .success((obs: Self.observations(picked), qualifiers: Self.qualifierCounts(picked)))
            }
        }
    }

    // MARK: Site altitude (legacy site service `alt_va` / `alt_datum_cd`)

    static func parseLocation(_ data: Data, site: String) -> USGSSiteDatumResult {
        guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else {
            return .refused("USGS \(site): monitoring-locations answer unreadable (\(unreadable(data).code.rawValue))")
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
        case .failed(let f) where f.why == "HTTP 404": return .refused("USGS \(site): site record not found")
        case .failed(let f): return .refused("USGS \(site): monitoring-locations \(f.code.rawValue): \(f.why)")
        case .ok(let data): return Self.parseLocation(data, site: site)
        }
    }

    // MARK: History (legacy `/nwis/dv/` and the year-by-year `/nwis/iv/` walk)

    /// Daily values. `stat` "dv": every statistic is requested (as legacy did without `statCd`), each one selected on its own, and
    /// merged with the legacy precedence; an ambiguous statistic is dropped and the others kept. A statistic code takes only that
    /// statistic and is refused when the API serves no daily series of it (D3).
    func daily(site: String, param: String, stat: String, offsetFt: Double, since: String?, now: Date, timeZone: TimeZone,
               src: String, singleSeries: Bool) async -> LakeUSGSV1Daily {
        if stat == "iv" {
            return await ivDaily(site: site, param: param, offsetFt: offsetFt, since: since, now: now, timeZone: timeZone, src: src,
                                 singleSeries: singleSeries)
        }
        let end = LakeLevelCalendar.dayString(now, timeZone: timeZone)
        let rows: [Row]
        switch await paged(Self.dailyURL(site: site, parameter: param, statistics: stat == "dv" ? nil : [stat],
                                         time: "\(since ?? "1900-01-01")/\(end)"), timeout: 120) {
        case .failure(let f): return .failed(f)
        case .success(let r): rows = r
        }
        let order = LakeFleetClients.usgsStatOrder
        let present = Set(rows.compactMap(\.statistic))
        let stats = stat == "dv" ? order + present.subtracting(order).sorted() : [stat]
        var byStat: [String: [String: Double]] = [:]
        var dropped: [String: String] = [:]
        var firstDrop: ReadFailure?
        for s in stats {
            let ofStat = rows.filter { ($0.statistic ?? "") == s }
            if ofStat.isEmpty { continue }
            switch await select(ofStat, site: site, parameter: param, pick: singleSeries ? .single : .primary, label: "\(param)/\(s)", timeout: 120) {
            case .failure(let f):
                // A named statistic, or the gage-height reader (one series per answer, as legacy): the whole read is refused.
                if stat != "dv" || singleSeries { return .failed(f) }
                // Only an ambiguous statistic is dropped. A failed or unreadable metadata read (429, unreachable, 5xx) says nothing
                // about the statistic, so the whole read is refused with that failure rather than answering with fewer statistics.
                guard Self.droppable(f) else { return LakeUSGSV1Daily(levels: nil, failure: f, droppedStatistics: dropped) }
                dropped[s] = f.code.rawValue
                if firstDrop == nil { firstDrop = f }
            case .success(let picked):
                for r in picked { if let v = r.value, r.time.count >= 10 { byStat[s, default: [:]][String(r.time.prefix(10))] = v } }
            }
        }
        if stat == "dv", byStat.isEmpty, let f = firstDrop {
            return LakeUSGSV1Daily(levels: nil, failure: f, droppedStatistics: dropped)
        }
        if stat != "dv" && (byStat[stat] ?? [:]).isEmpty {
            // Empty: a statistic the API does not serve is refused, never substituted; a full-history pull that is empty is refused too.
            switch await servesDaily(site: site, param: param, stat: stat) {
            case .failure(let f): return .failed(f)
            case .success(false): return .failed(ReadFailure(.statisticNotServed, "statistic \(stat) of \(param) is not served as a daily series at USGS \(site)"))
            case .success(true):
                guard since != nil else { return .failed(ReadFailure(.emptyHistory, "full-history pull of statistic \(stat) returned no values")) }
                return LakeUSGSV1Daily(levels: [], failure: nil)
            }
        }
        var merged: [String: Double] = [:]
        for s in stats { for (d, x) in byStat[s] ?? [:] where merged[d] == nil { merged[d] = x } }
        return LakeUSGSV1Daily(levels: LakeDailyHistory.dedupe(merged.map { DailyLevel(date: $0.key, ft: $0.value + offsetFt, sourceId: src) }),
                               failure: nil, droppedStatistics: dropped)
    }

    /// A `dv` statistic whose selection failed this way is dropped and the others kept; any other failure refuses the read.
    /// `severalSeries` cannot reach this today: only a `.single` pick returns it, and a `.single` (gage-height) `dv` read refuses
    /// before `droppable` is asked. It is listed so that a `.primary` pick that ever reports it is dropped like `ambiguousPrimary`.
    static func droppable(_ f: ReadFailure) -> Bool { f.code == .ambiguousPrimary || f.code == .severalSeries }

    /// Whether `time-series-metadata` lists a daily series of `stat` for the site and parameter.
    func servesDaily(site: String, param: String, stat: String) async -> Result<Bool, ReadFailure> {
        switch await fetch(Self.metadataURL(site: site, parameter: param, statistic: stat), timeout: 60) {
        case .failed(let f): return .failure(ReadFailure(f.code, "time-series-metadata: \(f.why)"))
        case .ok(let data):
            guard let meta = Self.parseMetadata(data) else { return .failure(Self.unreadable(data)) }
            return .success(meta.contains { $0.statistic == stat && ($0.computationPeriod == nil || $0.computationPeriod?.lowercased() == "daily") })
        }
    }

    /// Instantaneous values reduced to the median of each lake-local day, year by year back from now until two empty years
    /// (a 200 with no features is an empty year, D4). Each window is one lake-local calendar year or less (the API allows ≤ 3 years).
    func ivDaily(site: String, param: String, offsetFt: Double, since: String?, now: Date, timeZone: TimeZone, src: String,
                 singleSeries: Bool) async -> LakeUSGSV1Daily {
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
                  let e = LakeLevelCalendar.utcBounds(day: end, timeZone: timeZone)?.1 else {
                return .failed(ReadFailure(.badRequest, "bad window \(start)/\(end)"))
            }
            let url = Self.continuousURL(site: site, parameter: param, time: Self.interval(s, e.addingTimeInterval(-1)))
            let rows: [Row]
            switch await paged(url, timeout: 120) {
            case .failure(let f): return .failed(ReadFailure(f.code, "\(year): \(f.why)"))
            case .success(let r): rows = r
            }
            switch await select(rows, site: site, parameter: param, pick: singleSeries ? .single : .primary, label: param, timeout: 120) {
            case .failure(let f): return .failed(ReadFailure(f.code, "\(year): \(f.why)"))
            case .success(let picked):
                let obs = Self.observations(picked)
                empty = obs.isEmpty ? empty + 1 : 0
                out += LakeFleetClients.dailyMedians(obs, timeZone: timeZone, offsetFt: offsetFt, src: src)
            }
            year -= 1
        }
        return LakeUSGSV1Daily(levels: LakeDailyHistory.dedupe(out), failure: nil)
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
        /// The v1 failure (or refusal) text, logged quoted as `ogcWhy=`.
        var detail: String?

        /// v1 missed the shadow deadline (its read was cancelled; the legacy answer was served).
        static func timeout(legacyN: Int) -> Verdict {
            Verdict(verdict: "disagree", reason: "ogc-timeout", legacyN: legacyN, ogcN: 0, detail: "v1 read missed the shadow deadline")
        }
    }

    /// One token for `key=value`: letters, digits and `._:-` kept, anything else (spaces, `=`, quotes) becomes `_`.
    static func token(_ s: String) -> String {
        let ok = Set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")
        let t = String(s.map { ok.contains($0) ? $0 : "_" }.prefix(80))
        return t.isEmpty ? "-" : t
    }

    /// A quoted value with `\`, `"` and line breaks escaped, at most 240 characters.
    static func quoted(_ s: String) -> String {
        var out = ""
        for c in s.prefix(240) {
            switch c {
            case "\\": out += "\\\\"
            case "\"": out += "\\\""
            case "\n": out += "\\n"
            case "\r": out += "\\r"
            case "\t": out += "\\t"
            default: out.append(c)
            }
        }
        return "\"\(out)\""
    }

    static func line(site: String, param: String, kind: String, _ v: Verdict, qualifiers: [String: Int] = [:],
                     dropped: [String: String] = [:]) -> String {
        var s = "[usgs-shadow] site=\(token(site)) param=\(token(param)) kind=\(token(kind)) verdict=\(token(v.verdict)) reason=\(token(v.reason))"
        s += " legacyN=\(v.legacyN) ogcN=\(v.ogcN)"
        s += " maxAbsDelta=" + (v.maxAbsDelta.map { String(format: "%.3f", $0) } ?? "-")
        s += " tsDelta=" + (v.tsDelta.map { String(Int($0)) } ?? "-")
        if !qualifiers.isEmpty { s += " ogcQualifiers=" + qualifiers.sorted { $0.key < $1.key }.map { "\(token($0.key)):\($0.value)" }.joined(separator: ",") }
        if !dropped.isEmpty { s += " ogcDroppedStats=" + dropped.sorted { $0.key < $1.key }.map { "\(token($0.key)):\(token($0.value))" }.joined(separator: ",") }
        if let d = v.detail { s += " ogcWhy=" + quoted(d) }
        return s
    }


    /// Live series: same latest timestamp or OGC newer by ≤ 2 h; the value at legacy's latest timestamp within `tolerance`; ≥ 99 % of
    /// common timestamps within `tolerance`. A failed legacy read never counts against OGC.
    static func compareLive(legacy: FeedResult, ogc: FeedResult, ogcFailure: LakeUSGSReadFailure? = nil, tolerance: Double = 0.01) -> Verdict {
        let l = legacy.observations, o = ogc.observations
        guard let ll = l.last else {
            return Verdict(verdict: "legacy-unavailable", reason: "legacy-failed", legacyN: 0, ogcN: o.count, detail: ogcFailure?.why)
        }
        guard let ol = o.last else {
            return Verdict(verdict: "disagree", reason: "ogc-failed:" + (ogcFailure?.code.rawValue ?? "unknown"), legacyN: l.count, ogcN: 0,
                           detail: ogc.error ?? ogcFailure?.why)
        }
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
    /// last date equal or OGC newer by ≤ 1 day. The plan's "same statistic per date" cannot be checked (`LakeUSGSV1Daily`).
    static func compareDaily(legacy: [DailyLevel]?, ogc: [DailyLevel]?, ogcFailure: LakeUSGSReadFailure? = nil, tolerance: Double = 0.01) -> Verdict {
        guard let l = legacy else {
            return Verdict(verdict: "legacy-unavailable", reason: "legacy-failed", legacyN: 0, ogcN: ogc?.count ?? 0, detail: ogcFailure?.why)
        }
        guard let o = ogc else {
            return Verdict(verdict: "disagree", reason: "ogc-failed:" + (ogcFailure?.code.rawValue ?? "unknown"), legacyN: l.count, ogcN: 0,
                           detail: ogcFailure?.why)
        }
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
            var detail: String?
            if case .refused(let o) = ogc { detail = o }
            return Verdict(verdict: "legacy-unavailable", reason: "legacy-failed", legacyN: 0, ogcN: 0, detail: detail)
        case (.refused, .refused(let o)):
            return Verdict(verdict: "agree", reason: "both-refused", legacyN: 0, ogcN: 0, detail: o)
        case (.ok, .refused(let o)):
            return Verdict(verdict: "disagree", reason: "ogc-refused", legacyN: 1, ogcN: 0, detail: o)
        case (.refused, .ok):
            return Verdict(verdict: "disagree", reason: "legacy-refused", legacyN: 0, ogcN: 1)
        case (.ok(let a), .ok(let b)):
            let d = abs(a.altitudeFt - b.altitudeFt)
            let norm = { (s: String) in s.trimmingCharacters(in: .whitespaces).uppercased() }
            if norm(a.datum) != norm(b.datum) {
                return Verdict(verdict: "disagree", reason: "datum-\(norm(a.datum))-vs-\(norm(b.datum))", legacyN: 1, ogcN: 1, maxAbsDelta: d,
                               detail: "legacy datum \(a.datum), v1 datum \(b.datum)")
            }
            if d > 0.01 + 1e-9 { return Verdict(verdict: "disagree", reason: "altitude", legacyN: 1, ogcN: 1, maxAbsDelta: d) }
            return Verdict(verdict: "agree", reason: "-", legacyN: 1, ogcN: 1, maxAbsDelta: d)
        }
    }
}
