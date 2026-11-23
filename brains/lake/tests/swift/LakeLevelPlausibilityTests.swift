//
//  LakeLevelPlausibilityTests.swift
//  Lake Brain — physically impossible level readings are rejected, labelled and replaced by the last valid reading
//  (Lake Tahoe, Sector_Ops #51 comment 7091893754, 2026-11-23). Synthetic series only.
//

import XCTest
@testable import SectorEngine
@testable import LakeBrain

final class LakeLevelPlausibilityTests: XCTestCase {

    let utc = TimeZone(identifier: "UTC")!
    func iso(_ s: String) -> Date { ISO8601DateFormatter().date(from: s)! }

    /// Tahoe-like daily history: 6,226 ft ± 2.5 ft seasonal, 2013-01-01 … `through`.
    func tahoeHistory(through: String = "2025-12-31") -> [DailyLevel] {
        var out: [DailyLevel] = []
        var d = LakeLevelCalendar.date(year: 2013, month: 1, day: 1)
        while true {
            let day = LakeLevelCalendar.dayString(d, timeZone: utc)
            if day > through { break }
            let doy = Double(LakeLevelCalendar.doy365(day)!)
            out.append(DailyLevel(date: day, ft: ((6226 + 2.5 * sin(doy / 365 * 2 * .pi)) * 100).rounded() / 100, sourceId: "cwms:SPK:test"))
            d = d.addingTimeInterval(86_400)
        }
        return out
    }

    /// Tahoe's binding shape: a daily USACE manual series first, the hourly NWS gauge second.
    let cwms = LevelSeriesRef(provider: .cwms, capability: .directOperatorPool, station: "SPK",
                              series: "Lake Tahoe.Elev.Inst.~1Day.0.MANUAL", cadenceMin: 1440, lagMin: 1440)
    let nwps = LevelSeriesRef(provider: .nwps, capability: .directLakeGauge, station: "THLC1", series: "HPIRG", cadenceMin: 60, lagMin: 120)

    func binding(_ live: [LevelSeriesRef]) -> LakeSourceBinding {
        LakeSourceBinding(lakeId: "Lake Tahoe|NV", status: .reviewed, capability: .directOperatorPool, live: live, history: [], guide: nil,
                          datum: nil, timeZone: "America/Los_Angeles", damName: nil, riverSystem: nil, topOfGatesFt: nil, hydropower: nil,
                          floodControl: nil, operatorName: nil, reviewedAt: nil, note: nil)
    }

    /// Eight daily manual readings ending today 08:00Z; the newest is the decimal slip seen on 2026-11-23.
    func cwmsDaily(newest: Double) -> [LevelObservation] {
        let end = iso("2026-11-23T08:00:00Z")
        return (0..<8).map { i in
            LevelObservation(at: end.addingTimeInterval(-Double(7 - i) * 86_400), ft: i == 7 ? newest : 6225.98 + Double(i) * 0.01)
        }
    }

    func inputs(live: [(LevelSeriesRef, [LevelObservation])], reference: LakeLevelPlausibility.Reference?, fullPool: Double? = 6229.1) -> LakeLevelInputs {
        var x = LakeLevelInputs(lakeId: "Lake Tahoe|NV", binding: binding(live.map { $0.0 }), capabilityIfUnbound: .noSource, fullPoolFt: fullPool,
                                poolBasisIsFullPool: true, poolConfidenceLow: false, live: live.map { ($0.0, $0.1, nil) }, archivedHourly: [],
                                guide: nil, baseline: nil, now: iso("2026-11-23T10:00:00Z"), processingVersion: "test")
        x.levelReference = reference
        return x
    }

    // MARK: the live Tahoe case

    func testTahoeDecimalSlipIsRejectedAndThePreviousValidReadingIsPublished() {
        let ref = LakeLevelPlausibility.reference(historyFt: tahoeHistory().map(\.ft), fullPoolFt: 6229.1)
        XCTAssertNotNil(ref)
        let s = LakeLevelClassifier.evaluate(inputs(live: [(cwms, cwmsDaily(newest: 6_226_054))], reference: ref))
        XCTAssertEqual(s.kind, .observed)
        XCTAssertEqual(s.currentElevationFt, 6226.04, "the last valid manual reading, never the slip")
        XCTAssertEqual(s.observationTime, "2026-11-22T08:00:00Z")
        XCTAssertFalse(s.freshness.stale, "one day old is inside the daily series' stale rule")
        XCTAssertEqual(s.differenceFromNormalPoolFt, -3.06)
        XCTAssertNotEqual(s.trendState, .risingRapidly)
        let flags = s.provenance.qualityFlags ?? []
        XCTAssertTrue(flags.contains("implausibleReading:\(cwms.sourceId)@2026-11-23T08:00:00Z=6226054.00"), "\(flags)")
        XCTAssertTrue(flags.contains("implausibleLatestRejected:\(cwms.sourceId)"))
        XCTAssertFalse(s.facts?.joined().contains("6226054") ?? true)
    }

    func testTahoeSlipIsRejectedWithoutHistoryFromTheFullPoolAlone() {
        let s = LakeLevelClassifier.evaluate(inputs(live: [(cwms, cwmsDaily(newest: 6_226_054))], reference: nil))
        XCTAssertEqual(s.currentElevationFt, 6226.04)
        XCTAssertTrue((s.provenance.qualityFlags ?? []).contains { $0.hasPrefix("implausibleReading:") })
    }

    func testTahoeSlipIsRejectedWithNoReferenceAtAllFromTheSeriesItself() {
        let s = LakeLevelClassifier.evaluate(inputs(live: [(cwms, cwmsDaily(newest: 6_226_054))], reference: nil, fullPool: nil))
        XCTAssertEqual(s.currentElevationFt, 6226.04)
    }

    func testWhenTheOnlyValidPrimaryReadingIsStaleTheFallbackSourceIsUsedAndLabelled() {
        // The primary's only other reading is 5 days old (past its stale rule): the hourly gauge supplies the level.
        let old = LevelObservation(at: iso("2026-11-18T08:00:00Z"), ft: 6226.00)
        let slip = LevelObservation(at: iso("2026-11-23T08:00:00Z"), ft: 6_226_054)
        let hourly = (0..<24).map { LevelObservation(at: iso("2026-11-23T09:00:00Z").addingTimeInterval(-Double(23 - $0) * 3600), ft: 6226.06) }
        let ref = LakeLevelPlausibility.reference(historyFt: tahoeHistory().map(\.ft), fullPoolFt: 6229.1)
        let s = LakeLevelClassifier.evaluate(inputs(live: [(cwms, [old, slip]), (nwps, hourly)], reference: ref))
        XCTAssertEqual(s.currentElevationFt, 6226.06)
        XCTAssertEqual(s.sourceFallback?.selectedSourceId, nwps.sourceId)
        XCTAssertEqual(s.sourceFallback?.primaryLastObservationAt, "2026-11-18T08:00:00Z", "the primary's last VALID reading")
        XCTAssertTrue((s.provenance.qualityFlags ?? []).contains("fallbackSource:\(nwps.sourceId)"))
        XCTAssertTrue((s.provenance.qualityFlags ?? []).contains { $0.hasPrefix("implausibleReading:\(cwms.sourceId)") })
    }

    func testEveryReadingImpossibleIsUnavailableNeverTheImpossibleNumber() {
        let s = LakeLevelClassifier.evaluate(inputs(live: [(cwms, [LevelObservation(at: iso("2026-11-23T08:00:00Z"), ft: 6_226_054)])],
                                                    reference: LakeLevelPlausibility.reference(historyFt: tahoeHistory().map(\.ft), fullPoolFt: 6229.1)))
        XCTAssertEqual(s.kind, .unavailable)
        XCTAssertNil(s.currentElevationFt)
        XCTAssertTrue((s.provenance.qualityFlags ?? []).contains("allReadingsImplausible"))
    }

    // MARK: the rule itself

    func testReferenceIsTheLakesOwnRangeWithAFloorMargin() throws {
        let r = try XCTUnwrap(LakeLevelPlausibility.reference(historyFt: tahoeHistory().map(\.ft), fullPoolFt: 6229.1))
        XCTAssertEqual(r.hi, 6229.1, "the full pool widens the band when it agrees with the record")
        XCTAssertEqual(r.marginFt, LakeLevelPlausibility.minMarginFt, "Tahoe's recorded range is ~6 ft: the 50 ft floor applies")
        // A lake with a wide record gets its own range as the margin.
        let wide = (0..<400).map { 1000 + Double($0 % 200) }                     // 1000 … 1199 ft
        let w = try XCTUnwrap(LakeLevelPlausibility.reference(historyFt: wide, fullPoolFt: nil))
        XCTAssertGreaterThan(w.marginFt, 190)
        XCTAssertTrue(w.contains(1000 - 150), "a drought 150 ft below anything recorded is still plausible for this lake")
        XCTAssertFalse(w.contains(10_000))
        XCTAssertFalse(w.contains(100))
    }

    func testReferenceOnAnotherDatumIsRecentredOnTheSeriesNotUsedToRejectIt() {
        // History in elevation (~6226 ft), live series a 3 ft stage gauge: the band must not throw away the whole series.
        let ref = LakeLevelPlausibility.reference(historyFt: tahoeHistory().map(\.ft), fullPoolFt: 6229.1)
        let stage = (0..<48).map { LevelObservation(at: iso("2026-11-23T00:00:00Z").addingTimeInterval(Double($0) * 3600), ft: 3 + Double($0) * 0.01) }
        let f = LakeLevelPlausibility.filter(stage, sourceId: "s", reference: ref)
        XCTAssertEqual(f.kept.count, 48)
        XCTAssertTrue(f.rejected.isEmpty)
        // …but a slip on that stage series is still caught (×10).
        var slipped = stage; slipped[47].ft = 34.7
        XCTAssertEqual(LakeLevelPlausibility.filter(slipped, sourceId: "s", reference: ref).rejected.map(\.rawFt), [34.7])
    }

    func testFloodRisesAndFloodControlReleasesAreNeverRejected() {
        let t0 = iso("2026-05-01T00:00:00Z")
        // Flash-flood inflow into a small pool: +1.5 ft/h for 24 h (36 ft in a day).
        let rise = (0...24).map { LevelObservation(at: t0.addingTimeInterval(Double($0) * 3600), ft: 600 + 1.5 * Double($0)) }
        XCTAssertTrue(LakeLevelPlausibility.filter(rise, sourceId: "s", reference: .init(lo: 595, hi: 605, marginFt: 50, basis: "t")).rejected.isEmpty)
        XCTAssertTrue(LakeLevelPlausibility.filter(rise, sourceId: "s", reference: nil).rejected.isEmpty)
        // Flood-control evacuation: −0.5 ft/h for 4 days (48 ft), hourly.
        let release = (0...96).map { LevelObservation(at: t0.addingTimeInterval(Double($0) * 3600), ft: 1070 - 0.5 * Double($0)) }
        XCTAssertTrue(LakeLevelPlausibility.filter(release, sourceId: "s", reference: .init(lo: 1020, hi: 1075, marginFt: 55, basis: "t")).rejected.isEmpty)
        // A daily series that rose 20 ft between two manual readings two days apart.
        let gap = [LevelObservation(at: t0, ft: 900), LevelObservation(at: t0.addingTimeInterval(86_400), ft: 900.2),
                   LevelObservation(at: t0.addingTimeInterval(3 * 86_400), ft: 920.2)]
        XCTAssertTrue(LakeLevelPlausibility.filter(gap, sourceId: "s", reference: nil).rejected.isEmpty)
    }

    func testAnImpossibleStepIsRejectedEvenInsideTheBand() {
        let t0 = iso("2026-05-01T00:00:00Z")
        var xs = (0..<30).map { LevelObservation(at: t0.addingTimeInterval(Double($0) * 3600), ft: 600) }
        xs[20].ft = 615                                                            // 15 ft in one hour and back: limit is 12 ft
        let f = LakeLevelPlausibility.filter(xs, sourceId: "s", reference: .init(lo: 560, hi: 640, marginFt: 80, basis: "t"))
        XCTAssertEqual(f.rejected.map(\.rawFt), [615])
        XCTAssertEqual(f.kept.count, 29)
        XCTAssertTrue(f.rejected[0].reason.hasPrefix("step"), f.rejected[0].reason)
    }

    func testABadFirstReadingDoesNotTakeTheGoodOnesWithIt() {
        let t0 = iso("2026-05-01T00:00:00Z")
        var xs = (0..<10).map { LevelObservation(at: t0.addingTimeInterval(Double($0) * 3600), ft: 600) }
        xs[0].ft = 630                                                             // inside a wide band, impossible as a step
        let f = LakeLevelPlausibility.filter(xs, sourceId: "s", reference: .init(lo: 500, hi: 700, marginFt: 200, basis: "t"))
        XCTAssertEqual(f.rejected.map(\.rawFt), [630])
        XCTAssertEqual(f.kept.count, 9)
    }

    func testTooFewReadingsWithNoReferenceAreKept() {
        let t0 = iso("2026-05-01T00:00:00Z")
        let xs = [LevelObservation(at: t0, ft: 6226)]
        XCTAssertTrue(LakeLevelPlausibility.filter(xs, sourceId: "s", reference: nil).rejected.isEmpty)
    }

    // MARK: history baselines (extends the #218 spike filter)

    func testTahoeHistorySlipsAreLeftOutOfTheBaseline() throws {
        var xs = tahoeHistory()
        // Twelve slips 2014–2016 like the archived ones, two of them on consecutive days (the neighbour filter alone needs ≥ 4
        // in-band neighbours; a run of slips or a gap defeats it).
        let slips: [(String, Double)] = [("2014-02-03", 622.83), ("2014-02-04", 622.83), ("2014-05-10", 62_223.31), ("2014-08-21", 622.61),
                                         ("2014-11-30", 62_259.0), ("2015-01-15", 622.47), ("2015-04-02", 62_241.2), ("2015-06-18", 622.55),
                                         ("2015-09-09", 62_230.0), ("2016-01-05", 622.30), ("2016-03-22", 62_255.5), ("2016-07-14", 622.40)]
        for (d, v) in slips { xs[xs.firstIndex { $0.date == d }!].ft = v }
        let b = LakeBaselineBuilder.build(lakeId: "Lake Tahoe|NV", daily: xs, today: "2026-11-23")
        XCTAssertEqual(Set(b.excludedSpikeDays ?? []), Set(slips.map { $0.0 }))
        XCTAssertEqual(b.observationCount, xs.count - slips.count)
        let lows = b.days.compactMap { $0.levelQ?.first }, highs = b.days.compactMap { $0.levelQ?.last }
        XCTAssertGreaterThan(lows.min() ?? 0, 6223)
        XCTAssertLessThan(highs.max() ?? .infinity, 6229)
        XCTAssertLessThan(b.days.compactMap { $0.rateQ?.last }.max() ?? .infinity, 1, "no slip-sized |Δ24h| in the rate climatology")
        // The same history with no slips: identical climatology.
        let clean = LakeBaselineBuilder.build(lakeId: "Lake Tahoe|NV", daily: tahoeHistory().filter { d in !slips.contains { $0.0 == d.date } },
                                              today: "2026-11-23")
        XCTAssertEqual(clean.days, b.days)
    }

    func testANewestHistoryDaySlipIsLeftOutThoughItHasNoLaterNeighbours() {
        var xs = tahoeHistory(through: "2026-11-23")
        xs[xs.count - 1].ft = 6_226_054
        let b = LakeBaselineBuilder.build(lakeId: "Lake Tahoe|NV", daily: xs, today: "2026-11-23")
        XCTAssertEqual(b.excludedSpikeDays, ["2026-11-23"])
        XCTAssertEqual(b.historyEnd, "2026-11-22")
    }

    func testARealDeepDrawdownInHistoryIsKept() {
        // 600 ft ± 3 ft for 13 years; in 2020 a flood-control/repair drawdown of 2 ft/day to 560 ft, held 20 days, refilled.
        var xs: [DailyLevel] = []
        var d = LakeLevelCalendar.date(year: 2013, month: 1, day: 1)
        let end = LakeLevelCalendar.date(year: 2025, month: 12, day: 31)
        while d <= end {
            let day = LakeLevelCalendar.dayString(d, timeZone: utc)
            xs.append(DailyLevel(date: day, ft: 600 + 3 * sin(Double(LakeLevelCalendar.doy365(day)!) / 365 * 2 * .pi), sourceId: "t"))
            d = d.addingTimeInterval(86_400)
        }
        let start = xs.firstIndex { $0.date == "2020-03-01" }!
        for j in 0..<60 {
            let drop = j < 20 ? 2 * Double(j + 1) : j < 40 ? 40 : 40 - 2 * Double(j - 39)
            xs[start + j].ft -= drop
        }
        let b = LakeBaselineBuilder.build(lakeId: "T|ST", daily: xs, today: "2026-06-01")
        XCTAssertNil(b.excludedSpikeDays, "a real 40 ft drawdown is water, not a slip")
        XCTAssertEqual(b.observationCount, xs.count)
    }
}
