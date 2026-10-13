//
//  LakePredictionLedgerTests.swift
//  Lake Brain prospective prediction ledger: synthetic lakes and series only. Fakes and temp directories;
//  nothing here touches a database or a bucket.
//

import XCTest
@testable import SectorEngine

/// Deterministic feeds: hourly level ending 30 min before `now`, a fixed daily history, a fixed guide.
final class LedgerFeeds: LakeLevelFeeds, @unchecked Sendable {
    let history: [DailyLevel]
    let liveFt: Double?
    let slopePerHour: Double
    init(history: [DailyLevel], liveFt: Double? = 600.2, slopePerHour: Double = 0) {
        self.history = history; self.liveFt = liveFt; self.slopePerHour = slopePerHour
    }
    func recent(_ ref: LevelSeriesRef, hours: Int, now: Date) async -> FeedResult {
        guard let ft = liveFt else { return FeedResult(observations: [], error: nil) }
        let end = now.addingTimeInterval(-1800)
        return FeedResult(observations: (0..<hours).map { i in
            LevelObservation(at: end.addingTimeInterval(-Double(hours - 1 - i) * 3600), ft: ft - Double(hours - 1 - i) * slopePerHour)
        }, error: nil)
    }
    func guide(_ source: LakeGuideSource, day: String, timeZone: TimeZone) async -> LakeGuideForDay? {
        LakeGuideForDay(guideFt: 600, zone: LakeOperatingZone(bottomFt: 595, topFt: 605, bottomLabel: "b", topLabel: "t", source: "fake"),
                        levels: [], topOfGatesFt: nil, floodPoolBottomFt: nil, source: "fake")
    }
    func daily(_ source: LakeHistorySource, since: String?, now: Date, timeZone: TimeZone) async -> [DailyLevel]? { history }
    func archivedHourly(_ source: LakeHistorySource, days: Int, now: Date, timeZone: TimeZone) async -> [LevelObservation] { [] }
}

/// Records every write; optionally refuses writes under a prefix.
final class RecordingArchive: LakeBrainArchive, @unchecked Sendable {
    struct Boom: Error, CustomStringConvertible { var description: String { "boom" } }
    let failPrefix: String?
    private let lock = NSLock()
    private var store: [String: Data] = [:]
    private var writesLog: [String] = []
    var writes: [String] { lock.withLock { writesLog } }
    var uri: String { "gs://fake-never-real" }
    init(failPrefix: String? = nil, seed: [String: Data] = [:]) { self.failPrefix = failPrefix; store = seed }
    func read(_ path: String) async throws -> Data? { lock.withLock { store[path] } }
    func write(_ path: String, _ data: Data, contentType: String) async throws {
        if let p = failPrefix, path.hasPrefix(p) { throw Boom() }
        lock.withLock { store[path] = data; writesLog.append(path) }
    }
    func get(_ path: String) -> Data? { lock.withLock { store[path] } }
}

final class LakePredictionLedgerTests: XCTestCase {

    let utc = TimeZone(identifier: "UTC")!
    func iso(_ s: String) -> Date { ISO8601DateFormatter().date(from: s)! }

    /// 600 ft + 3 ft annual sine + (year % 7) * 0.1; complete years only.
    func history(_ years: ClosedRange<Int>) -> [DailyLevel] {
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

    func directory(_ id: String) throws -> DirectoryLake { try XCTUnwrap(LakeDirectory.all.first { $0.id == id }) }

    func evaluate(_ lakeId: String, history h: [DailyLevel], now: Date, liveFt: Double? = 600.2) async throws -> LakeBrainLakeResult {
        var o = LakeBrainRunOptions(); o.force = true
        return await LakeBrainRunner.evaluateLake(try directory(lakeId), feeds: LedgerFeeds(history: h, liveFt: liveFt), archive: nil, presence: nil,
                                                  published: nil, previousProfile: nil, options: o, now: now)
    }

    func record(_ r: LakeBrainLakeResult, runId: String = "r1", now: Date) throws -> LakePredictionRecord {
        let lake = try directory(r.lakeId)
        return try XCTUnwrap(LakePredictionLedger.record(for: r, binding: LakeSourceBindings.binding(for: r.lakeId),
                                                         regulated: lake.poolBasis.map { $0 == .fullPool }, poolBasis: lake.poolBasis?.rawValue,
                                                         runId: runId, generatedAt: now))
    }

    // MARK: record content

    func testTVALakeRecordWithProvisionalTier() async throws {
        let now = iso("2026-06-01T12:30:00Z")
        let r = try await evaluate("Guntersville|AL", history: history(2019...2025), now: now)
        let rec = try record(r, now: now)
        XCTAssertEqual(rec.ledgerVersion, "lake-prediction-ledger-v1")
        XCTAssertEqual(rec.runId, "r1")
        XCTAssertEqual(rec.generatedAt, "2026-06-01T12:30:00Z")
        XCTAssertEqual(rec.lakeId, "Guntersville|AL")
        XCTAssertEqual(rec.rulesVersion, "lake-level-rules-v2")
        XCTAssertEqual(rec.baselineMethod, "doy15-percentile-v2")
        XCTAssertEqual(rec.baselineVersion, r.baseline?.baselineVersion)
        XCTAssertEqual(rec.historicalTier, "PROVISIONAL")
        XCTAssertEqual(rec.baselineStatus, "SUFFICIENT")
        XCTAssertEqual(rec.bindingVersion, LakeSourceBindings.version)
        XCTAssertEqual(rec.bindingStatus, "REVIEWED")
        XCTAssertEqual(rec.sourceId, "tva:GVDA1")
        XCTAssertEqual(rec.provider, "tva")
        XCTAssertEqual(rec.kind, "OBSERVED")
        XCTAssertEqual(rec.timeZone, "America/Chicago")
        XCTAssertEqual(rec.baseDate, "2026-06-01")          // 12:00Z is 07:00 in Chicago
        XCTAssertEqual(rec.observation.at, "2026-06-01T12:00:00Z")
        XCTAssertEqual(rec.observation.ft, 600.2)
        XCTAssertEqual(rec.labels.levelState, "IN_ZONE")
        XCTAssertEqual(rec.labels.floodPoolState, "UNKNOWN")
        XCTAssertEqual(rec.stableFloorFt, 0.10)               // Guntersville is a regulated fullPool lake
        XCTAssertEqual(rec.poolBasis, "fullPool")
        XCTAssertTrue(rec.flags.contains("historicalProvisional"))
        XCTAssertEqual(rec.horizons.map(\.days), [1, 7, 30])
        XCTAssertEqual(rec.horizons.map(\.targetDate), ["2026-06-02", "2026-06-08", "2026-07-01"])
        XCTAssertEqual(rec.horizons.map(\.doy), [153, 159, 182])
        // Bands equal the baseline grid for exactly those days of year.
        let b = try XCTUnwrap(r.baseline)
        for h in rec.horizons {
            let q = try XCTUnwrap(b.day(h.doy)?.levelQ)
            let band = try XCTUnwrap(h.band)
            XCTAssertEqual(band.p02, q[LakeLevelBaseline.grid.firstIndex(of: 2)!])
            XCTAssertEqual(band.p10, q[LakeLevelBaseline.grid.firstIndex(of: 10)!])
            XCTAssertEqual(band.p50, q[LakeLevelBaseline.grid.firstIndex(of: 50)!])
            XCTAssertEqual(band.p90, q[LakeLevelBaseline.grid.firstIndex(of: 90)!])
            XCTAssertEqual(band.p98, q[LakeLevelBaseline.grid.firstIndex(of: 98)!])
            XCTAssertEqual(h.bandN, b.day(h.doy)?.n)
            XCTAssertLessThan(band.p02, band.p10); XCTAssertLessThan(band.p10, band.p50)
            XCTAssertLessThan(band.p50, band.p90); XCTAssertLessThan(band.p90, band.p98)
            // Independent sanity: the synthetic series is 600 + 3 sin(doy) + 0.0...0.6, so p50 sits near the sine + 0.3.
            XCTAssertEqual(band.p50, 600 + 3 * sin(Double(h.doy) / 365 * 2 * .pi) + 0.3, accuracy: 0.5)
            XCTAssertNotNil(h.rateP95)
        }
    }

    func testCWMSLakeRecordWithFullTier() async throws {
        let now = iso("2026-06-01T15:30:00Z")
        let r = try await evaluate("Lake Hartwell|SC", history: history(1996...2025), now: now)
        let rec = try record(r, now: now)
        XCTAssertEqual(rec.historicalTier, "FULL")
        XCTAssertEqual(rec.provider, "cwms")
        XCTAssertTrue(rec.sourceId.hasPrefix("cwms:SAS:"))
        XCTAssertEqual(rec.timeZone, "America/New_York")
        XCTAssertEqual(rec.baseDate, "2026-06-01")            // 15:00Z is 11:00 EDT
        XCTAssertFalse(rec.flags.contains("historicalProvisional"))
        let rapid = try XCTUnwrap(rec.rapidThresholdFt)
        XCTAssertGreaterThanOrEqual(rapid, 0.25)
        XCTAssertEqual(rec.horizons.count, 3)
        XCTAssertEqual(rec.horizons.map(\.targetDate), ["2026-06-02", "2026-06-08", "2026-07-01"])
        let b = try XCTUnwrap(r.baseline)
        for h in rec.horizons {
            XCTAssertEqual(h.band?.p10, LakeBaselineBuilder.at(10, try XCTUnwrap(b.day(h.doy)?.levelQ)))
            XCTAssertEqual(h.rateP95, LakeBaselineBuilder.at(95, try XCTUnwrap(b.day(h.doy)?.rateQ)))
            XCTAssertEqual(h.bandN, b.day(h.doy)?.n)
        }
        // The stored threshold is the one the classifier used for today, not recomputed for the target.
        XCTAssertEqual(rec.rapidThresholdFt, r.state?.rapidChangeThresholdFt)
    }

    func testYearWrapAndLeapDayHorizonsFollowDoy365() async throws {
        let h = history(2000...2025)
        // Year wrap: 2026-12-20 +1/+7/+30 = 12-21 (355), 12-27 (361), 2027-01-19 (19). Chicago 12:00Z = 06:00 same day.
        var now = iso("2026-12-20T12:30:00Z")
        var rec = try record(try await evaluate("Guntersville|AL", history: h, now: now), now: now)
        XCTAssertEqual(rec.horizons.map(\.targetDate), ["2026-12-21", "2026-12-27", "2027-01-19"])
        XCTAssertEqual(rec.horizons.map(\.doy), [355, 361, 19])
        // Leap year: base 2028-02-28 +1 = Feb 29 (shares Feb 28's index 59), +7 = Mar 6 (65), +30 = Mar 29 (88).
        now = iso("2028-02-28T12:30:00Z")
        rec = try record(try await evaluate("Guntersville|AL", history: h, now: now), now: now)
        XCTAssertEqual(rec.horizons.map(\.targetDate), ["2028-02-29", "2028-03-06", "2028-03-29"])
        XCTAssertEqual(rec.horizons.map(\.doy), [59, 65, 88])
        // Feb 29 reads Feb 28's climatology (index 59), same as the classifier does for a Feb 29 observation.
        let leapResult = try await evaluate("Guntersville|AL", history: h, now: now)
        let leapBaseline = try XCTUnwrap(leapResult.baseline)
        XCTAssertEqual(rec.horizons[0].band?.p50, LakeBaselineBuilder.at(50, try XCTUnwrap(leapBaseline.day(59)?.levelQ)))
        // Non-leap: 2027-01-30 +30 = 2027-03-01 (doy 60); leap: 2028-01-30 +30 = 2028-02-29 (doy 59).
        XCTAssertEqual(LakePredictionLedger.addDays("2027-01-30", 30), "2027-03-01")
        XCTAssertEqual(LakeLevelCalendar.doy365("2027-03-01"), 60)
        XCTAssertEqual(LakePredictionLedger.addDays("2028-01-30", 30), "2028-02-29")
        XCTAssertEqual(LakeLevelCalendar.doy365("2028-02-29"), 59)
        XCTAssertEqual(LakePredictionLedger.addDays("2028-12-31", 1), "2029-01-01")
        XCTAssertEqual(LakePredictionLedger.addDays("2026-12-31", 30), "2027-01-30")
    }

    func testBandsOmittedWhenHistoryHasNoTierAndRateKeptWhenAvailable() async throws {
        let now = iso("2026-06-01T12:30:00Z")
        // 1 complete year: INSUFFICIENT, no level climatology at all.
        var r = try await evaluate("Guntersville|AL", history: history(2025...2025), now: now)
        var rec = try record(r, now: now)
        XCTAssertEqual(rec.baselineStatus, "INSUFFICIENT")
        XCTAssertEqual(rec.historicalTier, "NONE")
        XCTAssertEqual(rec.labels.historicalState, "INSUFFICIENT_HISTORY")
        XCTAssertTrue(rec.horizons.allSatisfy { $0.band == nil && $0.bandN == nil })
        XCTAssertEqual(rec.horizons.map(\.days), [1, 7, 30], "horizons are still recorded (target dates and trend claims)")
        // 3 complete years: LIMITED. The Brain publishes no historical claim at tier NONE, so no band is stored either.
        r = try await evaluate("Guntersville|AL", history: history(2023...2025), now: now)
        rec = try record(r, now: now)
        XCTAssertEqual(rec.baselineStatus, "LIMITED")
        XCTAssertEqual(rec.historicalTier, "NONE")
        XCTAssertTrue(rec.horizons.allSatisfy { $0.band == nil })
        XCTAssertTrue(rec.horizons.allSatisfy { $0.rateP95 != nil }, "the rate climatology exists with ≥ 20 samples")
        // The record encodes absent bands as absent keys.
        let line = String(decoding: try BrainJSON.encode(rec), as: UTF8.self)
        XCTAssertFalse(line.contains("\"band\""))
    }

    func testNoRecordWithoutObservationOrOnSkip() async throws {
        let now = iso("2026-06-01T12:30:00Z")
        let none = try await evaluate("Guntersville|AL", history: history(2019...2025), now: now, liveFt: nil)
        XCTAssertEqual(none.state?.kind, .unavailable)
        XCTAssertNil(LakePredictionLedger.record(for: none, binding: nil, regulated: true, poolBasis: "fullPool", runId: "r", generatedAt: now))
        // A skipped lake carries the published state and no baseline: not recomputed, not ledgered.
        var skipped = try await evaluate("Guntersville|AL", history: history(2019...2025), now: now)
        skipped.baseline = nil
        XCTAssertNil(LakePredictionLedger.record(for: skipped, binding: nil, regulated: true, poolBasis: "fullPool", runId: "r", generatedAt: now))
    }

    // MARK: path

    func testPathFormatAndRunIdSanitising() {
        XCTAssertEqual(LakePredictionLedger.path(generatedAt: iso("2026-06-01T12:30:00Z"), runId: "abc123"),
                       "predictions/2026/06/01/123000Z-abc123.jsonl")
        XCTAssertEqual(LakePredictionLedger.path(generatedAt: iso("2026-12-31T23:59:59Z"), runId: "x"),
                       "predictions/2026/12/31/235959Z-x.jsonl")
        XCTAssertEqual(LakePredictionLedger.path(generatedAt: iso("2027-01-02T03:04:05Z"), runId: "../evil id/"),
                       "predictions/2027/01/02/030405Z-evilid.jsonl")
        XCTAssertEqual(LakePredictionLedger.sanitizeRunId(""), "run")
        XCTAssertEqual(LakePredictionLedger.sanitizeRunId(String(repeating: "a", count: 90)).count, 40)
    }

    // MARK: byte stability

    func testEncodingIsByteStableSortedKeyedJSONLines() async throws {
        let now = iso("2026-06-01T12:30:00Z")
        let a = try await evaluate("Guntersville|AL", history: history(2019...2025), now: now)
        let b = try await evaluate("Lake Hartwell|SC", history: history(1996...2025), now: now)
        let recs = [try record(a, now: now), try record(b, now: now)]
        let d1 = try LakePredictionLedger.encode(recs)
        let d2 = try LakePredictionLedger.encode([try record(a, now: now), try record(b, now: now)])
        XCTAssertEqual(d1, d2)
        let text = String(decoding: d1, as: UTF8.self)
        XCTAssertTrue(text.hasSuffix("\n"))
        let lines = text.split(separator: "\n", omittingEmptySubsequences: false).dropLast()
        XCTAssertEqual(lines.count, 2)
        for l in lines {
            XCTAssertTrue(l.hasPrefix("{\"baseDate\":"), "keys are sorted")
            let obj = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(l.utf8)) as? [String: Any])
            XCTAssertEqual(obj["ledgerVersion"] as? String, "lake-prediction-ledger-v1")
            XCTAssertFalse(l.contains("\\/"), "no escaped slashes")
            // Round trip.
            let back = try JSONDecoder().decode(LakePredictionRecord.self, from: Data(l.utf8))
            XCTAssertEqual(try BrainJSON.encode(back), Data(l.utf8))
        }
        // Records stay in the given order.
        XCTAssertTrue(lines[0].contains("\"lakeId\":\"Guntersville|AL\""))
        XCTAssertTrue(lines[1].contains("\"lakeId\":\"Lake Hartwell|SC\""))
    }

    // MARK: golden fixture (the Python scorer parses the same file)

    /// Integer-driven, so every value is bit-identical on every platform (no transcendental functions).
    func goldenHistory(_ years: ClosedRange<Int>) -> [DailyLevel] {
        var out: [DailyLevel] = []
        var d = LakeLevelCalendar.date(year: years.lowerBound, month: 1, day: 1)
        let end = LakeLevelCalendar.date(year: years.upperBound, month: 12, day: 31)
        while d <= end {
            let day = LakeLevelCalendar.dayString(d, timeZone: utc)
            let k = (Int(day.prefix(4))! * 7 + LakeLevelCalendar.doy365(day)! * 3) % 11
            out.append(DailyLevel(date: day, ft: 600 + Double(k) * 0.1, sourceId: "golden"))
            d = d.addingTimeInterval(86_400)
        }
        return out
    }

    private static let goldenURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        .appendingPathComponent("jobs/lake-brain/ledger/fixtures/sample_ledger.jsonl")

    /// Regenerate with LEDGER_REGEN_GOLDEN=1 swift test --filter testGoldenLedgerMatchesCheckedInFixture, then review the diff.
    func testGoldenLedgerMatchesCheckedInFixture() async throws {
        let now = iso("2026-06-01T12:30:00Z")
        let tva = try await evaluate("Guntersville|AL", history: goldenHistory(2019...2025), now: now)
        let cwms = try await evaluate("Lake Hartwell|SC", history: goldenHistory(1996...2025), now: now)
        let data = try LakePredictionLedger.encode([try record(tva, runId: "golden", now: now), try record(cwms, runId: "golden", now: now)])
        if ProcessInfo.processInfo.environment["LEDGER_REGEN_GOLDEN"] == "1" {
            try FileManager.default.createDirectory(at: Self.goldenURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            try data.write(to: Self.goldenURL)
        }
        let golden = try Data(contentsOf: Self.goldenURL)
        XCTAssertEqual(String(decoding: data, as: UTF8.self), String(decoding: golden, as: UTF8.self))
    }

    // MARK: runner hook

    func runFleet(store: BrainStore, archive: LakeBrainArchive?, ledger: LakeBrainArchive?, now: Date, force: Bool = true,
                  lakeIds: [String] = ["Guntersville|AL", "Lake Hartwell|SC"], runId: String = "run1",
                  feeds: LedgerFeeds? = nil) async -> LakeBrainRunResult {
        var o = LakeBrainRunOptions()
        o.lakeIds = lakeIds; o.force = force; o.ledgerArchive = ledger; o.runId = runId
        return await LakeBrainRunner.run(store: store, feeds: feeds ?? LedgerFeeds(history: history(2000...2025)), archive: archive,
                                         presenceArchive: nil, options: o, now: now)
    }

    func tempDir() -> String { NSTemporaryDirectory() + "lake-ledger-test-\(UUID().uuidString)" }

    func testRunWritesOneObjectWithOneLinePerRecomputedLake() async throws {
        let now = iso("2026-06-01T12:30:00Z")
        let ledgerDir = tempDir()
        let ledger = LocalLakeBrainArchive(directory: ledgerDir)
        let store = LocalDirectoryStore(directory: tempDir(), brainId: LakeBrainSpec.brainId)
        let r = await runFleet(store: store, archive: nil, ledger: ledger, now: now)
        XCTAssertTrue(r.ok, r.writeError ?? "")
        XCTAssertEqual(r.ledgerObject, "predictions/2026/06/01/123000Z-run1.jsonl")
        XCTAssertEqual(r.ledgerRecords, 2)
        XCTAssertNil(r.ledgerWarning)
        let stored = try await ledger.read("predictions/2026/06/01/123000Z-run1.jsonl")
        let data = try XCTUnwrap(stored)
        let lines = String(decoding: data, as: UTF8.self).split(separator: "\n")
        XCTAssertEqual(lines.count, 2)
        XCTAssertTrue(lines[0].contains("\"lakeId\":\"Guntersville|AL\""))
        XCTAssertTrue(lines[1].contains("\"lakeId\":\"Lake Hartwell|SC\""))
        // Exactly one object in the whole ledger tree.
        let files = FileManager.default.enumerator(atPath: ledgerDir)?.allObjects.compactMap { $0 as? String }.filter { $0.hasSuffix(".jsonl") }
        XCTAssertEqual(files?.count, 1)
    }

    func testPureSkipRunWritesNoObject() async throws {
        let now = iso("2026-06-01T12:30:00Z")
        let ledger = RecordingArchive()
        let store = LocalDirectoryStore(directory: tempDir(), brainId: LakeBrainSpec.brainId)
        let first = await runFleet(store: store, archive: nil, ledger: ledger, now: now)
        XCTAssertEqual(first.ledgerRecords, 2)
        XCTAssertEqual(ledger.writes.count, 1)
        // Ten minutes later, nothing is due: plan() skips both lakes, so nothing is recomputed and nothing is written.
        let second = await runFleet(store: store, archive: nil, ledger: ledger, now: now.addingTimeInterval(600), force: false, runId: "run2")
        XCTAssertTrue(second.lakes.allSatisfy { $0.plan?.action == .skip }, "\(second.lakes.map { $0.plan?.reasons ?? [] })")
        XCTAssertNil(second.ledgerObject)
        XCTAssertEqual(second.ledgerRecords, 0)
        XCTAssertNil(second.ledgerWarning)
        XCTAssertEqual(ledger.writes.count, 1)
    }

    func testLedgerFailureNeverFailsOrChangesThePublish() async throws {
        let now = iso("2026-06-01T12:30:00Z")
        let storeA = LocalDirectoryStore(directory: tempDir(), brainId: LakeBrainSpec.brainId)
        let storeB = LocalDirectoryStore(directory: tempDir(), brainId: LakeBrainSpec.brainId)
        let good = await runFleet(store: storeA, archive: nil, ledger: RecordingArchive(), now: now)
        let bad = await runFleet(store: storeB, archive: nil, ledger: RecordingArchive(failPrefix: "predictions/"), now: now)
        XCTAssertTrue(bad.ok)
        XCTAssertEqual(bad.health, good.health)
        XCTAssertNil(bad.writeError)
        XCTAssertNil(bad.ledgerObject)
        XCTAssertEqual(bad.ledgerRecords, 0)
        XCTAssertEqual(bad.ledgerWarning, "ledger: boom")
        XCTAssertTrue(bad.archiveErrors.contains("ledger: boom"), "the job prints archiveErrors")
        // The RTDB writes are identical with and without a ledger failure.
        XCTAssertEqual(storeA.updates.count, storeB.updates.count)
        let flat = { (s: LocalDirectoryStore) in s.updates.flatMap { $0.map { "\($0.key)=\(String(decoding: $0.value, as: UTF8.self))" } }.sorted() }
        // Everything except the timing-dependent fields (durationMs inside health records).
        let strip = { (xs: [String]) in xs.filter { !$0.hasPrefix("health/") } }
        XCTAssertEqual(strip(flat(storeA)), strip(flat(storeB)))
    }

    func testExistingLedgerObjectIsNeverOverwritten() async throws {
        let now = iso("2026-06-01T12:30:00Z")
        let path = "predictions/2026/06/01/123000Z-run1.jsonl"
        let ledger = RecordingArchive(seed: [path: Data("original\n".utf8)])
        let store = LocalDirectoryStore(directory: tempDir(), brainId: LakeBrainSpec.brainId)
        let r = await runFleet(store: store, archive: nil, ledger: ledger, now: now)
        XCTAssertTrue(r.ok)
        XCTAssertEqual(ledger.get(path), Data("original\n".utf8))
        XCTAssertEqual(ledger.writes, [])
        XCTAssertNotNil(r.ledgerWarning)
    }

    func testDryRunNeverWritesTheLedgerToTheHistoryArchive() async throws {
        let now = iso("2026-06-01T12:30:00Z")
        let dir = tempDir()
        let store = LocalDirectoryStore(directory: dir, brainId: LakeBrainSpec.brainId)
        let bucketLike = RecordingArchive()          // stands in for gs://sector-lake-brain
        let r = await runFleet(store: store, archive: bucketLike, ledger: nil, now: now)
        XCTAssertTrue(r.ok)
        XCTAssertFalse(bucketLike.writes.contains { $0.hasPrefix("predictions/") })
        XCTAssertTrue(bucketLike.writes.contains { $0.hasPrefix("history/") }, "history still goes to the archive as before")
        XCTAssertEqual(r.ledgerObject, "predictions/2026/06/01/123000Z-run1.jsonl")
        XCTAssertTrue(FileManager.default.fileExists(atPath: dir + "/_ledger/" + (r.ledgerObject ?? "")), "dry run lands under <dir>/_ledger")
    }

    func testLiveRunWritesTheLedgerToTheHistoryArchive() async throws {
        let now = iso("2026-06-01T12:30:00Z")
        let store = InMemoryBrainStore(brainId: LakeBrainSpec.brainId)    // not a dry-run store
        let bucketLike = RecordingArchive()
        let r = await runFleet(store: store, archive: bucketLike, ledger: nil, now: now)
        XCTAssertTrue(r.ok, r.writeError ?? "")
        XCTAssertTrue(bucketLike.writes.contains("predictions/2026/06/01/123000Z-run1.jsonl"))
    }

    func testLedgerCanBeDisabledAndNoArchiveMeansNoLedger() async throws {
        let now = iso("2026-06-01T12:30:00Z")
        let ledger = RecordingArchive()
        var o = LakeBrainRunOptions(); o.lakeIds = ["Guntersville|AL"]; o.force = true; o.ledgerArchive = ledger; o.ledgerEnabled = false
        let off = await LakeBrainRunner.run(store: LocalDirectoryStore(directory: tempDir(), brainId: LakeBrainSpec.brainId),
                                            feeds: LedgerFeeds(history: history(2000...2025)), archive: nil, presenceArchive: nil, options: o, now: now)
        XCTAssertTrue(off.ok); XCTAssertNil(off.ledgerObject); XCTAssertEqual(ledger.writes, [])
        // Live store, no archive: nowhere to write, so nothing happens and nothing fails.
        let none = await runFleet(store: InMemoryBrainStore(brainId: LakeBrainSpec.brainId), archive: nil, ledger: nil, now: now)
        XCTAssertTrue(none.ok); XCTAssertNil(none.ledgerObject); XCTAssertNil(none.ledgerWarning)
    }

    func testUnavailableLakesAreNotLedgered() async throws {
        let now = iso("2026-06-01T12:30:00Z")
        let ledger = RecordingArchive()
        let store = LocalDirectoryStore(directory: tempDir(), brainId: LakeBrainSpec.brainId)
        let r = await runFleet(store: store, archive: nil, ledger: ledger, now: now,
                               feeds: LedgerFeeds(history: history(2000...2025), liveFt: nil))
        XCTAssertTrue(r.ok)
        XCTAssertNil(r.ledgerObject)
        XCTAssertEqual(ledger.writes, [])
    }
}
