import XCTest
@testable import SectorEngine

/// Baseline recompute policy, content fingerprint, immutable objects and the latest.json pointer (LakeBaselineStore).
final class LakeBaselineStoreTests: XCTestCase {

    let utc = TimeZone(identifier: "UTC")!
    let lake = "Test|AL"
    func iso(_ s: String) -> Date { ISO8601DateFormatter().date(from: s)! }

    /// Deterministic daily history from `from` through `through` (inclusive).
    func history(from: String = "2005-01-01", through: String) -> [DailyLevel] {
        var out: [DailyLevel] = []
        var d = iso(from + "T00:00:00Z")
        let end = iso(through + "T00:00:00Z")
        while d <= end {
            let day = LakeLevelCalendar.dayString(d, timeZone: utc)
            let doy = Double(LakeLevelCalendar.doy365(day)!)
            out.append(DailyLevel(date: day, ft: 600 + 3 * sin(doy / 365 * 2 * .pi) + Double(Int(day.prefix(4))! % 7) * 0.1, sourceId: "test"))
            d = d.addingTimeInterval(86_400)
        }
        return out
    }

    /// What history/{key}/daily.csv stores: deduplicated, two decimals. The artifact is built from this.
    func norm(_ h: [DailyLevel]) -> [DailyLevel] { LakeDailyHistory.decode(LakeDailyHistory.encode(h)) }

    func ensure(_ h: [DailyLevel], today: String, at: String, archive: LakeBrainArchive?, backfill: Bool = false) async -> LakeBaselineStore.Outcome {
        await LakeBaselineStore.ensure(lakeId: lake, merged: h, today: today, poolBasisIsFullPool: true, archive: archive,
                                       now: iso(at), forceRecompute: backfill)
    }

    func pointer(_ a: RecordingArchive) throws -> LakeBaselinePointer {
        try JSONDecoder().decode(LakeBaselinePointer.self, from: try XCTUnwrap(a.get(LakeBaselineBuilder.pointerPath(lake))))
    }

    func objects(_ a: RecordingArchive) -> Set<String> { Set(a.writes.filter { $0.hasPrefix("baselines-archive/") }) }

    // MARK: SHA-256

    func testSHA256KnownVectors() {
        XCTAssertEqual(LakeSHA256.hex(""), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        XCTAssertEqual(LakeSHA256.hex("abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        XCTAssertEqual(LakeSHA256.hex("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"), "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1")
        XCTAssertEqual(LakeSHA256.hex(String(repeating: "a", count: 1_000_000)), "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0")
    }

    // MARK: fingerprint

    func testFingerprintIsDeterministicOrderIndependentAndSensitive() {
        let h = history(through: "2026-03-01")
        let fp = LakeBaselineBuilder.inputFingerprint(daily: h, asOfYear: 2026, poolBasisIsFullPool: true)
        XCTAssertEqual(fp.count, 64)
        XCTAssertEqual(fp, LakeBaselineBuilder.inputFingerprint(daily: h.reversed(), asOfYear: 2026, poolBasisIsFullPool: true))
        XCTAssertNotEqual(fp, LakeBaselineBuilder.inputFingerprint(daily: h, asOfYear: 2027, poolBasisIsFullPool: true))
        XCTAssertNotEqual(fp, LakeBaselineBuilder.inputFingerprint(daily: h, asOfYear: 2026, poolBasisIsFullPool: false))
        var revised = h; revised[100].ft += 0.05
        XCTAssertNotEqual(fp, LakeBaselineBuilder.inputFingerprint(daily: revised, asOfYear: 2026, poolBasisIsFullPool: true))
        XCTAssertNotEqual(fp, LakeBaselineBuilder.inputFingerprint(daily: Array(h.dropLast()), asOfYear: 2026, poolBasisIsFullPool: true))
    }

    // MARK: first publish, unchanged input, appended history

    func testFirstRunPublishesObjectAndPointerAndTheArtifactEqualsTodaysBuilderOutput() async throws {
        let a = RecordingArchive()
        let h = history(through: "2026-10-12")
        let o = await ensure(h, today: "2026-10-12", at: "2026-10-12T12:00:00Z", archive: a)
        XCTAssertEqual(o.action, .published); XCTAssertEqual(o.reason, .noPointer)
        let p = try pointer(a)
        let bytes = try XCTUnwrap(a.get(p.objectPath))
        XCTAssertEqual(LakeSHA256.hex(bytes), p.objectSha256); XCTAssertEqual(bytes.count, p.objectBytes)
        // The artifact is exactly what the unchanged builder + encoder produce.
        let direct = LakeBaselineBuilder.build(lakeId: lake, daily: norm(h), today: "2026-10-12", poolBasisIsFullPool: true)
        XCTAssertEqual(bytes, try BrainJSON.encode(direct))
        XCTAssertEqual(p.baselineVersion, direct.baselineVersion)
        XCTAssertTrue(p.objectPath.hasPrefix("baselines-archive/Test_AL/"))
        XCTAssertEqual(a.writes, [p.objectPath, "baselines/Test_AL/latest.json"], "object first, pointer second")
    }

    func testUnchangedInputWritesNothingAndAppendedRowsInsideTheWeekWriteNothing() async throws {
        let a = RecordingArchive()
        _ = await ensure(history(through: "2026-10-12"), today: "2026-10-12", at: "2026-10-12T12:00:00Z", archive: a)
        let before = a.writes.count
        let same = await ensure(history(through: "2026-10-12"), today: "2026-10-12", at: "2026-10-12T18:00:00Z", archive: a)
        XCTAssertEqual(same.action, .reused); XCTAssertEqual(same.reason, .current)
        let appended = await ensure(history(through: "2026-10-15"), today: "2026-10-15", at: "2026-10-15T12:00:00Z", archive: a)
        XCTAssertEqual(appended.action, .reused, "3 appended days inside the weekly window do not recompute")
        XCTAssertEqual(a.writes.count, before, "no write at all")
        XCTAssertEqual(appended.baseline.historyEnd, "2026-10-12", "the classifier keeps the stored baseline between recomputes")
    }

    func testWeeklyRecomputeWithNewRowsWritesNewObjectAndMovesPointer() async throws {
        let a = RecordingArchive()
        _ = await ensure(history(through: "2026-10-12"), today: "2026-10-12", at: "2026-10-12T12:00:00Z", archive: a)
        let p1 = try pointer(a)
        let o = await ensure(history(through: "2026-10-20"), today: "2026-10-20", at: "2026-10-20T12:00:00Z", archive: a)
        XCTAssertEqual(o.action, .published); XCTAssertEqual(o.reason, .weeklyDue)
        let p2 = try pointer(a)
        XCTAssertNotEqual(p1.objectPath, p2.objectPath)
        XCTAssertEqual(p2.supersedes, p1.objectPath)
        XCTAssertEqual(p2.historyEnd, "2026-10-20")
        XCTAssertEqual(objects(a).count, 2)
        XCTAssertNotNil(a.get(p1.objectPath), "the older immutable object is still there")
    }

    func testWeeklyRecomputeOfAStalledHistoryWritesNothing() async throws {
        let a = RecordingArchive()
        let h = history(through: "2026-10-12")
        _ = await ensure(h, today: "2026-10-12", at: "2026-10-12T12:00:00Z", archive: a)
        let n = a.writes.count
        let o = await ensure(h, today: "2026-10-20", at: "2026-10-20T12:00:00Z", archive: a)
        XCTAssertEqual(o.reason, .weeklyDue); XCTAssertEqual(o.action, .unchanged)
        XCTAssertEqual(a.writes.count, n, "identical inputs give the identical object name and bytes: no new object, no pointer move")
    }

    func testRefreshReuploadsTheSameBytesOnlyAfterRefreshDays() async throws {
        let a = RecordingArchive()
        let h = history(through: "2026-10-12")
        _ = await ensure(h, today: "2026-10-12", at: "2026-10-12T12:00:00Z", archive: a)
        let p1 = try pointer(a)
        let bytes1 = try XCTUnwrap(a.get(p1.objectPath))
        let n = a.writes.count
        let early = await ensure(h, today: "2026-11-20", at: "2026-11-20T12:00:00Z", archive: a)   // 39 days
        XCTAssertEqual(early.action, .unchanged); XCTAssertEqual(a.writes.count, n)
        let late = await ensure(h, today: "2026-11-30", at: "2026-11-30T12:00:00Z", archive: a)    // 49 days
        XCTAssertEqual(late.action, .refreshed)
        let p2 = try pointer(a)
        XCTAssertEqual(p2.objectPath, p1.objectPath); XCTAssertEqual(a.get(p2.objectPath), bytes1, "same bytes")
        XCTAssertEqual(p2.computedAt, p1.computedAt); XCTAssertNotEqual(p2.refreshedAt, p1.refreshedAt)
    }

    // MARK: input changes that recompute immediately

    func testBackfillOrRevisedRowBeforeHistoryEndRecomputesImmediately() async throws {
        let a = RecordingArchive()
        var h = history(through: "2026-10-12")
        _ = await ensure(h, today: "2026-10-12", at: "2026-10-12T12:00:00Z", archive: a)
        h[1000].ft += 0.37                                                  // an operator revision of an old row
        let o = await ensure(h, today: "2026-10-13", at: "2026-10-13T12:00:00Z", archive: a)
        XCTAssertEqual(o.reason, .historyRevised); XCTAssertEqual(o.action, .published)
        // deeper history appended BEFORE the first stored row (a backfill) is also a revision
        let back = history(from: "1995-01-01", through: "2026-10-13")
        let o2 = await ensure(back, today: "2026-10-13", at: "2026-10-13T13:00:00Z", archive: a)
        XCTAssertEqual(o2.reason, .historyRevised); XCTAssertEqual(o2.action, .published)
        // the --backfill run flag forces a recompute even with equal rows (result then equals: nothing new to write)
        let o3 = await ensure(back, today: "2026-10-13", at: "2026-10-13T14:00:00Z", archive: a, backfill: true)
        XCTAssertEqual(o3.reason, .forced); XCTAssertEqual(o3.action, .unchanged)
    }

    func testNewCalendarYearAndPoolBasisChangeRecompute() async throws {
        let a = RecordingArchive()
        _ = await ensure(history(through: "2026-12-30"), today: "2026-12-30", at: "2026-12-30T12:00:00Z", archive: a)
        let ny = await ensure(history(through: "2027-01-02"), today: "2027-01-02", at: "2027-01-02T12:00:00Z", archive: a)
        XCTAssertEqual(ny.reason, .newCalendarYear); XCTAssertEqual(ny.action, .published)
        let pb = await LakeBaselineStore.ensure(lakeId: lake, merged: history(through: "2027-01-02"), today: "2027-01-02", poolBasisIsFullPool: false,
                                                archive: a, now: iso("2027-01-02T13:00:00Z"))
        XCTAssertEqual(pb.reason, .poolBasisChanged)
    }

    func testMethodOrBuilderBumpIsDetectedFromThePointer() async throws {
        let a = RecordingArchive()
        let h = history(through: "2026-10-12")
        _ = await ensure(h, today: "2026-10-12", at: "2026-10-12T12:00:00Z", archive: a)
        var p = try pointer(a)
        p.builderVersion = "builder-older"
        let r = LakeBaselineStore.decide(pointer: p, objectReadable: true, merged: h, today: "2026-10-12", poolBasisIsFullPool: true,
                                         now: iso("2026-10-12T13:00:00Z"), forceRecompute: false)
        XCTAssertEqual(r, .methodOrBuilderChanged)
        p.builderVersion = LakeBaselineBuilder.builderVersion; p.method = "doy15-percentile-v1"
        XCTAssertEqual(LakeBaselineStore.decide(pointer: p, objectReadable: true, merged: h, today: "2026-10-12", poolBasisIsFullPool: true,
                                                now: iso("2026-10-12T13:00:00Z"), forceRecompute: false), .methodOrBuilderChanged)
    }

    // MARK: corruption and fallback

    func testMissingPointerFallsBackToBuildAndWrites() async throws {
        let h = history(through: "2026-10-12")
        let none = await ensure(h, today: "2026-10-12", at: "2026-10-12T12:00:00Z", archive: nil)
        XCTAssertEqual(none.action, .builtNotStored)
        XCTAssertEqual(none.baseline, LakeBaselineBuilder.build(lakeId: lake, daily: norm(h), today: "2026-10-12", poolBasisIsFullPool: true))
        // a legacy object next to a missing pointer is ignored, never trusted
        let a = RecordingArchive(seed: ["baselines/Test_AL/doy15_percentile_v1_2026_10_06_deadbeef.json": Data("{}".utf8)])
        let o = await ensure(h, today: "2026-10-12", at: "2026-10-12T12:00:00Z", archive: a)
        XCTAssertEqual(o.action, .published); XCTAssertEqual(o.reason, .noPointer); XCTAssertTrue(o.errors.isEmpty)
    }

    func testCorruptPointerFallsBackSafelyAndIsRepaired() async throws {
        let h = history(through: "2026-10-12")
        let a = RecordingArchive(seed: [LakeBaselineBuilder.pointerPath(lake): Data("{not json".utf8)])
        let o = await ensure(h, today: "2026-10-12", at: "2026-10-12T12:00:00Z", archive: a)
        XCTAssertEqual(o.reason, .pointerCorrupt); XCTAssertEqual(o.action, .published)
        XCTAssertFalse(o.errors.isEmpty)
        XCTAssertEqual(o.baseline, LakeBaselineBuilder.build(lakeId: lake, daily: norm(h), today: "2026-10-12", poolBasisIsFullPool: true))
        let again = await ensure(h, today: "2026-10-12", at: "2026-10-12T13:00:00Z", archive: a)
        XCTAssertEqual(again.action, .reused, "the repaired pointer is trusted again")
        XCTAssertTrue(again.errors.isEmpty)
    }

    func testPointerNamingAMissingOrTamperedObjectFallsBack() async throws {
        let h = history(through: "2026-10-12")
        let a = RecordingArchive()
        _ = await ensure(h, today: "2026-10-12", at: "2026-10-12T12:00:00Z", archive: a)
        let p = try pointer(a)
        // tamper: same name, different bytes
        try await a.write(p.objectPath, Data("{\"lakeId\":\"Test|AL\"}".utf8), contentType: "application/json")
        let t = await ensure(h, today: "2026-10-12", at: "2026-10-12T13:00:00Z", archive: a)
        XCTAssertEqual(t.reason, .pointerCorrupt); XCTAssertEqual(t.action, .published)
        XCTAssertEqual(t.baseline, LakeBaselineBuilder.build(lakeId: lake, daily: norm(h), today: "2026-10-12", poolBasisIsFullPool: true))
        XCTAssertEqual(try XCTUnwrap(a.get(p.objectPath)).count, p.objectBytes, "the object was rewritten with the correct bytes")
        // pointer to a path that does not exist
        var q = try pointer(a); q.objectPath = "baselines-archive/Test_AL/missing.json"
        try await a.write(LakeBaselineBuilder.pointerPath(lake), try BrainJSON.encode(q), contentType: "application/json")
        let m = await ensure(h, today: "2026-10-12", at: "2026-10-12T14:00:00Z", archive: a)
        XCTAssertEqual(m.reason, .pointerCorrupt)
        // a pointer for another lake or an escaping path is rejected
        var w = try pointer(a); w.lakeId = "Other|AL"
        try await a.write(LakeBaselineBuilder.pointerPath(lake), try BrainJSON.encode(w), contentType: "application/json")
        let r = await LakeBaselineStore.resolve(archive: a, lakeId: lake)
        XCTAssertNil(r.resolved); XCTAssertTrue(r.corrupt)
    }

    func testAWriteFailureLeavesTheOldPointerAndStillReturnsAUsableBaseline() async throws {
        let a = RecordingArchive()
        _ = await ensure(history(through: "2026-10-12"), today: "2026-10-12", at: "2026-10-12T12:00:00Z", archive: a)
        let p1 = try pointer(a)
        let failing = RecordingArchive(failPrefix: "baselines-archive/", seed: ["baselines/Test_AL/latest.json": try XCTUnwrap(a.get("baselines/Test_AL/latest.json")),
                                                                             p1.objectPath: try XCTUnwrap(a.get(p1.objectPath))])
        let o = await ensure(history(through: "2026-10-20"), today: "2026-10-20", at: "2026-10-20T12:00:00Z", archive: failing)
        XCTAssertEqual(o.action, .builtNotStored); XCTAssertFalse(o.errors.isEmpty)
        XCTAssertEqual(o.baseline.historyEnd, "2026-10-20")
        XCTAssertEqual(try pointer(failing).objectPath, p1.objectPath, "the pointer did not move")
    }

    // MARK: reproducibility and rollback

    func testFeedPrecisionBeyondTwoDecimalsDoesNotChangeTheArtifact() async throws {
        let raw = history(through: "2026-10-12")                                 // unrounded feed values
        let a = RecordingArchive(), b = RecordingArchive()
        _ = await ensure(raw, today: "2026-10-12", at: "2026-10-12T12:00:00Z", archive: a)
        _ = await ensure(norm(raw), today: "2026-10-12", at: "2026-10-12T12:00:00Z", archive: b)
        XCTAssertEqual(try pointer(a).objectSha256, try pointer(b).objectSha256)
        XCTAssertEqual(try pointer(a).inputFingerprint, try pointer(b).inputFingerprint)
    }

    func testReDerivingFromAPinnedHistorySnapshotIsByteIdentical() async throws {
        let a = RecordingArchive()
        let h = history(through: "2026-10-12")
        let snapshot = LakeDailyHistory.encode(h)                         // the history/{key}/daily.csv bytes at that moment
        _ = await ensure(h, today: "2026-10-12", at: "2026-10-12T12:00:00Z", archive: a)
        let p = try pointer(a)
        // Later: history moved on; a verifier re-derives the artifact from the pinned snapshot only.
        let rows = LakeDailyHistory.decode(snapshot)
        let rebuilt = LakeBaselineBuilder.build(lakeId: lake, daily: rows, today: "2026-10-12", poolBasisIsFullPool: true)
        let bytes = try BrainJSON.encode(rebuilt)
        XCTAssertEqual(LakeSHA256.hex(bytes), p.objectSha256)
        XCTAssertEqual(bytes, try XCTUnwrap(a.get(p.objectPath)))
        XCTAssertEqual(LakeBaselineBuilder.inputFingerprint(daily: rows, asOfYear: 2026, poolBasisIsFullPool: true), p.inputFingerprint)
        // and again from a second build: deterministic
        XCTAssertEqual(try BrainJSON.encode(LakeBaselineBuilder.build(lakeId: lake, daily: rows, today: "2026-10-12", poolBasisIsFullPool: true)), bytes)
    }

    func testRollbackPointsAtTheOlderObjectAndReproducesIdenticalResults() async throws {
        let a = RecordingArchive()
        let h1 = history(through: "2026-10-12")
        let first = await ensure(h1, today: "2026-10-12", at: "2026-10-12T12:00:00Z", archive: a)
        let p1 = try pointer(a)
        let bytes1 = try XCTUnwrap(a.get(p1.objectPath))
        let second = await ensure(history(through: "2026-10-20"), today: "2026-10-20", at: "2026-10-20T12:00:00Z", archive: a)
        let p2 = try pointer(a)
        XCTAssertNotEqual(p1.objectPath, p2.objectPath)

        let rb = try await LakeBaselineStore.rollback(archive: a, lakeId: lake, toObjectPath: p1.objectPath, reason: "test rollback", now: iso("2026-10-21T00:00:00Z"))
        XCTAssertTrue(rb.pinned); XCTAssertEqual(rb.supersedes, p2.objectPath)
        let resolvedNow = await LakeBaselineStore.resolve(archive: a, lakeId: lake)
        let res = try XCTUnwrap(resolvedNow.resolved)
        XCTAssertEqual(res.pointer.objectPath, p1.objectPath)
        XCTAssertEqual(res.bytes, bytes1, "the older object is untouched")
        XCTAssertEqual(res.baseline, first.baseline, "identical baseline, identical classifier input")
        XCTAssertNotEqual(res.baseline, second.baseline)

        // Pinned: later runs reuse it, however old and however much the history moved. Nothing is written.
        let n = a.writes.count
        let later = await ensure(history(through: "2027-02-01"), today: "2027-02-01", at: "2027-02-01T12:00:00Z", archive: a)
        XCTAssertEqual(later.reason, .pinned); XCTAssertEqual(later.action, .reused)
        XCTAssertEqual(later.baseline, first.baseline)
        XCTAssertEqual(a.writes.count, n)
        // Rollback to something that is not this lake's archive is refused.
        do { _ = try await LakeBaselineStore.rollback(archive: a, lakeId: lake, toObjectPath: "baselines-archive/Other_AL/x.json", reason: "x", now: Date()); XCTFail("accepted") }
        catch { XCTAssertTrue("\(error)".contains("baselines-archive")) }
    }

    /// Through the real runner: two runs on the same inputs leave one baseline object and one pointer; the classifier sees the same baseline.
    func testRunnerWritesPointerAndObjectOnceAndAnOldPointerlessBucketStillWorks() async throws {
        let lakeDir = try XCTUnwrap(LakeDirectory.all.first { $0.id == "Wheeler|AL" })
        let tz = TimeZone(identifier: LakeSourceBindings.reviewedBinding(for: lakeDir.id)?.timeZone ?? "UTC") ?? utc
        let now = iso("2026-10-13T15:00:00Z")
        let today = LakeLevelCalendar.dayString(now, timeZone: tz)
        let feeds = LedgerFeeds(history: history(through: today))
        let a = RecordingArchive(seed: ["baselines/Wheeler_AL/doy15_percentile_v1_2026_10_06_00000000.json": Data("{}".utf8)])   // legacy object present
        var o = LakeBrainRunOptions(); o.force = true
        let r1 = await LakeBrainRunner.evaluateLake(lakeDir, feeds: feeds, archive: a, presence: nil, published: nil, previousProfile: nil, options: o, now: now)
        XCTAssertNotNil(r1.state); XCTAssertTrue(r1.errors.isEmpty, "\(r1.errors)")
        XCTAssertEqual(a.writes.filter { $0.hasPrefix("baselines-archive/Wheeler_AL/") }.count, 1)
        XCTAssertEqual(a.writes.filter { $0 == "baselines/Wheeler_AL/latest.json" }.count, 1)
        let nb = a.writes.filter { $0.hasPrefix("baselines") }.count
        let r2 = await LakeBrainRunner.evaluateLake(lakeDir, feeds: feeds, archive: a, presence: nil, published: nil, previousProfile: nil, options: o, now: now.addingTimeInterval(7200))
        XCTAssertEqual(r2.baseline, r1.baseline)
        XCTAssertEqual(a.writes.filter { $0.hasPrefix("baselines") }.count, nb, "the second run wrote no baseline object or pointer")
        XCTAssertEqual(r2.state?.baselineStatus, r1.state?.baselineStatus)
    }
}
