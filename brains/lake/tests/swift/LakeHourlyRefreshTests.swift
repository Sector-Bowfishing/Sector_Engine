//
//  LakeHourlyRefreshTests.swift
//  Lake runs about hourly (2026-11-21). A run whose history archive already holds yesterday reads only the newest level,
//  the guide and the rain: it calls no operator daily feed and rewrites neither the history file nor the baseline.
//

import XCTest
@testable import SectorEngine
@testable import LakeBrain

/// FakeFeeds plus counters for the daily pulls and a fixed rain answer.
final class HourlyCountingFeeds: LakeLevelFeeds, @unchecked Sendable {
    let base = FakeFeeds()
    var now: Date { base.now }
    let rain: Double?
    private let lock = NSLock()
    private var d = 0
    var dailyCalls: Int { lock.withLock { d } }
    init(rain: Double?) { self.rain = rain }
    func recent(_ ref: LevelSeriesRef, hours: Int, now: Date) async -> FeedResult { await base.recent(ref, hours: hours, now: now) }
    func guide(_ source: LakeGuideSource, day: String, timeZone: TimeZone) async -> LakeGuideForDay? { await base.guide(source, day: day, timeZone: timeZone) }
    func daily(_ source: LakeHistorySource, since: String?, now: Date, timeZone: TimeZone) async -> [DailyLevel]? {
        lock.withLock { d += 1 }
        return [DailyLevel(date: "2026-05-31", ft: 593.9, sourceId: "fresh")]
    }
    func archivedHourly(_ source: LakeHistorySource, days: Int, now: Date, timeZone: TimeZone) async -> [LevelObservation] { [] }
    func rainNext12h(lat: Double, lon: Double, now: Date) async -> Double? { rain }
}

final class LakeHourlyRefreshTests: XCTestCase {

    func lakeWithDailyHistory() throws -> (DirectoryLake, LakeSourceBinding) {
        let b = try XCTUnwrap(LakeSourceBindings.reviewed.first { b in
            b.history.contains { if case .sharedTVAArchive = $0 { return false }; return true }
        })
        return (try XCTUnwrap(LakeDirectory.all.first { $0.id == b.lakeId }), b)
    }

    func testACurrentArchiveSkipsTheDailyPullsAndRewritesNoHistory() async throws {
        let (lake, binding) = try lakeWithDailyHistory()
        let dir = NSTemporaryDirectory() + "lb-hourly-\(UUID().uuidString)"
        let archive = LocalLakeBrainArchive(directory: dir)
        let tz = TimeZone(identifier: binding.timeZone) ?? TimeZone(identifier: "UTC")!
        let feeds = HourlyCountingFeeds(rain: 0)
        let yesterday = LakeLevelCalendar.dayString(feeds.now.addingTimeInterval(-86_400), timeZone: tz)
        let seeded = LakeDailyHistory.encode([DailyLevel(date: yesterday, ft: 593.8, sourceId: "archive")])
        try await archive.write(LakeDailyHistory.path(lake.id), seeded, contentType: "text/csv")

        let r = await LakeBrainRunner.evaluateLake(lake, feeds: feeds, archive: archive, presence: nil, published: nil,
                                                    previousProfile: nil, options: LakeBrainRunOptions(), now: feeds.now)
        XCTAssertEqual(feeds.dailyCalls, 0, "no operator daily pull when the archive holds yesterday")
        let after = try await archive.read(LakeDailyHistory.path(lake.id))
        XCTAssertEqual(after, seeded, "the history file is not rewritten")
        let s = try XCTUnwrap(r.state)
        XCTAssertNotNil(s.freshness.freshUntil, "the newest level is still read and published")
    }

    func testAnArchiveThatIsBehindStillPullsTheRecentTail() async throws {
        let (lake, _) = try lakeWithDailyHistory()
        let archive = LocalLakeBrainArchive(directory: NSTemporaryDirectory() + "lb-hourly-\(UUID().uuidString)")
        let feeds = HourlyCountingFeeds(rain: 0)
        try await archive.write(LakeDailyHistory.path(lake.id),
                                LakeDailyHistory.encode([DailyLevel(date: "2026-05-20", ft: 593.8, sourceId: "archive")]), contentType: "text/csv")
        _ = await LakeBrainRunner.evaluateLake(lake, feeds: feeds, archive: archive, presence: nil, published: nil,
                                               previousProfile: nil, options: LakeBrainRunOptions(), now: feeds.now)
        XCTAssertGreaterThan(feeds.dailyCalls, 0)
    }

    func testTheRainSignalReachesThePublishedWindow() async throws {
        let (lake, _) = try lakeWithDailyHistory()
        let dry = await LakeBrainRunner.evaluateLake(lake, feeds: HourlyCountingFeeds(rain: 0), archive: nil, presence: nil, published: nil,
                                                     previousProfile: nil, options: LakeBrainRunOptions(), now: FakeFeeds().now)
        let wet = await LakeBrainRunner.evaluateLake(lake, feeds: HourlyCountingFeeds(rain: 1.5), archive: nil, presence: nil, published: nil,
                                                     previousProfile: nil, options: LakeBrainRunOptions(), now: FakeFeeds().now)
        let d = try XCTUnwrap(dry.state?.freshness), w = try XCTUnwrap(wet.state?.freshness)
        XCTAssertTrue(w.refreshReason.hasPrefix("FAST"), w.refreshReason)
        let wu = try XCTUnwrap(w.freshUntil), du = try XCTUnwrap(d.freshUntil)
        XCTAssertLessThanOrEqual(wu, du, "rain never lengthens the window")
    }
}
