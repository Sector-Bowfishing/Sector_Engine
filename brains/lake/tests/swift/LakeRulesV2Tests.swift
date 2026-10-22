//
//  LakeRulesV2Tests.swift
//  Lake Brain rules v2 (`lake-level-rules-v2`, `doy15-percentile-v2`): history tiers, trend labels, versions.
//  Pre-registered in docs/brains/LAKE_BRAIN_RULES_V2_PREREGISTRATION.md. The conformance cases are the shared file
//  contracts/conformance/lake_rules_v2.json, which jobs/lake-brain/validation/test_rules_v2.py runs against the Python mirror.
//

import XCTest
@testable import SectorEngine
@testable import LakeBrain

final class LakeRulesV2Tests: XCTestCase {

    let utc = TimeZone(identifier: "UTC")!
    func iso(_ s: String) -> Date { ISO8601DateFormatter().date(from: s)! }

    // MARK: fixture plumbing

    private static let fixtureURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()   // brains/<dir>/tests/swift/<file> -> repo root
        .appendingPathComponent("contracts/conformance/lake_rules_v2.json")

    private func fixture() throws -> [String: Any] {
        try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: Self.fixtureURL)) as? [String: Any])
    }
    private func num(_ x: Any?) -> Double? { (x as? NSNumber).map { $0.doubleValue } }
    private func cases(_ fx: [String: Any], _ key: String) throws -> [[String: Any]] { try XCTUnwrap(fx[key] as? [[String: Any]]) }

    static func tier(_ s: String) -> LakeHistoricalTier { LakeHistoricalTier(rawValue: s)! }

    /// level = 100 + ((year*7 + dayOfYear*3) % 11) * 0.1 + (year - 2000) * 0.01  (the fixture's integer-valued synthetic series)
    func fixtureSeries(_ spec: [String: Any]) -> [DailyLevel] {
        let years = (spec["years"] as! [Int])
        let gap = Set((spec["gapYears"] as? [Int]) ?? [])
        var cal = Calendar(identifier: .gregorian); cal.timeZone = utc
        var out: [DailyLevel] = []
        func add(_ d: Date) {
            let y = cal.component(.year, from: d)
            let n = cal.ordinality(of: .day, in: .year, for: d)!
            if gap.contains(y) && n > 300 { return }
            let k = (y * 7 + n * 3) % 11
            out.append(DailyLevel(date: LakeLevelCalendar.dayString(d, timeZone: utc), ft: 100 + Double(k) * 0.1 + Double(y - 2000) * 0.01, sourceId: "fx"))
        }
        for y in years[0]...years[1] {
            var d = LakeLevelCalendar.date(year: y, month: 1, day: 1)
            while cal.component(.year, from: d) == y { add(d); d = d.addingTimeInterval(86_400) }
        }
        if let pt = spec["partialYear"] as? [String: Any] {
            let end = LakeLevelCalendar.dayString(iso("\(pt["through"] as! String)T00:00:00Z"), timeZone: utc)
            var d = LakeLevelCalendar.date(year: pt["year"] as! Int, month: 1, day: 1)
            while LakeLevelCalendar.dayString(d, timeZone: utc) <= end { add(d); d = d.addingTimeInterval(86_400) }
        }
        return out
    }

    // MARK: conformance (shared with the Python mirror)

    func testConformanceTier() throws {
        for c in try cases(fixture(), "tier") {
            XCTAssertEqual(LakeLevelBaseline.tier(basisYears: c["basisYears"] as! Int).rawValue, c["expect"] as? String, "\(c)")
        }
    }

    func testConformanceHistorical() throws {
        for c in try cases(fixture(), "historical") {
            let e = c["expect"] as! [String: Any]
            let (state, flags) = LakeLevelClassifier.historicalState(
                current: num(c["current"])!, p02: num(c["p02"])!, p10: num(c["p10"])!, p90: num(c["p90"])!, p98: num(c["p98"])!,
                tier: Self.tier(c["tier"] as! String))
            XCTAssertEqual(state.rawValue, e["state"] as? String, "\(c)")
            XCTAssertEqual(flags, e["flags"] as? [String], "\(c)")
        }
    }

    func testConformanceTrend() throws {
        for c in try cases(fixture(), "trend") {
            let e = c["expect"] as! [String: Any]
            var day: LakeBaselineDay?
            if let p95 = num(c["rateP95"]) {
                let p50 = num(c["rateP50"])
                let grid = LakeLevelBaseline.grid.map { g -> Double in
                    guard let p50 else { return p95 }
                    return g <= 50 ? p50 : g >= 95 ? p95 : p50 + (g - 50) / 45 * (p95 - p50)
                }
                day = LakeBaselineDay(doy: 1, n: 0, levelQ: nil, rateN: 100, rateQ: grid)
            }
            let r = LakeLevelClassifier.trend(delta24h: num(c["delta24h"]), delta72h: num(c["delta72h"]), day: day, regulated: c["regulated"] as! Bool)
            XCTAssertEqual(r.0.rawValue, e["state"] as? String, "\(c)")
            if let want = num(e["rapidThresholdFt"]) { XCTAssertEqual(try XCTUnwrap(r.rapidThreshold), want, accuracy: 1e-12, "\(c)") }
            else { XCTAssertNil(r.rapidThreshold, "\(c)") }
            XCTAssertEqual(r.flags, e["flags"] as? [String], "\(c)")
        }
    }

    func testConformanceBaseline() throws {
        for c in try cases(fixture(), "baseline") {
            let name = c["name"] as! String
            let e = c["expect"] as! [String: Any]
            let b = LakeBaselineBuilder.build(lakeId: "Fx|ST", daily: fixtureSeries(c["series"] as! [String: Any]), today: c["today"] as! String,
                                              poolBasisIsFullPool: c["poolBasisIsFullPool"] as! Bool)
            XCTAssertEqual(b.completeYears.count, e["completeYears"] as? Int, name)
            XCTAssertEqual(b.basisYears.count, e["basisYears"] as? Int, name)
            XCTAssertEqual(b.basisYears.first, e["firstBasisYear"] as? Int, name)
            XCTAssertEqual(b.status.rawValue, e["status"] as? String, name)
            XCTAssertEqual(b.historicalTier.rawValue, e["tier"] as? String, name)
            for (doy, v) in e["doy"] as! [String: [String: Any]] {
                let day = try XCTUnwrap(b.day(Int(doy)!), name)
                XCTAssertEqual(day.n, v["levelN"] as? Int, "\(name) doy \(doy)")
                XCTAssertEqual(day.rateN, v["rateN"] as? Int, "\(name) doy \(doy)")
                let q = try XCTUnwrap(day.levelQ, name)
                for (p, want) in zip([2.0, 10, 50, 90, 98], v["level"] as! [Double]) {
                    XCTAssertEqual(try XCTUnwrap(LakeBaselineBuilder.at(p, q)), want, accuracy: 1e-9, "\(name) doy \(doy) p\(p)")
                }
                if let want = num(v["rateP95"]) {
                    XCTAssertEqual(try XCTUnwrap(LakeBaselineBuilder.at(95, try XCTUnwrap(day.rateQ, name))), want, accuracy: 1e-9, "\(name) doy \(doy) rate")
                }
            }
        }
    }

    // MARK: versions

    func testVersionsAreV2() {
        XCTAssertEqual(LakeBrainSpec.modelVersion, "lake-level-rules-v2")
        XCTAssertEqual(LakeBrainSpec.baselineMethod, "doy15-percentile-v2")
        let b = LakeBaselineBuilder.build(lakeId: "T|ST", daily: synthetic(years: 2010...2025), today: "2026-06-01")
        XCTAssertEqual(b.method, "doy15-percentile-v2")
        XCTAssertTrue(b.baselineVersion.hasPrefix("doy15-percentile-v2@"), "a method bump yields a new artifact version, so the old artifact is not reused")
    }

    // MARK: R1 tiers

    func synthetic(years: ClosedRange<Int>) -> [DailyLevel] {
        var out: [DailyLevel] = []
        var d = LakeLevelCalendar.date(year: years.lowerBound, month: 1, day: 1)
        let end = LakeLevelCalendar.date(year: years.upperBound, month: 12, day: 31)
        while d <= end {
            let day = LakeLevelCalendar.dayString(d, timeZone: utc)
            let doy = Double(LakeLevelCalendar.doy365(day)!)
            out.append(DailyLevel(date: day, ft: 600 + 3 * sin(doy / 365 * 2 * .pi) + Double(Int(day.prefix(4))! % 7) * 0.1, sourceId: "test"))
            d = d.addingTimeInterval(86_400)
        }
        return out
    }

    func baseline(years n: Int, regulated: Bool = true) -> LakeLevelBaseline {
        LakeBaselineBuilder.build(lakeId: "T|ST", daily: synthetic(years: (2026 - n)...2025), today: "2026-06-01", poolBasisIsFullPool: regulated)
    }

    func testTierBoundaries() {
        let expect: [(Int, LakeHistoricalTier)] = [(4, .none), (5, .provisional), (9, .provisional), (10, .standard), (14, .standard), (15, .full)]
        for (n, t) in expect { XCTAssertEqual(baseline(years: n).historicalTier, t, "\(n) years") }
    }

    func testBaselineStatusSemanticsAreUnchangedByTiers() {
        XCTAssertEqual(baseline(years: 4).status, .limited)
        XCTAssertEqual(baseline(years: 5).status, .sufficient)
        XCTAssertEqual(baseline(years: 14).status, .sufficient)
        XCTAssertEqual(baseline(years: 3).status, .limited)
        XCTAssertEqual(baseline(years: 1).status, .insufficient)
    }

    func testBasisYearCapByPoolBasis() {
        let daily = synthetic(years: 1950...2025)
        let reg = LakeBaselineBuilder.build(lakeId: "T|ST", daily: daily, today: "2026-06-01", poolBasisIsFullPool: true)
        let nat = LakeBaselineBuilder.build(lakeId: "T|ST", daily: daily, today: "2026-06-01", poolBasisIsFullPool: false)
        XCTAssertEqual(reg.basisYears.count, 30)
        XCTAssertEqual(nat.basisYears.count, 60)
        XCTAssertEqual(nat.basisYears.first, 1966)
        XCTAssertEqual(reg.historicalTier, .full); XCTAssertEqual(nat.historicalTier, .full)
    }

    // MARK: classifier end-to-end (evaluate)

    func ref() -> LevelSeriesRef { LevelSeriesRef(provider: .usgs, capability: .directOperatorPool, station: "P", series: "00062", cadenceMin: 60, lagMin: 60) }

    func evaluate(readings: [LevelObservation], baseline: LakeLevelBaseline?, regulated: Bool = true, now: Date) -> LakeLevelStateRecord {
        let r = ref()
        let binding = LakeSourceBinding(lakeId: "Test|ST", status: .reviewed, capability: .directOperatorPool, live: [r], history: [], guide: nil, datum: nil,
                                        timeZone: "UTC", damName: nil, riverSystem: nil, topOfGatesFt: nil, hydropower: nil, floodControl: nil,
                                        operatorName: nil, reviewedAt: nil, note: nil)
        return LakeLevelClassifier.evaluate(LakeLevelInputs(
            lakeId: "Test|ST", binding: binding, capabilityIfUnbound: .noSource, fullPoolFt: 600, poolBasisIsFullPool: regulated,
            poolConfidenceLow: false, live: [(r, readings, nil)], archivedHourly: [], guide: nil, baseline: baseline, now: now, processingVersion: "test"))
    }

    func hourly(hours: Int, endLevel: Double, perHour: Double) -> [LevelObservation] {
        let end = iso("2026-06-01T12:00:00Z")
        return (0...hours).map { LevelObservation(at: end.addingTimeInterval(-Double(hours - $0) * 3600), ft: endLevel - Double(hours - $0) * perHour) }
    }
    let now = ISO8601DateFormatter().date(from: "2026-06-01T12:30:00Z")!

    func testVeryUnusualSuppressedBelowFullTier() {
        let flat = hourly(hours: 100, endLevel: 580, perHour: 0)         // far outside p02-p98 of a ~600 ft lake
        let prov = evaluate(readings: flat, baseline: baseline(years: 7), now: now)
        XCTAssertEqual(prov.historicalState, .unusual)
        XCTAssertEqual(prov.historicalTier, .provisional)
        XCTAssertTrue(prov.provenance.qualityFlags!.contains("historicalProvisional"))
        let std = evaluate(readings: flat, baseline: baseline(years: 12), now: now)
        XCTAssertEqual(std.historicalState, .unusual)
        XCTAssertEqual(std.historicalTier, .standard)
        XCTAssertFalse(std.provenance.qualityFlags!.contains("historicalProvisional"))
        let full = evaluate(readings: flat, baseline: baseline(years: 16), now: now)
        XCTAssertEqual(full.historicalState, .veryUnusual)
        XCTAssertEqual(full.historicalTier, .full)
        let none = evaluate(readings: flat, baseline: baseline(years: 4), now: now)
        XCTAssertEqual(none.historicalState, .insufficientHistory)
        XCTAssertNil(none.seasonalPercentile)
        XCTAssertEqual(none.historicalTier, LakeHistoricalTier.none)
        // baselineStatus still reads as in v1 (rubric facts unchanged)
        XCTAssertEqual(prov.baselineStatus, .sufficient); XCTAssertEqual(none.baselineStatus, .limited)
    }

    func testNaturalVsRegulatedStableFloor() {
        // 0.18 ft over 72 h = 0.06 ft/day: above the natural floor (0.05), inside the regulated one (0.10)
        let s = hourly(hours: 100, endLevel: 600, perHour: 0.0025)
        XCTAssertEqual(evaluate(readings: s, baseline: nil, regulated: true, now: now).trendState, .stable)
        XCTAssertEqual(evaluate(readings: s, baseline: nil, regulated: false, now: now).trendState, .rising)
        let down = hourly(hours: 100, endLevel: 600, perHour: -0.0025)
        XCTAssertEqual(evaluate(readings: down, baseline: nil, regulated: false, now: now).trendState, .falling)
    }

    func testRapidThresholdIsMaxOfSeasonalP95AndQuarterFoot() {
        let b = baseline(years: 16)                                      // smooth seasonal lake: seasonal p95 of |Δ24h| is well under 0.25 ft
        let p95 = LakeBaselineBuilder.at(95, b.day(152)!.rateQ!)!
        XCTAssertLessThan(p95, 0.25)
        let fast = evaluate(readings: hourly(hours: 100, endLevel: 600, perHour: 0.02), baseline: b, now: now)   // +0.48 ft / 24 h
        XCTAssertEqual(fast.trendState, .risingRapidly)
        XCTAssertEqual(fast.rapidChangeThresholdFt, 0.25)
        let mid = evaluate(readings: hourly(hours: 100, endLevel: 600, perHour: 0.0083), baseline: b, now: now)  // ≈ +0.20 ft / 24 h, ≈ 0.6 ft / 72 h
        XCTAssertEqual(mid.trendState, .rising, "0.20 ft/24 h is under the 0.25 ft RAPID floor even though it exceeds the seasonal p95")
        XCTAssertGreaterThan(abs(mid.change!.h24!), p95)
        XCTAssertNil(mid.provenance.qualityFlags?.first { $0 == "rateBaselineLimited" })
        // a seasonal p95 above the floor wins
        let day = LakeBaselineDay(doy: 152, n: 0, levelQ: nil, rateN: 100, rateQ: Array(repeating: 0.40, count: LakeLevelBaseline.grid.count))
        let t = LakeLevelClassifier.trend(delta24h: 0.35, delta72h: 0.9, day: day, regulated: true)
        XCTAssertEqual(t.0, .rising); XCTAssertEqual(t.rapidThreshold, 0.40)
    }

    func testNoRateBaselineStillHasTheFloorAndSaysSo() {
        let r = evaluate(readings: hourly(hours: 100, endLevel: 600, perHour: 0.02), baseline: nil, now: now)
        XCTAssertEqual(r.trendState, .risingRapidly)
        XCTAssertEqual(r.rapidChangeThresholdFt, 0.25)
        XCTAssertTrue(r.provenance.qualityFlags!.contains("rateBaselineLimited"))
    }

    func testSeventyTwoHourMeanAndTwentyFourHourFallbackFlag() {
        // ≥ 72 h of readings: mean72 is used, no fallback flag
        let long = evaluate(readings: hourly(hours: 100, endLevel: 600, perHour: 0.0025), baseline: nil, now: now)
        XCTAssertNotNil(long.change?.d3)
        XCTAssertFalse(long.provenance.qualityFlags!.contains("trend24hFallback"))
        // only 48 h (e.g. the TVA observed-data feed on its own): fall back to the 24 h change and say so
        let short = evaluate(readings: hourly(hours: 48, endLevel: 600, perHour: 0.005), baseline: nil, now: now)   // 0.12 ft / 24 h
        XCTAssertNil(short.change?.d3)
        XCTAssertTrue(short.provenance.qualityFlags!.contains("trend24hFallback"))
        XCTAssertEqual(short.trendState, .rising)
        // a 72 h mean that is flat while the last day moved 0.12 ft is STABLE; the 24 h fallback alone would call it RISING
        var s = hourly(hours: 100, endLevel: 600, perHour: 0)
        for i in 76...100 { s[i].ft += 0.005 * Double(i - 76) }          // +0.12 ft in the last 24 h; the level 72 h ago is ~0.06 ft below
        let r = evaluate(readings: s, baseline: nil, now: now)
        XCTAssertEqual(r.trendState, .stable)
    }

    func testSeasonalMedianTermIsRemoved() {
        // v1: STABLE at or below max(0.10, seasonal p50 |Δ24h|). v2: only the floor. A 0.15 ft/day trend is RISING even if the seasonal median is 0.20.
        let day = LakeBaselineDay(doy: 1, n: 0, levelQ: nil, rateN: 100,
                                  rateQ: LakeLevelBaseline.grid.map { $0 <= 50 ? 0.20 : $0 >= 95 ? 0.50 : 0.20 + ($0 - 50) / 45 * 0.30 })
        XCTAssertEqual(LakeLevelClassifier.trend(delta24h: 0.15, delta72h: 0.45, day: day, regulated: true).0, .rising)
    }

    func testProxyNeverPublishesRapid() {
        var r = ref(); r.capability = .nearbyGaugeProxy
        let binding = LakeSourceBinding(lakeId: "Test|ST", status: .reviewed, capability: .nearbyGaugeProxy, live: [r], history: [], guide: nil, datum: nil,
                                        timeZone: "UTC", damName: nil, riverSystem: nil, topOfGatesFt: nil, hydropower: nil, floodControl: nil,
                                        operatorName: nil, reviewedAt: nil, note: nil)
        let s = LakeLevelClassifier.evaluate(LakeLevelInputs(
            lakeId: "Test|ST", binding: binding, capabilityIfUnbound: .noSource, fullPoolFt: nil, poolBasisIsFullPool: false, poolConfidenceLow: true,
            live: [(r, hourly(hours: 100, endLevel: 3, perHour: 0.02), nil)], archivedHourly: [], guide: nil, baseline: baseline(years: 16), now: now, processingVersion: "t"))
        XCTAssertEqual(s.trendState, .rising)
        XCTAssertNil(s.rapidChangeThresholdFt); XCTAssertNil(s.rateOfChangePercentile)
    }
}
