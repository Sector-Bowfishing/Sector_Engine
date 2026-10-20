import XCTest
@testable import SectorEngine
@testable import WaterTemperatureBrain

/// Regression: pruning must never delete another brain's events (2026-10-12 platform audit).
final class WaterTemperatureBrainPruneTests: XCTestCase {
    func testPrunesOnlyOwnOldEventsByAtNotByKey() {
        let now = ISO8601DateFormatter().date(from: "2026-10-12T12:00:00Z")!
        let activity: [String: Any] = [
            "20260901T000000000-water-temp-brain-registered": ["at": "2026-09-01T00:00:00Z", "brainId": "water-temp"],
            "20261011T000000000-water-temp-run": ["at": "2026-10-11T00:00:00Z", "brainId": "water-temp"],
            "1756684800000-wc-001": ["at": "2026-09-01T00:00:00Z", "brainId": "water-clarity"],   // old, NOT ours
            "1791784800000-wind-001": ["at": "2026-10-12T00:00:00Z", "brainId": "wind"],
            "1756684800000_wind_000": ["at": "2026-09-01T00:00:00Z", "brainId": "wind"],          // old, NOT ours
            "orphan": ["at": "2026-01-01T00:00:00Z"],
            "mine-no-at": ["brainId": "water-temp"],
        ]
        XCTAssertEqual(WaterTemperatureBrainRunner.pruneKeys(activity: activity, now: now),
                       ["20260901T000000000-water-temp-brain-registered"])
    }

    func testCountCapKeepsNewestByAt() {
        let now = ISO8601DateFormatter().date(from: "2026-10-12T12:00:00Z")!
        var activity: [String: Any] = [:]
        for h in 0..<5 { activity["k\(4 - h)"] = ["at": String(format: "2026-10-12T0%d:00:00Z", h), "brainId": "water-temp"] }
        XCTAssertEqual(WaterTemperatureBrainRunner.pruneKeys(activity: activity, now: now, keep: 2), ["k2", "k3", "k4"], "k0 (04:00) and k1 (03:00) are the newest by at")
    }
}
