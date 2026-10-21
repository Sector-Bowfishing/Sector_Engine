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
        XCTAssertEqual(numbersByValue(try Self.stable(fresh) + "\n"), numbersByValue(committed),
                       "the Lake runner's write set changed: review the change, then regenerate with SECTOR_WRITE_BRAIN_FIXTURES=1")
    }
}

/// Platform-independent fixture text: every JSON NUMBER token (outside string literals) is rewritten as Swift's shortest exact representation
/// of its Double value, so Darwin's 17-digit `23.100000000000001` and Linux's `23.1` (the same Double) compare equal, while any change of value,
/// key, string, order or structure still fails. Everything else is compared character for character.
func numbersByValue(_ s: String) -> String {
    var out = "", token = "", inString = false, escaped = false
    func flush() {
        if !token.isEmpty { out += Double(token).map { "\($0)" } ?? token; token = "" }
    }
    for c in s {
        if inString {
            out.append(c)
            if escaped { escaped = false } else if c == "\\" { escaped = true } else if c == "\"" { inString = false }
            continue
        }
        if c == "\"" { flush(); inString = true; out.append(c); continue }
        if c.isNumber || c == "-" || c == "+" || c == "." || c == "e" || c == "E" { token.append(c); continue }
        flush(); out.append(c)
    }
    flush()
    return out
}
