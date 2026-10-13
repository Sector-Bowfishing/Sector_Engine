//
//  DamRosterTests.swift
//  SectorEngineTests
//
//  DamRoster is generated data (scripts/generate-dam-roster.py), and WaterContext
//  trusts it to say which water a dam releases into. A tailwater whose dam is
//  missing resolves as the lake above it and loses its release gauges, so these
//  tests gate regeneration: the roster decodes, every scoring dam is present,
//  the tailwaters the gauge-selection spec was validated on exist with usable
//  reaches, and the reach site lists the selector tests lean on are intact.
//

import XCTest
#if canImport(CoreLocation)
import CoreLocation
#endif
@testable import SectorEngine

final class DamRosterTests: XCTestCase {

    private func dam(_ name: String) -> RosterDam? {
        DamRoster.all.first { $0.name == name }
    }

    // MARK: Decoding

    func testPolylineDecodesGoogleReferenceVector() {
        // The worked example from Google's encoded-polyline documentation.
        let points = RosterDam.decodePolyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
        XCTAssertEqual(points.count, 3)
        XCTAssertEqual(points[0].lat, 38.5, accuracy: 1e-9)
        XCTAssertEqual(points[0].lon, -120.2, accuracy: 1e-9)
        XCTAssertEqual(points[1].lat, 40.7, accuracy: 1e-9)
        XCTAssertEqual(points[1].lon, -120.95, accuracy: 1e-9)
        XCTAssertEqual(points[2].lat, 43.252, accuracy: 1e-9)
        XCTAssertEqual(points[2].lon, -126.453, accuracy: 1e-9)
        XCTAssertEqual(RosterDam.encodePolyline(points), "_p~iF~ps|U_ulLnnqC_mqNvxq`@")
    }

    func testMalformedPolylineStopsAtLastWholeVertex() {
        // A truncated string must not trap: generated data is trusted, fixtures aren't.
        XCTAssertEqual(RosterDam.decodePolyline("_p~iF~ps|U_ulL").count, 1)
        XCTAssertTrue(RosterDam.decodePolyline("").isEmpty)
    }

    func testFixtureInitRoundTripsVertices() {
        let fixture = RosterDam(id: "fixture", name: "Fixture Dam", latitude: 36.3639, longitude: -92.5769,
                                reach: [(36.3649, -92.5778), (36.3594, -92.5911), (36.3559, -92.5949)])
        XCTAssertEqual(fixture.reach.count, 3)
        XCTAssertEqual(fixture.reach[1].lat, 36.3594, accuracy: 1e-9)
        XCTAssertEqual(fixture.reach[1].lon, -92.5911, accuracy: 1e-9)
        let same = RosterDam(id: "fixture", name: "Fixture Dam", latitude: 36.3639, longitude: -92.5769,
                             coordinateSource: "fixture", river: "", impoundmentLakeID: nil, impoundmentName: nil,
                             normalPoolFt: nil, encodedReach: fixture.encodedReach, reachSiteCodes: [],
                             snapMiles: 0, scoresTailwater: false)
        XCTAssertEqual(fixture, same)
    }

    func testGeneratedRosterDecodesWithUsableReaches() {
        let all = DamRoster.all
        XCTAssertGreaterThan(all.count, 100)
        XCTAssertEqual(Set(all.map(\.id)).count, all.count, "ids must be unique")
        XCTAssertEqual(Set(all.map(\.name)).count, all.count, "names must be unique")
        for d in all {
            XCTAssertGreaterThanOrEqual(d.reach.count, 2, d.name)
            guard let start = d.reach.first else { continue }
            // The reach starts at the dam's projection onto NHDPlus, snapMiles away.
            let startMiles = TailwaterRegistry.haversineMiles(lat1: d.latitude, lon1: d.longitude,
                                                              lat2: start.lat, lon2: start.lon)
            XCTAssertEqual(startMiles, d.snapMiles, accuracy: 0.01, d.name)
            if let lakeID = d.impoundmentLakeID {
                XCTAssertTrue(LakeDirectory.all.contains { $0.id == lakeID }, "\(d.name): \(lakeID)")
            }
        }
    }

    // MARK: Coverage

    func testEveryTailwaterRegistryDamIsPresent() {
        for registered in TailwaterRegistry.dams {
            guard let d = dam(registered.name) else {
                XCTFail("\(registered.name) missing from DamRoster")
                continue
            }
            XCTAssertTrue(d.scoresTailwater, registered.name)
            XCTAssertEqual(d.coordinateSource, "TailwaterRegistry", registered.name)
        }
        XCTAssertEqual(DamRoster.all.filter(\.scoresTailwater).count, TailwaterRegistry.dams.count)
    }

    /// The tailwaters the gauge-selection rule was validated on (spec test
    /// testGeneratedRosterCoversKnownTailwaters). Each needs a reach and a
    /// coordinate that snaps to NHDPlus, or its face/tailwater geometry is wrong.
    func testKnownTailwatersExistWithSnappedReaches() {
        let known = [
            "Buford", "Bull Shoals", "Table Rock", "Beaver", "Norfork", "Greers Ferry", "Allatoona", "Carters",
            "West Point", "Philpott", "Saluda", "Pinopolis", "Bagnell", "Keystone", "Denison", "Tenkiller Ferry",
            "Broken Bow", "Walter F. George", "Livingston", "Hartwell", "J. Strom Thurmond", "Wolf Creek",
            "Kinzua", "Holter", "Folsom", "Gathright", "Beltzville",
        ]
        for name in known.map({ "\($0) Dam" }) {
            guard let d = dam(name) else {
                XCTFail("\(name) missing from DamRoster")
                continue
            }
            XCTAssertGreaterThanOrEqual(d.reach.count, 2, name)
            XCTAssertLessThanOrEqual(d.snapMiles, 0.25, name)
        }
        XCTAssertNotNil(dam("Kentucky Dam"))
        XCTAssertNotNil(dam("Murray Lock and Dam"))
    }

    /// GaugeSelector's on-reach test reads these lists; the Buford cases in the
    /// spec (mainstem turbidity, the Suwanee pond rejecting McGinnis Ferry) rely on
    /// them. The Lanier forebay gauge sits behind the dam and must not be listed.
    func testBufordReachListsTailwaterGaugesNotTheForebay() throws {
        let buford = try XCTUnwrap(dam("Buford Dam"))
        XCTAssertEqual(buford.impoundmentLakeID, "Lanier (Sidney Lanier)|GA")
        for code in ["02334430", "02334500", "02334653"] {
            XCTAssertTrue(buford.reachSiteCodes.contains(code), code)
        }
        XCTAssertFalse(buford.reachSiteCodes.contains("02334400"))
    }

    // MARK: Lookup

    func testDamsWithinOrdersByDistance() throws {
        let atBullShoals = CLLocationCoordinate2D(latitude: 36.3639, longitude: -92.5769)
        let hits = DamRoster.dams(within: 35, of: atBullShoals)
        XCTAssertEqual(hits.first?.0.name, "Bull Shoals Dam")
        XCTAssertEqual(try XCTUnwrap(hits.first).1, 0, accuracy: 0.01)
        XCTAssertTrue(hits.contains { $0.0.name == "Norfork Dam" })
        XCTAssertEqual(hits.map(\.1), hits.map(\.1).sorted())
        XCTAssertTrue(hits.allSatisfy { $0.1 <= 35 })
        XCTAssertFalse(hits.contains { $0.0.name == "Table Rock Dam" }, "Table Rock is ~48 mi away")
    }

    func testDamsWithinUsesTheGivenRoster() {
        let near = RosterDam(id: "a", name: "A", latitude: 35.0, longitude: -90.0, reach: [(35.0, -90.0), (34.9, -90.0)])
        let mid = RosterDam(id: "b", name: "B", latitude: 35.1, longitude: -90.0, reach: [(35.1, -90.0), (35.0, -90.0)])
        let far = RosterDam(id: "c", name: "C", latitude: 36.0, longitude: -90.0, reach: [(36.0, -90.0), (35.9, -90.0)])
        let hits = DamRoster.dams(within: 10, of: CLLocationCoordinate2D(latitude: 34.99, longitude: -90.0),
                                  in: [far, mid, near])
        XCTAssertEqual(hits.map(\.0.id), ["a", "b"])
        XCTAssertEqual(hits[0].1, 0.69, accuracy: 0.01)
        XCTAssertEqual(hits[1].1, 7.60, accuracy: 0.02)
    }
}
