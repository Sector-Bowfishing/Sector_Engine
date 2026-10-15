//
//  BrainPlatformConformanceTests.swift
//  The shared conformance suite (contracts/conformance/*.json) run against the Swift platform.
//  The Python package jobs/brain_platform/ runs the very same fixtures.
//

import XCTest
@testable import SectorEngine

final class BrainPlatformConformanceTests: XCTestCase {

    private static let fixtures = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        .appendingPathComponent("contracts/conformance")

    private func fixture(_ name: String) throws -> [String: Any] {
        let data = try Data(contentsOf: Self.fixtures.appendingPathComponent(name))
        return try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
    }
    private func json<T: Encodable>(_ v: T) throws -> Data { try BrainJSON.encode(v) }

    // MARK: keys

    func testLakeKeys() throws {
        let fx = try fixture("lake_keys.json")
        for c in try XCTUnwrap(fx["cases"] as? [[String: Any]]) {
            XCTAssertEqual(BrainPlatform.lakeKey(c["lakeId"] as! String), c["key"] as? String)
        }
        for c in try XCTUnwrap(fx["collisions"] as? [[String: Any]]) {
            XCTAssertEqual(!BrainPlatform.keyCollisions(c["ids"] as! [String]).isEmpty, c["collides"] as! Bool, "\(c)")
        }
        for k in try XCTUnwrap(fx["illegal_keys"] as? [String]) {
            XCTAssertThrowsError(try BrainPlatform.checkKeys([k: 1]), "should reject \(k.debugDescription)")
        }
        for k in try XCTUnwrap(fx["legal_keys"] as? [String]) {
            XCTAssertNoThrow(try BrainPlatform.checkKeys([k: 1]))
        }
        XCTAssertNoThrow(try BrainPlatform.checkUpdate(["lakes/Guntersville_AL/states/waterTemp": try json(["kind": "measured"])]))
        XCTAssertThrowsError(try BrainPlatform.checkUpdate(["lakes/Gunters.ville/states": try json(1)]))
        XCTAssertThrowsError(try BrainPlatform.checkUpdate(["lakes/x": try json(["bad.key": 1])]))
    }

    // MARK: events

    func testEventIds() throws {
        let fx = try fixture("event_ids.json")
        let re = try NSRegularExpression(pattern: fx["pattern"] as! String)
        for c in try XCTUnwrap(fx["cases"] as? [[String: Any]]) {
            let id = BrainActivity.eventId(atMs: Int64(c["atMs"] as! Int), brainId: c["brainId"] as! String, n: c["n"] as! Int)
            XCTAssertEqual(id, c["id"] as? String)
            XCTAssertNotNil(re.firstMatch(in: id, range: NSRange(id.startIndex..., in: id)))
        }
        let ordering = fx["ordering"] as! [String: [String]]
        XCTAssertEqual(ordering["ids"]!.sorted(), ordering["sorted"]!)
        XCTAssertEqual(BrainActivity.eventId(at: Date(timeIntervalSince1970: 1_791_778_800), brainId: "wind", n: 1), "1791778800000-wind-001")
    }

    func testPruning() throws {
        let fx = try fixture("pruning.json")
        let now = try XCTUnwrap(BrainPlatform.parseTime(fx["now"] as? String))
        for c in try XCTUnwrap(fx["cases"] as? [[String: Any]]) {
            let keep = (c["keep"] as? Int) ?? (fx["keep"] as! Int)
            let dels = BrainActivity.pruneKeys(activity: c["activity"] as! [String: Any], brainId: c["brainId"] as! String,
                                               now: now, keep: keep, maxAgeDays: fx["maxAgeDays"] as! Int)
            XCTAssertEqual(dels, (c["expectDeleted"] as! [String]).sorted(), c["name"] as! String)
        }
    }

    func testPruneOverStoreTouchesOnlyOwnEvents() async throws {
        let fx = try fixture("pruning.json")
        let c = (fx["cases"] as! [[String: Any]])[0]
        let store = InMemoryBrainStore(tree: ["activity": c["activity"]!], brainId: "water-temp")
        let now = try XCTUnwrap(BrainPlatform.parseTime(fx["now"] as? String))
        let deleted = try await BrainActivity.prune(store: store, brainId: "water-temp", now: now)
        XCTAssertEqual(deleted, ["20260901T000000000-water-temp-brain-registered"])
        let left = try await store.shallowKeys("activity")
        XCTAssertEqual(left.count, 5)
        XCTAssertTrue(left.contains("1756684800000-wc-001"), "other brains' events survive")
    }

    // MARK: transport

    func testRetryPolicy() throws {
        let fx = try fixture("retry_policy.json")
        for d in try XCTUnwrap(fx["decisions"] as? [[String: Any]]) {
            let status = d["status"] as? Int
            if status == 200 { continue }
            XCTAssertEqual(BrainTransportPolicy.shouldRetry(status: status), d["retry"] as! Bool, "\(d)")
        }
        XCTAssertEqual((0..<(fx["attempts"] as! Int - 1)).map(BrainTransportPolicy.backoffSeconds), fx["backoffSeconds"] as! [Double])
        for u in fx["refusedUrls"] as! [String] {
            XCTAssertFalse(BrainPlatform.acceptedDatabaseURL(u))
            XCTAssertThrowsError(try RTDBRestStore(databaseURL: u, accessToken: "t"))
        }
        for u in fx["acceptedUrls"] as! [String] { XCTAssertTrue(BrainPlatform.acceptedDatabaseURL(u)) }
    }

    func testStoreRejectsIllegalKeysAndForeignPaths() async throws {
        let s = InMemoryBrainStore(brainId: "water-temp")
        do {
            try await s.update(["brains/water-temp/bad.key": try json(1)])
            XCTFail("illegal key accepted")
        } catch {}
        do {
            try await s.update(["brains/water-temp/x": try json(1), "lakeFleet/Guntersville_AL/lastUpdatedAt": try json("now")])
            XCTFail("foreign path accepted")
        } catch {}
        XCTAssertTrue(s.patches.isEmpty, "refused whole")
        try await s.update(["brains/water-temp/x": try json(1), "lakeFleet/Guntersville_AL/lakeId": try json("Guntersville|AL")])
        let got = try await s.get("lakeFleet/Guntersville_AL/lakeId")
        XCTAssertEqual(String(decoding: try XCTUnwrap(got), as: UTF8.self), "\"Guntersville|AL\"")
        let keys = try await s.shallowKeys("lakeFleet")
        XCTAssertEqual(keys, ["Guntersville_AL"])
        try await s.delete("brains/water-temp/x")
        let gone = try await s.get("brains/water-temp/x")
        XCTAssertNil(gone)
    }

    // MARK: health / freshness

    func testHealth() throws {
        for c in try XCTUnwrap(try fixture("health.json")["cases"] as? [[String: Any]]) {
            XCTAssertEqual(BrainHealth.runHealth(attempted: c["attempted"] as! Int, ok: c["ok"] as! Int, failed: c["failed"] as! Int,
                                                 aborted: c["aborted"] as! Bool, partial: c["partial"] as! Bool,
                                                 publishFailed: c["publishFailed"] as! Bool), c["health"] as? String, "\(c)")
        }
    }

    func testFreshness() throws {
        for c in try XCTUnwrap(try fixture("freshness.json")["cases"] as? [[String: Any]]) {
            let f = BrainFreshness.envelope(generatedAt: try XCTUnwrap(BrainPlatform.parseTime(c["generatedAt"] as? String)),
                                            now: try XCTUnwrap(BrainPlatform.parseTime(c["now"] as? String)),
                                            staleAfterHours: (c["staleAfterHours"] as! NSNumber).doubleValue,
                                            stalenessModel: c["stalenessModel"] as! String,
                                            evidenceStale: c["evidenceStale"] as! Bool,
                                            evidenceReasons: [(c["evidenceReason"] as? String) ?? ""])
            let e = c["expect"] as! [String: Any]
            XCTAssertEqual(f.stale, e["stale"] as! Bool, "\(c)")
            XCTAssertEqual(f.freshUntil, e["freshUntil"] as? String, "\(c)")
            XCTAssertEqual(f.staleReasons?.count ?? 0, e["staleReasonsCount"] as! Int, "\(c)")
            XCTAssertEqual(f.evidenceStale, c["evidenceStale"] as! Bool)
            XCTAssertEqual(f.generatedAt, c["generatedAt"] as? String)
        }
    }

    // MARK: ownership / vocabularies

    func testOwnership() throws {
        let fx = try fixture("ownership.json")
        for c in try XCTUnwrap(fx["cases"] as? [[String: Any]]) {
            XCTAssertEqual(BrainOwnership.pathAllowed(c["brainId"] as! String, c["path"] as! String), c["allowed"] as! Bool, "\(c)")
        }
        for (sid, owner) in fx["sourceOwners"] as! [String: String] { XCTAssertEqual(BrainOwnership.sourceOwner(sid), owner) }
        XCTAssertThrowsError(try BrainOwnership.check(["schemaVersion": try json(2)], brainId: "wind"))
    }

    func testVocabularies() throws {
        let fx = try fixture("vocabularies.json")
        XCTAssertEqual(BrainVocabulary.health, fx["health"] as? [String])
        XCTAssertEqual(BrainVocabulary.readiness, fx["readiness"] as? [String])
        XCTAssertEqual(BrainVocabulary.readinessLadder, fx["readinessLadder"] as? [String])
        XCTAssertEqual(BrainVocabulary.brainStatus, fx["brainStatus"] as? [String])
        XCTAssertEqual(BrainVocabulary.modelLifecycle, fx["modelLifecycle"] as? [String])
        XCTAssertEqual(BrainVocabulary.versionStatus, fx["versionStatus"] as? [String])
        XCTAssertEqual(BrainVocabulary.stateKind, fx["stateKind"] as? [String])
        XCTAssertEqual(BrainVocabulary.stalenessModel, fx["stalenessModel"] as? [String])
        XCTAssertEqual(BrainVocabulary.severity, fx["severity"] as? [String])
        XCTAssertEqual(BrainVocabulary.activityKind, fx["activityKind"] as? [String])
        for (bid, b) in fx["brains"] as! [String: [String: String]] {
            XCTAssertEqual(BrainPlatform.slot(for: bid), b["slot"])
            XCTAssertEqual(BrainPlatform.snapshotField(for: bid), b["snapshotField"])
            XCTAssertEqual(BrainPlatform.brains[bid]?.displayName, b["displayName"])
        }
        for p in fx["promotions"] as! [[String: Any]] {
            XCTAssertEqual(BrainVocabulary.isPromotion(from: p["from"] as? String, to: p["to"] as? String), p["promoted"] as! Bool, "\(p)")
        }
        let legacy = fx["legacyMappings"] as! [String: [String: String]]
        for (old, new) in legacy["modelLifecycle"]! { XCTAssertEqual(BrainVocabulary.normalizeModelLifecycle(old), new) }
        for (old, new) in legacy["stateKind"]! { XCTAssertEqual(BrainVocabulary.normalizeStateKind(old), new) }
        XCTAssertNil(BrainVocabulary.normalizeStateKind("stateType"))
    }

    func testFailureWritesAreOwnedAndComplete() throws {
        let now = Date(timeIntervalSince1970: 1_791_806_400)
        let w = try BrainFailure.writes(brainId: "water-temp", message: "boom", now: now, started: now.addingTimeInterval(-5), jobId: "water-temp-brain")
        XCTAssertNoThrow(try BrainOwnership.check(w, brainId: "water-temp"))
        XCTAssertEqual(String(decoding: w["health/brains/water-temp/status"]!, as: UTF8.self), "\"FAILED\"")
        XCTAssertEqual(String(decoding: w["health/brains/water-temp/durationMs"]!, as: UTF8.self), "5000")
        let evKey = try XCTUnwrap(w.keys.first { $0.hasPrefix("activity/") })
        let ev = try JSONDecoder().decode(BrainActivityEvent.self, from: w[evKey]!)
        XCTAssertEqual(ev.kind, "run.failed"); XCTAssertEqual(ev.severity, "critical"); XCTAssertEqual(ev.brainId, "water-temp")
        XCTAssertEqual(evKey, "activity/\(ev.id)")
    }
}
