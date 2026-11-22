//
//  LakeBrainCWMSDivisionOfficeTests.swift
//  Lake Brain: USACE Northwestern Division CWMS offices (NWDP / NWDM) are read by the existing CWMS reader, unchanged. No network.
//

import XCTest
@testable import SectorEngine
@testable import LakeBrain

final class LakeBrainCWMSDivisionOfficeTests: XCTestCase {

    func iso(_ s: String) -> Date { ISO8601DateFormatter().date(from: s)! }

    /// The CWMS reader sends the binding's `station` as the CDA `office` unchanged, so a series published under a division office id is
    /// read like any district's.
    func testDivisionOfficeIsPassedThroughToCWMS() async {
        final class Capture: @unchecked Sendable { let lock = NSLock(); var urls: [String] = [] }
        let cap = Capture()
        let now = iso("2026-11-21T12:00:00Z")
        let body = cwmsPage(now: now, hours: 6, lagH: 1, ft: 1046.4)
        let transport = CWMSTransport(fetch: { url, _, _ in
            cap.lock.withLock { cap.urls.append(url) }
            return .success(CWMSResponse(status: 200, body: body, retryAfter: nil))
        }, sleep: { _ in }, jitter: { 0 }, log: { _ in })
        let feeds = PublicLakeLevelFeeds.legacyUSGS(cwmsTransport: transport)
        let ref = LevelSeriesRef(provider: .cwms, capability: .directOperatorPool, station: "NWDP", series: "MLAW.Elev-Forebay.Inst.0.0.RFC-RAW",
                                 cadenceMin: 60, lagMin: 120)
        let r = await feeds.recent(ref, hours: 6, now: now)
        XCTAssertNil(r.error)
        XCTAssertEqual(r.observations.count, 6)
        let url = cap.lock.withLock { cap.urls.first } ?? ""
        XCTAssertTrue(url.contains("office=NWDP"), url)
        XCTAssertTrue(url.contains("name=MLAW.Elev-Forebay.Inst.0.0.RFC-RAW"), url)
    }

    /// Reviewed bindings already read division offices (e.g. Moses Lake|WA on NWDP, Lake Oahe|SD on NWDM).
    func testReviewedBindingsAlreadyReadDivisionOffices() {
        let division: Set<String> = ["NWDP", "NWDM"]
        let reviewed = LakeSourceBindings.all.filter { $0.status == .reviewed && $0.live.contains { $0.provider == .cwms && division.contains($0.station) } }
        XCTAssertFalse(reviewed.isEmpty)
        XCTAssertNotNil(LakeSourceBindings.reviewedBinding(for: "Moses Lake|WA"))
        XCTAssertNotNil(LakeSourceBindings.reviewedBinding(for: "Lake Oahe|SD"))
    }
}
