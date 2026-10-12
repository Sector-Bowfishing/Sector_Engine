//
//  LakeBrainTests.swift
//  Lake Brain: synthetic lakes, series and species only (no research data).
//

import XCTest
@testable import SectorEngine

final class LakeBrainTests: XCTestCase {

    let utc = TimeZone(identifier: "UTC")!
    let chicago = TimeZone(identifier: "America/Chicago")!

    func iso(_ s: String) -> Date { ISO8601DateFormatter().date(from: s)! }

    // MARK: TVA parsing

    func testTVAMidnightRowIsNextDayStart() {
        let at = PublicLakeLevelFeeds.tvaTime(day: "10/10/2026", time: "Midnight CDT")
        XCTAssertEqual(at, iso("2026-10-11T05:00:00Z"))
        XCTAssertEqual(PublicLakeLevelFeeds.tvaTime(day: "10/11/2026", time: "1 AM CDT"), iso("2026-10-11T06:00:00Z"))
    }

    func testTVAObservedOrdersMidnightBetweenElevenPMAndOneAM() {
        let rows = """
        [{"Day":"10/10/2026","Time":"11 PM CDT","ReservoirElevation":"594.02"},
         {"Day":"10/10/2026","Time":"Midnight CDT","ReservoirElevation":"594.03"},
         {"Day":"10/11/2026","Time":"1 AM CDT","ReservoirElevation":"594.05"}]
        """
        let obs = PublicLakeLevelFeeds.parseTVAObserved(Data(rows.utf8))
        XCTAssertEqual(obs.map(\.ft), [594.02, 594.03, 594.05])
    }

    func testTVAGuideZeroIsMissingAndYearLabelIgnored() {
        let json = """
        {"items":[{"Day":"10/11/2025","GuideCurve":594.2,"BtmOpZone":593.6,"TopOpZone":594.6,"TopOfGates":595.4,"CurYrElev":593.8,"PrevYrElev":594.1},
                  {"Day":"10/12/2025","GuideCurve":594.19,"BtmOpZone":593.6,"TopOpZone":594.6,"TopOfGates":595.4,"CurYrElev":593.82,"PrevYrElev":594.13},
                  {"Day":"10/13/2025","GuideCurve":594.18,"BtmOpZone":593.6,"TopOpZone":594.6,"TopOfGates":595.4,"CurYrElev":0,"PrevYrElev":594.12}]}
        """
        let rows = PublicLakeLevelFeeds.parseTVAGuide(Data(json.utf8))!
        XCTAssertNil(rows[2].curYrElev)
        let daily = PublicLakeLevelFeeds.tvaDaily(rows: rows, locationId: "TEST1", now: iso("2026-10-12T18:00:00Z"), timeZone: chicago)
        XCTAssertEqual(daily.first { $0.date == "2026-10-12" }?.ft, 593.82)
        XCTAssertEqual(daily.first { $0.date == "2025-10-13" }?.ft, 594.12)
        XCTAssertNil(daily.first { $0.date == "2026-10-13" }, "future days of the current year are absent")
    }

    // MARK: Baseline

    /// Synthetic seasonal lake: 600 ft ± 3 ft annual cycle, small year offsets.
    func syntheticDaily(years: ClosedRange<Int>, through: String? = nil) -> [DailyLevel] {
        var out: [DailyLevel] = []
        var d = LakeLevelCalendar.date(year: years.lowerBound, month: 1, day: 1)
        let end = LakeLevelCalendar.date(year: years.upperBound, month: 12, day: 31)
        while d <= end {
            let day = LakeLevelCalendar.dayString(d, timeZone: utc)
            if let t = through, day > t { break }
            let doy = Double(LakeLevelCalendar.doy365(day)!)
            let y = Double(Int(day.prefix(4))! % 7) * 0.1
            out.append(DailyLevel(date: day, ft: 600 + 3 * sin(doy / 365 * 2 * .pi) + y, sourceId: "test"))
            d = d.addingTimeInterval(86_400)
        }
        return out
    }

    func testBaselineStatusByCompleteYears() {
        XCTAssertEqual(LakeBaselineBuilder.build(lakeId: "T|ST", daily: syntheticDaily(years: 2018...2025), today: "2026-06-01").status, .sufficient)
        XCTAssertEqual(LakeBaselineBuilder.build(lakeId: "T|ST", daily: syntheticDaily(years: 2023...2025), today: "2026-06-01").status, .limited)
        XCTAssertEqual(LakeBaselineBuilder.build(lakeId: "T|ST", daily: syntheticDaily(years: 2025...2026, through: "2026-05-31"), today: "2026-06-01").status, .insufficient)
        XCTAssertEqual(LakeBaselineBuilder.build(lakeId: "T|ST", daily: [], today: "2026-06-01").status, .none)
    }

    func testBaselineKeepsOnlyRecentThirtyCompleteYears() {
        let b = LakeBaselineBuilder.build(lakeId: "T|ST", daily: syntheticDaily(years: 1980...2025), today: "2026-06-01")
        XCTAssertEqual(b.basisYears.count, 30)
        XCTAssertEqual(b.basisYears.first, 1996)
        XCTAssertEqual(b.days.count, 365)
    }

    func testPercentileGridRoundTrip() {
        let q = LakeBaselineBuilder.grid((1...101).map(Double.init))
        XCTAssertEqual(LakeBaselineBuilder.percentile(of: 51, grid: q), 50, accuracy: 0.01)
        XCTAssertEqual(LakeBaselineBuilder.percentile(of: 0, grid: q), 0)
        XCTAssertEqual(LakeBaselineBuilder.percentile(of: 500, grid: q), 100)
    }

    // MARK: Classifier

    func zone(_ b: Double, _ t: Double, floodBottom: Double? = nil) -> LakeGuideForDay {
        LakeGuideForDay(guideFt: t, zone: LakeOperatingZone(bottomFt: b, topFt: t, bottomLabel: "bottom", topLabel: "top", source: "test"),
                        levels: [], topOfGatesFt: nil, floodPoolBottomFt: floodBottom, source: "test")
    }

    func testLevelStateOperatorZoneFirst() {
        XCTAssertEqual(LakeLevelClassifier.levelState(current: 593.0, guide: zone(593.6, 594.6)), .belowZone)
        XCTAssertEqual(LakeLevelClassifier.levelState(current: 594.0, guide: zone(593.6, 594.6)), .inZone)
        XCTAssertEqual(LakeLevelClassifier.levelState(current: 594.7, guide: zone(593.6, 594.6)), .aboveZone)
        XCTAssertEqual(LakeLevelClassifier.levelState(current: 661, guide: zone(656, 660, floodBottom: 660)), .floodPool)
        XCTAssertEqual(LakeLevelClassifier.levelState(current: 600, guide: nil), .unknown)
        XCTAssertEqual(LakeLevelClassifier.floodPoolState(current: 600, guide: zone(593.6, 594.6)), .unknown)
        XCTAssertEqual(LakeLevelClassifier.floodPoolState(current: 659, guide: zone(656, 660, floodBottom: 660)), .normal)
    }

    func testTrendRules() {
        let rates = LakeBaselineDay(doy: 1, n: 0, levelQ: nil, rateN: 100,
                                    rateQ: LakeBaselineBuilder.grid((0..<100).map { Double($0) / 200 }))  // 0 … 0.495
        XCTAssertEqual(LakeLevelClassifier.trend(delta24h: 0.05, day: rates).0, .stable)
        XCTAssertEqual(LakeLevelClassifier.trend(delta24h: 0.30, day: rates).0, .rising)
        XCTAssertEqual(LakeLevelClassifier.trend(delta24h: -0.49, day: rates).0, .fallingRapidly)
        XCTAssertEqual(LakeLevelClassifier.trend(delta24h: 0.08, day: nil).0, .stable, "0.10 ft floor without a baseline")
        XCTAssertEqual(LakeLevelClassifier.trend(delta24h: 0.9, day: nil).0, .rising, "no rapid without a rate baseline")
        XCTAssertEqual(LakeLevelClassifier.trend(delta24h: nil, day: rates).0, .unknown)
    }

    func testHistoricalCutPoints() {
        let b = LakeBaselineBuilder.build(lakeId: "T|ST", daily: syntheticDaily(years: 2010...2025), today: "2026-06-01")
        let q = b.day(152)!.levelQ!
        let p10 = LakeBaselineBuilder.at(10, q)!, p02 = LakeBaselineBuilder.at(2, q)!, p50 = LakeBaselineBuilder.at(50, q)!
        XCTAssertEqual(LakeLevelClassifier.historical(current: p50, baseline: b, doy: 152).0, .normal)
        XCTAssertEqual(LakeLevelClassifier.historical(current: (p10 + p02) / 2, baseline: b, doy: 152).0, .unusual)
        XCTAssertEqual(LakeLevelClassifier.historical(current: p02 - 1, baseline: b, doy: 152).0, .veryUnusual)
        let limited = LakeBaselineBuilder.build(lakeId: "T|ST", daily: syntheticDaily(years: 2023...2025), today: "2026-06-01")
        XCTAssertEqual(LakeLevelClassifier.historical(current: p50, baseline: limited, doy: 152).0, .insufficientHistory)
    }

    func ref(_ cap: LevelSourceCapability, _ station: String) -> LevelSeriesRef {
        LevelSeriesRef(provider: .usgs, capability: cap, station: station, series: "00062", cadenceMin: 60, lagMin: 60)
    }

    func binding(_ live: [LevelSeriesRef], cap: LevelSourceCapability = .directOperatorPool) -> LakeSourceBinding {
        LakeSourceBinding(lakeId: "Test|ST", status: .reviewed, capability: cap, live: live, history: [], guide: nil, datum: nil,
                          timeZone: "UTC", damName: nil, riverSystem: nil, topOfGatesFt: nil, hydropower: nil, floodControl: nil,
                          operatorName: nil, reviewedAt: nil, note: nil)
    }

    func hourly(_ end: Date, hours: Int, start: Double, step: Double) -> [LevelObservation] {
        (0...hours).map { LevelObservation(at: end.addingTimeInterval(-Double(hours - $0) * 3600), ft: start + Double($0) * step) }
    }

    func inputs(_ b: LakeSourceBinding, live: [(LevelSeriesRef, [LevelObservation])], guide: LakeGuideForDay? = nil,
                baseline: LakeLevelBaseline? = nil, now: Date) -> LakeLevelInputs {
        LakeLevelInputs(lakeId: "Test|ST", binding: b, capabilityIfUnbound: .noSource, fullPoolFt: 600, poolBasisIsFullPool: true,
                        poolConfidenceLow: false, live: live.map { ($0.0, $0.1, nil) }, archivedHourly: [], guide: guide,
                        baseline: baseline, now: now, processingVersion: "test")
    }

    func testProxyGetsTrendOnly() {
        let now = iso("2026-06-01T12:30:00Z")
        let r = ref(.nearbyGaugeProxy, "P1")
        let s = LakeLevelClassifier.evaluate(inputs(binding([r], cap: .nearbyGaugeProxy), live: [(r, hourly(iso("2026-06-01T12:00:00Z"), hours: 30, start: 3, step: 0.02))],
                                                guide: zone(599, 601), baseline: LakeBaselineBuilder.build(lakeId: "T|ST", daily: syntheticDaily(years: 2010...2025), today: "2026-06-01"), now: now))
        XCTAssertEqual(s.kind, .proxy)
        XCTAssertEqual(s.levelState, .unknown)
        XCTAssertNil(s.seasonalPercentile)
        XCTAssertNil(s.differenceFromNormalPoolFt)
        XCTAssertNil(s.operatingZone)
        XCTAssertEqual(s.trendState, .rising)
    }

    func testFallbackUsedWhenPrimaryStaleAndFlagged() {
        let now = iso("2026-06-01T12:30:00Z")
        let p = ref(.directOperatorPool, "PRIMARY"), f = ref(.directLakeGauge, "FALLBACK")
        let s = LakeLevelClassifier.evaluate(inputs(binding([p, f]), live: [
            (p, hourly(iso("2026-05-28T00:00:00Z"), hours: 10, start: 600, step: 0)),
            (f, hourly(iso("2026-06-01T12:00:00Z"), hours: 30, start: 600, step: 0)),
        ], now: now))
        XCTAssertEqual(s.provenance.sources?.first?.sourceId, f.sourceId)
        XCTAssertTrue(s.provenance.qualityFlags!.contains { $0.hasPrefix("primarySourceStale:\(p.sourceId)") })
        XCTAssertFalse(s.freshness.stale)
    }

    func testStaleKeepsLastValueAndChecksAfterOneCadence() {
        let now = iso("2026-06-01T12:30:00Z")
        let p = ref(.directOperatorPool, "PRIMARY")
        let s = LakeLevelClassifier.evaluate(inputs(binding([p]), live: [(p, hourly(iso("2026-05-31T00:00:00Z"), hours: 5, start: 600, step: 0))], now: now))
        XCTAssertTrue(s.freshness.stale)
        XCTAssertEqual(s.currentElevationFt, 600)
        XCTAssertEqual(s.provenance.readiness, "DEGRADED")
        XCTAssertEqual(ISO8601DateFormatter().date(from: s.freshness.nextCheckAt)!.timeIntervalSince(now), 3600, accuracy: 1)
    }

    func testNoReadingIsUnavailableAndUnboundNeverPublishesLevel() {
        let now = iso("2026-06-01T12:30:00Z")
        let p = ref(.directOperatorPool, "PRIMARY")
        XCTAssertEqual(LakeLevelClassifier.evaluate(inputs(binding([p]), live: [(p, [])], now: now)).kind, .unavailable)
        var cand = binding([p]); cand.status = .candidate
        let s = LakeLevelClassifier.evaluate(inputs(cand, live: [(p, hourly(now, hours: 2, start: 600, step: 0))], now: now))
        XCTAssertEqual(s.kind, .unavailable)
        XCTAssertNil(s.currentElevationFt)
    }

    func testFreshStableLakeNextCheckIsTwoHoursNeverFasterThanCadence() {
        let now = iso("2026-06-01T12:30:00Z")
        let p = ref(.directOperatorPool, "PRIMARY")
        let s = LakeLevelClassifier.evaluate(inputs(binding([p]), live: [(p, hourly(iso("2026-06-01T12:00:00Z"), hours: 30, start: 600, step: 0))],
                                                guide: zone(599, 601), now: now))
        XCTAssertEqual(s.levelState, .inZone)
        XCTAssertEqual(s.trendState, .stable)
        XCTAssertEqual(s.differenceFromNormalPoolFt, 0)
        XCTAssertEqual(ISO8601DateFormatter().date(from: s.freshness.nextCheckAt)!.timeIntervalSince(now), 7200, accuracy: 1)
        XCTAssertEqual(s.freshness.freshUntil, "2026-06-01T14:00:00Z")
    }

    // MARK: Presence

    func bundle(_ rows: [LakePresenceBundle.Row]) -> LakePresenceBundle {
        LakePresenceBundle(schemaVersion: 1, kind: "lake-brain-presence", researchVersion: "test-1", presenceAuthority: "canonical-research",
                           assessedSpecies: ["example_fish", "other_fish"], sourceArtifacts: nil, rows: rows)
    }

    func row(_ lake: String, _ sp: String, _ state: String, disc: [String]? = nil) -> LakePresenceBundle.Row {
        .init(lakeId: lake, speciesId: sp, presenceState: state, confidence: "low", nativeStatus: nil, sourceTier: nil,
              latestRecord: nil, dataGaps: nil, discrepancyIds: disc)
    }

    func testPresenceUnknownIsNotWrittenAndSummaryCountsIt() throws {
        let idx = try LakePresenceIndex(bundle: bundle([row("Test|ST", "example_fish", "historical", disc: ["DISC-T"]),
                                                       row("Test|ST", "other_fish", "unknown")]),
                                        fingerprint: "f", sourceRef: "test", knownLakeIds: ["Test|ST"])
        let recs = idx.resolveLakeSpecies("Test|ST", updatedAt: "2026-01-01T00:00:00Z")
        XCTAssertEqual(recs.map(\.speciesId), ["example_fish"])
        XCTAssertEqual(recs.first?.discrepancyIds, ["DISC-T"])
        XCTAssertEqual(idx.summary("Test|ST").byState, ["historical": 1, "unknown": 1])
        XCTAssertTrue(idx.resolveLakeSpecies("Other|ST", updatedAt: "x").isEmpty, "absent = not assessed")
    }

    func testPresenceRejectsBadBundles() {
        XCTAssertThrowsError(try LakePresenceIndex(bundle: bundle([row("Test|ST", "example_fish", "PRESENT")]), fingerprint: "f", sourceRef: "t", knownLakeIds: ["Test|ST"]))
        XCTAssertThrowsError(try LakePresenceIndex(bundle: bundle([row("Nope|ST", "example_fish", "historical")]), fingerprint: "f", sourceRef: "t", knownLakeIds: ["Test|ST"]))
        XCTAssertThrowsError(try LakePresenceIndex(bundle: bundle([row("Test|ST", "not_assessed", "historical")]), fingerprint: "f", sourceRef: "t", knownLakeIds: ["Test|ST"]))
        XCTAssertThrowsError(try LakePresenceIndex(bundle: bundle([row("Test|ST", "example_fish", "historical"), row("Test|ST", "example_fish", "reported")]),
                                                   fingerprint: "f", sourceRef: "t", knownLakeIds: ["Test|ST"]))
    }

    // MARK: Plan / single-flight / paths

    func testPlanSkipsCurrentStateAndPublishesWhenDue() {
        let now = iso("2026-06-01T12:30:00Z")
        let p = ref(.directOperatorPool, "PRIMARY")
        let s = LakeLevelClassifier.evaluate(inputs(binding([p]), live: [(p, hourly(iso("2026-06-01T12:00:00Z"), hours: 30, start: 600, step: 0))], now: now))
        let v = LakeSourceBindings.version
        XCTAssertEqual(LakeBrainPlanner.planState(lakeId: "Test|ST", published: s, bindingVersion: v, publishedBindingVersion: v, now: now.addingTimeInterval(600)).action, .skip)
        XCTAssertEqual(LakeBrainPlanner.planState(lakeId: "Test|ST", published: s, bindingVersion: v, publishedBindingVersion: v, now: now.addingTimeInterval(7300)).action, .publish)
        XCTAssertEqual(LakeBrainPlanner.planState(lakeId: "Test|ST", published: s, bindingVersion: "new", publishedBindingVersion: v, now: now).action, .publish)
        XCTAssertEqual(LakeBrainPlanner.planState(lakeId: "Test|ST", published: nil, bindingVersion: v, publishedBindingVersion: nil, now: now).action, .publish)
    }

    func testSingleFlightJoinsConcurrentRefreshes() async {
        let f = LakeBrainSingleFlight<Int>()
        let counter = Counter()
        async let a = f.run("lake") { await counter.bump(); try? await Task.sleep(nanoseconds: 50_000_000); return 1 }
        async let b = f.run("lake") { await counter.bump(); try? await Task.sleep(nanoseconds: 50_000_000); return 2 }
        let (x, y) = await (a, b)
        let calls = await counter.n
        XCTAssertEqual(calls, 1)
        XCTAssertEqual(x, y)
    }

    actor Counter { var n = 0; func bump() { n += 1 } }

    func testPublisherWritesLeafPathsOnlyOnSharedNodes() async throws {
        let feeds = FakeFeeds()
        let dir = NSTemporaryDirectory() + "lake-brain-test-\(UUID().uuidString)"
        let store = LocalDirectoryStore(directory: dir)
        var opts = LakeBrainRunOptions(); opts.lakeIds = ["Guntersville|AL"]; opts.force = true
        let r = await LakeBrainRunner.run(store: store, feeds: feeds, archive: nil, presenceArchive: nil, options: opts, now: feeds.now)
        XCTAssertTrue(r.ok, r.writeError ?? "")
        let paths = Set(store.updates.flatMap(\.keys))
        XCTAssertTrue(paths.contains("lakes/Guntersville_AL/states/lake"))
        XCTAssertTrue(paths.contains("snapshots/Guntersville_AL/latest/lakeState"))
        XCTAssertTrue(paths.contains("lakeFleet/Guntersville_AL/readiness/lake"))
        for p in paths {
            XCTAssertNotEqual(p, "lakeFleet/Guntersville_AL")
            XCTAssertNotEqual(p, "snapshots/Guntersville_AL/latest")
            XCTAssertNotEqual(p, "lakes/Guntersville_AL")
            XCTAssertFalse(p.hasPrefix("schemaVersion"))
            for other in ["waterTemp", "waterClarity", "wind", "biology", "intelligence"] { XCTAssertFalse(p.hasSuffix("/\(other)"), p) }
        }
        XCTAssertFalse(paths.contains("brains/lake-brain"), "a --lake subset leaves the registry to full runs")
        let st = r.lakes.first?.state
        XCTAssertEqual(st?.kind, .observed)
        XCTAssertEqual(st?.levelState, .inZone)
    }
}

/// Deterministic feeds for one TVA-style pilot: flat 593.8 ft, zone 593.6–594.6.
final class FakeFeeds: LakeLevelFeeds, @unchecked Sendable {
    let now = ISO8601DateFormatter().date(from: "2026-06-01T12:30:00Z")!
    func recent(_ ref: LevelSeriesRef, hours: Int, now: Date) async -> FeedResult {
        let end = ISO8601DateFormatter().date(from: "2026-06-01T12:00:00Z")!
        return FeedResult(observations: (0...47).map { LevelObservation(at: end.addingTimeInterval(-Double(47 - $0) * 3600), ft: 593.8) }, error: nil)
    }
    func guide(_ source: LakeGuideSource, day: String, timeZone: TimeZone) async -> LakeGuideForDay? {
        LakeGuideForDay(guideFt: 594.2, zone: LakeOperatingZone(bottomFt: 593.6, topFt: 594.6, bottomLabel: "b", topLabel: "t", source: "fake"),
                        levels: [], topOfGatesFt: nil, floodPoolBottomFt: nil, source: "fake")
    }
    func daily(_ source: LakeHistorySource, since: String?, now: Date, timeZone: TimeZone) async -> [DailyLevel]? { [] }
    func archivedHourly(_ source: LakeHistorySource, days: Int, now: Date, timeZone: TimeZone) async -> [LevelObservation] { [] }
}
