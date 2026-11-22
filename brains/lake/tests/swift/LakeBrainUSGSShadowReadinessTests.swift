//
//  LakeBrainUSGSShadowReadinessTests.swift
//  Lake Brain: what has to hold before LAKE_USGS_API=shadow is set on the job (review of PR #228): the v1 failure reason reaches
//  the shadow line, shadow time is bounded, `dv` keeps the unambiguous statistics, the key stays on the API host. No network.
//

import XCTest
@testable import SectorEngine
@testable import LakeBrain

final class LakeBrainUSGSShadowReadinessTests: XCTestCase {

    typealias T = LakeBrainUSGSWaterDataTests
    let utc = TimeZone(identifier: "UTC")!
    let now = ISO8601DateFormatter().date(from: "2026-11-22T12:00:00Z")!

    /// A legacy WaterServices `dv` answer with one 00003 value.
    static let legacyDV = Data(#"{"value":{"timeSeries":[{"name":"USGS:01314500:62614:00003","variable":{"noDataValue":-999999.0,"options":{"option":[{"optionCode":"00003"}]}},"values":[{"value":[{"value":"1556.20","dateTime":"2026-11-20T00:00:00.000"}]}]}]}}"#.utf8)

    func fleet(_ mode: LakeUSGSAPIMode, v1: LakeUSGSWaterDataClient, gov: LakeUSGSShadowGovernor, log: LineLog,
               legacyDelay: TimeInterval = 0) -> LakeFleetClients {
        LakeFleetClients(transport: { _, _, _ in
            if legacyDelay > 0 { try? await Task.sleep(nanoseconds: UInt64(legacyDelay * 1_000_000_000)) }
            return T.ok(Self.legacyDV)
        }, usgsMode: mode, waterData: v1, shadowLog: { log.add($0) }, shadowGovernor: gov)
    }

    func dv(_ f: LakeFleetClients) async -> [DailyLevel]? {
        await f.usgsDaily(site: "01314500", param: "62614", stat: "dv", offsetFt: 0, since: "2026-11-01", now: now, timeZone: utc)
    }

    static func meta(_ ids: [String], primary: String?) -> Data {
        let p = primary.map { "\"\($0)\"" } ?? "null"
        return Data(#"{"type":"FeatureCollection","features":[\#(ids.map { #"{"id":"\#($0)","properties":{"primary":\#(p)}}"# }.joined(separator: ","))]}"#.utf8)
    }

    // MARK: M1 the v1 failure reason reaches the shadow line

    func stageShadow(_ v1: WaterDataFake, log: LineLog) throws -> LakeUSGSStageClient {
        let rdb = try T.stageFixture("04082500_site.rdb"), iv = try T.stageFixture("04082500_iv_00065.json")
        return LakeUSGSStageClient(fetch: { url, _ in T.ok(url.contains("/nwis/site/") ? rdb : iv) }, cache: USGSSiteCache(),
                                   mode: .shadow, waterData: v1.client(), shadowLog: { log.add($0) }, governor: LakeUSGSShadowGovernor(hasKey: true))
    }

    func liveLine(continuous: @escaping @Sendable (Int) -> LakeFeedHTTP.Response?) async throws -> String {
        let loc = try T.v1("location_04082500.json")
        let fake = WaterDataFake { url, n in url.contains("/monitoring-locations/") ? T.ok(loc) : continuous(n) }
        let log = LineLog()
        let ref = LevelSeriesRef(provider: .usgsStage, capability: .directLakeGauge, station: "04082500", series: "NAVD88", cadenceMin: 60, lagMin: 60)
        let r = try await stageShadow(fake, log: log).recent(ref, hours: 24)
        XCTAssertEqual(r.observations.last?.ft ?? 0, 746.74, accuracy: 1e-9, "legacy is served")
        return try XCTUnwrap(log.lines.first { $0.contains("kind=live") })
    }

    func testLiveShadowLineCarriesTheV1FailureCodeAndReason() async throws {
        let limited = try await liveLine { _ in T.status(429) }
        XCTAssertTrue(limited.contains("reason=ogc-failed:rate-limited"), limited)
        XCTAssertTrue(limited.contains(#"ogcWhy="USGS 04082500 00065: unreachable (Water Data API: HTTP 429 after 2 retries (no USGS_API_KEY))""#), limited)
        let html = try T.v1("blackout.html")
        let page = try await liveLine { _ in T.ok(html) }
        XCTAssertTrue(page.contains("reason=ogc-failed:html-page"), page)
        let garbage = try await liveLine { _ in T.ok(Data("not json".utf8)) }
        XCTAssertTrue(garbage.contains("reason=ogc-failed:non-json"), garbage)
        let two = T.collection([
            T.feature("a", site: "04082500", param: "00065", time: "2026-11-22T10:45:00+00:00", value: #""2.83""#),
            T.feature("b", site: "04082500", param: "00065", time: "2026-11-22T10:45:00+00:00", value: #""9.10""#)])
        let several = try await liveLine { _ in T.ok(two) }
        XCTAssertTrue(several.contains("reason=ogc-failed:several-series"), several)
        let down = try await liveLine { _ in T.status(503) }
        XCTAssertTrue(down.contains("reason=ogc-failed:http "), down)
    }

    func testDailyShadowLineCarriesAmbiguousPrimaryAndUnservedStatistic() async throws {
        let body = T.collection([
            T.feature("a", site: "01314500", param: "62614", time: "2026-11-20", value: #""1556.20""#, stat: "00003"),
            T.feature("b", site: "01314500", param: "62614", time: "2026-11-20", value: #""1559.90""#, stat: "00003")])
        let meta = Self.meta(["a", "b"], primary: nil)
        let log = LineLog()
        let f = fleet(.shadow, v1: WaterDataFake { url, _ in T.ok(url.contains("/time-series-metadata/") ? meta : body) }.client(),
                      gov: LakeUSGSShadowGovernor(hasKey: true), log: log)
        let served = await dv(f)
        XCTAssertEqual(served?.first?.ft, 1556.20, "legacy is served")
        let line = try XCTUnwrap(log.lines.first)
        XCTAssertTrue(line.contains("reason=ogc-failed:ambiguous-primary"), line)
        XCTAssertTrue(line.contains("ogcDroppedStats=00003:ambiguous-primary"), line)
        XCTAssertTrue(line.contains(#"0 marked Primary; ambiguous"#), line)
    }

    func testCompareLiveNamesAFailureWithoutAReason() {
        let l = FeedResult(observations: [LevelObservation(at: now, ft: 1)], error: nil)
        let v = LakeUSGSShadow.compareLive(legacy: l, ogc: .failed("boom"))
        XCTAssertEqual(v.reason, "ogc-failed:unknown")
        XCTAssertEqual(v.detail, "boom")
    }

    // MARK: M2 shadow time is bounded

    func testShadowReadsV1ConcurrentlyWithLegacy() async throws {
        let d = try T.v1("daily_01314500_62614.json")
        let log = LineLog()
        let f = fleet(.shadow, v1: WaterDataFake { _, _ in T.ok(d) }.client(delay: 0.6), gov: LakeUSGSShadowGovernor(hasKey: true), log: log,
                      legacyDelay: 0.6)
        let start = Date()
        _ = await dv(f)
        XCTAssertLessThan(Date().timeIntervalSince(start), 1.1, "one 0.6 s read each, side by side, not one after the other")
        XCTAssertEqual(log.lines.count, 1)
        XCTAssertFalse(log.lines[0].contains("ogc-timeout"), log.lines[0])
    }

    func testAMissedDeadlineServesLegacyAndLogsATimeout() async throws {
        let d = try T.v1("daily_01314500_62614.json")
        let log = LineLog()
        let gov = LakeUSGSShadowGovernor(perReadSeconds: 0.2, budgetSeconds: 60, hasKey: true)
        let f = fleet(.shadow, v1: WaterDataFake { _, _ in T.ok(d) }.client(delay: 5), gov: gov, log: log)
        let start = Date()
        let served = await dv(f)
        XCTAssertLessThan(Date().timeIntervalSince(start), 2, "never waits for v1 past the per-read deadline")
        XCTAssertEqual(served?.first?.ft, 1556.20)
        XCTAssertTrue(log.lines.first?.contains("kind=daily verdict=disagree reason=ogc-timeout") ?? false, "\(log.lines)")
        XCTAssertGreaterThan(gov.waitedSeconds, 0.1)
    }

    func testTheRunBudgetTurnsShadowOffAndSaysSoOnce() async throws {
        let d = try T.v1("daily_01314500_62614.json")
        let log = LineLog()
        let gov = LakeUSGSShadowGovernor(perReadSeconds: 0.1, budgetSeconds: 0.15, hasKey: true)
        let fake = WaterDataFake { _, _ in T.ok(d) }
        let f = fleet(.shadow, v1: fake.client(delay: 5), gov: gov, log: log)
        for _ in 0..<4 { _ = await dv(f) }
        XCTAssertEqual(fake.urls.count, 2, "no v1 read once the budget is spent")
        XCTAssertEqual(log.lines.filter { $0.contains("reason=ogc-timeout") }.count, 2)
        XCTAssertEqual(log.lines.filter { $0.contains("shadow-off reason=budget-exhausted") }.count, 1, "\(log.lines)")
        XCTAssertEqual(log.lines.count, 3)
    }

    func testRepeated429sWithoutAKeyTurnShadowOffOnce() async throws {
        let log = LineLog()
        let gov = LakeUSGSShadowGovernor(hasKey: false, rateLimitThreshold: 3)
        let fake = WaterDataFake { _, _ in T.status(429) }
        let f = fleet(.shadow, v1: fake.client(governor: gov), gov: gov, log: log)
        for _ in 0..<3 { _ = await dv(f) }
        XCTAssertEqual(fake.urls.count, 3, "the first read: one request and two retries; then shadow is off")
        XCTAssertTrue(log.lines[0].contains("reason=ogc-failed:rate-limited"), log.lines[0])
        XCTAssertEqual(log.lines.filter { $0.contains("shadow-off reason=rate-limited-no-key rateLimited=3 apiKey=unset") }.count, 1, "\(log.lines)")
        XCTAssertEqual(log.lines.count, 2)

        let keyed = LakeUSGSShadowGovernor(hasKey: true, rateLimitThreshold: 3)
        let kf = WaterDataFake { _, _ in T.status(429) }
        let k = fleet(.shadow, v1: kf.client(apiKey: "k", governor: keyed), gov: keyed, log: LineLog())
        for _ in 0..<2 { _ = await dv(k) }
        XCTAssertEqual(kf.urls.count, 6, "with a key, 429s do not turn shadow off")
    }

    func testGovernorReadsItsBoundsFromTheEnvironment() {
        let g = LakeUSGSShadowGovernor.fromEnvironment(["LAKE_USGS_SHADOW_READ_SECONDS": "7", "LAKE_USGS_SHADOW_BUDGET_SECONDS": "90", "USGS_API_KEY": "k"])
        XCTAssertEqual(g.perReadSeconds, 7); XCTAssertEqual(g.budgetSeconds, 90); XCTAssertTrue(g.hasKey)
        let d = LakeUSGSShadowGovernor.fromEnvironment(["LAKE_USGS_SHADOW_READ_SECONDS": "x"])
        XCTAssertEqual(d.perReadSeconds, 20); XCTAssertEqual(d.budgetSeconds, 300); XCTAssertFalse(d.hasKey)
    }

    func testPendingReturnsAFinishedValueEvenWithNoTimeLeft() async {
        let p = LakeUSGSPending<Int>()
        p.fulfil(4)
        let v = await p.wait(seconds: 0)
        XCTAssertEqual(v, 4)
        let late = LakeUSGSPending<Int>()
        let none = await late.wait(seconds: 0.05)
        XCTAssertNil(none)
        late.fulfil(5)
    }

    // MARK: M3 dv keeps the unambiguous statistics

    func daily(_ features: [String], ambiguous: [String]) async -> LakeUSGSV1Daily {
        let body = T.collection(features), meta = Self.meta(ambiguous, primary: nil)
        return await WaterDataFake { url, _ in T.ok(url.contains("/time-series-metadata/") ? meta : body) }.client()
            .daily(site: "01314500", param: "62614", stat: "dv", offsetFt: 0, since: "2026-11-01", now: now, timeZone: utc, src: "s", singleSeries: false)
    }

    func testAnAmbiguousStatisticIsDroppedAndTheOthersKept() async {
        let f = { (ts: String, d: String, v: String, st: String) in
            T.feature(ts, site: "01314500", param: "62614", time: d, value: "\"\(v)\"", stat: st)
        }
        // 00003 ambiguous (two series, none Primary): 30800 is kept.
        let a = await daily([f("a", "2026-11-20", "1.0", "00003"), f("b", "2026-11-20", "9.0", "00003"), f("c", "2026-11-20", "2.0", "30800"),
                             f("c", "2026-11-21", "2.1", "30800")], ambiguous: ["a", "b"])
        XCTAssertEqual(a.levels?.map(\.ft), [2.0, 2.1])
        XCTAssertEqual(a.droppedStatistics, ["00003": "ambiguous-primary"])
        XCTAssertNil(a.failure)
        // 00003 unambiguous, 30800 ambiguous: 00003 is kept, 30800's dates are not filled from an ambiguous statistic.
        let b = await daily([f("a", "2026-11-20", "1.0", "00003"), f("c", "2026-11-20", "2.0", "30800"), f("d", "2026-11-21", "2.1", "30800")],
                            ambiguous: ["c", "d"])
        XCTAssertEqual(b.levels?.map(\.date), ["2026-11-20"])
        XCTAssertEqual(b.levels?.first?.ft, 1.0)
        XCTAssertEqual(b.droppedStatistics, ["30800": "ambiguous-primary"])
        // Every statistic ambiguous: refused, with the reason.
        let c = await daily([f("a", "2026-11-20", "1.0", "00003"), f("b", "2026-11-20", "9.0", "00003")], ambiguous: ["a", "b"])
        XCTAssertNil(c.levels)
        XCTAssertEqual(c.failure?.code, .ambiguousPrimary)
    }

    /// Only an ambiguous statistic is dropped: a failed or unreadable metadata read refuses the whole `dv` read, with its code.
    func testADvMetadataFailureRefusesTheReadInsteadOfDroppingTheStatistic() async {
        let body = T.collection([
            T.feature("a", site: "01314500", param: "62614", time: "2026-11-20", value: #""1.0""#, stat: "00003"),
            T.feature("b", site: "01314500", param: "62614", time: "2026-11-20", value: #""9.0""#, stat: "00003"),
            T.feature("c", site: "01314500", param: "62614", time: "2026-11-21", value: #""2.0""#, stat: "30800")])
        func read(_ metadata: LakeFeedHTTP.Response?) async -> LakeUSGSV1Daily {
            await WaterDataFake { url, _ in url.contains("/time-series-metadata/") ? metadata : T.ok(body) }.client()
                .daily(site: "01314500", param: "62614", stat: "dv", offsetFt: 0, since: "2026-11-01", now: now, timeZone: utc, src: "s", singleSeries: false)
        }
        for (metadata, inner) in [(T.status(429), "rate-limited"), (T.status(503), "http"), (nil, "unreachable")] as [(LakeFeedHTTP.Response?, String)] {
            let r = await read(metadata)
            XCTAssertNil(r.levels, "\(inner): refused, not answered with 30800 alone")
            XCTAssertEqual(r.failure?.code, .metadataUnreadable, inner)
            XCTAssertTrue(r.failure?.why.contains("(\(inner):") ?? false, r.failure?.why ?? "")
            XCTAssertTrue(r.droppedStatistics.isEmpty, inner)
        }
        let garbage = await read(T.ok(Data("not json".utf8)))
        XCTAssertNil(garbage.levels)
        XCTAssertEqual(garbage.failure?.code, .metadataUnreadable)
        XCTAssertTrue(garbage.failure?.why.contains("(non-json:") ?? false, garbage.failure?.why ?? "")
        let page = await read(T.ok(Data("<!DOCTYPE html><html><body>notice</body></html>".utf8)))
        XCTAssertEqual(page.failure?.code, .metadataUnreadable)
        XCTAssertTrue(page.failure?.why.contains("(html-page:") ?? false, page.failure?.why ?? "")
        // Ambiguous (metadata read, none Primary): still dropped, 30800 kept.
        let ambiguous = await read(T.ok(Self.meta(["a", "b"], primary: nil)))
        XCTAssertEqual(ambiguous.levels?.map(\.ft), [2.0])
        XCTAssertEqual(ambiguous.droppedStatistics, ["00003": "ambiguous-primary"])
        XCTAssertTrue(LakeUSGSWaterDataClient.droppable(LakeUSGSReadFailure(.severalSeries, "x")))
        XCTAssertFalse(LakeUSGSWaterDataClient.droppable(LakeUSGSReadFailure(.rateLimited, "x")))

        // In shadow the refusal reaches the line with its code; legacy is served.
        let log = LineLog()
        let f = fleet(.shadow, v1: WaterDataFake { url, _ in url.contains("/time-series-metadata/") ? T.status(503) : T.ok(body) }.client(),
                      gov: LakeUSGSShadowGovernor(hasKey: true), log: log)
        let served = await dv(f)
        XCTAssertEqual(served?.first?.ft, 1556.20)
        XCTAssertTrue(log.lines.first?.contains("kind=daily verdict=disagree reason=ogc-failed:metadata-unreadable") ?? false, "\(log.lines)")
    }

    // MARK: the legacy stage read never waits on the v1 site record

    func slowSiteStage(v1Delay: TimeInterval, perRead: TimeInterval = 20, legacy: URLRecorder, log: LineLog) throws -> LakeUSGSStageClient {
        let rdb = try T.stageFixture("04082500_site.rdb"), iv = try T.stageFixture("04082500_iv_00065.json")
        let loc = try T.v1("location_04082500.json")
        let v1 = WaterDataFake { url, _ in url.contains("/monitoring-locations/") ? T.ok(loc) : T.status(503) }
        return LakeUSGSStageClient(fetch: { url, _ in legacy.add(url); return T.ok(url.contains("/nwis/site/") ? rdb : iv) },
                                   cache: USGSSiteCache(), mode: .shadow, waterData: v1.client(delay: v1Delay), shadowLog: { log.add($0) },
                                   governor: LakeUSGSShadowGovernor(perReadSeconds: perRead, budgetSeconds: 300, hasKey: true))
    }

    func testTheLegacyStageReadDoesNotWaitOnASlowV1SiteRead() async throws {
        let ref = LevelSeriesRef(provider: .usgsStage, capability: .directLakeGauge, station: "04082500", series: "NAVD88", cadenceMin: 60, lagMin: 60)
        let rec = URLRecorder(), log = LineLog()
        let shadow = try slowSiteStage(v1Delay: 1.5, legacy: rec, log: log)
        let start = Date()
        let r = await shadow.recentLegacy(ref, hours: 24)
        XCTAssertLessThan(Date().timeIntervalSince(start), 0.5, "the legacy iv request goes out without waiting for monitoring-locations")
        XCTAssertEqual(r.observations.last?.ft ?? 0, 746.74, accuracy: 1e-9)
        XCTAssertFalse(log.lines.contains { $0.contains("kind=site") }, "the site comparison has not answered yet")

        // The same legacy requests as the legacy switch.
        let legacyRec = URLRecorder()
        let rdb = try T.stageFixture("04082500_site.rdb"), iv = try T.stageFixture("04082500_iv_00065.json")
        let legacy = LakeUSGSStageClient.legacy(fetch: { url, _ in
            legacyRec.add(url)
            return T.ok(url.contains("/nwis/site/") ? rdb : iv)
        }, cache: USGSSiteCache())
        let l = await legacy.recentLegacy(ref, hours: 24)
        XCTAssertEqual(r.observations, l.observations)
        XCTAssertEqual(rec.urls, legacyRec.urls)

        // The history path: the altitude does not wait either.
        let hist = URLRecorder()
        let fleet = LakeFleetClients(transport: { url, _, _ in hist.add(url); return T.ok(Self.legacyDV) }, usgsMode: .legacy,
                                     waterData: .unreachable(), shadowLog: { _ in }, shadowGovernor: LakeUSGSShadowGovernor(hasKey: true))
        let historyStart = Date()
        _ = try await slowSiteStage(v1Delay: 1.5, legacy: URLRecorder(), log: LineLog())
            .daily(site: "04082500", datum: "NAVD88", stat: "dv", since: "2026-11-01", now: now, timeZone: utc, fleet: fleet)
        XCTAssertLessThan(Date().timeIntervalSince(historyStart), 0.5)
        XCTAssertFalse(hist.urls.isEmpty, "the dv request was sent")

        // The comparison still lands, as its own line, once v1 answers.
        let site = await log.waitFor(5) { $0.contains("kind=site") }
        XCTAssertTrue(site?.contains("kind=site verdict=agree") ?? false, "\(log.lines)")
        // The comparison read the legacy record from the run's cache: still no legacy request beyond the legacy switch's.
        XCTAssertEqual(rec.urls, legacyRec.urls)
    }

    func testASiteComparisonPastItsDeadlineLogsATimeout() async throws {
        let ref = LevelSeriesRef(provider: .usgsStage, capability: .directLakeGauge, station: "04082500", series: "NAVD88", cadenceMin: 60, lagMin: 60)
        let log = LineLog()
        let start = Date()
        let r = try await slowSiteStage(v1Delay: 5, perRead: 0.2, legacy: URLRecorder(), log: log).recentLegacy(ref, hours: 24)
        XCTAssertLessThan(Date().timeIntervalSince(start), 0.5)
        XCTAssertNil(r.error)
        let site = await log.waitFor(3) { $0.contains("kind=site") }
        XCTAssertTrue(site?.contains("kind=site verdict=disagree reason=ogc-timeout legacyN=1") ?? false, "\(log.lines)")
    }

    // MARK: the job drains detached site comparisons before it exits

    func testTheDrainWaitsForAPendingSiteComparisonAndLogsOneSummary() async throws {
        let ref = LevelSeriesRef(provider: .usgsStage, capability: .directLakeGauge, station: "04082500", series: "NAVD88", cadenceMin: 60, lagMin: 60)
        let log = LineLog(), drained = LineLog()
        let stage = try slowSiteStage(v1Delay: 0.5, legacy: URLRecorder(), log: log)
        _ = await stage.recentLegacy(ref, hours: 24)
        XCTAssertEqual(stage.governor.detachedShadows.pendingCount, 1)
        XCTAssertFalse(log.lines.contains { $0.contains("kind=site") })
        await LakeUSGSShadowDrain.beforeExit(mode: .shadow, governor: stage.governor, log: { drained.add($0) })
        XCTAssertTrue(log.lines.contains { $0.contains("kind=site verdict=agree") }, "the comparison was logged before the drain returned: \(log.lines)")
        XCTAssertEqual(drained.lines.count, 1)
        XCTAssertTrue(drained.lines[0].hasPrefix("[usgs-shadow] detached kind=site completed=1 timedOut=0 dropped=0 drainedMs="), drained.lines[0])
    }

    func testTheDrainIsBoundedByTheDeadlineAndCountsTimeoutsAndDrops() async throws {
        let ref = LevelSeriesRef(provider: .usgsStage, capability: .directLakeGauge, station: "04082500", series: "NAVD88", cadenceMin: 60, lagMin: 60)
        let log = LineLog(), drained = LineLog()
        let stage = try slowSiteStage(v1Delay: 5, perRead: 0.3, legacy: URLRecorder(), log: log)
        _ = await stage.recentLegacy(ref, hours: 24)
        // A comparison whose v1 answers but whose compare never finishes in time: dropped, not waited for past deadline + grace.
        LakeUSGSRouting.detached(governor: stage.governor, v1: { () async -> Int in 1 }, compare: { (_: Int?) async -> String in
            try? await Task.sleep(nanoseconds: 10_000_000_000)
            return "late"
        }, log: { log.add($0) })
        let start = Date()
        await LakeUSGSShadowDrain.beforeExit(mode: .shadow, governor: stage.governor, grace: 0.3, log: { drained.add($0) })
        XCTAssertLessThan(Date().timeIntervalSince(start), 2, "bounded by the 0.3 s per-read deadline plus grace, not the 5 s v1 read")
        XCTAssertTrue(log.lines.contains { $0.contains("kind=site verdict=disagree reason=ogc-timeout") }, "\(log.lines)")
        XCTAssertTrue(drained.lines.first?.hasPrefix("[usgs-shadow] detached kind=site completed=0 timedOut=1 dropped=1 ") ?? false, "\(drained.lines)")
    }

    func testLegacyRegistersNothingAndTheDrainDoesNotDelayExit() async throws {
        let ref = LevelSeriesRef(provider: .usgsStage, capability: .directLakeGauge, station: "04082500", series: "NAVD88", cadenceMin: 60, lagMin: 60)
        let rdb = try T.stageFixture("04082500_site.rdb"), iv = try T.stageFixture("04082500_iv_00065.json")
        let v1 = WaterDataFake { _, _ in T.status(503) }
        let gov = LakeUSGSShadowGovernor(perReadSeconds: 20, budgetSeconds: 300, hasKey: true)
        let log = LineLog(), drained = LineLog()
        let legacy = LakeUSGSStageClient(fetch: { url, _ in T.ok(url.contains("/nwis/site/") ? rdb : iv) }, cache: USGSSiteCache(),
                                         mode: .legacy, waterData: v1.client(delay: 5), shadowLog: { log.add($0) }, governor: gov)
        let r = await legacy.recent(ref, hours: 24)
        XCTAssertNil(r.error)
        XCTAssertEqual(gov.detachedShadows.registeredCount, 0, "legacy starts no detached comparison")
        XCTAssertTrue(v1.urls.isEmpty)
        XCTAssertTrue(log.lines.isEmpty)
        let start = Date()
        await LakeUSGSShadowDrain.beforeExit(mode: .legacy, governor: gov, log: { drained.add($0) })
        XCTAssertLessThan(Date().timeIntervalSince(start), 0.1)
        XCTAssertTrue(drained.lines.isEmpty, "legacy logs no summary")
        // Even with something registered, legacy and v1 never wait.
        _ = gov.detachedShadows.register(deadline: Date().addingTimeInterval(10))
        let again = Date()
        await LakeUSGSShadowDrain.beforeExit(mode: .legacy, governor: gov, log: { drained.add($0) })
        await LakeUSGSShadowDrain.beforeExit(mode: .v1, governor: gov, log: { drained.add($0) })
        XCTAssertLessThan(Date().timeIntervalSince(again), 0.1)
        XCTAssertTrue(drained.lines.isEmpty)
    }

    // MARK: the site cache honours cancellation

    func testACancelledSiteReadCancelsTheFetchAndIsNotCached() async {
        final class Seen: @unchecked Sendable {
            let lock = NSLock(); var cancelled = 0, calls = 0
            func call() { lock.withLock { calls += 1 } }
            func cancel() { lock.withLock { cancelled += 1 } }
            var counts: (calls: Int, cancelled: Int) { lock.withLock { (calls, cancelled) } }
        }
        let seen = Seen()
        let datum = USGSSiteDatum(site: "04082500", name: nil, siteType: "LK", altitudeFt: 743.91, accuracyFt: nil, datum: "NAVD88")
        let slow: @Sendable (String) async -> USGSSiteDatumResult = { s in
            seen.call()
            do { try await Task.sleep(nanoseconds: 5_000_000_000) } catch { seen.cancel(); return .refused("USGS \(s): cancelled") }
            return .ok(datum)
        }
        let cache = USGSSiteCache()
        let start = Date()
        let read = Task { await cache.site("04082500", fetch: slow) }
        try? await Task.sleep(nanoseconds: 100_000_000)
        read.cancel()
        _ = await read.value
        XCTAssertLessThan(Date().timeIntervalSince(start), 2, "the fetch stopped when its only caller was cancelled")
        XCTAssertEqual(seen.counts.cancelled, 1)
        // Not cached: the next caller fetches again.
        let next = await cache.site("04082500", fetch: { _ in .ok(datum) })
        XCTAssertEqual(next, .ok(datum))

        // A cancelled joiner does not cancel the fetch another caller is waiting on.
        let shared = USGSSiteCache()
        let quick: @Sendable (String) async -> USGSSiteDatumResult = { _ in
            seen.call()
            do { try await Task.sleep(nanoseconds: 300_000_000) } catch { seen.cancel(); return .refused("cancelled") }
            return .ok(datum)
        }
        let before = seen.counts
        let keeper = Task { await shared.site("04082500", fetch: quick) }
        try? await Task.sleep(nanoseconds: 50_000_000)
        let quitter = Task { await shared.site("04082500", fetch: quick) }
        try? await Task.sleep(nanoseconds: 50_000_000)
        quitter.cancel()
        let kept = await keeper.value
        _ = await quitter.value
        XCTAssertEqual(kept, .ok(datum))
        XCTAssertEqual(seen.counts.calls - before.calls, 1, "the second caller joined the first fetch")
        XCTAssertEqual(seen.counts.cancelled, before.cancelled, "the shared fetch was not cancelled")
    }

    // MARK: LOW: legacy's fallback statistics (D3)

    func testDvUsesOtherStatisticsAfterTheFiveLikeLegacy() async {
        let f = { (ts: String, d: String, v: String, st: String) in
            T.feature(ts, site: "01314500", param: "62614", time: d, value: "\"\(v)\"", stat: st)
        }
        let r = await daily([f("a", "2026-11-20", "1.0", "00003"), f("e", "2026-11-20", "8.0", "00008"), f("e", "2026-11-21", "8.1", "00008")],
                            ambiguous: [])
        XCTAssertEqual(r.levels?.map(\.ft), [1.0, 8.1], "00003 first; 00008 only where none of the five has the date")
    }

    // MARK: LOW: the key stays on the API host

    func testTheKeyIsSentOnlyToTheWaterDataAPIHost() async {
        XCTAssertTrue(LakeUSGSWaterDataClient.sendsKey(to: "https://api.waterdata.usgs.gov/ogcapi/v1/collections/daily/items?f=json"))
        XCTAssertFalse(LakeUSGSWaterDataClient.sendsKey(to: "http://api.waterdata.usgs.gov/ogcapi/v1/collections"))
        XCTAssertFalse(LakeUSGSWaterDataClient.sendsKey(to: "https://api.waterdata.usgs.gov.example.com/x"))
        XCTAssertFalse(LakeUSGSWaterDataClient.sendsKey(to: "https://waterservices.usgs.gov/nwis/iv/"))

        let page = T.collection([T.feature("s", site: "03351700", param: "62614", time: "2026-11-22T10:00:00Z", value: #""745.1""#)])
        // A `next` link to another host: followed without the key.
        let first = T.collection([T.feature("s", site: "03351700", param: "62614", time: "2026-11-22T09:00:00Z", value: #""745.0""#)],
                                 next: "https://mirror.example.org/continuous?page=2")
        let nextFake = WaterDataFake { url, _ in T.ok(url.contains("mirror.example.org") ? page : first) }
        let n = await nextFake.client(apiKey: "k-1").recentLevel(site: "03351700", parameter: "62614", hours: 2)
        XCTAssertEqual(n.result.observations.count, 2)
        XCTAssertEqual(nextFake.headers, [["X-Api-Key": "k-1"], [:]])
        // A redirect to another host: followed without the key. A redirect on the same host keeps it.
        let away = WaterDataFake { url, _ in url.contains("elsewhere.example") ? T.ok(page)
            : LakeFeedHTTP.Response(status: 302, body: Data(), location: "https://elsewhere.example/x") }
        _ = await away.client(apiKey: "k-1").recentLevel(site: "03351700", parameter: "62614", hours: 2)
        XCTAssertEqual(away.headers, [["X-Api-Key": "k-1"], [:]])
        let home = WaterDataFake { url, _ in url.contains("moved=1") ? T.ok(page)
            : LakeFeedHTTP.Response(status: 307, body: Data(), location: "/ogcapi/v1/collections/continuous/items?f=json&moved=1") }
        _ = await home.client(apiKey: "k-1").recentLevel(site: "03351700", parameter: "62614", hours: 2)
        XCTAssertEqual(home.headers, [["X-Api-Key": "k-1"], ["X-Api-Key": "k-1"]])
        XCTAssertTrue(home.urls[1].hasPrefix("https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/items?f=json&moved=1"), home.urls[1])
        // A redirect without a Location is a failure with its reason.
        let broken = await WaterDataFake { _, _ in T.status(302) }.client().recentLevel(site: "03351700", parameter: "62614", hours: 2)
        XCTAssertEqual(broken.failure?.code, .redirect)
    }

    // MARK: LOW: the shadow line cannot be broken by a value

    func testShadowLineEscapesDatumAndReasonText() {
        let a = USGSSiteDatum(site: "04082500", name: nil, siteType: "LK", altitudeFt: 743.91, accuracyFt: nil, datum: "NAVD88")
        var b = a; b.datum = #"NAV D88" verdict=agree"#
        let line = LakeUSGSShadow.line(site: "04082500", param: "00065", kind: "site", LakeUSGSShadow.compareSite(legacy: .ok(a), ogc: .ok(b)))
        XCTAssertTrue(line.hasPrefix("[usgs-shadow] site=04082500 param=00065 kind=site verdict=disagree reason="), line)
        let unquoted = line.components(separatedBy: #" ogcWhy=""#)[0]
        XCTAssertEqual(unquoted.components(separatedBy: " verdict=").count, 2, "a value cannot add an unquoted field: \(line)")
        XCTAssertTrue(line.contains("reason=datum-NAVD88-vs-NAV_D88__VERDICT_AGREE"), line)
        XCTAssertTrue(line.contains(#"ogcWhy="legacy datum NAVD88, v1 datum NAV D88\" verdict=agree""#), line)
        XCTAssertEqual(LakeUSGSShadow.quoted("a\nb\\c"), #""a\nb\\c""#)
        XCTAssertEqual(LakeUSGSShadow.token(""), "-")
    }
}
