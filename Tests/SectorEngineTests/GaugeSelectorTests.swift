//
//  GaugeSelectorTests.swift
//  SectorEngineTests
//
//  GaugeSelector decides which USGS series may drive an input. Every case here
//  is a wrong answer the nearest-gauge rule gave on 2026-09-14 (gauge_final.json):
//  Lake Lanier scoring 52 °F release water and a generation pulse from the gauge
//  at Buford Dam, Lake Catherine reading a 153 °F hot spring, Calico Rock taking
//  North Fork water from 10.6 mi, a Suwanee pond borrowing the Buford reach's
//  cold flow. Site codes, names, values and distances are the prototype's cached
//  readings; dams are synthetic fixtures (the generated roster's first reach
//  vertices and the site codes each case needs) so a regenerated roster can't
//  move these verdicts. The open-pond case runs the generated roster on purpose.
//

import XCTest
#if canImport(CoreLocation)
import CoreLocation
#endif
@testable import SectorEngine

final class GaugeSelectorTests: XCTestCase {

    private let now = Date(timeIntervalSince1970: 1_789_425_000)

    // MARK: Fixtures

    private let buford = RosterDam(
        id: "buford-dam", name: "Buford Dam", latitude: 34.16215, longitude: -84.07582,
        impoundmentLakeID: "Lanier (Sidney Lanier)|GA", impoundmentName: "Lanier (Sidney Lanier)", normalPoolFt: 1065.77,
        reach: [(34.16204, -84.0757), (34.16055, -84.07631), (34.15835, -84.07599), (34.15684, -84.07837),
                (34.15449, -84.08055), (34.15329, -84.08073)],
        reachSiteCodes: ["02334401", "02334430", "02334500"])

    private let bullShoals = RosterDam(
        id: "bull-shoals-dam", name: "Bull Shoals Dam", latitude: 36.3639, longitude: -92.5769,
        impoundmentLakeID: "Bull Shoals Lake|AR", impoundmentName: "Bull Shoals Lake", normalPoolFt: 654,
        reach: [(36.3649, -92.5778), (36.3594, -92.5911), (36.3559, -92.5949), (36.3536, -92.5948),
                (36.3486, -92.5911), (36.3482, -92.5895), (36.3434, -92.583), (36.3421, -92.5756),
                (36.3435, -92.5731), (36.3438, -92.5699)],
        reachSiteCodes: ["07054502", "07054527"])

    private let norfork = RosterDam(
        id: "norfork-dam", name: "Norfork Dam", latitude: 36.2506, longitude: -92.2408,
        impoundmentLakeID: "Norfork|AR", impoundmentName: "Norfork", normalPoolFt: 552,
        reach: [(36.25029, -92.24199), (36.24885, -92.24182), (36.24624, -92.24245), (36.24559, -92.24956)],
        reachSiteCodes: ["07060500"])

    private let tableRock = RosterDam(
        id: "table-rock-dam", name: "Table Rock Dam", latitude: 36.5958, longitude: -93.3114,
        impoundmentLakeID: "Table Rock Lake|MO", impoundmentName: "Table Rock Lake", normalPoolFt: 915,
        reach: [(36.59519, -93.31231), (36.59467, -93.31177), (36.5945, -93.31041), (36.59583, -93.30892)],
        reachSiteCodes: ["07053450"])

    private let kentucky = RosterDam(
        id: "kentucky-dam", name: "Kentucky Dam", latitude: 37.01, longitude: -88.27,
        impoundmentLakeID: "Kentucky Lake|KY", impoundmentName: "Kentucky Lake", normalPoolFt: 359,
        reach: [(37.00996, -88.26939), (37.01322, -88.26809), (37.01237, -88.27042), (37.01822, -88.2752)])

    private func directoryLake(_ name: String, state: String? = nil) -> DirectoryLake {
        guard let lake = LakeDirectory.all.first(where: { $0.name == name && (state == nil || $0.state == state) }) else {
            fatalError("LakeDirectory has no \(name)")
        }
        return lake
    }

    private func lake(_ name: String, state: String? = nil) -> WaterContext {
        let row = directoryLake(name, state: state)
        return .lake(LakeRef(name: row.name, directoryLake: row, dam: nil))
    }

    private func reading(_ site: String, _ name: String, type: String? = "ST", code: String, value: Double,
                         miles: Double?, lat: Double = 0, lon: Double = 0, method: String? = nil, block: Int = 0,
                         age: TimeInterval = 30 * 60, change: Double = 0) -> WaterLevelReading {
        WaterLevelReading(siteCode: site, siteName: name, parameterCode: code, parameterName: code, value: value,
                          unit: "", dateTime: now.addingTimeInterval(-age), latitude: lat, longitude: lon,
                          trend: .steady, change: change, distanceMiles: miles,
                          siteTypeCode: type, methodDescription: method, blockIndex: block)
    }

    private func inputs(_ context: WaterContext, model: Double? = nil, pool: Double? = nil,
                        level: [WaterLevelReading] = []) -> GaugeInputs {
        GaugeInputs(context: context, now: now, modeledWaterTempF: model, poolFt: pool, levelCandidates: level)
    }

    private func decision(_ decisions: [GaugeDecision], _ site: String, code: String? = nil,
                          block: Int? = nil) -> GaugeDecision? {
        decisions.first { $0.siteCode == site && (code == nil || $0.parameterCode == code)
            && (block == nil || $0.blockIndex == block) }
    }

    private func explain(_ decisions: [GaugeDecision]) -> String {
        decisions.map { "\($0.siteCode)/\($0.parameterCode)/b\($0.blockIndex) \($0.role) "
            + "\($0.accepted ? "ACCEPT" : "reject"): \($0.reason)" }.joined(separator: "\n")
    }

    // MARK: Lake context

    func testLanierLakeRejectsTailwaterAndPicksPool() {
        let context = lake("Lanier (Sidney Lanier)")
        let level = [
            reading("02334401", "CHATTAHOOCHEE RIVER BUFORD DAM NR BUFORD, GA", code: "00065", value: 915.94,
                    miles: 6.10, lat: 34.1615833, lon: -84.0761111, change: 3.80),
            reading("02334430", "CHATTAHOOCHEE RIVER AT BUFORD DAM, NEAR BUFORD, GA", code: "00065", value: 2.51,
                    miles: 6.37, lat: 34.15666667, lon: -84.0784167),
            reading("02334400", "LAKE SIDNEY LANIER NEAR BUFORD, GA", type: "LK", code: "00062", value: 1065.00,
                    miles: 6.04, lat: 34.1627222, lon: -84.0755278, change: -0.03),
        ]
        let temp = [
            reading("02334430", "CHATTAHOOCHEE RIVER AT BUFORD DAM, NEAR BUFORD, GA", code: "00010", value: 11.1,
                    miles: 6.37, lat: 34.15666667, lon: -84.0784167),
            reading("02334480", "RICHLAND CREEK AT SUWANEE DAM ROAD, NEAR BUFORD,GA", code: "00010", value: 24.7,
                    miles: 6.94, lat: 34.1325, lon: -84.07),
            reading("02334500", "CHATTAHOOCHEE RIVER NEAR BUFORD, GA", code: "00010", value: 11.1,
                    miles: 8.25, lat: 34.1261111, lon: -84.09338889),
        ]
        let discharge = [
            reading("02334430", "CHATTAHOOCHEE RIVER AT BUFORD DAM, NEAR BUFORD, GA", code: "00060", value: 4790,
                    miles: 6.37, lat: 34.15666667, lon: -84.0784167, change: 4184),
        ]
        let turbidity = [
            reading("02334480", "RICHLAND CREEK AT SUWANEE DAM ROAD, NEAR BUFORD,GA", code: "63680", value: 11.0,
                    miles: 6.94, lat: 34.1325, lon: -84.07),
        ]
        let shared = inputs(context, pool: 1065, level: level)

        let levelResult = GaugeSelector.select(level, kind: .level, inputs: shared, roster: [buford])
        XCTAssertEqual(levelResult.pick?.siteCode, "02334400", explain(levelResult.decisions))
        XCTAssertEqual(levelResult.pick?.acceptance, .matchedPool)

        let tempResult = GaugeSelector.select(temp, kind: .waterTemp, inputs: shared, roster: [buford])
        XCTAssertNil(tempResult.pick, explain(tempResult.decisions))
        let release = decision(tempResult.decisions, "02334430")
        XCTAssertEqual(release?.accepted, false)
        XCTAssertTrue(release?.reason.contains("release") ?? false, release?.reason ?? "no decision")

        let dischargeResult = GaugeSelector.select(discharge, kind: .discharge, inputs: shared, roster: [buford])
        XCTAssertNil(dischargeResult.pick, explain(dischargeResult.decisions))

        let turbidityResult = GaugeSelector.select(turbidity, kind: .turbidity, inputs: shared, roster: [buford])
        XCTAssertNil(turbidityResult.pick, explain(turbidityResult.decisions))
    }

    func testTaneycomoOwnColdGaugeKeptTableRockReleaseRejected() {
        let context = lake("Lake Taneycomo")
        let level = [
            reading("07053600", "Lake Taneycomo at School of the Ozarks, MO", type: "LK", code: "62615", value: 701.51,
                    miles: 2.01, lat: 36.6173333, lon: -93.24275),
            reading("07053690", "Turkey Creek near Hollister, MO", code: "00065", value: 2.50,
                    miles: 3.99, lat: 36.58277778, lon: -93.2102778),
        ]
        let temp = [
            reading("07053600", "Lake Taneycomo at School of the Ozarks, MO", type: "LK", code: "00010", value: 15.6,
                    miles: 2.01, lat: 36.6173333, lon: -93.24275),
            reading("07053450", "White River bl Table Rock Dam near Branson, MO", code: "00010", value: 13.0,
                    miles: 3.2, lat: 36.5950631, lon: -93.3090721),
        ]
        let shared = inputs(context, pool: nil, level: level)

        let levelResult = GaugeSelector.select(level, kind: .level, inputs: shared, roster: [tableRock])
        XCTAssertEqual(levelResult.pick?.siteCode, "07053600", explain(levelResult.decisions))
        XCTAssertEqual(levelResult.pick?.parameterCode, "62615")
        XCTAssertEqual(decision(levelResult.decisions, "07053690")?.accepted, false)

        let tempResult = GaugeSelector.select(temp, kind: .waterTemp, inputs: shared, roster: [tableRock])
        XCTAssertEqual(tempResult.pick?.siteCode, "07053600", explain(tempResult.decisions))
        XCTAssertEqual((tempResult.pick?.value ?? 0) * 9 / 5 + 32, 60.08, accuracy: 0.01)
        XCTAssertEqual(tempResult.pick?.acceptance, .matchedPool)
        XCTAssertEqual(decision(tempResult.decisions, "07053450")?.accepted, false)
    }

    func testHotSpringAndWrongLakeRejectedAtCatherine() {
        let context = lake("Catherine")
        let temp = [
            reading("343048093031301", "Quapaw Spring", type: "SP", code: "00010", value: 67.3,
                    miles: 5.35, lat: 34.5133, lon: -93.0536),
        ]
        let level = [
            reading("07358500", "Lake Hamilton at Carpenter Dam nr. Hot Springs, AR", type: "LK", code: "00065",
                    value: 399.72, miles: 1.52, lat: 34.44446389, lon: -93.0258472),
            reading("07359000", "Lake Catherine at Jones Mill, AR", type: "LK", code: "00065", value: 303.92,
                    miles: 6.26, lat: 34.429503, lon: -92.892978),
        ]
        let shared = inputs(context, level: level)

        let tempResult = GaugeSelector.select(temp, kind: .waterTemp, inputs: shared, roster: [])
        XCTAssertNil(tempResult.pick)
        let spring = decision(tempResult.decisions, "343048093031301")
        XCTAssertTrue(spring?.reason.contains("nonSurface") ?? false, spring?.reason ?? "no decision")

        let levelResult = GaugeSelector.select(level, kind: .level, inputs: shared, roster: [])
        XCTAssertEqual(levelResult.pick?.siteCode, "07359000", explain(levelResult.decisions))
        XCTAssertEqual(decision(levelResult.decisions, "07358500")?.accepted, false)
    }

    func testPoolValueMatchRescuesRiverNamedDockAndPrefersElevationCode() {
        let name = "CHATTAHOOCHEE RIVER AT COAST GUARD DOCK AT EUFAULA"
        let level = [
            reading("0234296910", name, type: "LK", code: "00065", value: 38.73, miles: 0.62,
                    lat: 31.90821568, lon: -85.144932),
            reading("0234296910", name, type: "LK", code: "62614", value: 188.73, miles: 0.62,
                    lat: 31.90821568, lon: -85.144932),
        ]
        let result = GaugeSelector.select(level, kind: .level,
                                          inputs: inputs(lake("Eufaula / W.F. George"), pool: 188.6, level: level),
                                          roster: [])
        XCTAssertEqual(result.pick?.parameterCode, "62614", explain(result.decisions))
        XCTAssertEqual(result.pick?.value, 188.73)
        XCTAssertEqual(result.pick?.acceptance, .matchedPool)
    }

    func testPoolValueMatchIgnoresAnotherDirectoryLake() {
        let level = [
            reading("05429000", "LAKE MONONA AT MADISON, WI", type: "LK", code: "00062", value: 844.79, miles: 2.5,
                    lat: 43.0636, lon: -89.3614),
        ]
        let result = GaugeSelector.select(level, kind: .level,
                                          inputs: inputs(lake("Lake Mendota"), pool: 845.5, level: level), roster: [])
        XCTAssertNil(result.pick, explain(result.decisions))
        let monona = decision(result.decisions, "05429000")
        XCTAssertTrue(monona?.reason.contains("another directory lake") ?? false, monona?.reason ?? "no decision")
    }

    func testTaylorsvilleMultiBlockSite() {
        let name = "TAYLORSVILLE LAKE NEAR TAYLORSVILLE, KY"
        let site = "03295597"
        let (lat, lon) = (38.01645276, -85.30773099)
        let level = [
            reading(site, name, type: "LK", code: "00065", value: 47.24, miles: 1.2, lat: lat, lon: lon,
                    method: "[Lake]", block: 0),
            reading(site, name, type: "LK", code: "00065", value: 68.53, miles: 1.2, lat: lat, lon: lon,
                    method: "Tailwater, [Tailwater]", block: 1),
            reading(site, name, type: "LK", code: "62614", value: 547.24, miles: 1.2, lat: lat, lon: lon),
        ]
        let temp = [
            reading(site, name, type: "LK", code: "00010", value: 26.2, miles: 1.2, lat: lat, lon: lon,
                    method: "Tailwater", block: 0),
        ]
        let shared = inputs(lake("Taylorsville Lake"), pool: 547.3, level: level)

        let levelResult = GaugeSelector.select(level, kind: .level, inputs: shared, roster: [])
        XCTAssertEqual(levelResult.pick?.parameterCode, "62614", explain(levelResult.decisions))
        XCTAssertEqual(levelResult.pick?.value, 547.24)
        // The local-datum [Lake] block passes (no veto on 00065); the site just prefers 62614.
        let lakeBlock = decision(levelResult.decisions, site, code: "00065", block: 0)
        XCTAssertEqual(lakeBlock?.accepted, true, lakeBlock?.reason ?? "no decision")
        XCTAssertEqual(decision(levelResult.decisions, site, code: "00065", block: 1)?.accepted, false)

        let tempResult = GaugeSelector.select(temp, kind: .waterTemp, inputs: shared, roster: [])
        XCTAssertNil(tempResult.pick, explain(tempResult.decisions))
        XCTAssertEqual(decision(tempResult.decisions, site)?.role, .damRelease)
    }

    func testStaleNearestDoesNotHideFreshAccepted() {
        let level = [
            reading("A", "LAKE SIDNEY LANIER AT BROWNS BRIDGE", type: "LK", code: "00062", value: 1065.0,
                    miles: 1, age: 4 * 3600),
            reading("B", "LAKE SIDNEY LANIER NEAR BUFORD, GA", type: "LK", code: "00062", value: 1065.0,
                    miles: 3, age: 20 * 60),
        ]
        let result = GaugeSelector.select(level, kind: .level,
                                          inputs: inputs(lake("Lanier (Sidney Lanier)"), pool: 1065, level: level),
                                          roster: [])
        XCTAssertEqual(result.pick?.siteCode, "B", explain(result.decisions))
        let stale = decision(result.decisions, "A")
        XCTAssertEqual(stale?.accepted, false)
        XCTAssertTrue(stale?.reason.contains("stale") ?? false, stale?.reason ?? "no decision")
    }

    /// Not a spec case: the veto rejects a name-matched elevation series far from
    /// P without touching a local-datum 00065 at the same site.
    func testNameMatchedElevationFarFromPoolIsVetoed() {
        let name = "LAKE SIDNEY LANIER NEAR BUFORD, GA"
        let level = [
            reading("02334400", name, type: "LK", code: "62614", value: 1040.0, miles: 6),
            reading("02334400", name, type: "LK", code: "00065", value: 65.0, miles: 6),
        ]
        let result = GaugeSelector.select(level, kind: .level,
                                          inputs: inputs(lake("Lanier (Sidney Lanier)"), pool: 1065, level: level),
                                          roster: [])
        XCTAssertEqual(result.pick?.parameterCode, "00065", explain(result.decisions))
        XCTAssertEqual(decision(result.decisions, "02334400", code: "62614")?.accepted, false)
    }

    // MARK: Below a dam

    func testBufordTailwaterKeepsReleaseAndPrefersMainstemTurbidity() {
        let context = WaterContext.belowDam(dam: buford, damMiles: 0.9, ownLake: nil)
        let temp = [
            reading("02334430", "CHATTAHOOCHEE RIVER AT BUFORD DAM, NEAR BUFORD, GA", code: "00010", value: 11.1,
                    miles: 0.53, lat: 34.15666667, lon: -84.0784167),
        ]
        let level = [
            reading("02334400", "LAKE SIDNEY LANIER NEAR BUFORD, GA", type: "LK", code: "00062", value: 1065,
                    miles: 0.98, lat: 34.1627222, lon: -84.0755278),
            reading("02334430", "CHATTAHOOCHEE RIVER AT BUFORD DAM, NEAR BUFORD, GA", code: "00065", value: 2.51,
                    miles: 0.53, lat: 34.15666667, lon: -84.0784167),
        ]
        let turbidity = [
            reading("02334480", "RICHLAND CREEK AT SUWANEE DAM ROAD, NEAR BUFORD,GA", code: "63680", value: 11.0,
                    miles: 1.42, lat: 34.1325, lon: -84.07),
            reading("02334500", "CHATTAHOOCHEE RIVER NEAR BUFORD, GA", code: "63680", value: 4.6,
                    miles: 1.75, lat: 34.1261111, lon: -84.09338889),
        ]
        let shared = inputs(context, level: level)

        let tempResult = GaugeSelector.select(temp, kind: .waterTemp, inputs: shared, roster: [buford])
        XCTAssertEqual(tempResult.pick?.siteCode, "02334430", explain(tempResult.decisions))
        XCTAssertEqual(tempResult.pick?.acceptance, .onReach)

        let levelResult = GaugeSelector.select(level, kind: .level, inputs: shared, roster: [buford])
        XCTAssertEqual(levelResult.pick?.siteCode, "02334430", explain(levelResult.decisions))
        XCTAssertEqual(decision(levelResult.decisions, "02334400")?.accepted, false)

        let turbidityResult = GaugeSelector.select(turbidity, kind: .turbidity, inputs: shared, roster: [buford])
        XCTAssertEqual(turbidityResult.pick?.siteCode, "02334500", explain(turbidityResult.decisions))
    }

    func testBullShoalsTailwaterRejectsCrookedCreek() {
        let context = WaterContext.belowDam(dam: bullShoals, damMiles: 1.45, ownLake: nil)
        let temp = [
            reading("07054527", "White River below Bull Shoals Dam near Fairview", code: "00010", value: 15.3,
                    miles: 0.22, lat: 36.3436111, lon: -92.5741667),
        ]
        let crooked = "Crooked Creek at Kelly Crossing at Yellville, AR"
        let level = [reading("07055607", crooked, code: "00065", value: 3.1, miles: 10.69,
                             lat: 36.23027778, lon: -92.7094444)]
        let discharge = [reading("07055607", crooked, code: "00060", value: 120, miles: 10.69,
                                 lat: 36.23027778, lon: -92.7094444)]
        let shared = inputs(context, level: level)

        let tempResult = GaugeSelector.select(temp, kind: .waterTemp, inputs: shared, roster: [bullShoals])
        XCTAssertEqual(tempResult.pick?.siteCode, "07054527", explain(tempResult.decisions))
        XCTAssertNil(GaugeSelector.select(level, kind: .level, inputs: shared, roster: [bullShoals]).pick)
        XCTAssertNil(GaugeSelector.select(discharge, kind: .discharge, inputs: shared, roster: [bullShoals]).pick)
    }

    func testCalicoRockRanksByDistanceAndLocalLimit() {
        let context = WaterContext.belowDam(dam: norfork, damMiles: 11, ownLake: nil)
        let temp = [
            reading("07060500", "White River at Calico Rock, AR", code: "00010", value: 21.9, miles: 0.00,
                    lat: 36.11666667, lon: -92.1430556),
            reading("07060000", "North Fork Riv US of Dry Ck bl Norfork Dam, AR", code: "00010", value: 12.3,
                    miles: 10.6, lat: 36.2403, lon: -92.2396),
        ]
        let result = GaugeSelector.select(temp, kind: .waterTemp, inputs: inputs(context), roster: [norfork])
        XCTAssertEqual(result.pick?.siteCode, "07060500", explain(result.decisions))
        let northFork = decision(result.decisions, "07060000")
        XCTAssertEqual(northFork?.accepted, false)
        XCTAssertTrue(northFork?.reason.contains("8 mi") ?? false, northFork?.reason ?? "no decision")
    }

    func testFarReachTempNeedsLocalGauge() {
        let context = WaterContext.belowDam(dam: tableRock, damMiles: 14, ownLake: nil)
        let temp = [
            reading("07053450", "White River bl Table Rock Dam near Branson, MO", code: "00010", value: 13.0,
                    miles: 12.99, lat: 36.5950631, lon: -93.3090721),
        ]
        let result = GaugeSelector.select(temp, kind: .waterTemp, inputs: inputs(context), roster: [tableRock])
        XCTAssertNil(result.pick, explain(result.decisions))
    }

    func testNWPSRejectedBelowDamAcceptedOnLake() {
        var pool = reading("KYDK2", "Kentucky Lake", type: "LK", code: "62614", value: 357.2, miles: nil,
                           lat: 37.03, lon: -88.29, method: "NWPS pool")
        pool.fullPoolFt = 359

        let below = GaugeSelector.select([pool], kind: .level,
                                         inputs: inputs(.belowDam(dam: kentucky, damMiles: 1.6, ownLake: nil), level: [pool]),
                                         roster: [kentucky])
        XCTAssertNil(below.pick, explain(below.decisions))
        XCTAssertEqual(below.decisions.first?.accepted, false)

        let onLake = GaugeSelector.select([pool], kind: .level,
                                          inputs: inputs(lake("Kentucky Lake", state: "KY"), level: [pool]),
                                          roster: [kentucky])
        XCTAssertEqual(onLake.pick?.siteCode, "KYDK2", explain(onLake.decisions))
        XCTAssertEqual(onLake.pick?.acceptance, .matchedPool)
    }

    // MARK: Open water

    func testOpenPondRejectsReachGaugesBeyond1_5Miles() {
        XCTAssertTrue(DamRoster.all.contains { $0.reachSiteCodes.contains("02334653") },
                      "generated roster should list McGinnis Ferry on a reach")
        let mcginnis = "CHATTAHOOCHEE R 0.76 MI US MCGINNIS FY SUWANEE GA"
        let temp = [
            reading("02334653", mcginnis, code: "00010", value: 14.1, miles: 6.2, lat: 34.0567222, lon: -84.1083333),
            reading("02218565", "APALACHEE RIVER AT FENCE ROAD, NEAR DACULA, GA", code: "00010", value: 24.8,
                    miles: 6.65, lat: 34.01027778, lon: -83.8941667),
        ]
        let discharge = [
            reading("02334653", mcginnis, code: "00060", value: 654, miles: 6.2, lat: 34.0567222, lon: -84.1083333),
        ]
        let shared = inputs(.open, model: 77.5)

        let tempResult = GaugeSelector.select(temp, kind: .waterTemp, inputs: shared)
        XCTAssertEqual(tempResult.pick?.siteCode, "02218565", explain(tempResult.decisions))
        let reach = decision(tempResult.decisions, "02334653")
        XCTAssertEqual(reach?.accepted, false)
        XCTAssertTrue(reach?.reason.contains("reach") ?? false, reach?.reason ?? "no decision")

        let dischargeResult = GaugeSelector.select(discharge, kind: .discharge, inputs: shared)
        XCTAssertNotEqual(dischargeResult.pick?.siteCode, "02334653", explain(dischargeResult.decisions))
    }

    func testOpenRiverBeatsStormTributary() {
        let level = [
            reading("02206465", "WATSON CREEK TRIB 2, TANGLEWOOD DR, SNELLVILLE, GA", code: "00065", value: 1.2,
                    miles: 0.57, lat: 33.86302778, lon: -84.0354167),
            reading("02206500", "YELLOW RIVER NEAR SNELLVILLE, GA", code: "00065", value: 4.1,
                    miles: 3.01, lat: 33.85305556, lon: -84.0783333),
        ]
        let result = GaugeSelector.select(level, kind: .level, inputs: inputs(.open, level: level))
        XCTAssertEqual(result.pick?.siteCode, "02206500", explain(result.decisions))
    }

    func testOpenAcceptsDamReleaseWithin5Miles() {
        let near = reading("07331600", "Red Rv at Denison Dam nr Denison, TX", code: "00065", value: 3.2, miles: 0.3)
        let far = reading("07331600", "Red Rv at Denison Dam nr Denison, TX", code: "00065", value: 3.2, miles: 6)

        let accepted = GaugeSelector.select([near], kind: .level, inputs: inputs(.open), roster: [], directory: [])
        XCTAssertEqual(accepted.decisions.first?.role, .damRelease)
        XCTAssertEqual(accepted.pick?.siteCode, "07331600", explain(accepted.decisions))

        let rejected = GaugeSelector.select([far], kind: .level, inputs: inputs(.open), roster: [], directory: [])
        XCTAssertNil(rejected.pick, explain(rejected.decisions))
    }

    func testTempPlausibilityAndWarmGap() {
        let temp = [
            reading("T1", "SAMPLE RIVER AT ONE", code: "00010", value: 38.0, miles: 1),
            reading("T2", "SAMPLE RIVER AT TWO", code: "00010", value: 36.0, miles: 1),
            reading("T3", "SAMPLE RIVER AT THREE", code: "00010", value: 30.0, miles: 1),
        ]
        let result = GaugeSelector.select(temp, kind: .waterTemp, inputs: inputs(.open, model: 70), roster: [])
        XCTAssertEqual(result.pick?.siteCode, "T3", explain(result.decisions))
        let implausible = decision(result.decisions, "T1")
        XCTAssertEqual(implausible?.accepted, false)
        XCTAssertTrue(implausible?.reason.contains("implausible") ?? false, implausible?.reason ?? "no decision")
        let warm = decision(result.decisions, "T2")
        XCTAssertEqual(warm?.accepted, false)
        XCTAssertTrue(warm?.reason.contains("model") ?? false, warm?.reason ?? "no decision")
        XCTAssertEqual(decision(result.decisions, "T3")?.accepted, true)
    }

    // MARK: Kill switch

    /// Not a spec case: the legacy pick is today's — nearest block-0 reading within
    /// the input's search distance, with an NWPS pool winning for level.
    func testLegacyNearestMatchesThePreSelectionPick() {
        let block1 = reading("S1", "X RIVER AT A", code: "00065", value: 1, miles: 0.1, block: 1)
        let block0 = reading("S2", "Y RIVER AT B", code: "00065", value: 2, miles: 2)
        let tooFar = reading("S3", "Z RIVER AT C", code: "00010", value: 20, miles: 16)
        XCTAssertEqual(GaugeSelector.legacyNearest([block1, block0], kind: .level)?.siteCode, "S2")
        XCTAssertNil(GaugeSelector.legacyNearest([tooFar], kind: .waterTemp))

        let pool = reading("KYDK2", "Kentucky Lake", type: "LK", code: "62614", value: 357, miles: nil,
                           method: "NWPS pool")
        XCTAssertEqual(GaugeSelector.legacyNearest([block0, pool], kind: .level)?.siteCode, "KYDK2")
    }
}
