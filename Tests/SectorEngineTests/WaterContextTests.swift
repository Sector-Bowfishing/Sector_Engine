//
//  WaterContextTests.swift
//  SectorEngineTests
//
//  WaterContext decides whether a point is on a lake, below a dam, or neither,
//  and GaugeSelector trusts gauges only for that water. A wrong answer is a
//  wrong reading: Lake Lanier took 52 °F release water from the gauge at Buford
//  Dam, and the Bull Shoals production coordinate (a bluff over the lake) took
//  the tailwater's 59 °F. The fixture cases pin each branch of rule step B on
//  hand-checked reach vertices (gauge_final.json); the golden cases run the
//  generated DamRoster against the points the Python prototype was judged on,
//  so a regenerated roster can't silently move a tailwater onto a lake.
//

import XCTest
#if canImport(CoreLocation)
import CoreLocation
#endif
@testable import SectorEngine

final class WaterContextTests: XCTestCase {

    // MARK: Fixtures

    private let bullShoals = RosterDam(
        id: "bull-shoals-dam", name: "Bull Shoals Dam", latitude: 36.3639, longitude: -92.5769,
        impoundmentLakeID: "Bull Shoals Lake|AR", impoundmentName: "Bull Shoals Lake", normalPoolFt: 654,
        reach: [(36.3649, -92.5778), (36.3594, -92.5911), (36.3559, -92.5949), (36.3536, -92.5948),
                (36.3486, -92.5911), (36.3482, -92.5895), (36.3434, -92.583), (36.3421, -92.5756),
                (36.3435, -92.5731), (36.3438, -92.5699)])

    /// The spec's Buford dam coordinate with the first three vertices of the
    /// generated Buford reach (DamRoster.all, 2026-09-14 generation).
    private let buford = RosterDam(
        id: "buford-dam", name: "Buford Dam", latitude: 34.1597, longitude: -84.0750,
        impoundmentLakeID: "Lanier (Sidney Lanier)|GA", impoundmentName: "Lanier (Sidney Lanier)", normalPoolFt: 1065.77,
        reach: [(34.16204, -84.0757), (34.16055, -84.07631), (34.15835, -84.07599)])

    private let keystone = RosterDam(
        id: "keystone-dam", name: "Keystone Dam", latitude: 36.1503, longitude: -96.2506,
        impoundmentLakeID: "Keystone Lake|OK", impoundmentName: "Keystone Lake",
        reach: [(36.1494, -96.251), (36.1463, -96.2468), (36.143, -96.2447), (36.1403, -96.2406),
                (36.1389, -96.2348), (36.1407, -96.2208)])

    private let bagnell = RosterDam(
        id: "bagnell-dam", name: "Bagnell Dam", latitude: 38.2047, longitude: -92.6231,
        impoundmentLakeID: "Lake of the Ozarks|MO", impoundmentName: "Lake of the Ozarks",
        reach: [(38.2035, -92.6247), (38.1941, -92.6157), (38.1919, -92.6104), (38.1914, -92.6075),
                (38.1906, -92.596), (38.192, -92.5938), (38.1981, -92.5883)])

    private func resolve(_ lat: Double, _ lon: Double, elevation: Double? = nil, pool: Double? = nil,
                         roster: [RosterDam]? = nil) -> WaterContextResolution {
        WaterContext.resolve(latitude: lat, longitude: lon, groundElevationFt: elevation,
                             poolFtForDam: { pool ?? $0.normalPoolFt },
                             roster: roster ?? DamRoster.all, directory: LakeDirectory.all)
    }

    private func assertLake(_ r: WaterContextResolution, _ name: String,
                            file: StaticString = #filePath, line: UInt = #line) {
        guard case .lake(let ref) = r.context else {
            return XCTFail("expected lake(\(name)), got \(describe(r))", file: file, line: line)
        }
        XCTAssertEqual(ref.name, name, r.reason, file: file, line: line)
    }

    private func assertBelowDam(_ r: WaterContextResolution, _ damName: String,
                                file: StaticString = #filePath, line: UInt = #line) {
        guard case .belowDam(let dam, _, _) = r.context else {
            return XCTFail("expected belowDam(\(damName)), got \(describe(r))", file: file, line: line)
        }
        XCTAssertEqual(dam.name, damName, r.reason, file: file, line: line)
    }

    private func assertOpen(_ r: WaterContextResolution, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertEqual(r.context, .open, "got \(describe(r))", file: file, line: line)
    }

    private func describe(_ r: WaterContextResolution) -> String {
        switch r.context {
        case .lake(let ref): return "lake(\(ref.name)) — \(r.reason)"
        case .belowDam(let dam, let miles, let own):
            return "belowDam(\(dam.name), \(miles) mi, ownLake \(own?.name ?? "nil")) — \(r.reason)"
        case .open: return "open — \(r.reason)"
        }
    }

    // MARK: Fixture roster

    func testExactDirectoryCoordinateIsLake() {
        let r = resolve(36.45, -92.55, roster: [bullShoals])
        assertLake(r, "Bull Shoals Lake")
        XCTAssertEqual(r.context.damName, "Bull Shoals Dam")
        XCTAssertEqual(r.context.lakeID, "Bull Shoals Lake|AR")
        XCTAssertFalse(r.context.isBelowDam)
    }

    func testOnReachIsBelowDam() {
        for (lat, lon) in [(36.343, -92.578), (36.3622, -92.584)] {
            let r = resolve(lat, lon, roster: [bullShoals])
            assertBelowDam(r, "Bull Shoals Dam")
            guard case .belowDam(_, _, let ownLake) = r.context else { continue }
            XCTAssertNil(ownLake, "(\(lat), \(lon))")
            XCTAssertTrue(r.context.isBelowDam)
            XCTAssertEqual(r.context.damName, "Bull Shoals Dam")
            XCTAssertNil(r.context.lakeName)
        }
    }

    func testReservoirFaceNearDamIsLake() {
        // DEM-verified pool surface (653 ft), 0.3 mi from the dam.
        assertLake(resolve(36.36607, -92.57223, roster: [bullShoals]), "Bull Shoals Lake")
        assertLake(resolve(36.3639, -92.57151, roster: [bullShoals]), "Bull Shoals Lake")
        // 0.35 mi from the reach start: outside the 0.30 mi face corridor.
        assertLake(resolve(34.1597, -84.06975, roster: [buford]), "Lanier (Sidney Lanier)")
    }

    func testBluffAbovePoolIsLakeOnlyWithElevation() {
        // The Bull Shoals production coordinate: 784 ft ground over a 654 ft pool.
        let bluff = resolve(36.36, -92.58, elevation: 784, pool: 654, roster: [bullShoals])
        assertLake(bluff, "Bull Shoals Lake")
        XCTAssertTrue(bluff.reason.contains("bluff"), bluff.reason)
        // No elevation: deterministic belowDam, never a guess.
        assertBelowDam(resolve(36.36, -92.58, elevation: nil, pool: 654, roster: [bullShoals]), "Bull Shoals Dam")
        // A bank 19 ft over pool is still the tailwater.
        assertBelowDam(resolve(36.36, -92.58, elevation: 673, pool: 654, roster: [bullShoals]), "Bull Shoals Dam")
    }

    func testDownstreamSectorCatchesOffCenterlineTailwater() {
        let roster = [keystone, bagnell]
        let keystoneTailwater = resolve(36.146, -96.238, roster: roster)
        assertBelowDam(keystoneTailwater, "Keystone Dam")
        assertLake(resolve(36.15, -96.25, roster: roster), "Keystone Lake")          // exact directory point
        assertBelowDam(resolve(38.199, -92.605, roster: roster), "Bagnell Dam")
        assertBelowDam(resolve(38.203, -92.620, roster: roster), "Bagnell Dam")
        assertLake(resolve(38.20, -92.63, roster: roster), "Lake of the Ozarks")     // exact directory point
    }

    func testBehindTheDamIsNeverOnTheReach() {
        // Straight upstream of the Bull Shoals dam end, inside the 0.30 corridor
        // distance of the reach start but behind it: the reservoir side.
        let behind = WaterContext.distanceToReach(bullShoals.reach, lat: 36.3665, lon: -92.5730, allowBehind: false)
        XCTAssertNil(behind)
        // Inside damNoiseMiles the side test is skipped.
        let noisy = WaterContext.distanceToReach(bullShoals.reach, lat: 36.3665, lon: -92.5730, allowBehind: true)
        XCTAssertNotNil(noisy)
        XCTAssertEqual(noisy?.alongMiles ?? -1, 0, accuracy: 1e-9)
        XCTAssertLessThan(noisy?.firstSegmentT ?? 1, 0)
    }

    func testReachPointWalksAlongTheLine() {
        let reach = bagnell.reach
        let start = WaterContext.reachPoint(reach, atAlongMiles: 0)
        XCTAssertEqual(start.lat, reach[0].lat, accuracy: 1e-9)
        XCTAssertEqual(start.lon, reach[0].lon, accuracy: 1e-9)
        let end = WaterContext.reachPoint(reach, atAlongMiles: 100)
        XCTAssertEqual(end.lat, reach[reach.count - 1].lat, accuracy: 1e-9)
        // A point placed 1 mi along lies on the line, 1 mi along.
        let mid = WaterContext.reachPoint(reach, atAlongMiles: 1)
        let projection = WaterContext.distanceToReach(reach, lat: mid.lat, lon: mid.lon, allowBehind: false)
        XCTAssertEqual(projection?.miles ?? 1, 0, accuracy: 1e-6)
        XCTAssertEqual(projection?.alongMiles ?? 0, 1, accuracy: 1e-6)
    }

    // MARK: Generated roster

    func testOffReachPointsAreOpenOrLakeByIdentity() {
        assertOpen(resolve(34.05, -84.00))       // Suwanee pond, off the Buford reach
        assertOpen(resolve(34.237, -84.495))     // Etowah at Canton, 14 mi above Allatoona
        assertOpen(resolve(34.066, -84.68))      // Lake Acworth, 7.0 mi from the Allatoona point
        assertOpen(resolve(33.87, -84.03))       // Yellow River near Snellville
        let lanier = resolve(34.20, -83.98)      // Lanier reported point, 5.3 mi from its directory point
        assertLake(lanier, "Lanier (Sidney Lanier)")
        XCTAssertEqual(lanier.context.damName, "Buford Dam")
    }

    func testGeneratedRosterCoversKnownTailwaters() {
        let known = ["Buford", "Bull Shoals", "Table Rock", "Beaver", "Norfork", "Greers Ferry", "Allatoona",
                     "Carters", "West Point", "Philpott", "Saluda", "Pinopolis", "Bagnell", "Keystone", "Denison",
                     "Tenkiller Ferry", "Broken Bow", "Walter F. George", "Livingston", "Hartwell",
                     "J. Strom Thurmond", "Wolf Creek", "Kinzua", "Holter", "Folsom", "Gathright", "Beltzville"]
        for name in known {
            guard let dam = DamRoster.all.first(where: { $0.name == "\(name) Dam" }) else {
                XCTFail("\(name) Dam missing from DamRoster"); continue
            }
            XCTAssertGreaterThanOrEqual(dam.reach.count, 2, dam.name)
            XCTAssertLessThanOrEqual(dam.snapMiles, 0.25, dam.name)
        }
        let rosterNames = Set(DamRoster.all.map(\.name))
        for dam in TailwaterRegistry.dams {
            XCTAssertTrue(rosterNames.contains(dam.name), "\(dam.name) (TailwaterRegistry) missing from DamRoster")
        }
    }

    func testGoldenScenarioContexts() {
        assertBelowDam(resolve(34.150, -84.083), "Buford Dam")
        assertBelowDam(resolve(33.9858, -84.3157), "Buford Dam")          // Roswell, ~50 river km down
        assertBelowDam(resolve(36.343, -92.578), "Bull Shoals Dam")
        assertBelowDam(resolve(36.5950, -93.3080), "Table Rock Dam")
        assertBelowDam(resolve(36.68, -93.10), "Table Rock Dam")          // Forsyth, ~25 mi along
        assertLake(resolve(36.64, -93.22), "Lake Taneycomo")
        assertBelowDam(resolve(32.9168, -85.1878), "West Point Dam")
        assertBelowDam(resolve(34.1633, -84.7320), "Allatoona Dam")
        assertBelowDam(resolve(35.5870, -95.0580), "Tenkiller Ferry Dam")
        assertBelowDam(resolve(33.815, -96.565), "Denison Dam")
        assertBelowDam(resolve(36.1167, -92.1431), "Norfork Dam")         // Calico Rock
        assertBelowDam(resolve(36.215, -92.285), "Norfork Dam")
        assertBelowDam(resolve(37.03, -88.29), "Kentucky Dam")
        assertBelowDam(resolve(37.018, -88.280), "Kentucky Dam")
        assertBelowDam(resolve(34.785, -92.345), "Murray Lock and Dam")
        assertLake(resolve(30.75, -84.85), "Seminole")
        assertLake(resolve(33.25, -80.02), "Lake Moultrie")
        assertOpen(resolve(33.836, -79.046))                               // Waccamaw at Conway
        assertLake(resolve(36.54, -85.45), "Dale Hollow Lake")
    }
}
