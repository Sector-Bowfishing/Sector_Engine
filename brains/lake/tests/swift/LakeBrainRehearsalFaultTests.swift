//
//  LakeBrainRehearsalFaultTests.swift
//  The dry-run CWMS fault (Sector_Ops #48 B4b): every CWMS request fails at once, and Lake still degrades honestly (the
//  Hartwell USGS fallback). No network, no bucket, no database.
//

import XCTest
@testable import LakeBrain
@testable import SectorEngine

final class LakeBrainRehearsalFaultTests: XCTestCase {
    func testUnreachableFaultFailsEveryCWMSRequestWithoutWaiting() async {
        let now = Date()
        let feeds = PublicLakeLevelFeeds(rehearsalFaults: .init(cwmsUnreachable: true))
        let t0 = Date()
        let r = await feeds.cwms(office: "SAS", name: "Hartwell.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS", begin: now.addingTimeInterval(-192 * 3600), end: now)
        XCTAssertTrue(r.observations.isEmpty)
        XCTAssertTrue(r.error?.contains("fault injection: CWMS unreachable") ?? false, r.error ?? "nil")
        XCTAssertLessThan(Date().timeIntervalSince(t0), 2, "the fault never waits for a backoff")
    }

    func testNoFaultKeepsTheLiveTransport() {
        XCTAssertEqual(PublicLakeLevelFeeds.RehearsalFaults(), .init(cwmsUnreachable: false))
    }

    func testHartwellDegradesHonestlyWhenCWMSIsDown() async {
        let feeds = LakeBrainCWMSRetryTests.SplitFeeds(cwms: PublicLakeLevelFeeds(rehearsalFaults: .init(cwmsUnreachable: true)),
                                                       rest: LedgerFeeds(history: [], liveFt: 649.1))
        var o = LakeBrainRunOptions()
        o.lakeIds = ["Lake Hartwell|SC"]; o.force = true; o.ledgerEnabled = false; o.runId = "cwms-fault"
        let store = LocalDirectoryStore(directory: NSTemporaryDirectory() + "lake-cwms-fault-\(UUID().uuidString)", brainId: LakeBrainSpec.brainId)
        let r = await LakeBrainRunner.run(store: store, feeds: feeds, archive: nil, presenceArchive: nil, options: o, now: Date())
        let lake = r.lakes.first { $0.lakeId == "Lake Hartwell|SC" }
        XCTAssertNotNil(lake?.state, "a CWMS outage never blanks the lake")
        let flags = lake?.state?.provenance.qualityFlags ?? []
        XCTAssertTrue(flags.contains("sourceError:cwms:SAS:Hartwell.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS"), "\(flags)")
        XCTAssertTrue(flags.contains("fallbackSource:usgs:02187010:00062"), "\(flags)")
        XCTAssertEqual(lake?.state?.kind, .observed)
        XCTAssertEqual(r.health, "WARNING", "the outage is reported, not hidden")
    }
}
