//
//  LakePublicationFixtureTests.swift
//  Lake Brain — the runner's real write set on deterministic feeds, as one flat {path: value} JSON object.
//
//  brains/lake/tests/golden/lake_run_updates.json is the input of the Python Publisher artifact builder
//  (brains/lake/runtime/publish_artifact.py) and of the Brain Certification Kit adapter (brains/lake/tests/lake_cert_spec.py).
//  It is produced ONLY by this test, from the unchanged runner:
//      SECTOR_WRITE_BRAIN_FIXTURES=1 swift test --filter LakePublicationFixtureTests
//  Without the variable the test re-runs the Brain and fails if the committed fixture no longer matches the runner's output,
//  so the fixture can never drift from what the job would write.
//

import XCTest
@testable import SectorEngine
@testable import LakeBrain

final class LakePublicationFixtureTests: XCTestCase {
    static let fixtureURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent()      // brains/lake/tests
        .appendingPathComponent("golden/lake_run_updates.json")

    /// One full pilot-scope run (registry, validation, health, sources, activity included) on FakeFeeds, flattened in write order (last write wins).
    static func runUpdates() async throws -> Data {
        let feeds = FakeFeeds()
        let store = LocalDirectoryStore(directory: NSTemporaryDirectory() + "lake-brain-fixture-\(UUID().uuidString)", brainId: LakeBrainSpec.brainId)
        var opts = LakeBrainRunOptions(); opts.force = true
        let r = await LakeBrainRunner.run(store: store, feeds: feeds, archive: nil, presenceArchive: nil, options: opts, now: feeds.now)
        XCTAssertTrue(r.ok, r.writeError ?? "")
        var flat: [String: Any] = [:]
        for patch in store.updates {
            for (path, data) in patch {
                flat[path] = try JSONSerialization.jsonObject(with: data, options: [.fragmentsAllowed])
            }
        }
        return try JSONSerialization.data(withJSONObject: flat, options: [.sortedKeys, .prettyPrinted, .withoutEscapingSlashes])
    }

    /// The runner stamps PROCESS facts (run/fetch/success times, the activity event id and time) with the wall clock, not with the injected
    /// `now`; they are masked to FakeFeeds.now so the fixture is reproducible. Every domain value is compared exactly. (The Publisher treats these
    /// fields as volatile or Orchestrator-owned anyway: brains/lake/runtime/publish_artifact.py.)
    static let maskedNow = "2026-06-01T12:30:00Z", maskedMs = "1780317000000"
    static func stable(_ data: Data) throws -> String {
        var s = String(data: data, encoding: .utf8)!
        s = s.replacingOccurrences(of: #""durationMs" : [0-9]+"#, with: #""durationMs" : 0"#, options: .regularExpression)
        for key in ["lastFetchAt", "lastRun", "lastRunAt", "lastSuccess", "lastSuccessfulRun"] {
            s = s.replacingOccurrences(of: "\"\(key)\" : \"[0-9T:.-]+Z\"", with: "\"\(key)\" : \"\(maskedNow)\"", options: .regularExpression)
        }
        s = s.replacingOccurrences(of: #"[0-9]{13}-lake-brain-"#, with: "\(maskedMs)-lake-brain-", options: .regularExpression)
        s = s.replacingOccurrences(of: #""at" : "[0-9T:.-]+Z""#, with: "\"at\" : \"\(maskedNow)\"", options: .regularExpression)
        return s
    }

    func testFixtureIsTheRunnersCurrentWriteSet() async throws {
        let fresh = try await Self.runUpdates()
        if ProcessInfo.processInfo.environment["SECTOR_WRITE_BRAIN_FIXTURES"] == "1" {
            try FileManager.default.createDirectory(at: Self.fixtureURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            try (try Self.stable(fresh) + "\n").write(to: Self.fixtureURL, atomically: true, encoding: .utf8)
            return
        }
        let committed = try String(contentsOf: Self.fixtureURL, encoding: .utf8)
        XCTAssertEqual(try Self.stable(fresh) + "\n", committed,
                       "the Lake runner's write set changed: review the change, then regenerate with SECTOR_WRITE_BRAIN_FIXTURES=1")
    }
}
