//
//  LakeBrainCWMSRetryTests.swift
//  Bounded, classified CWMS retries (LakeLevelFeedsCWMS.swift): timeout, HTTP errors, successful retry, exhausted retries,
//  Retry-After, permanent errors, and the Lake Brain fallback/health behaviour around them. Fake transport only: no network,
//  no sleeping (the fake records requested waits), no bucket, no database.
//

import XCTest
@testable import SectorEngine

/// Scripted CWMS transport: returns the queued outcomes in order (the last one repeats) and records every call and wait.
final class ScriptedCWMS: @unchecked Sendable {
    private let lock = NSLock()
    private var script: [Result<CWMSResponse, CWMSTransportFailure>]
    private(set) var calls = 0
    private(set) var waits: [TimeInterval] = []
    private(set) var timeouts: [TimeInterval] = []
    private(set) var lines: [String] = []
    let jitterValue: Double

    init(_ script: [Result<CWMSResponse, CWMSTransportFailure>], jitter: Double = 0.5) {
        precondition(!script.isEmpty); self.script = script; self.jitterValue = jitter
    }

    var transport: CWMSTransport {
        CWMSTransport(
            fetch: { [self] _, _, timeout in
                lock.withLock {
                    calls += 1; timeouts.append(timeout)
                    return script.count > 1 ? script.removeFirst() : script[0]
                }
            },
            sleep: { [self] s in lock.withLock { waits.append(s) } },
            jitter: { [self] in jitterValue },
            log: { [self] l in lock.withLock { lines.append(l) } })
    }

    static func ok(_ body: Data = Data("{}".utf8)) -> Result<CWMSResponse, CWMSTransportFailure> { .success(CWMSResponse(status: 200, body: body, retryAfter: nil)) }
    static func http(_ s: Int, retryAfter: TimeInterval? = nil) -> Result<CWMSResponse, CWMSTransportFailure> { .success(CWMSResponse(status: s, body: Data("<html>err</html>".utf8), retryAfter: retryAfter)) }
}

/// A CWMS JSON page (version=2 layout) with hourly readings ending `lagH` hours before `now`.
func cwmsPage(now: Date, hours: Int = 48, lagH: Double = 1, ft: Double = 649.0) -> Data {
    let end = now.addingTimeInterval(-lagH * 3600).timeIntervalSince1970
    let start = (end - Double(hours - 1) * 3600)
    let rows = (0..<hours).map { i in "[\(Int((start + Double(i) * 3600) * 1000)),\(ft),0]" }.joined(separator: ",")
    return Data(#"{"name":"Hartwell.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS","units":"ft","values":[\#(rows)]}"#.utf8)
}

final class LakeBrainCWMSRetryTests: XCTestCase {
    let policy = CWMSRetryPolicy()
    let label = "SAS Hartwell.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS"

    func get(_ f: ScriptedCWMS, _ p: CWMSRetryPolicy? = nil) async -> CWMSFetch {
        await CWMSRequest.get("https://example.invalid/cwms", accept: "application/json;version=2", label: label, transport: f.transport, policy: p ?? policy)
    }

    // MARK: policy

    func testPolicyDefaultsAreBounded() {
        XCTAssertEqual(policy.maxAttempts, 3)
        XCTAssertEqual(policy.attemptTimeout, 20)
        XCTAssertEqual(CWMSRetryPolicy.transientStatus, [408, 429, 500, 502, 503, 504])
        // worst case per request stays well inside the 15 min job budget: 3 x 20 s + max backoff
        let backoff = (1..<policy.maxAttempts).map { policy.delay(beforeRetry: $0, retryAfter: nil, jitter: 1) }.reduce(0, +)
        XCTAssertLessThanOrEqual(Double(policy.maxAttempts) * policy.attemptTimeout + backoff, 70)
    }

    func testBackoffIsExponentialCappedAndJittered() {
        XCTAssertEqual(policy.delay(beforeRetry: 1, retryAfter: nil, jitter: 0), 1.0)     // 2 s x 0.5
        XCTAssertEqual(policy.delay(beforeRetry: 1, retryAfter: nil, jitter: 1), 2.0)     // 2 s x 1.0
        XCTAssertEqual(policy.delay(beforeRetry: 2, retryAfter: nil, jitter: 1), 4.0)
        XCTAssertEqual(policy.delay(beforeRetry: 9, retryAfter: nil, jitter: 1), 10.0)    // capped at maxDelay
        for j in stride(from: 0.0, through: 1.0, by: 0.1) {
            let d = policy.delay(beforeRetry: 2, retryAfter: nil, jitter: j)
            XCTAssert((2.0...4.0).contains(d), "\(d)")
        }
        XCTAssertEqual(policy.delay(beforeRetry: 1, retryAfter: 7, jitter: 1), 7)          // server wait wins when longer
    }

    // MARK: transient → retried

    func testTimeoutThenSuccessRetriesOnce() async {
        let f = ScriptedCWMS([.failure(.timeout), ScriptedCWMS.ok()])
        let r = await get(f)
        XCTAssertEqual(r, .ok(Data("{}".utf8), attempts: 2))
        XCTAssertEqual(f.calls, 2)
        XCTAssertEqual(f.waits, [1.5])                       // 2 s nominal x (0.5 + 0.5 x 0.5)
        XCTAssertEqual(f.timeouts, [20, 20])                 // per-attempt timeout, not the 8 s render-path cap
        XCTAssertTrue(f.lines.contains { $0.contains("ok on attempt 2/3") })
    }

    func testServerErrorsThenSuccess() async {
        let f = ScriptedCWMS([ScriptedCWMS.http(502), ScriptedCWMS.http(504), ScriptedCWMS.ok()])
        let r = await get(f)
        XCTAssertEqual(r, .ok(Data("{}".utf8), attempts: 3))
        XCTAssertEqual(f.waits.count, 2)
    }

    func testExhaustedTimeoutsGiveUpAfterThreeAttempts() async {
        let f = ScriptedCWMS([.failure(.timeout)])
        let r = await get(f)
        guard case .exhausted(let m, let n) = r else { return XCTFail("\(r)") }
        XCTAssertEqual(n, 3); XCTAssertEqual(f.calls, 3); XCTAssertEqual(f.waits.count, 2)
        XCTAssertTrue(m.contains("timed out (20 s) after 3 attempts"), m)
    }

    func testExhaustedHTTP503KeepsTheReason() async {
        let f = ScriptedCWMS([ScriptedCWMS.http(503)])
        let r = await get(f)
        XCTAssertEqual(r.failure, "CWMS \(label): HTTP 503 after 3 attempts")
        XCTAssertEqual(f.calls, 3)
    }

    func testConnectionErrorsAreTransient() async {
        let f = ScriptedCWMS([.failure(.connection("connection reset by peer")), ScriptedCWMS.ok()])
        if case .ok(_, let n) = await get(f) { XCTAssertEqual(n, 2) } else { XCTFail() }
    }

    // MARK: rate limits

    func test429HonoursRetryAfter() async {
        let f = ScriptedCWMS([ScriptedCWMS.http(429, retryAfter: 12), ScriptedCWMS.ok()])
        if case .ok(_, let n) = await get(f) { XCTAssertEqual(n, 2) } else { XCTFail() }
        XCTAssertEqual(f.waits, [12])
    }

    func testRetryAfterOverTheCapIsNotHammered() async {
        let f = ScriptedCWMS([ScriptedCWMS.http(503, retryAfter: 600), ScriptedCWMS.ok()])
        let r = await get(f)
        guard case .exhausted(let m, let n) = r else { return XCTFail("\(r)") }
        XCTAssertEqual(n, 1); XCTAssertEqual(f.calls, 1); XCTAssertEqual(f.waits, [])
        XCTAssertTrue(m.contains("Retry-After 600 s"), m)
    }

    // MARK: permanent → not retried

    func testPermanentHTTPErrorsAreNotRetried() async {
        for s in [400, 401, 403, 404, 410] {
            let f = ScriptedCWMS([ScriptedCWMS.http(s), ScriptedCWMS.ok()])
            let r = await get(f)
            XCTAssertEqual(r, .permanent("CWMS \(label): HTTP \(s) (permanent; not retried)"))
            XCTAssertEqual(f.calls, 1); XCTAssertEqual(f.waits, [])
        }
    }

    func testSingleAttemptPolicyMeansNoRetry() async {
        var p = CWMSRetryPolicy(); p.maxAttempts = 1
        let f = ScriptedCWMS([.failure(.timeout), ScriptedCWMS.ok()])
        if case .exhausted(_, let n) = await get(f, p) { XCTAssertEqual(n, 1) } else { XCTFail() }
        XCTAssertEqual(f.calls, 1); XCTAssertEqual(f.waits, [])
    }

    // MARK: through the real feed parser

    func testFeedParsesTheRetriedPage() async {
        let now = Date()
        let f = ScriptedCWMS([.failure(.timeout), ScriptedCWMS.ok(cwmsPage(now: now))])
        let feeds = PublicLakeLevelFeeds(cwmsTransport: f.transport)
        let r = await feeds.cwms(office: "SAS", name: "Hartwell.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS", begin: now.addingTimeInterval(-192 * 3600), end: now)
        XCTAssertNil(r.error); XCTAssertEqual(r.observations.count, 48); XCTAssertEqual(r.observations.last?.ft, 649.0)
    }

    func testFeedReportsTheExhaustedReason() async {
        let now = Date()
        let f = ScriptedCWMS([.failure(.timeout)])
        let feeds = PublicLakeLevelFeeds(cwmsTransport: f.transport)
        let r = await feeds.cwms(office: "SAS", name: "Hartwell.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS", begin: now.addingTimeInterval(-192 * 3600), end: now)
        XCTAssertTrue(r.observations.isEmpty)
        XCTAssertEqual(r.error, "CWMS SAS Hartwell.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS: timed out (20 s) after 3 attempts")
    }

    // MARK: Lake Brain behaviour is unchanged around the retry

    /// CWMS through the real PublicLakeLevelFeeds (scripted transport); USGS, guide and history from the ledger test fake.
    final class SplitFeeds: LakeLevelFeeds, @unchecked Sendable {
        let cwms: PublicLakeLevelFeeds
        let rest: LedgerFeeds
        init(cwms: PublicLakeLevelFeeds, rest: LedgerFeeds) { self.cwms = cwms; self.rest = rest }
        func recent(_ ref: LevelSeriesRef, hours: Int, now: Date) async -> FeedResult {
            ref.provider == .cwms ? await cwms.recent(ref, hours: hours, now: now) : await rest.recent(ref, hours: hours, now: now)
        }
        func guide(_ source: LakeGuideSource, day: String, timeZone: TimeZone) async -> LakeGuideForDay? { await rest.guide(source, day: day, timeZone: timeZone) }
        func daily(_ source: LakeHistorySource, since: String?, now: Date, timeZone: TimeZone) async -> [DailyLevel]? { await rest.daily(source, since: since, now: now, timeZone: timeZone) }
        func archivedHourly(_ source: LakeHistorySource, days: Int, now: Date, timeZone: TimeZone) async -> [LevelObservation] { [] }
    }

    func runHartwell(_ script: [Result<CWMSResponse, CWMSTransportFailure>], now: Date) async -> (LakeBrainRunResult, LakeBrainLakeResult?, ScriptedCWMS) {
        let f = ScriptedCWMS(script)
        let feeds = SplitFeeds(cwms: PublicLakeLevelFeeds(cwmsTransport: f.transport), rest: LedgerFeeds(history: [], liveFt: 649.1))
        var o = LakeBrainRunOptions()
        o.lakeIds = ["Lake Hartwell|SC"]; o.force = true; o.ledgerEnabled = false; o.runId = "cwms-retry"
        let store = LocalDirectoryStore(directory: NSTemporaryDirectory() + "lake-cwms-retry-\(UUID().uuidString)", brainId: LakeBrainSpec.brainId)
        let r = await LakeBrainRunner.run(store: store, feeds: feeds, archive: nil, presenceArchive: nil, options: o, now: now)
        return (r, r.lakes.first { $0.lakeId == "Lake Hartwell|SC" }, f)
    }

    func testCWMSDownAfterRetriesStillFallsBackToUSGSAndReportsWarning() async {
        let now = Date()
        let (run, lake, f) = await runHartwell([.failure(.timeout)], now: now)
        XCTAssertEqual(f.calls, 3)                                                   // bounded: three attempts, no more
        let flags = lake?.state?.provenance.qualityFlags ?? []
        XCTAssertTrue(flags.contains("sourceError:cwms:SAS:Hartwell.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS"), "\(flags)")
        XCTAssertTrue(flags.contains("fallbackSource:usgs:02187010:00062"), "\(flags)")   // the USGS fallback is preserved
        XCTAssertEqual(lake?.state?.kind, .observed)
        XCTAssertEqual(run.health, "WARNING")                                       // a genuine warning is still a warning
    }

    func testTransientCWMSFailureRecoveredByRetryUsesThePrimarySource() async {
        let now = Date()
        let (run, lake, f) = await runHartwell([.failure(.timeout), ScriptedCWMS.ok(cwmsPage(now: now, lagH: 1))], now: now)
        XCTAssertEqual(f.calls, 2)
        let flags = lake?.state?.provenance.qualityFlags ?? []
        XCTAssertFalse(flags.contains { $0.hasPrefix("sourceError:cwms") || $0.hasPrefix("fallbackSource") }, "\(flags)")
        XCTAssertEqual(lake?.state?.provenance.sources?.first?.sourceId, "cwms:SAS:Hartwell.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS")
        XCTAssertEqual(run.health, "HEALTHY")
    }

    func testStaleButReachableCWMSIsStillAWarning() async {
        // Retries cannot and must not hide a feed that answers with old data (seen 2026-10-20 02:16Z: newest value 5.3 h old).
        let now = Date()
        let (run, lake, f) = await runHartwell([ScriptedCWMS.ok(cwmsPage(now: now, lagH: 6))], now: now)
        XCTAssertEqual(f.calls, 1)                                                   // a 200 is never retried
        let flags = lake?.state?.provenance.qualityFlags ?? []
        XCTAssertTrue(flags.contains { $0.hasPrefix("primarySourceStale:cwms:SAS:Hartwell") }, "\(flags)")
        XCTAssertTrue(flags.contains("fallbackSource:usgs:02187010:00062"), "\(flags)")
        XCTAssertEqual(run.health, "WARNING")
    }
}
