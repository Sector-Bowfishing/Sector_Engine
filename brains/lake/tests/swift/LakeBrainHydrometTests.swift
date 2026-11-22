//
//  LakeBrainHydrometTests.swift
//  Lake Brain: the Reclamation Hydromet reservoir-elevation reader (LakeLevelFeedsHydromet.swift) and the USACE Northwestern Division
//  CWMS offices (NWDP / NWDM) through the existing CWMS reader. No network.
//
//  The fixtures in tests/fixtures/hydromet/ have the documented Hydromet answer shapes (PN `instant.pl … format=csv`; GP `webarccsv.pl` /
//  `webdaycsv.pl … format=2` with BEGIN DATA / END DATA inside HTML), with the 998877 sentinel, a MISSING cell and a blank cell. They were
//  assembled from Reclamation's documentation and a published client's parser, not captured from usbr.gov: the host was not reachable
//  from the session that wrote this reader. Replace them with recorded answers when one is captured.
//

import XCTest
@testable import SectorEngine
@testable import LakeBrain

final class LakeBrainHydrometTests: XCTestCase {

    let pacific = TimeZone(identifier: "America/Los_Angeles")!
    let mountain = TimeZone(identifier: "America/Denver")!
    func iso(_ s: String) -> Date { ISO8601DateFormatter().date(from: s)! }

    static let fixtures = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
        .appendingPathComponent("fixtures/hydromet")

    func fixture(_ name: String) throws -> Data { try Data(contentsOf: Self.fixtures.appendingPathComponent(name)) }

    // MARK: binding shape

    func testStationParsing() {
        let s = LakeFleetClients.hydrometStation("PN:GCL:America/Los_Angeles")
        XCTAssertEqual(s?.region, .pn)
        XCTAssertEqual(s?.site, "GCL")
        XCTAssertEqual(s?.timeZone?.identifier, "America/Los_Angeles")
        XCTAssertEqual(LakeFleetClients.hydrometStation("gp:cafe")?.site, "CAFE")
        XCTAssertNil(LakeFleetClients.hydrometStation("gp:cafe")?.timeZone)
        XCTAssertNil(LakeFleetClients.hydrometStation("LC:GCL"), "only PN and GP")
        XCTAssertNil(LakeFleetClients.hydrometStation("PN:GCL:Not/AZone"))
        XCTAssertNil(LakeFleetClients.hydrometStation("PN:G C"))
        XCTAssertNil(LakeFleetClients.hydrometStation("GCL"))
    }

    func testOnlyForebayElevationIsALevel() {
        XCTAssertEqual(LakeFleetClients.hydrometParam(nil), "FB")
        XCTAssertEqual(LakeFleetClients.hydrometParam("fb"), "FB")
        XCTAssertNil(LakeFleetClients.hydrometParam("AF"), "storage in acre-feet")
        XCTAssertNil(LakeFleetClients.hydrometParam("GH"), "gage height")
        XCTAssertNil(LakeFleetClients.hydrometParam("Q"))
    }

    func testSourceIdLeavesTheTimeZoneOut() {
        let ref = LevelSeriesRef(provider: .hydromet, capability: .directOperatorPool, station: "PN:mlaw:America/Los_Angeles", series: "fb",
                                 cadenceMin: 60, lagMin: 240)
        XCTAssertEqual(ref.sourceId, "hydromet:PN:MLAW:FB")
        XCTAssertEqual(ref.providerName, "USBR Hydromet")
    }

    func testURLs() {
        let pn = LakeFleetClients.HydrometStation(region: .pn, site: "GCL", timeZone: pacific)
        XCTAssertEqual(LakeFleetClients.hydrometInstantURL(pn, param: "FB", hours: 26, start: "2026-11-19", end: "2026-11-22"),
                       "https://www.usbr.gov/pn-bin/instant.pl?list=GCL%20FB&back=26&format=csv&flags=false&description=false")
        let gp = LakeFleetClients.HydrometStation(region: .gp, site: "CAFE", timeZone: mountain)
        XCTAssertEqual(LakeFleetClients.hydrometInstantURL(gp, param: "FB", hours: 26, start: "2026-11-19", end: "2026-11-22"),
                       "https://www.usbr.gov/gp-bin/webdaycsv.pl?parameter=CAFE%20FB&syer=2026&smnth=11&sdy=19&eyer=2026&emnth=11&edy=22&format=2")
        XCTAssertEqual(LakeFleetClients.hydrometDailyURL(region: .pn, site: "GCL", param: "FB", start: "2016-11-21", end: "2026-11-21"),
                       "https://www.usbr.gov/pn-bin/daily.pl?station=GCL&format=csv&year=2016&month=11&day=21&year=2026&month=11&day=21&pcode=FB")
        XCTAssertEqual(LakeFleetClients.hydrometDailyURL(region: .gp, site: "CAFE", param: "FB", start: "2016-11-21", end: "2026-11-21"),
                       "https://www.usbr.gov/gp-bin/webarccsv.pl?parameter=CAFE%20FB&syer=2016&smnth=11&sdy=21&eyer=2026&emnth=11&edy=21&format=2")
    }

    // MARK: parser

    func testStamps() {
        XCTAssertEqual(LakeFleetClients.hydrometStamp("11/20/2026 21:15")?.day, "2026-11-20")
        XCTAssertEqual(LakeFleetClients.hydrometStamp("11/20/2026 21:15")?.hour, 21)
        XCTAssertNil(LakeFleetClients.hydrometStamp("11/20/2026")?.hour, "a daily row has no time")
        XCTAssertEqual(LakeFleetClients.hydrometStamp("2026-11-20 06:30")?.minute, 30)
        XCTAssertNil(LakeFleetClients.hydrometStamp("13/20/2026"))
        XCTAssertNil(LakeFleetClients.hydrometStamp("DATE"))
        XCTAssertNil(LakeFleetClients.hydrometStamp("11/20/2026 24:30"))
        // hour 24 is midnight ending the day
        let r = LakeFleetClients.HydrometRow(day: "2026-11-20", hour: 24, minute: 0, ft: 1)
        XCTAssertEqual(r.at(pacific), iso("2026-11-21T08:00:00Z"))
    }

    func testPNInstantFixtureDropsSentinelAndBlankAndReadsPacificTime() throws {
        let (rows, error) = LakeFleetClients.parseHydromet(try fixture("pn_instant_MLAW_FB.csv"), site: "MLAW", param: "FB")
        XCTAssertNil(error)
        XCTAssertEqual(rows.map(\.ft), [1046.38, 1046.39, 1046.41, 1046.44, 1046.45], "998877 and the blank cell dropped")
        XCTAssertEqual(rows[0].at(pacific), iso("2026-11-21T05:00:00Z"), "November: PST, UTC-8")
    }

    func testGPDailyFixtureIsReadBetweenBeginAndEndData() throws {
        let (rows, error) = LakeFleetClients.parseHydromet(try fixture("gp_daily_CAFE_FB.txt"), site: "CAFE", param: "FB")
        XCTAssertNil(error)
        XCTAssertEqual(rows.map(\.day), ["2026-11-16", "2026-11-17", "2026-11-20"], "998877 and MISSING dropped")
        XCTAssertTrue(rows.allSatisfy { $0.hour == nil })
        let d = LakeFleetClients.hydrometDailyLevels(rows, timeZone: mountain, offsetFt: 1.5, src: "hydromet:GP:CAFE:FB")
        XCTAssertEqual(d.map(\.date), ["2026-11-16", "2026-11-17", "2026-11-20"], "the day is the date in the stamp; no day is filled")
        for (got, want) in zip(d.map(\.ft), [3788.71, 3788.80, 3789.02]) { XCTAssertEqual(got, want, accuracy: 1e-9) }
        XCTAssertEqual(Set(d.map(\.sourceId)), ["hydromet:GP:CAFE:FB"])
    }

    func testTimedRowsBecomeLakeLocalDailyMedians() throws {
        let (rows, _) = LakeFleetClients.parseHydromet(try fixture("gp_instant_CAFE_FB.txt"), site: "CAFE", param: "FB")
        XCTAssertEqual(rows.count, 4)
        let d = LakeFleetClients.hydrometDailyLevels(rows, timeZone: mountain, offsetFt: 0, src: "x")
        XCTAssertEqual(d.count, 1)
        XCTAssertEqual(d[0].date, "2026-11-20")
        XCTAssertEqual(d[0].ft, 3787.56, accuracy: 1e-9)
    }

    func testBadAnswersFailWhole() {
        XCTAssertNotNil(LakeFleetClients.parseHydromet(Data("<html><body>Server error</body></html>".utf8), site: "GCL", param: "FB").error)
        let other = "DATE,GCL AF,GCL QD\n11/20/2026,5000000,30000\n"
        XCTAssertNotNil(LakeFleetClients.parseHydromet(Data(other.utf8), site: "GCL", param: "FB").error, "no FB column: refused, not guessed")
        let empty = "BEGIN DATA\nDATE, GCL FB\nEND DATA\n"
        let e = LakeFleetClients.parseHydromet(Data(empty.utf8), site: "GCL", param: "FB")
        XCTAssertNil(e.error)
        XCTAssertTrue(e.rows.isEmpty)
    }

    // MARK: live

    func testLiveKeepsTheWindowInTheSiteZone() throws {
        let r = LakeFleetClients.hydrometLive(try fixture("gp_instant_CAFE_FB.txt"), site: "CAFE", param: "FB", timeZone: mountain,
                                              since: iso("2026-11-21T05:10:00Z"))
        XCTAssertNil(r.error)
        // 22:15 MST = 05:15Z; 22:00 is before the window, 22:45 is the sentinel
        XCTAssertEqual(r.observations.map(\.ft), [3787.56, 3787.56, 3787.58])
        XCTAssertEqual(r.observations.last?.at, iso("2026-11-21T06:00:00Z"))
        let summer = "DATE,CAFE FB\n07/15/2026 13:00,3795.10\n"
        let s = LakeFleetClients.hydrometLive(Data(summer.utf8), site: "CAFE", param: "FB", timeZone: mountain, since: iso("2026-07-01T00:00:00Z"))
        XCTAssertEqual(s.observations.first?.at, iso("2026-07-15T19:00:00Z"), "July: MDT, UTC-6")
        let daily = LakeFleetClients.hydrometLive(Data("DATE,CAFE FB\n11/20/2026,3787.5\n".utf8), site: "CAFE", param: "FB", timeZone: mountain,
                                                  since: iso("2026-11-01T00:00:00Z"))
        XCTAssertNotNil(daily.error, "a daily row is not a live reading")
    }

    func testLiveBindingsFailClosedBeforeAnyRequest() async {
        let feeds = PublicLakeLevelFeeds()
        let now = iso("2026-11-21T12:00:00Z")
        func ref(_ station: String, _ series: String?) -> LevelSeriesRef {
            LevelSeriesRef(provider: .hydromet, capability: .directOperatorPool, station: station, series: series, cadenceMin: 60, lagMin: 240)
        }
        let noZone = await feeds.recent(ref("PN:GCL", "FB"), hours: 24, now: now)
        XCTAssertTrue(noZone.error?.contains("time zone") == true, noZone.error ?? "")
        let storage = await feeds.recent(ref("PN:GCL:America/Los_Angeles", "AF"), hours: 24, now: now)
        XCTAssertTrue(storage.error?.contains("not a reservoir elevation") == true, storage.error ?? "")
        let region = await feeds.recent(ref("LC:HOOVER:America/Phoenix", "FB"), hours: 24, now: now)
        XCTAssertTrue(region.error?.contains("REGION:SITE") == true, region.error ?? "")
    }

    // MARK: generated table + scope

    func testGeneratedHistoryRecordMapsToHydrometDaily() throws {
        let json = #"{"kind":"hydrometDaily","region":"PN","site":"GCL","param":"FB","offsetFt":1.25}"#
        let h = try JSONDecoder().decode(LakeGeneratedBindings.Record.Hist.self, from: Data(json.utf8))
        XCTAssertEqual(LakeGeneratedBindings.history(h), .hydrometDaily(region: "PN", site: "GCL", param: "FB", offsetFt: 1.25))
        let missing = try JSONDecoder().decode(LakeGeneratedBindings.Record.Hist.self, from: Data(#"{"kind":"hydrometDaily","site":"GCL"}"#.utf8))
        XCTAssertNil(LakeGeneratedBindings.history(missing))
        XCTAssertEqual(LakeHistorySource.hydrometDaily(region: "gp", site: "cafe", param: "fb", offsetFt: 0).profileDescription,
                       "hydromet:GP:CAFE:FB (Reclamation Hydromet daily archive, midnight reading)")
    }

    func testNoLakeIsBoundToHydromet() {
        XCTAssertFalse(LakeSourceBindings.all.contains { $0.live.contains { $0.provider == .hydromet } }, "binding a lake needs the owner's review")
        XCTAssertFalse(LakeSourceBindings.all.contains { $0.history.contains { if case .hydrometDaily = $0 { return true }; return false } })
    }

    // MARK: USACE Northwestern Division offices (NWDP / NWDM) use the existing CWMS reader

    /// The CWMS reader passes the binding's office through unchanged, so a series published under the division office id is read like any
    /// district's. Reviewed bindings already do this (e.g. Moses Lake|WA on NWDP, Lake Oahe|SD on NWDM).
    func testDivisionOfficeIsPassedThroughToCWMS() async {
        final class Capture: @unchecked Sendable { let lock = NSLock(); var urls: [String] = [] }
        let cap = Capture()
        let now = iso("2026-11-21T12:00:00Z")
        let body = cwmsPage(now: now, hours: 6, lagH: 1, ft: 1046.4)
        let transport = CWMSTransport(fetch: { url, _, _ in
            cap.lock.withLock { cap.urls.append(url) }
            return .success(CWMSResponse(status: 200, body: body, retryAfter: nil))
        }, sleep: { _ in }, jitter: { 0 }, log: { _ in })
        let feeds = PublicLakeLevelFeeds(cwmsTransport: transport)
        let ref = LevelSeriesRef(provider: .cwms, capability: .directOperatorPool, station: "NWDP", series: "MLAW.Elev-Forebay.Inst.0.0.RFC-RAW",
                                 cadenceMin: 60, lagMin: 120)
        let r = await feeds.recent(ref, hours: 6, now: now)
        XCTAssertNil(r.error)
        XCTAssertEqual(r.observations.count, 6)
        let url = cap.lock.withLock { cap.urls.first } ?? ""
        XCTAssertTrue(url.contains("office=NWDP"), url)
        XCTAssertTrue(url.contains("name=MLAW.Elev-Forebay.Inst.0.0.RFC-RAW"), url)
    }

    func testReviewedBindingsAlreadyReadDivisionOffices() {
        let division: Set<String> = ["NWDP", "NWDM"]
        let reviewed = LakeSourceBindings.all.filter { $0.status == .reviewed && $0.live.contains { $0.provider == .cwms && division.contains($0.station) } }
        XCTAssertFalse(reviewed.isEmpty)
    }
}
