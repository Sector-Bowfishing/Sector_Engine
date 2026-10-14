import XCTest
@testable import SectorEngine

/// Sector Ops must be able to show the reviewed vs candidate fleet from Engine truth (`/brains/lake-brain.breakdowns.fleetBindingStatus`).
final class LakeFleetVisibilityTests: XCTestCase {
    func testFleetBindingBreakdownCountsEveryBindingByStatus() {
        let m = LakeBrainRunner.fleetBindingBreakdown()
        XCTAssertEqual(m["REVIEWED"] ?? 0, LakeSourceBindings.reviewed.count)
        XCTAssertEqual(m["CANDIDATE"] ?? 0, LakeSourceBindings.candidates.count)
        XCTAssertEqual(m.values.reduce(0, +), LakeSourceBindings.all.count, "no binding is uncounted")
        // Until a human accepts a batch, candidates are never reviewed: the reviewed count is only the hand-written pilots.
        XCTAssertEqual(LakeSourceBindings.reviewed.count, LakeSourceBindings.pilots.filter { $0.status == .reviewed }.count + LakeSourceBindings.generated.filter { $0.status == .reviewed && !Set(LakeSourceBindings.pilots.map(\.lakeId)).contains($0.lakeId) }.count)
    }

    func testPredictionLedgerStatusIsPublishedForOpsAndNeverImpliesValidation() throws {
        let on = PredictionLedgerStatus.make(status: "enabled", lastObject: "predictions/2026/10/13/x.jsonl", lastRecords: 5, warning: nil)
        XCTAssertEqual(on.status, "enabled"); XCTAssertEqual(on.startedAt, "2026-10-13T18:53:14Z")
        XCTAssertEqual(on.lastRecords, 5); XCTAssertEqual(on.rulesVersion, LakeBrainSpec.modelVersion)
        XCTAssertTrue(on.note.contains("NOT_VALIDATED"))
        let off = PredictionLedgerStatus.make(status: "disabled", lastObject: nil, lastRecords: 0, warning: nil)
        XCTAssertNil(off.lastObject); XCTAssertNil(off.lastRecords, "no records are claimed when nothing was written")
        let json = String(data: try JSONEncoder().encode(on), encoding: .utf8) ?? ""
        XCTAssertTrue(json.contains("\"startedAt\""))
    }

    func testClaimMaturityIsPerClaimAndRapidStaysNotValidated() throws {
        let m = LakeClaimMaturity.current
        XCTAssertEqual(m["currentLevel"]?.level, 1); XCTAssertEqual(m["currentLevel"]?.maturity, "PROVIDER_VERIFIED")
        XCTAssertEqual(m["trend72h"]?.level, 2); XCTAssertEqual(m["levelDifference"]?.maturity, "DETERMINISTIC_VERIFIED")
        XCTAssertEqual(m["historicalState"]?.maturity, "CALIBRATION")
        // The failed pre-registered H-C check is preserved: RAPID is Level 3 and NOT_VALIDATED, and nothing else is VALIDATED by this table.
        XCTAssertEqual(m["rapidChange"]?.level, 3); XCTAssertEqual(m["rapidChange"]?.maturity, "NOT_VALIDATED")
        XCTAssertFalse(m.values.contains { $0.maturity == "VALIDATED" }, "no claim is claimed VALIDATED")
        // a failed Level-3 claim must not drag Level-1/2 claims down
        XCTAssertTrue(m.values.filter { $0.level < 3 }.allSatisfy { $0.maturity != "NOT_VALIDATED" })
        let json = String(data: try JSONEncoder().encode(m), encoding: .utf8) ?? ""
        XCTAssertTrue(json.contains("rapidChange"))
    }
}
