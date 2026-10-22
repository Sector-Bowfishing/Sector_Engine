import XCTest
@testable import SectorEngine
@testable import LakeBrain

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
}
