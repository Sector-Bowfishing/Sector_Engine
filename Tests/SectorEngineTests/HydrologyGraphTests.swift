import XCTest
@testable import SectorEngine

/// Lake Guntersville's hydrologic arm graph (Clarity Fusion Stage 1): the
/// connectivity proofs the stage was asked for, pinned.
final class HydrologyGraphTests: XCTestCase {

    let g = Hydrology.guntersville
    let grid = Hydrology.guntersvilleGrid

    func testGraphDecodesAndEveryPathReachesBelowTheDam() {
        XCTAssertEqual(g.lakeId, "Guntersville|AL")
        XCTAssertGreaterThanOrEqual(g.arms.count, 60)
        XCTAssertEqual(g.mainStem.upstreamDam.tva, "NKJT1")
        XCTAssertEqual(g.mainStem.downstreamDam.tva, "GVDA1")
        for a in g.arms {
            let path = g.downstreamPath(from: "head:\(a.id)")
            XCTAssertEqual(path.last, "wheeler-lake", "\(a.id) must drain out below Guntersville Dam")
            XCTAssertEqual(path.first, "arm:\(a.id)")
            XCTAssertTrue(path.contains("guntersville-dam"))
        }
    }

    /// The Geraldine Town Creek and the Jackson County Town Creek are two
    /// creeks; the gauge and the NWM reach each belong to exactly one.
    func testTownCreekIsTwoCreeksAndTheGaugeIsTheMarshallOnes() {
        let south = try! XCTUnwrap(g.arm("town-creek-marshall"))
        let north = try! XCTUnwrap(g.arm("town-creek-jackson"))
        XCTAssertEqual(south.usgsDischargeSite, "03572900")          // TOWN CREEK NEAR GERALDINE AL
        XCTAssertEqual(south.flowSource, "measuredUSGS")
        XCTAssertEqual(south.nwmFeatureId, "19649040")
        XCTAssertEqual(south.huc12Name, "Minky Creek-Town Creek")
        XCTAssertNil(north.usgsDischargeSite)
        XCTAssertEqual(north.nwmFeatureId, "19645450")               // the old registry's NWM id was this creek's
        XCTAssertGreaterThan(try! XCTUnwrap(south.drainageKm2AboveHead), 300)
        XCTAssertLessThan(try! XCTUnwrap(north.drainageKm2AboveHead), 20)
        // the Marshall Town Creek enters the main stem downstream of the Jackson one
        let order = g.mainStem.regions.map(\.id)
        XCTAssertLessThan(order.firstIndex(of: north.receivingRegion!)!, order.firstIndex(of: south.receivingRegion!)!)
    }

    func testSouthSautyReadsItsOwnGauge() {
        let a = try! XCTUnwrap(g.arm("south-sauty-creek"))
        XCTAssertEqual(a.usgsDischargeSite, "03572690")              // SOUTH SAUTY CREEK NEAR RAINSVILLE
        XCTAssertEqual(a.flowSource, "measuredUSGS")
    }

    /// Browns Creek has no gauge of its own and must not borrow one: its flow
    /// is its own NWM reach, labelled modeled.
    func testBrownsCreekBorrowsNoGauge() {
        let a = try! XCTUnwrap(g.arm("browns-creek"))
        XCTAssertNil(a.usgsDischargeSite)
        XCTAssertEqual(a.flowSource, "modeledNWM")
        XCTAssertEqual(a.nwmReachName, "Browns Creek")
        // no arm but the two gauged creeks has a gauge
        XCTAssertEqual(Set(g.arms.compactMap(\.usgsDischargeSite)), ["03572900", "03572690"])
    }

    /// Jagger Branch drains to Honeycomb Creek; South Sauty is not on its path.
    func testJaggerBranchIsHoneycombsNotSouthSautys() {
        let a = try! XCTUnwrap(g.arm("jagger-branch"))
        XCTAssertEqual(a.parent, "honeycomb-creek")
        XCTAssertEqual(a.topLevel, "honeycomb-creek")
        XCTAssertFalse(g.downstreamPath(from: "head:jagger-branch").contains("arm:south-sauty-creek"))
    }

    /// Water a few hundred metres apart across a peninsula belongs to different
    /// arms when the water between them runs 10-15 km round (found on the
    /// full-resolution lattice; these cells are in pure coarse blocks).
    func testAcrossAPeninsulaIsNotAdjacent() {
        let pairs: [(Double, Double, String, Double, Double, String)] = [
            (34.59505, -86.06196, "north-sauty-creek", 34.59825, -86.06035, "roseberry-creek"),   // 385 m apart, 15.0 km by water
            (34.79607, -85.83462, "nichols-branch", 34.79979, -85.84109, "brogue-branch"),         // 715 m, 9.7 km
            (34.80908, -85.82395, "marshall-branch", 34.8043, -85.82007, "nichols-branch"),        // 666 m, 13.0 km
        ]
        for (la, lo, a, lb, lob, b) in pairs {
            XCTAssertEqual(grid.membership(lat: la, lon: lo), .arm(a))
            XCTAssertEqual(grid.membership(lat: lb, lon: lob), .arm(b))
        }
    }

    /// Down the channel, top to bottom, with every region in order.
    func testMainStemRunsNickajackToTheDamInOrder() {
        let path = g.downstreamPath(from: "nickajack-dam")
        let regions = path.filter { $0.hasPrefix("ms-") }
        XCTAssertEqual(regions, g.mainStem.regions.map(\.id))
        for (r0, r1) in zip(g.mainStem.regions, g.mainStem.regions.dropFirst()) {
            XCTAssertEqual(r0.toKm, r1.fromKm, accuracy: 0.011)
        }
        XCTAssertEqual(path.suffix(2), ["guntersville-dam", "wheeler-lake"])
        XCTAssertEqual(g.mainStem.lengthKm, 124.5, accuracy: 3)       // TVA: 75.7 mi
    }

    /// Nested arms hand their water to their parent, never straight to the river.
    func testNestedArmsDrainThroughTheirParent() {
        for a in g.arms where a.parent != g.mainStem.id {
            let path = g.downstreamPath(from: "mouth:\(a.id)")
            XCTAssertEqual(path.first, "arm:\(a.parent)", "\(a.id) must enter \(a.parent)")
        }
    }

    /// Every main-stem region's centre is on the channel: main stem, never an arm.
    func testTheChannelIsMainStem() {
        for r in g.mainStem.regions {
            XCTAssertEqual(grid.membership(lat: r.center[0], lon: r.center[1]), .mainStem, r.id)
        }
    }
}

final class HydrologyInputsTests: XCTestCase {

    func testUSGSParse() throws {
        let json = #"{"value":{"timeSeries":[{"values":[{"value":[{"value":"12.0","dateTime":"2026-09-27T02:30:00.000-05:00"},{"value":"25.8","dateTime":"2026-09-27T14:30:00.000-05:00"}]}]}]}}"#
        let pts = TributaryFlowService.parseUSGS(Data(json.utf8))
        XCTAssertEqual(pts.map(\.1), [12.0, 25.8])
    }

    func testNWPSParseKeepsAnalysisAndForecastApart() throws {
        let json = #"{"analysisAssimilation":{"series":{"units":"ft³/s","data":[{"validTime":"2026-09-27T18:00:00Z","flow":14.0},{"validTime":"2026-09-27T19:00:00Z","flow":14.5}]}},"shortRange":{"series":{"units":"ft³/s","data":[{"validTime":"2026-09-27T20:00:00Z","flow":15.0}]}}}"#
        let p = try XCTUnwrap(TributaryFlowService.parseNWPS(Data(json.utf8)))
        XCTAssertEqual(p.analysis.map(\.1), [14.0, 14.5])
        XCTAssertEqual(p.forecast.map(\.1), [15.0])
    }

    /// No gauge and no matched reach: unavailable, with the reason, and no network.
    func testAnArmWithNoSourceIsUnavailableAndSaysWhy() async {
        let a = try! XCTUnwrap(Hydrology.guntersville.arms.first { $0.usgsDischargeSite == nil && $0.nwmFeatureId == nil })
        let f = await TributaryFlowService.flow(for: a)
        XCTAssertEqual(f.provenance, .unavailable)
        XCTAssertNil(f.cfs)
        XCTAssertNotNil(f.reason)
    }

    func testRainFeedParseAndStaleness() {
        let json = #"{"validTime":"2026-09-22T00:00:00Z","arms":{"town-creek-marshall":{"basis":"nhdplusBasinAtMouth","drainageKm2":559.6,"last1hIn":0.0,"last6hIn":0.4,"last12hIn":0.9,"last24hIn":1.1,"last48hIn":1.1,"last72hIn":1.2,"currentStormIn":1.1,"antecedent7dBeforeWindowIn":0.2}}}"#
        let f = ISO8601DateFormatter()
        let fresh = CatchmentRainfallFeed.parse(Data(json.utf8), arms: ["town-creek-marshall", "browns-creek"],
                                                now: f.date(from: "2026-09-22T01:00:00Z")!)!
        XCTAssertEqual(fresh["town-creek-marshall"]?.provenance, "mrmsPass2")
        XCTAssertEqual(fresh["town-creek-marshall"]?.last24hIn, 1.1)
        XCTAssertEqual(fresh["browns-creek"]?.provenance, "unavailable")
        let stale = CatchmentRainfallFeed.parse(Data(json.utf8), arms: ["town-creek-marshall"],
                                                now: f.date(from: "2026-09-22T09:00:00Z")!)!
        XCTAssertEqual(stale["town-creek-marshall"]?.provenance, "unavailable")
    }
}

final class VisibilityModelTests: XCTestCase {

    /// The canonical central value IS the conditions engine's gauge formula,
    /// so adopting it changes no score.
    func testCentralEqualsTheConditionsGaugePath() {
        for fnu in [0.5, 2, 5, 20, 80] {
            let input = ConditionsInput(date: Date(), latitude: 34.35, longitude: -86.3, region: .lowerMid,
                                        windMph: 5, windDirDeg: 0, airTempF: 70, cloudPct: 0, humidityPct: 50,
                                        pressureInHg: 30, pressureTrend: .steady, pressureChange12hInHg: 0,
                                        weatherCode: 0, cityGlowFactor: 0.2, turbidityFNU: fnu, hasTurbidityGage: true)
            XCTAssertEqual(VisibilityModel.centralFt(fnu: fnu), ClarityFactor.visibilityFt(input), accuracy: 1e-9)
        }
    }

    /// /conditions states the clarity number canonically: the gauge path with
    /// its 80% range, the uncalibrated rain-decay path with none.
    func testConditionsStatesClarityCanonically() {
        func input(_ fnu: Double?) -> ConditionsInput {
            ConditionsInput(date: Date(), latitude: 34.35, longitude: -86.3, region: .lowerMid,
                            windMph: 5, windDirDeg: 0, airTempF: 70, cloudPct: 0, humidityPct: 50,
                            pressureInHg: 30, pressureTrend: .steady, pressureChange12hInHg: 0,
                            weatherCode: 0, cityGlowFactor: 0.2, turbidityFNU: fnu, rainLast48hIn: 0.4,
                            rainWatershed72hIn: 0.6, hasTurbidityGage: fnu != nil)
        }
        let g = SectorEngineAPI.clarityVisibilityDTO(input(6), turbidity: nil, mrms: nil, config: .default)
        XCTAssertEqual(g.model, "secchi-power-v1"); XCTAssertEqual(g.source, "inSituGauge")
        XCTAssertEqual(g.centralFt, ClarityFactor.visibilityFt(input(6)), accuracy: 1e-9)
        XCTAssertLessThan(try! XCTUnwrap(g.lowFt), g.centralFt); XCTAssertGreaterThan(try! XCTUnwrap(g.highFt), g.centralFt)
        let r = SectorEngineAPI.clarityVisibilityDTO(input(nil), turbidity: nil, mrms: nil, config: .default)
        XCTAssertEqual(r.source, "rainDecayModel"); XCTAssertEqual(r.confidence, "low")
        XCTAssertNil(r.lowFt); XCTAssertNil(r.highFt)
        XCTAssertEqual(r.centralFt, ClarityFactor.visibilityFt(input(nil)), accuracy: 1e-9)
    }

    func testRangesBracketTheCentralAndFillsWidenWithDistance() {
        let g = VisibilityModel.estimate(fnu: 4.2, source: .inSituGauge)
        XCTAssertLessThan(g.lowFt, g.centralFt); XCTAssertGreaterThan(g.highFt, g.centralFt)
        XCTAssertEqual(g.confidence, "medium")
        let o = VisibilityModel.estimate(fnu: 4.2, source: .satelliteObserved)
        XCTAssertEqual(o.confidence, "low")
        XCTAssertGreaterThan(o.highFt / o.lowFt, g.highFt / g.lowFt, "satellite turbidity converts less surely than a gauge's")
        let near = VisibilityModel.estimate(fnu: 4.2, source: .satelliteEstimated, distanceToObservedM: 200)
        let far = VisibilityModel.estimate(fnu: 4.2, source: .satelliteEstimated, distanceToObservedM: 8_000)
        XCTAssertGreaterThan(near.highFt / near.lowFt, o.highFt / o.lowFt)
        XCTAssertGreaterThan(far.highFt / far.lowFt, near.highFt / near.lowFt)
    }
}
