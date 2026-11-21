//
//  LakeBrainTests.swift
//  Lake Brain: synthetic lakes, series and species only (no research data).
//

import XCTest
@testable import SectorEngine
@testable import LakeBrain

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

    func testTVAReleaseParsesDischargeAndTailwater() {
        let rows = """
        [{"Day":"10/10/2026","Time":"11 PM CDT","ReservoirElevation":"594.02","TailwaterElevation":"507.07","AverageHourlyDischarge":"63,258"},
         {"Day":"10/10/2026","Time":"Midnight CDT","ReservoirElevation":"594.03","TailwaterElevation":"","AverageHourlyDischarge":"0"},
         {"Day":"10/11/2026","Time":"1 AM CDT","ReservoirElevation":"594.05","TailwaterElevation":"507.01","AverageHourlyDischarge":"61,900"}]
        """
        let rel = PublicLakeLevelFeeds.parseTVARelease(Data(rows.utf8))
        XCTAssertEqual(rel.map(\.outflowCfs), [63258, 61900])          // the midnight row has neither value
        XCTAssertEqual(rel.map(\.tailwaterFt), [507.07, 507.01])
        XCTAssertEqual(rel.last?.at, iso("2026-10-11T06:00:00Z"))
        XCTAssertEqual(PublicLakeLevelFeeds.parseTVAObserved(Data(rows.utf8)).count, 3)   // level parsing unchanged
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
        // v2 (R2): without a rate baseline RAPID still fires at the 0.25 ft floor (flag rateBaselineLimited); v1 never did.
        XCTAssertEqual(LakeLevelClassifier.trend(delta24h: 0.9, day: nil).0, .risingRapidly, "v2: 0.25 ft RAPID floor applies without a rate baseline")
        XCTAssertEqual(LakeLevelClassifier.trend(delta24h: 0.2, day: nil).0, .rising)
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

    func testReleaseOnlyFromTheLevelSourceAndOnlyWhenObserved() {
        let now = iso("2026-06-01T12:30:00Z")
        let r = ref(.directOperatorPool, "R1")
        var x = inputs(binding([r]), live: [(r, hourly(iso("2026-06-01T12:00:00Z"), hours: 30, start: 600, step: 0.0))], now: now)
        XCTAssertNil(LakeLevelClassifier.evaluate(x).release)                       // no release series: absent = UNKNOWN
        x.releaseBySource = [r.sourceId: [ReleaseObservation(at: iso("2026-06-01T09:00:00Z"), outflowCfs: 41000, tailwaterFt: nil),
                                          ReleaseObservation(at: iso("2026-06-01T12:00:00Z"), outflowCfs: 52000, tailwaterFt: 507.2)]]
        let s = LakeLevelClassifier.evaluate(x).release
        XCTAssertEqual(s?.outflowCfs, 52000)
        XCTAssertEqual(s?.tailwaterElevationFt, 507.2)
        XCTAssertEqual(s?.observationTime, "2026-06-01T12:00:00Z")
        XCTAssertEqual(s?.sourceAgeHours, 0.5)
        XCTAssertEqual(s?.stale, false)
        x.releaseBySource = [r.sourceId: [ReleaseObservation(at: iso("2026-06-01T08:00:00Z"), outflowCfs: 41000, tailwaterFt: nil)]]
        XCTAssertEqual(LakeLevelClassifier.evaluate(x).release?.stale, true)       // older than cadence + lag
        x.releaseBySource = ["other": [ReleaseObservation(at: iso("2026-06-01T12:00:00Z"), outflowCfs: 1, tailwaterFt: nil)]]
        XCTAssertNil(LakeLevelClassifier.evaluate(x).release)                       // never from another series
        let p = ref(.nearbyGaugeProxy, "P1")
        var px = inputs(binding([p], cap: .nearbyGaugeProxy), live: [(p, hourly(iso("2026-06-01T12:00:00Z"), hours: 30, start: 3, step: 0.0))], now: now)
        px.releaseBySource = [p.sourceId: [ReleaseObservation(at: iso("2026-06-01T12:00:00Z"), outflowCfs: 9, tailwaterFt: nil)]]
        XCTAssertNil(LakeLevelClassifier.evaluate(px).release)                      // a proxy never carries release
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
        // PL-03: degraded but usable, primary kept, the source actually used named with its own capability (additive record)
        let fb = try! XCTUnwrap(s.sourceFallback)
        XCTAssertEqual(fb.usability, "DEGRADED_USABLE")
        XCTAssertEqual(fb.primarySourceId, p.sourceId)
        XCTAssertEqual(fb.primaryLastObservationAt, "2026-05-28T00:00:00Z")
        XCTAssertNil(fb.primaryError)
        XCTAssertEqual(fb.selectedSourceId, f.sourceId)
        XCTAssertEqual(fb.selectedCapability, .directLakeGauge)
        XCTAssertEqual(s.sourceCapability, .directOperatorPool, "the binding's capability is unchanged (additive correction)")
    }

    func testPrimarySourceSuppliesTheReadingSoThereIsNoFallbackRecord() {
        let now = iso("2026-06-01T12:30:00Z")
        let p = ref(.directOperatorPool, "PRIMARY"), f = ref(.directLakeGauge, "FALLBACK")
        let s = LakeLevelClassifier.evaluate(inputs(binding([p, f]), live: [
            (p, hourly(iso("2026-06-01T12:00:00Z"), hours: 30, start: 600, step: 0)),
            (f, hourly(iso("2026-06-01T12:00:00Z"), hours: 30, start: 600, step: 0)),
        ], now: now))
        XCTAssertNil(s.sourceFallback)
        XCTAssertFalse(String(decoding: try! BrainJSON.encode(s), as: UTF8.self).contains("sourceFallback"), "absent, never null")
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

    func testFreshStableLakeIsCurrentToTheStaleLimitAndRecomputedInTime() {
        let now = iso("2026-06-01T12:30:00Z")
        let p = ref(.directOperatorPool, "PRIMARY")
        var x = inputs(binding([p]), live: [(p, hourly(iso("2026-06-01T12:00:00Z"), hours: 30, start: 600, step: 0))],
                       guide: zone(599, 601), now: now)
        x.rainNext12hIn = 0
        let s = LakeLevelClassifier.evaluate(x)
        XCTAssertEqual(s.levelState, .inZone)
        XCTAssertEqual(s.trendState, .stable)
        XCTAssertEqual(s.differenceFromNormalPoolFt, 0)
        // Recomputed early enough that its replacement is published before freshUntil: freshUntil − refresh latency (16:00 − 150 min).
        XCTAssertEqual(ISO8601DateFormatter().date(from: s.freshness.nextCheckAt)!.timeIntervalSince(now), 3600, accuracy: 1)
        // STABLE and dry: current until the source's own stale limit (lag 60 + 3 × cadence 60 = 4 h after the reading).
        XCTAssertEqual(s.freshness.freshUntil, "2026-06-01T16:00:00Z")
        XCTAssertTrue(s.freshness.refreshReason.hasPrefix("STABLE"), s.freshness.refreshReason)
    }

    // MARK: Adaptive validity (owner direction 2026-11-20: watch the level and the rain, not a flat window)

    func evaluate(step: Double, rain: Double?, hours: Int = 30) -> LakeLevelStateRecord {
        let now = iso("2026-06-01T12:30:00Z")
        let p = ref(.directOperatorPool, "PRIMARY")
        var x = inputs(binding([p]), live: [(p, hourly(iso("2026-06-01T12:00:00Z"), hours: hours, start: 600, step: step))],
                       guide: zone(590, 610), now: now)
        x.rainNext12hIn = rain
        return LakeLevelClassifier.evaluate(x)
    }

    func testRainForecastShortensTheWindowOfAStableLake() {
        let dry = evaluate(step: 0, rain: 0), wet = evaluate(step: 0, rain: 0.4), soaked = evaluate(step: 0, rain: 1.5)
        XCTAssertEqual(dry.freshness.freshUntil, "2026-06-01T16:00:00Z")
        XCTAssertEqual(wet.freshness.freshUntil, "2026-06-01T15:00:00Z")
        XCTAssertTrue(wet.freshness.refreshReason.hasPrefix("CHANGING"), wet.freshness.refreshReason)
        XCTAssertTrue(soaked.freshness.refreshReason.hasPrefix("FAST"), soaked.freshness.refreshReason)
        // FAST wants 2 h after the reading (14:00), but the next run's value cannot be published before now + refresh latency (15:00).
        XCTAssertEqual(soaked.freshness.freshUntil, "2026-06-01T15:00:00Z")
        XCTAssertTrue(wet.facts?.contains { $0.contains("rain forecast") } ?? false)
    }

    func testAChangingLakeIsCurrentForLessTimeAndCheckedAtTheNextReading() {
        let s = evaluate(step: 0.008, rain: 0)           // 0.19 ft in 24 h: RISING (above the 0.10 ft stable band, below the 0.25 ft rapid floor)
        XCTAssertTrue(s.freshness.refreshReason.hasPrefix("CHANGING"), s.freshness.refreshReason)
        XCTAssertEqual(s.freshness.freshUntil, "2026-06-01T15:00:00Z")
        XCTAssertEqual(s.freshness.nextCheckAt, "2026-06-01T13:15:00Z", "recomputed on the next hourly grant")
        let fast = evaluate(step: 0.25, rain: 0)         // 1.5 ft in 6 h
        XCTAssertTrue(fast.freshness.refreshReason.hasPrefix("FAST"), fast.freshness.refreshReason)
    }

    func testUnknownRainIsTreatedConservatively() {
        let s = evaluate(step: 0, rain: nil)
        XCTAssertTrue(s.freshness.refreshReason.contains("rain forecast unavailable"), s.freshness.refreshReason)
        XCTAssertEqual(s.freshness.freshUntil, "2026-06-01T15:00:00Z")
    }

    func testTheWindowNeverOutlivesTheSourcesStaleRuleAndNeverEndsBeforeTheNextRunCanReplaceIt() {
        let now = iso("2026-06-01T12:55:00Z")
        let latency = Double(LakeLevelValidity.refreshLatencyMin) * 60
        for tier in [LakeTrendState.stable, .rising, .risingRapidly] {
            for rain in [nil, 0.0, 0.5, 2.0] as [Double?] {
                for (c, l) in [(60, 60), (60, 120), (15, 30), (1440, 360), (1440, 2880)] {
                    for ageMin in stride(from: l, through: l + 3 * c, by: max(5, c / 4)) {
                        let obs = now.addingTimeInterval(-Double(ageMin) * 60)
                        let d = LakeLevelValidity.decide(trend: tier, change: LakeLevelChange(h1: nil, h6: nil, h24: nil, d3: nil, d7: nil),
                                                         rainNext12hIn: rain, cadenceMin: c, lagMin: l, observedAt: obs, now: now)
                        let ceiling = obs.addingTimeInterval(Double(l + 3 * c) * 60)
                        XCTAssertLessThanOrEqual(d.freshUntil, ceiling, "ceiling: the source's stale rule")
                        XCTAssertGreaterThanOrEqual(d.freshUntil, min(ceiling, now.addingTimeInterval(latency)), "floor: counted from the run")
                        XCTAssertGreaterThanOrEqual(d.nextCheckAt, now)
                        XCTAssertTrue(d.nextCheckAt <= now.addingTimeInterval(Double(LakeLevelValidity.recheckMin) * 60)
                                      || d.nextCheckAt <= d.freshUntil.addingTimeInterval(-latency), "recomputed before its window runs out")
                    }
                }
            }
        }
        // A daily source 7 h after its reading: FAST wants 2 h after the reading, the run floor holds it to now + latency.
        let obs = now.addingTimeInterval(-7 * 3600)
        let daily = LakeLevelValidity.decide(trend: .risingRapidly, change: LakeLevelChange(h1: nil, h6: 2, h24: nil, d3: nil, d7: nil),
                                             rainNext12hIn: 3, cadenceMin: 1440, lagMin: 360, observedAt: obs, now: now)
        XCTAssertEqual(daily.freshUntil, now.addingTimeInterval(latency))
        XCTAssertEqual(daily.tier, .fast)
    }

    /// Review of #216 (B1): hourly grants at :50, one publish cycle of lag, the copy lane checking every 10 min. While the gauge itself
    /// is not overdue, the customer copy is never withdrawn, for every tier and when NWS fails.
    func testHourlyGrantsNeverLetTheCopyLapseWhileTheGaugeIsCurrent() {
        let start = iso("2026-06-01T00:50:00Z")
        struct Case { var name: String; var lag: Int; var step: Double; var rain: Double? }
        let cases = [60, 120].flatMap { lag in [
            Case(name: "STABLE", lag: lag, step: 0, rain: 0), Case(name: "CHANGING", lag: lag, step: 0.008, rain: 0),
            Case(name: "FAST", lag: lag, step: 0, rain: 1.5), Case(name: "NWS failure", lag: lag, step: 0, rain: nil)] }
        for c in cases {
            let p = LevelSeriesRef(provider: .usgs, capability: .directOperatorPool, station: "SIM", series: "00062", cadenceMin: 60, lagMin: c.lag)
            var visible: [(at: Date, state: LakeLevelStateRecord)] = []
            var published: LakeLevelStateRecord?
            for k in 0..<48 {
                let runAt = start.addingTimeInterval(Double(k) * 3600 + 5 * 60)           // granted at :50, running by :55
                let plan = LakeBrainPlanner.planState(lakeId: "Test|ST", published: published, bindingVersion: "b",
                                                      publishedBindingVersion: "b", now: runAt)
                guard plan.action == .publish else { continue }
                // The newest reading available now: top of the hour, `lag` minutes ago.
                let avail = runAt.addingTimeInterval(-Double(c.lag) * 60)
                let obs = Date(timeIntervalSince1970: (avail.timeIntervalSince1970 / 3600).rounded(.down) * 3600)
                var x = inputs(binding([p]), live: [(p, hourly(obs, hours: 30, start: 600 + Double(k) * c.step, step: c.step))],
                               guide: zone(590, 700), now: runAt)
                x.rainNext12hIn = c.rain
                let s = LakeLevelClassifier.evaluate(x)
                XCTAssertFalse(s.freshness.stale, c.name)
                published = s
                visible.append((runAt.addingTimeInterval(3600), s))                        // reaches customers one publish cycle later
            }
            XCTAssertGreaterThan(visible.count, 30, "\(c.name) lag \(c.lag): recomputed on (nearly) every grant")
            let f = ISO8601DateFormatter()
            var t = visible[0].at
            while t < start.addingTimeInterval(47 * 3600) {
                let current = visible.last { $0.at <= t }!.state
                let until = f.date(from: current.freshness.freshUntil!)!
                XCTAssertLessThanOrEqual(t, until, "\(c.name) lag \(c.lag): copy would be withdrawn at \(f.string(from: t))")
                t.addTimeInterval(600)
            }
        }
    }

    func testAStaleSourceIsNeverPresentedAsCurrentWhateverTheTier() {
        let now = iso("2026-06-01T12:30:00Z")
        let p = ref(.directOperatorPool, "PRIMARY")
        var x = inputs(binding([p]), live: [(p, hourly(iso("2026-05-31T00:00:00Z"), hours: 5, start: 600, step: 0))], now: now)
        x.rainNext12hIn = 0
        let s = LakeLevelClassifier.evaluate(x)
        XCTAssertTrue(s.freshness.stale)
        let until = ISO8601DateFormatter().date(from: s.freshness.freshUntil!)!
        XCTAssertLessThan(until, now, "the window ended before now: the copy lane and the Engine both refuse it")
    }

    // MARK: Rain signal (NWS forecastGridData)

    func testRainForecastSumsTheNext12HoursPartialPeriodsInProportion() {
        let json = """
        {"properties":{"quantitativePrecipitation":{"uom":"wmoUnit:mm","values":[
          {"validTime":"2026-06-01T06:00:00+00:00/PT6H","value":25.4},
          {"validTime":"2026-06-01T12:00:00+00:00/PT6H","value":12.7},
          {"validTime":"2026-06-01T18:00:00+00:00/PT6H","value":0},
          {"validTime":"2026-06-02T00:00:00+00:00/P1DT0H","value":50.8}]}}}
        """
        let now = iso("2026-06-01T09:00:00Z")
        // 06–12Z: half of 1.0 in = 0.50; 12–18Z: 0.50; 18–21Z: 0; 00Z+ is outside the 12 h window.
        XCTAssertEqual(LakeRainSignal.forecastInches(gridData: Data(json.utf8), now: now), 1.0)
        XCTAssertNil(LakeRainSignal.forecastInches(gridData: Data("{\"properties\":{}}".utf8), now: now))
        XCTAssertEqual(LakeRainSignal.parseValidTime("2026-06-02T00:00:00+00:00/P1DT6H")?.1, 30)
        XCTAssertEqual(LakeRainSignal.decodePoint(Data("{\"properties\":{\"forecastGridData\":\"https://api.weather.gov/gridpoints/HUN/76,30\"}}".utf8)),
                       LakeRainSignal.Point(forecastGridData: "https://api.weather.gov/gridpoints/HUN/76,30"))
    }

    func testRainClientKeepsTheGridCellAcrossRunsAndFailsToUnknown() async {
        final class Calls: @unchecked Sendable { var urls: [String] = []; let lock = NSLock()
            func add(_ u: String) { lock.lock(); urls.append(u); lock.unlock() }
            var count: Int { lock.lock(); defer { lock.unlock() }; return urls.count } }
        let calls = Calls()
        let grid = "https://api.weather.gov/gridpoints/HUN/1,1"
        let fetch: LakeRainSignalClient.Fetch = { url in
            calls.add(url)
            if url.contains("/points/") { return Data("{\"properties\":{\"forecastGridData\":\"\(grid)\"}}".utf8) }
            return Data("{\"properties\":{\"quantitativePrecipitation\":{\"uom\":\"wmoUnit:mm\",\"values\":[{\"validTime\":\"2026-06-01T12:00:00+00:00/PT6H\",\"value\":6.35}]}}}".utf8)
        }
        let now = iso("2026-06-01T12:00:00Z")
        let first = LakeRainSignalClient(fetch: fetch, spacing: 0)
        let a = await first.nextHours(lat: 34.4, lon: -86.3, now: now)
        let b = await first.nextHours(lat: 34.4, lon: -86.3, now: now)
        XCTAssertEqual(a, 0.25); XCTAssertEqual(b, 0.25)
        XCTAssertEqual(calls.count, 2, "one points + one grid request, then cached for the run")
        // The next run is seeded with the learned map (what LakeBrainRunner saves in the archive): grid request only.
        let learned = await first.pointMap()
        XCTAssertEqual(learned, [LakeRainSignalClient.pointKey(lat: 34.4, lon: -86.3): grid])
        let second = LakeRainSignalClient(fetch: fetch, spacing: 0)
        await second.seed(learned)
        let c = await second.nextHours(lat: 34.4, lon: -86.3, now: now)
        XCTAssertEqual(c, 0.25)
        XCTAssertEqual(calls.count, 3, "no /points lookup on a seeded run")
        // A cell whose forecast cannot be read is forgotten (looked up again next run), and the answer is unknown.
        let broken = LakeRainSignalClient(fetch: { _ in nil }, spacing: 0, knownPoints: learned)
        let unknown = await broken.nextHours(lat: 34.4, lon: -86.3, now: now)
        XCTAssertNil(unknown)
        let forgotten = await broken.pointMap()
        XCTAssertTrue(forgotten.isEmpty)
    }

    func testRainClientSpacesItsRequests() async {
        let c = LakeRainSignalClient(fetch: { _ in nil }, spacing: 0.2)
        let t0 = Date()
        _ = await c.nextHours(lat: 1, lon: 1, now: t0)
        _ = await c.nextHours(lat: 2, lon: 2, now: t0)
        _ = await c.nextHours(lat: 3, lon: 3, now: t0)
        XCTAssertGreaterThanOrEqual(Date().timeIntervalSince(t0), 0.39, "three requests, at least 0.2 s apart")
    }

    // MARK: Hourly runs skip the daily history pulls

    func testHistoryIsCurrentWhenTheArchiveHoldsTheSourcesNewestExpectedDay() {
        let now = iso("2026-06-02T15:00:00Z")
        let cwms = LakeHistorySource.cwmsDaily(office: "SAS", series: "x"), rise = LakeHistorySource.riseDaily(item: "1")
        func rows(_ days: String...) -> [DailyLevel] { days.map { DailyLevel(date: $0, ft: 600, sourceId: "x") } }
        XCTAssertTrue(LakeBrainRunner.historyIsCurrent(rows("2026-05-28", "2026-06-01"), source: cwms, backfill: false, now: now, timeZone: utc))
        XCTAssertFalse(LakeBrainRunner.historyIsCurrent(rows("2026-05-28"), source: cwms, backfill: false, now: now, timeZone: utc), "behind: pull the recent tail")
        XCTAssertFalse(LakeBrainRunner.historyIsCurrent([], source: cwms, backfill: false, now: now, timeZone: utc), "empty archive: full pull")
        XCTAssertFalse(LakeBrainRunner.historyIsCurrent(rows("2026-06-01"), source: cwms, backfill: true, now: now, timeZone: utc), "backfill always pulls")
        // RISE posts about 48 h late: a row for 2026-05-31 is all it can have, so the hourly run does not re-pull it.
        XCTAssertFalse(LakeBrainRunner.historyIsCurrent(rows("2026-05-31"), source: cwms, backfill: false, now: now, timeZone: utc))
        XCTAssertTrue(LakeBrainRunner.historyIsCurrent(rows("2026-05-31"), source: rise, backfill: false, now: now, timeZone: utc))
        XCTAssertFalse(LakeBrainRunner.historyIsCurrent(rows("2026-05-30"), source: rise, backfill: false, now: now, timeZone: utc))
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

    /// Operational truth: a non-HEALTHY Lake Brain publishes WHY (health/brains/lake-brain.reasons), with the same rule as the status.
    func testHealthReasonsExplainWarningAndAreAbsentWhenHealthy() async throws {
        let feeds = FakeFeeds()
        let store = LocalDirectoryStore(directory: NSTemporaryDirectory() + "lake-brain-reasons-\(UUID().uuidString)", brainId: LakeBrainSpec.brainId)
        var opts = LakeBrainRunOptions(); opts.lakeIds = ["Guntersville|AL"]; opts.force = true
        let r = await LakeBrainRunner.run(store: store, feeds: feeds, archive: nil, presenceArchive: nil, options: opts, now: feeds.now)
        let ok = try XCTUnwrap(r.lakes.first)
        XCTAssertEqual(LakeBrainRunner.health([ok], writeFailed: false), "HEALTHY")
        XCTAssertEqual(LakeBrainRunner.healthReasons([ok], writeFailed: false), [])

        var fallback = ok
        let flags = (ok.state?.provenance.qualityFlags ?? []) + ["fallbackSource:usgs-x"]
        fallback.state?.provenance.qualityFlags = flags
        XCTAssertEqual(LakeBrainRunner.health([fallback], writeFailed: false), "WARNING")
        XCTAssertEqual(LakeBrainRunner.healthReasons([fallback], writeFailed: false), ["Guntersville|AL: primary source unavailable, on fallback source usgs-x"])

        var missing = ok
        missing.state = nil
        let four = [ok, ok, ok, missing]                              // 1 of 4 unavailable: WARNING (not DEGRADED)
        XCTAssertEqual(LakeBrainRunner.health(four, writeFailed: false), "WARNING")
        XCTAssertEqual(LakeBrainRunner.healthReasons(four, writeFailed: false), ["Guntersville|AL: state unavailable"])
        XCTAssertEqual(LakeBrainRunner.healthReasons([ok], writeFailed: true), ["publish failed"])
    }

    func testHealthRecordReasonsAreAdditiveJSON() throws {
        let rec = BrainHealthRecord(status: "WARNING", staleLakeCount: 0, errorCount: 0, reasons: ["X|ST: state stale"])
        let json = String(data: try BrainJSON.encode(rec), encoding: .utf8)!
        XCTAssertTrue(json.contains("\"reasons\":[\"X|ST: state stale\"]"))
        let healthy = String(data: try BrainJSON.encode(BrainHealthRecord(status: "HEALTHY", staleLakeCount: 0, errorCount: 0)), encoding: .utf8)!
        XCTAssertFalse(healthy.contains("reasons"))
    }

    func testPublisherWritesLeafPathsOnlyOnSharedNodes() async throws {
        let feeds = FakeFeeds()
        let dir = NSTemporaryDirectory() + "lake-brain-test-\(UUID().uuidString)"
        let store = LocalDirectoryStore(directory: dir, brainId: LakeBrainSpec.brainId)
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
