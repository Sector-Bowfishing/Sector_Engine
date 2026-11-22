//
//  LakeBrainUSGSStageTests.swift
//  Lake Brain: USGS gage height (00065) + the site's published altitude (LakeLevelFeedsUSGSStage.swift). No network.
//
//  Fixtures (tests/fixtures/usgs-stage/): `04082500_site.rdb` has the site service's expanded RDB layout (42 columns, field-width
//  row). Its header, field-width row and the values of station_nm, site_tp_cd, alt_va (743.91), alt_meth_cd, alt_acy_va (.01),
//  alt_datum_cd (NAVD88) and tz_cd were read from the live service on 2026-11-22 (Lake Winnebago at Oshkosh); the coordinates are
//  approximate and the other columns blank. `04082500_iv_00065.json` has the WaterServices IV JSON shape with a -999999 row; its
//  stage values are illustrative (2.84 ft + 743.91 ft = 746.75 ft, the level the 2026-10-13 exercise recorded for this lake).
//  Neither is a byte-for-byte capture (the session's shell could not reach the host).
//

import XCTest
@testable import SectorEngine
@testable import LakeBrain

final class LakeBrainUSGSStageTests: XCTestCase {

    func iso(_ s: String) -> Date { ISO8601DateFormatter().date(from: s)! }

    static func fixture(_ name: String) throws -> Data {
        try Data(contentsOf: URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("fixtures/usgs-stage/\(name)"))
    }

    static func ok(_ d: Data) -> LakeFeedHTTP.Response { LakeFeedHTTP.Response(status: 200, body: d) }

    func client(_ rec: URLRecorder, site: Data?, iv: Data?) -> LakeUSGSStageClient {
        LakeUSGSStageClient.legacy(fetch: { url, _ in
            rec.add(url)
            if url.contains("/nwis/site/") { return site.map(Self.ok) }
            return iv.map(Self.ok)
        }, cache: USGSSiteCache())
    }

    func ref(_ datum: String?) -> LevelSeriesRef {
        LevelSeriesRef(provider: .usgsStage, capability: .directLakeGauge, station: "04082500", series: datum, cadenceMin: 60, lagMin: 60)
    }

    // MARK: site record

    func testSiteRecordGivesAltitudeAndDatum() throws {
        guard case .ok(let d) = LakeUSGSStageClient.parseSiteRDB(try Self.fixture("04082500_site.rdb"), site: "04082500") else { return XCTFail() }
        XCTAssertEqual(d.altitudeFt, 743.91)
        XCTAssertEqual(d.datum, "NAVD88")
        XCTAssertEqual(d.siteType, "LK")
        XCTAssertEqual(d.name, "LAKE WINNEBAGO AT OSHKOSH, WI")
        XCTAssertEqual(d.accuracyFt ?? 0, 0.01, accuracy: 1e-9)
    }

    func testSiteWithoutAltitudeOrDatumIsRefused() throws {
        let rdb = String(decoding: try Self.fixture("04082500_site.rdb"), as: UTF8.self)
        let noAlt = rdb.replacingOccurrences(of: " 743.91", with: "")
        guard case .refused(let a) = LakeUSGSStageClient.parseSiteRDB(Data(noAlt.utf8), site: "04082500") else { return XCTFail() }
        XCTAssertTrue(a.contains("alt_va"))
        let noDatum = rdb.replacingOccurrences(of: "NAVD88", with: "")
        guard case .refused(let b) = LakeUSGSStageClient.parseSiteRDB(Data(noDatum.utf8), site: "04082500") else { return XCTFail() }
        XCTAssertTrue(b.contains("alt_datum_cd"))
        guard case .refused = LakeUSGSStageClient.parseSiteRDB(Data(rdb.utf8), site: "04084445") else { return XCTFail("another site's row is not this site") }
        guard case .refused = LakeUSGSStageClient.parseSiteRDB(Data("# No sites found matching all criteria\n".utf8), site: "04082500") else { return XCTFail() }
    }

    // MARK: live

    func testStageIsShiftedByTheSiteAltitude() async throws {
        let rec = URLRecorder()
        let c = client(rec, site: try Self.fixture("04082500_site.rdb"), iv: try Self.fixture("04082500_iv_00065.json"))
        let r = await c.recent(ref("NAVD88"), hours: 192)
        XCTAssertNil(r.error)
        XCTAssertEqual(r.observations.map(\.ft).count, 3, "-999999 dropped")
        XCTAssertEqual(r.observations[0].ft, 746.75, accuracy: 1e-9)
        XCTAssertEqual(r.observations[0].at, iso("2026-11-22T10:00:00Z"))
        XCTAssertEqual(r.observations[2].ft, 746.74, accuracy: 1e-9)
        let iv = try XCTUnwrap(rec.urls.first { $0.contains("/nwis/iv/") })
        XCTAssertTrue(iv.contains("sites=04082500") && iv.contains("parameterCd=00065") && iv.contains("period=PT192H"), iv)
        XCTAssertEqual(ref("NAVD88").sourceId, "usgs-stage:04082500:00065:NAVD88")
    }

    func testRefusedWithoutAnExpectedDatumOrOnADifferentDatum() async throws {
        let rec = URLRecorder()
        let c = client(rec, site: try Self.fixture("04082500_site.rdb"), iv: try Self.fixture("04082500_iv_00065.json"))
        let none = await c.recent(ref(nil), hours: 24)
        XCTAssertNotNil(none.error)
        XCTAssertTrue(rec.urls.isEmpty, "refused before any request")
        let other = await c.recent(ref("NGVD29"), hours: 24)
        XCTAssertTrue(other.error?.contains("NAVD88") ?? false, other.error ?? "")
        XCTAssertTrue(other.observations.isEmpty)
        XCTAssertFalse(rec.urls.contains { $0.contains("/nwis/iv/") }, "no gage height is read when the datum does not match")
    }

    func testStageNotInFeetIsRefused() throws {
        let iv = String(decoding: try Self.fixture("04082500_iv_00065.json"), as: UTF8.self).replacingOccurrences(of: #""unitCode":"ft""#, with: #""unitCode":"m""#)
        let r = LakeUSGSStageClient.stageReadings(Data(iv.utf8), site: "04082500", altitudeFt: 743.91)
        XCTAssertNotNil(r.error)
    }

    func testSeveralGageHeightSeriesAtOneSiteAreRefused() throws {
        // A second `values` block (another method / sub-location, e.g. a dam's tailwater) in the same answer.
        let one = String(decoding: try Self.fixture("04082500_iv_00065.json"), as: UTF8.self)
        let block = #"{"value":[{"value":"9.10","qualifiers":["P"],"dateTime":"2026-11-22T04:00:00.000-06:00"}],"qualifier":[],"method":[{"methodDescription":"tailwater","methodID":2}]}"#
        let two = one.replacingOccurrences(of: #""values":[{"#, with: #""values":[\#(block),{"#)
        XCTAssertNotEqual(one, two)
        let r = LakeUSGSStageClient.stageReadings(Data(two.utf8), site: "04082500", altitudeFt: 743.91)
        XCTAssertTrue(r.error?.contains("sub-locations") ?? false, r.error ?? "")
        XCTAssertEqual(LakeFleetClients.usgsSeriesPerStatistic(Data(one.utf8)), 1)
    }

    func testZeroAltitudeIsRefusedLiveAndInHistory() async throws {
        let rdb = String(decoding: try Self.fixture("04082500_site.rdb"), as: UTF8.self).replacingOccurrences(of: " 743.91", with: "0")
        let rec = URLRecorder()
        let c = client(rec, site: Data(rdb.utf8), iv: try Self.fixture("04082500_iv_00065.json"))
        let live = await c.recent(ref("NAVD88"), hours: 24)
        XCTAssertTrue(live.error?.contains("altitude is 0") ?? false, live.error ?? "")
        let h = await c.daily(site: "04082500", datum: "NAVD88", stat: "dv", since: nil, now: iso("2026-11-22T12:00:00Z"),
                              timeZone: TimeZone(identifier: "UTC")!, fleet: LakeFleetClients.legacy(transport: { _, _, _ in nil }))
        XCTAssertNil(h)
        XCTAssertFalse(LakeUSGSStageClient.isSiteNumber("０４０８２５００"), "ASCII digits only")
    }

    func testSiteRecordIsReadOncePerRun() async throws {
        let rec = URLRecorder()
        let c = client(rec, site: try Self.fixture("04082500_site.rdb"), iv: try Self.fixture("04082500_iv_00065.json"))
        _ = await c.altitude(site: "04082500", expectedDatum: "NAVD88")
        let again = await c.altitude(site: "04082500", expectedDatum: "navd88")
        XCTAssertEqual(again.ft, 743.91)
        XCTAssertEqual(rec.urls.filter { $0.contains("/nwis/site/") }.count, 1)
    }

    func testUnreachableSiteServiceIsAnError() async {
        let rec = URLRecorder()
        let c = client(rec, site: nil, iv: nil)
        let r = await c.recent(ref("NAVD88"), hours: 24)
        XCTAssertEqual(r.error, "USGS 04082500: site service unreachable")
    }

    // MARK: PublicLakeLevelFeeds wiring (refusals happen before any network call)

    func testFeedsRefuseAStageBindingWithoutADatum() async {
        let feeds = PublicLakeLevelFeeds.legacyUSGS()
        let live = await feeds.recent(ref(nil), hours: 24, now: Date())
        XCTAssertNotNil(live.error)
        let h = await feeds.daily(.usgsStageDaily(site: "04082500", datum: "", stat: "dv"), since: nil, now: Date(), timeZone: TimeZone(identifier: "UTC")!)
        XCTAssertNil(h)
    }

    func testHistorySourceDecodesFromTheGeneratedTable() throws {
        let h = try JSONDecoder().decode(LakeGeneratedBindings.Record.Hist.self,
                                         from: Data(#"{"kind":"usgsStageDaily","site":"04082500","datum":"NAVD88","stat":"dv"}"#.utf8))
        XCTAssertEqual(LakeGeneratedBindings.history(h), .usgsStageDaily(site: "04082500", datum: "NAVD88", stat: "dv"))
        XCTAssertTrue(LakeHistorySource.usgsStageDaily(site: "04082500", datum: "NAVD88", stat: "dv").profileDescription.contains("NAVD88"))
    }

    func testNoLakeIsBoundToUSGSStage() {
        for b in LakeSourceBindings.all {
            XCTAssertFalse(b.live.contains { $0.provider == .usgsStage }, b.lakeId)
            XCTAssertFalse(b.history.contains { if case .usgsStageDaily = $0 { return true } else { return false } }, b.lakeId)
        }
    }
}
