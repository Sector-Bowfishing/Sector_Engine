//
//  LakeKnowledgeMemoryTests.swift
//  Approved memory (Cortex 2.1 BR-11, BR-18): the presence release (presence/latest.json -> fingerprinted bundle) and the compiled reviewed
//  bindings. A missing pointer is explicit absence (load returns nil); a missing, tampered or corrupt release named by the pointer throws. The
//  runner then records presenceError and lakePaths writes no speciesPresence node (LakeBrainRunner: `if presence != nil`). Synthetic data in a temp dir only: no bucket, no research root.
//

import XCTest
@testable import SectorEngine
@testable import LakeBrain

final class LakeKnowledgeMemoryTests: XCTestCase {

    var dir: URL!

    override func setUpWithError() throws {
        dir = FileManager.default.temporaryDirectory.appendingPathComponent("lake-memory-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    }

    override func tearDownWithError() throws { try? FileManager.default.removeItem(at: dir) }

    let lakes: Set<String> = ["Test|ST"]

    func release() throws -> (bundle: Data, pointer: LakePresencePointer) {
        let b = LakePresenceBundle(schemaVersion: 1, kind: "lake-brain-presence", researchVersion: "test-1", presenceAuthority: "canonical-research",
                                   assessedSpecies: ["example_fish"], sourceArtifacts: nil,
                                   rows: [.init(lakeId: "Test|ST", speciesId: "example_fish", presenceState: "historical", confidence: "low", nativeStatus: nil,
                                                sourceTier: nil, latestRecord: nil, dataGaps: nil, discrepancyIds: nil)])
        let d = try JSONEncoder().encode(b)
        return (d, LakePresencePointer(researchVersion: "test-1", path: "presence/releases/test-1.json",
                                       fingerprint: LakeBaselineBuilder.fingerprint(String(decoding: d, as: UTF8.self)), rowCount: 1))
    }

    func put(_ path: String, _ d: Data) throws {
        let f = dir.appendingPathComponent(path)
        try FileManager.default.createDirectory(at: f.deletingLastPathComponent(), withIntermediateDirectories: true)
        try d.write(to: f)
    }

    func load() async throws -> LakePresenceIndex? {
        try await LakePresenceIndex.load(from: LocalLakeBrainArchive(directory: dir.path), knownLakeIds: lakes)
    }

    func testAVerifiedReleaseLoads() async throws {
        let r = try release()
        try put("presence/latest.json", try JSONEncoder().encode(r.pointer)); try put(r.pointer.path, r.bundle)
        let idx = try await load()
        XCTAssertEqual(idx?.resolveLakeSpecies("Test|ST", updatedAt: "2026-01-01T00:00:00Z").map(\.speciesId), ["example_fish"])
    }

    func testNoPointerIsExplicitAbsenceNotAFallback() async throws {
        let idx = try await load()
        XCTAssertNil(idx, "no release: presence is not written; nothing is synthesized from research or defaults")
    }

    func testAPointerNamingAMissingReleaseThrows() async throws {
        let r = try release()
        try put("presence/latest.json", try JSONEncoder().encode(r.pointer))
        do { _ = try await load(); XCTFail("must throw") } catch { XCTAssertTrue("\(error)".contains("missing")) }
    }

    func testATamperedReleaseFailsItsFingerprint() async throws {
        let r = try release()
        try put("presence/latest.json", try JSONEncoder().encode(r.pointer))
        try put(r.pointer.path, r.bundle + Data(" ".utf8))
        do { _ = try await load(); XCTFail("must throw") } catch { XCTAssertTrue("\(error)".contains("fingerprint mismatch")) }
    }

    func testACorruptPointerThrows() async throws {
        try put("presence/latest.json", Data("{not json".utf8))
        do { _ = try await load(); XCTFail("must throw") } catch {}
    }

    func testAPointerThatDisagreesWithItsReleaseThrows() async throws {
        var r = try release()
        r.pointer.rowCount = 2
        try put("presence/latest.json", try JSONEncoder().encode(r.pointer)); try put(r.pointer.path, r.bundle)
        do { _ = try await load(); XCTFail("must throw") } catch { XCTAssertTrue("\(error)".contains("disagree")) }
    }

    func testTheReviewedBindingsAreCompiledAndVersioned() {
        XCTAssertFalse(LakeSourceBindings.version.isEmpty, "bindings are compiled into the binary and carry a bindingVersion (published in provenance)")
    }
}
