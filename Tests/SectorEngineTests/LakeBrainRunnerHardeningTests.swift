//
//  LakeBrainRunnerHardeningTests.swift
//  Lake Brain runner hardening: the ledger switch (on by default, off only by the explicit flag), the production job args,
//  and the concurrency clamp. Synthetic feeds and temp directories only; no network, no bucket, no database.
//

import XCTest
@testable import SectorEngine

final class LakeBrainRunnerHardeningTests: XCTestCase {

    func iso(_ s: String) -> Date { ISO8601DateFormatter().date(from: s)! }
    func tempDir() -> String { NSTemporaryDirectory() + "lake-hardening-test-\(UUID().uuidString)" }

    private static let repoRoot = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()

    func history() -> [DailyLevel] {
        var out: [DailyLevel] = []
        var d = LakeLevelCalendar.date(year: 2000, month: 1, day: 1)
        let end = LakeLevelCalendar.date(year: 2025, month: 12, day: 31)
        let utc = TimeZone(identifier: "UTC")!
        while d <= end {
            let day = LakeLevelCalendar.dayString(d, timeZone: utc)
            out.append(DailyLevel(date: day, ft: 600 + Double((LakeLevelCalendar.doy365(day) ?? 1) % 11) * 0.1, sourceId: "t"))
            d = d.addingTimeInterval(86_400)
        }
        return out
    }

    func run(_ o: LakeBrainRunOptions, store: BrainStore, archive: LakeBrainArchive? = nil, now: Date) async -> LakeBrainRunResult {
        await LakeBrainRunner.run(store: store, feeds: LedgerFeeds(history: history()), archive: archive, presenceArchive: nil, options: o, now: now)
    }

    func baseOptions() -> LakeBrainRunOptions {
        var o = LakeBrainRunOptions()
        o.lakeIds = ["Guntersville|AL", "Lake Hartwell|SC"]; o.force = true; o.runId = "hard1"
        return o
    }

    // MARK: ledger switch

    func testDefaultOptionsHaveTheLedgerOn() async throws {
        XCTAssertTrue(LakeBrainRunOptions().ledgerEnabled)
        XCTAssertTrue(LakeBrainJobFlags.ledgerEnabled(argv: []))
        XCTAssertTrue(LakeBrainJobFlags.ledgerEnabled(argv: ["LakeBrainJob", "--rtdb", "https://x", "--scope", "pilots", "--force"]))
        var o = LakeBrainRunOptions()
        LakeBrainJobFlags.apply(argv: ["LakeBrainJob", "--dry-run", "d"], to: &o)
        XCTAssertTrue(o.ledgerEnabled)
        let ledger = RecordingArchive()
        var run1 = baseOptions(); run1.ledgerArchive = ledger
        let r = await run(run1, store: LocalDirectoryStore(directory: tempDir(), brainId: LakeBrainSpec.brainId), now: iso("2026-06-01T12:30:00Z"))
        XCTAssertEqual(r.ledgerStatus, "enabled")
        XCTAssertEqual(ledger.writes.count, 1)
        XCTAssertEqual(LakeBrainJobFlags.ledgerLine(enabled: true), "ledger: enabled")
    }

    /// The real production args, parsed from jobs/lake-brain/deploy-job.sh, never carry --no-ledger.
    func testProductionDeployScriptCannotSilentlyDisableTheLedger() throws {
        let script = try String(contentsOf: Self.repoRoot.appendingPathComponent("jobs/lake-brain/deploy-job.sh"), encoding: .utf8)
        XCTAssertTrue(script.contains("--command /app/LakeBrainJob"), "sanity: this is the job deploy script")
        XCTAssertFalse(script.contains("no-ledger"), "the production deploy script must not mention --no-ledger anywhere")
        let argsLine = try XCTUnwrap(script.split(separator: "\n").map(String.init).first { $0.contains("--args=") }, "the --args= line")
        let value = try XCTUnwrap(argsLine.components(separatedBy: "--args=\"").last?.components(separatedBy: "\"").first)
        let args = value.components(separatedBy: ",").map { $0.replacingOccurrences(of: "$RTDB_URL", with: "https://example.invalid")
            .replacingOccurrences(of: "$ARCHIVE_BUCKET", with: "bucket") }
        XCTAssertGreaterThan(args.count, 4, "parsed the real args: \(args)")
        XCTAssertTrue(args.contains("--rtdb") && args.contains("--archive"), "production args: \(args)")
        XCTAssertTrue(LakeBrainJobFlags.ledgerEnabled(argv: ["LakeBrainJob"] + args))
        var o = LakeBrainRunOptions()
        LakeBrainJobFlags.apply(argv: ["LakeBrainJob"] + args, to: &o)
        XCTAssertTrue(o.ledgerEnabled)
        // And the job source routes the flag through the one tested function.
        let main = try String(contentsOf: Self.repoRoot.appendingPathComponent("Sources/LakeBrainJob/main.swift"), encoding: .utf8)
        XCTAssertTrue(main.contains("LakeBrainJobFlags.apply(argv: argv, to: &options)"))
        XCTAssertFalse(main.contains("ledgerEnabled = false"), "the job must not switch the ledger off any other way")
    }

    func testNoLedgerFlagWritesNothingAndRecordsDisabled() async throws {
        let argv = ["LakeBrainJob", "--dry-run", "d", "--no-ledger"]
        XCTAssertFalse(LakeBrainJobFlags.ledgerEnabled(argv: argv))
        XCTAssertEqual(LakeBrainJobFlags.ledgerLine(enabled: false), "ledger: disabled")
        var o = baseOptions()
        LakeBrainJobFlags.apply(argv: argv, to: &o)
        XCTAssertFalse(o.ledgerEnabled)
        // (a) an explicit ledger archive receives nothing
        let ledger = RecordingArchive()
        o.ledgerArchive = ledger
        let dir = tempDir()
        let r = await run(o, store: LocalDirectoryStore(directory: dir, brainId: LakeBrainSpec.brainId), now: iso("2026-06-01T12:30:00Z"))
        XCTAssertTrue(r.ok)
        XCTAssertEqual(r.ledgerStatus, "disabled")
        XCTAssertNil(r.ledgerObject); XCTAssertEqual(r.ledgerRecords, 0); XCTAssertNil(r.ledgerWarning)
        XCTAssertEqual(ledger.writes, [])
        // (b) the dry-run directory has no _ledger folder and the history archive got no predictions/
        XCTAssertFalse(FileManager.default.fileExists(atPath: dir + "/_ledger"))
        let hist = RecordingArchive()
        var o2 = baseOptions(); o2.ledgerEnabled = false
        let r2 = await run(o2, store: InMemoryBrainStore(brainId: LakeBrainSpec.brainId), archive: hist, now: iso("2026-06-01T12:30:00Z"))
        XCTAssertTrue(r2.ok)
        XCTAssertEqual(r2.ledgerStatus, "disabled")
        XCTAssertFalse(hist.writes.contains { $0.hasPrefix("predictions/") })
        XCTAssertTrue(hist.writes.contains { $0.hasPrefix("history/") }, "everything else is unchanged")
    }

    func testNoLedgerOnAPublishingRunWarns() {
        XCTAssertNotNil(LakeBrainJobFlags.publishWithoutLedgerWarning(argv: ["--rtdb", "u", "--no-ledger"], hasRTDB: true))
        XCTAssertNil(LakeBrainJobFlags.publishWithoutLedgerWarning(argv: ["--rtdb", "u"], hasRTDB: true))
        XCTAssertNil(LakeBrainJobFlags.publishWithoutLedgerWarning(argv: ["--dry-run", "d", "--no-ledger"], hasRTDB: false))
    }

    func testLedgerWriteFailureStillPublishesOnALiveStore() async throws {
        let now = iso("2026-06-01T12:30:00Z")
        let store = InMemoryBrainStore(brainId: LakeBrainSpec.brainId)
        let hist = RecordingArchive(failPrefix: "predictions/")     // only the ledger path fails; the live path uses the history archive
        let r = await run(baseOptions(), store: store, archive: hist, now: now)
        XCTAssertTrue(r.ok, r.writeError ?? "")
        XCTAssertNil(r.writeError)
        XCTAssertNotEqual(r.health, "FAILED")
        XCTAssertEqual(r.ledgerStatus, "enabled")
        XCTAssertEqual(r.ledgerWarning, "ledger: boom")
        XCTAssertNil(r.ledgerObject)
        XCTAssertTrue(hist.writes.contains { $0.hasPrefix("history/") })
        let published = try await store.get("lakes/\(BrainPlatform.lakeKey("Guntersville|AL"))/states/lake")
        XCTAssertNotNil(published, "the Brain state was published although the ledger failed")
    }

    // MARK: concurrency

    /// Runs `body` and fails the test if it does not finish in `seconds` (the old `concurrency == 0` loop never finished).
    func finishes<T: Sendable>(within seconds: Double, _ body: @escaping @Sendable () async -> T) async -> T? {
        await withTaskGroup(of: T?.self) { g in
            g.addTask { await body() }
            g.addTask { try? await Task.sleep(nanoseconds: UInt64(seconds * 1e9)); return nil }
            let first = await g.next() ?? nil
            g.cancelAll()
            return first
        }
    }

    func testClampConcurrency() {
        XCTAssertEqual(BrainPlatform.clampConcurrency(0), 1)
        XCTAssertEqual(BrainPlatform.clampConcurrency(-5), 1)
        XCTAssertEqual(BrainPlatform.clampConcurrency(Int.min), 1)
        XCTAssertEqual(BrainPlatform.clampConcurrency(1), 1)
        XCTAssertEqual(BrainPlatform.clampConcurrency(3), 3)
        XCTAssertEqual(BrainPlatform.clampConcurrency(BrainPlatform.maxConcurrency), BrainPlatform.maxConcurrency)
        XCTAssertEqual(BrainPlatform.clampConcurrency(10_000), BrainPlatform.maxConcurrency)
        XCTAssertEqual(BrainPlatform.clampConcurrency(Int.max), BrainPlatform.maxConcurrency)
    }

    func testZeroAndNegativeConcurrencyTerminateAndEvaluateEveryLake() async throws {
        let now = iso("2026-06-01T12:30:00Z")
        for c in [0, -1, Int.min, 1, 3, 1_000_000, Int.max] {
            var o = baseOptions(); o.concurrency = c
            let ledger = RecordingArchive(); o.ledgerArchive = ledger
            let dir = tempDir()
            let result = await finishes(within: 60) { [o] in
                await LakeBrainRunner.run(store: LocalDirectoryStore(directory: dir, brainId: LakeBrainSpec.brainId),
                                          feeds: LedgerFeeds(history: self.history()), archive: nil, presenceArchive: nil, options: o, now: now)
            }
            let r = try XCTUnwrap(result, "run with concurrency \(c) did not terminate")
            XCTAssertTrue(r.ok, "concurrency \(c): \(r.writeError ?? "")")
            XCTAssertEqual(r.lakes.map(\.lakeId), ["Guntersville|AL", "Lake Hartwell|SC"], "concurrency \(c)")
            XCTAssertEqual(r.concurrency, BrainPlatform.clampConcurrency(c))
            XCTAssertEqual(r.ledgerRecords, 2)
        }
    }

    // MARK: User-Agent

    func testUserAgentHasNoPersonalMailboxAndOptionalContact() throws {
        let base = "Sector-LakeBrain/1.0 (io.sector.co; Rehtac Labs; read-only public data)"
        XCTAssertEqual(LakeFeedHTTP.baseUserAgent, base)
        XCTAssertEqual(LakeFeedHTTP.userAgent(contact: nil), base)
        XCTAssertEqual(LakeFeedHTTP.userAgent(contact: "  "), base)
        XCTAssertEqual(LakeFeedHTTP.userAgent(contact: "ops@example.invalid"),
                       "Sector-LakeBrain/1.0 (io.sector.co; Rehtac Labs; read-only public data; contact ops@example.invalid)")
        XCTAssertEqual(LakeFeedHTTP.userAgent(contact: "bad\nvalue"), base, "control characters are refused")
        XCTAssertEqual(LakeFeedHTTP.userAgent(contact: String(repeating: "a", count: 121)), base)
        XCTAssertFalse(LakeFeedHTTP.baseUserAgent.contains("@"))
        // No personal address anywhere in the Lake Brain sources.
        let dir = Self.repoRoot.appendingPathComponent("Sources/SectorEngine/LakeBrain")
        let files = try FileManager.default.contentsOfDirectory(atPath: dir.path).filter { $0.hasSuffix(".swift") }
        XCTAssertGreaterThan(files.count, 5)
        for f in files {
            let text = try String(contentsOf: dir.appendingPathComponent(f), encoding: .utf8)
            XCTAssertFalse(text.contains("gmail.com"), "\(f) carries a personal mailbox")
        }
    }

    // MARK: create-only ledger writes

    /// An archive whose object appears between the existence check and the write (the race `ifGenerationMatch=0` closes).
    final class RacingArchive: LakeBrainArchive, @unchecked Sendable {
        var uri: String { "gs://fake-never-real" }
        private let lock = NSLock()
        private var plainWrites = 0
        var plainWriteCount: Int { lock.withLock { plainWrites } }
        func read(_ path: String) async throws -> Data? { nil }
        func write(_ path: String, _ data: Data, contentType: String) async throws { lock.withLock { plainWrites += 1 } }
        func writeIfAbsent(_ path: String, _ data: Data, contentType: String) async throws -> Bool { false }
    }

    func testLedgerUsesCreateOnlyWriteAndNeverOverwritesARacingObject() async throws {
        let racing = RacingArchive()
        var o = baseOptions(); o.ledgerArchive = racing
        let r = await run(o, store: LocalDirectoryStore(directory: tempDir(), brainId: LakeBrainSpec.brainId), now: iso("2026-06-01T12:30:00Z"))
        XCTAssertTrue(r.ok)
        XCTAssertNil(r.ledgerObject)
        XCTAssertEqual(r.ledgerRecords, 0)
        XCTAssertTrue(r.ledgerWarning?.contains("already exists; not overwritten") ?? false, r.ledgerWarning ?? "nil")
        XCTAssertEqual(racing.plainWriteCount, 0, "the ledger never uses the replacing write")
    }

    func testGCSCreateOnlyUploadUsesIfGenerationMatchZero() {
        let url = GCSLakeBrainArchive.uploadURL(bucket: "b", path: "predictions/2026/10/13/185314Z-x.jsonl", createOnly: true)
        XCTAssertTrue(url.hasSuffix("&ifGenerationMatch=0"), url)
        XCTAssertFalse(GCSLakeBrainArchive.uploadURL(bucket: "b", path: "history/x/daily.csv", createOnly: false).contains("ifGenerationMatch"))
    }
}
