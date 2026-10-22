//
//  LakeReviewedBindingsExportTests.swift
//  The Lake-owned, machine-readable view of the REVIEWED source bindings: brains/lake/contracts/reviewed-lake-bindings-v1.json.
//  Consumers (the Depth Brain's manifest builder) read this contract instead of parsing Lake's Swift source. It is produced ONLY by this test
//  from the compiled table:
//      SECTOR_WRITE_BRAIN_FIXTURES=1 swift test --filter LakeReviewedBindingsExportTests
//  Without the variable the test fails if the committed contract no longer matches the compiled bindings, so it cannot drift.
//

import XCTest
@testable import SectorEngine
@testable import LakeBrain

final class LakeReviewedBindingsExportTests: XCTestCase {
    static let contractURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()      // brains/lake
        .appendingPathComponent("contracts/reviewed-lake-bindings-v1.json")

    struct Row: Encodable { let lakeId: String; let capability: String; let liveSourceIds: [String]; let datum: String? }
    struct Export: Encodable {
        let schema = "reviewed-lake-bindings-v1"
        let owner = "lake-brain"
        let bindingVersion: String
        let reviewed: [Row]
    }

    static func export() throws -> String {
        let rows = LakeSourceBindings.reviewed
            .map { Row(lakeId: $0.lakeId, capability: $0.capability.rawValue, liveSourceIds: $0.live.map(\.sourceId), datum: $0.datum) }
            .sorted { $0.lakeId < $1.lakeId }
        let e = JSONEncoder(); e.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        let d = try e.encode(Export(bindingVersion: LakeSourceBindings.version, reviewed: rows))
        return String(decoding: d, as: UTF8.self) + "\n"
    }

    func testTheReviewedBindingsContractMatchesTheCompiledTable() throws {
        let fresh = try Self.export()
        if ProcessInfo.processInfo.environment["SECTOR_WRITE_BRAIN_FIXTURES"] == "1" {
            try fresh.write(to: Self.contractURL, atomically: true, encoding: .utf8)
            return
        }
        let committed = try String(contentsOf: Self.contractURL, encoding: .utf8)
        XCTAssertEqual(fresh, committed, "Lake's reviewed bindings changed: review, then regenerate with SECTOR_WRITE_BRAIN_FIXTURES=1")
    }

    func testOnlyReviewedRowsAreExported() {
        XCTAssertFalse(LakeSourceBindings.reviewed.isEmpty)
        XCTAssertTrue(LakeSourceBindings.reviewed.allSatisfy { $0.status == .reviewed })
    }
}
