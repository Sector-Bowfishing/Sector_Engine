import XCTest
import Foundation
@testable import SectorEngine

/// Sector_Ops #50 WT-P2: `WaterTempBrainJob --dry-run DIR --read-rtdb URL` reads the previous state from the live database
/// and writes ONLY to DIR. The live store must never receive an update or delete.
final class WaterTemperatureReadThroughTests: XCTestCase {
    final class LiveFake: BrainStore, @unchecked Sendable {
        var data: [String: Data]; var writes = 0
        init(_ d: [String: Data]) { data = d }
        func update(_ paths: [String: Data]) async throws { writes += 1; throw BrainStoreError("live store written") }
        func get(_ path: String) async throws -> Data? { data[path] }
        func delete(_ path: String) async throws { writes += 1; throw BrainStoreError("live store deleted") }
        func shallowKeys(_ path: String) async throws -> [String] { data.keys.filter { $0.hasPrefix(path + "/") }.map { String($0.dropFirst(path.count + 1)) } }
    }

    func testReadsGoLiveAndWritesStayLocal() async throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("wt-readthrough-\(UUID().uuidString)").path
        defer { try? FileManager.default.removeItem(atPath: dir) }
        let live = LiveFake(["brains/water-temp/status": Data("\"OK\"".utf8)])
        let store = ReadThroughDryRunStore(reader: live, writer: LocalDirectoryStore(directory: dir, brainId: "water-temp"))
        let prev = try await store.get("brains/water-temp/status")
        XCTAssertEqual(prev.map { String(decoding: $0, as: UTF8.self) }, "\"OK\"")
        try await store.update(["brains/water-temp/status": Data("\"WARNING\"".utf8)])
        try await store.delete("brains/water-temp/lastError")
        XCTAssertEqual(live.writes, 0)
        XCTAssertTrue(FileManager.default.fileExists(atPath: dir + "/brains/water-temp/status.json"))
        let again = try await store.get("brains/water-temp/status")                 // reads still come from the live store
        XCTAssertEqual(again.map { String(decoding: $0, as: UTF8.self) }, "\"OK\"")
    }
}
