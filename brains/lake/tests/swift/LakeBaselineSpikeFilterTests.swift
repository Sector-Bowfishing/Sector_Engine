import XCTest
@testable import SectorEngine
@testable import LakeBrain

/// A day far from its neighbours (a recording error, e.g. Beltzville 2025-02-10, 68 ft low) is left out of the baseline;
/// real movement, however fast, is kept.
final class LakeBaselineSpikeFilterTests: XCTestCase {

    private func days(from start: String, count: Int, ft: (Int) -> Double) -> [DailyLevel] {
        let utc = TimeZone(identifier: "UTC")!
        let p = start.split(separator: "-").compactMap { Int($0) }
        let d0 = LakeLevelCalendar.date(year: p[0], month: p[1], day: p[2], timeZone: utc)
        return (0..<count).map { i in
            DailyLevel(date: LakeLevelCalendar.dayString(d0.addingTimeInterval(Double(i) * 86_400), timeZone: utc), ft: ft(i), sourceId: "usgs:test")
        }
    }

    func testIsolatedDropIsExcluded() {
        let xs = days(from: "2025-02-01", count: 20) { $0 == 9 ? 558.39 : 626.5 }
        XCTAssertEqual(LakeBaselineBuilder.spikeDays(xs), ["2025-02-10"])
    }

    func testFastRealDrawdownIsKept() {
        // 2 ft a day for 20 days: fast for a reservoir, but every day agrees with its neighbours.
        let xs = days(from: "2025-03-01", count: 20) { 600 - 2 * Double($0) }
        XCTAssertTrue(LakeBaselineBuilder.spikeDays(xs).isEmpty)
    }

    func testTooFewNeighboursIsKept() {
        // A reading with gaps around it cannot be judged: kept.
        var xs = days(from: "2025-04-01", count: 3) { _ in 500 }
        xs.append(DailyLevel(date: "2025-04-10", ft: 450, sourceId: "usgs:test"))
        XCTAssertTrue(LakeBaselineBuilder.spikeDays(xs).isEmpty)
    }

    func testBuildLeavesSpikeOutAndReportsIt() {
        let xs = days(from: "2018-01-01", count: 365 * 7) { $0 == 2000 ? 400 : 500 + sin(Double($0) / 58) }
        let b = LakeBaselineBuilder.build(lakeId: "t", daily: xs, today: "2025-12-31")
        XCTAssertEqual(b.excludedSpikeDays?.count, 1)
        XCTAssertGreaterThan(b.days.compactMap { $0.levelQ?.first }.min() ?? 0, 498)
        XCTAssertEqual(b.observationCount, xs.count - 1)
    }

    func testCleanHistoryUnchanged() {
        let xs = days(from: "2018-01-01", count: 365 * 7) { 500 + sin(Double($0) / 58) }
        let b = LakeBaselineBuilder.build(lakeId: "t", daily: xs, today: "2025-12-31")
        XCTAssertNil(b.excludedSpikeDays)
        XCTAssertEqual(b.observationCount, xs.count)
    }
}
