import XCTest
@testable import SectorEngine
@testable import LakeBrain

/// The 0.1 ft NWS RVD archive rows (sourceId "nws:rvd…") feed the LEVEL climatology but never the |Δ24h| rate climatology.
final class LakeBaselineRateFilterTests: XCTestCase {

    private func series(years: ClosedRange<Int>, stepFt: Double, sourceId: String, start: Double = 500) -> [DailyLevel] {
        var out: [DailyLevel] = []
        var ft = start
        var up = true
        let cal = Calendar(identifier: .gregorian)
        var comps = DateComponents(); comps.year = years.lowerBound; comps.month = 1; comps.day = 1
        var d = cal.date(from: comps)!
        let end = cal.date(from: DateComponents(year: years.upperBound, month: 12, day: 31))!
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"; f.timeZone = TimeZone(identifier: "UTC")
        while d <= end {
            out.append(DailyLevel(date: f.string(from: d), ft: ft, sourceId: sourceId))
            if ft > start + 1 { up = false } else if ft < start - 1 { up = true }
            ft += up ? stepFt : -stepFt
            d = cal.date(byAdding: .day, value: 1, to: d)!
        }
        return out
    }

    func testRvdYearsStayInLevelClimatologyButNotInRateClimatology() {
        let coarse = series(years: 2010...2019, stepFt: 0.5, sourceId: "nws:rvdhun:WLSA1")       // big steps, low resolution
        let fine = series(years: 2020...2025, stepFt: 0.02, sourceId: "tva:operating-guide:WLSA1")
        let b = LakeBaselineBuilder.build(lakeId: "Test|AL", daily: coarse + fine, today: "2026-06-15", poolBasisIsFullPool: true)
        let day = b.days[166]
        XCTAssertGreaterThan(day.n, 0)
        XCTAssertEqual(b.basisYears.count, 16)                                                  // all 16 complete years feed the level climatology
        let p95 = LakeBaselineBuilder.at(95, day.rateQ ?? [])
        XCTAssertNotNil(p95)
        XCTAssertLessThan(p95 ?? 99, 0.05, "rate p95 must come from the 0.02 ft/day years only, not the 0.5 ft/day RVD years")
    }

    func testNonRvdSourcesAreUnchanged() {
        let all = series(years: 2010...2025, stepFt: 0.5, sourceId: "cwms:SAS:Hartwell.Elev")
        let b = LakeBaselineBuilder.build(lakeId: "Test|SC", daily: all, today: "2026-06-15", poolBasisIsFullPool: true)
        XCTAssertGreaterThan(LakeBaselineBuilder.at(95, b.days[166].rateQ ?? []) ?? 0, 0.4)
    }
}
