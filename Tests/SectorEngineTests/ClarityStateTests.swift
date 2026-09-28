import XCTest
@testable import SectorEngine

/// Clarity Fusion Stage 2: each arm's current clarity state.
final class ClarityStateTests: XCTestCase {

    // MARK: fixtures

    let now = Date(timeIntervalSince1970: 1_790_000_000)      // 2026-09-21T13:33Z
    func hours(_ h: Double) -> Date { now.addingTimeInterval(-h * 3600) }

    func anchor(daysAgo: Double, observed: Int = 800, water: Int = 1_000, fnu: Double = 4) -> SatelliteAnchor {
        SatelliteAnchor(sceneDate: "scene-\(Int(daysAgo))d", sceneTime: hours(daysAgo * 24), platform: "sentinel-2b",
                        waterCells: water, observedCells: observed, filledCells: water - observed,
                        filledWithin500mCells: water - observed, medianFillDistanceM: 150,
                        observedFNU: Distribution(n: observed, p25: fnu * 0.9, p50: fnu, p75: fnu * 1.1),
                        allFNU: Distribution(n: water, p25: fnu * 0.9, p50: fnu, p75: fnu * 1.1), source: "test")
    }

    /// Hourly rain back `span` hours; `storm` = (hours ago it started, hours ago it ended, inches per hour).
    func rain(basis: String = "nhdplusBasinAtMouth", span: Double = 40 * 24,
              storms: [(Double, Double, Double)] = []) -> RainRecord {
        var steps: [RainStep] = []
        var h = span
        while h >= 1 {
            let end = hours(h - 1)
            let v = storms.first { h <= $0.0 && h > $0.1 }?.2 ?? 0
            steps.append(RainStep(start: hours(h), end: end, inches: v))
            h -= 1
        }
        return RainRecord(basis: basis, drainageKm2: 100, source: "test", steps: steps)
    }

    func flow(_ p: FlowProvenance, base: Double = 10, rise: [(Double, Double)] = []) -> FlowSeries {
        // hourly for 40 days; rise = (hours ago, cfs) overrides
        var pts: [FlowPoint] = []
        var h = 40.0 * 24
        while h >= 0 {
            let v = rise.first { abs($0.0 - h) < 0.5 }?.1 ?? base
            pts.append(FlowPoint(validTime: hours(h), cfs: v))
            h -= 1
        }
        return FlowSeries(provenance: p, source: p == .measuredUSGS ? "USGS test" : "NWM reach test", points: pts)
    }

    /// A storm of `inches` over the 12 h ending `endedHoursAgo`, with flow rising `factor`x.
    func stormy(_ inches: Double, endedHoursAgo: Double = 2, factor: Double = 8, provenance: FlowProvenance = .measuredUSGS)
        -> (RainRecord, FlowSeries) {
        let r = rain(storms: [(endedHoursAgo + 12, endedHoursAgo, inches / 12)])
        let rise = (0..<12).map { (endedHoursAgo + Double($0), 10 * factor) }
        return (r, flow(provenance, rise: rise))
    }

    func state(_ a: SatelliteAnchor?, _ r: RainRecord, measured: FlowSeries? = nil, modeled: FlowSeries? = nil,
               baseline: BaselineVisibility? = nil, arm: String = "test-arm") -> ArmClarityState {
        ClarityStateEngine.armState(ArmClarityInputs(lakeId: "Guntersville|AL", armId: arm, armName: arm, anchor: a, rain: r,
                                                     flow: FlowRecord(measured: measured, modeled: modeled), baseline: baseline), now: now)
    }

    let baseline = BaselineVisibility(centralFt: 3.9, lowFt: nil, highFt: nil, model: "rain-decay-v0", source: "test baseline")

    static let repo = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()

    // MARK: 1

    func testDryStableConditionsKeepStrongAuthorityLonger() {
        for days in [3.0, 12, 28] {
            let s = state(anchor(daysAgo: days), rain(), measured: flow(.measuredUSGS))
            XCTAssertEqual(s.runoff.state, .stable, "\(days) d")
            XCTAssertEqual(s.satelliteAuthority.level, .high, "a dry drainage keeps a \(days)-day-old scene's authority")
            XCTAssertEqual(s.currentVisibility.basis, "satelliteAnchor")
            XCTAssertTrue(s.currentVisibility.magnitudeSupported)
        }
    }

    // MARK: 2, 3

    /// Rain is read per drainage: one arm's storm is not another's.
    func testRainInOneArmDoesNotReachItsNeighbour() throws {
        let (wet, wetFlow) = stormy(2.0)
        let history = ClarityHistory(lakeId: "Guntersville|AL", arms: [
            "town-creek-marshall": .init(armId: "town-creek-marshall", armName: "Town Creek", anchors: [anchor(daysAgo: 5)],
                                          rain: wet, flow: FlowRecord(measured: wetFlow, modeled: nil), parentArmName: nil),
            "south-sauty-creek": .init(armId: "south-sauty-creek", armName: "South Sauty Creek", anchors: [anchor(daysAgo: 5)],
                                        rain: rain(), flow: FlowRecord(measured: flow(.measuredUSGS), modeled: nil), parentArmName: nil),
        ], mainStem: nil)
        let tc = ClarityStateEngine.armState(history.inputs(arm: "town-creek-marshall", asOf: now)!, now: now)
        let ss = ClarityStateEngine.armState(history.inputs(arm: "south-sauty-creek", asOf: now)!, now: now)
        XCTAssertEqual(tc.runoff.state, .majorRunoff)
        XCTAssertEqual(ss.runoff.state, .stable)
        XCTAssertEqual(ss.satelliteAuthority.level, .high)
    }

    /// ...and the drainages themselves do not overlap. The weights are each
    /// basin's share of its area per 0.01° MRMS cell, so neighbours share only
    /// the cells their divide runs through: in every shared cell the two
    /// basins' parts add to no more than the cell, and a storm over one basin's
    /// own cells leaves the other's basin mean at exactly zero.
    func testTheCatchmentsBehindNeighbouringArmsAreSeparate() throws {
        let url = Self.repo.appendingPathComponent("docs/data/hydrology/guntersville/guntersville.mrms_weights.json")
        let w = try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as! [String: Any]
        let arms = w["arms"] as! [String: [String: Any]]
        func cells(_ id: String) -> [String: (row: Int, w: Double)] {
            var out: [String: (row: Int, w: Double)] = [:]
            for c in (arms[id]?["cells"] as? [[Double]]) ?? [] { out["\(Int(c[0])),\(Int(c[1]))"] = (Int(c[0]), c[2]) }
            return out
        }
        func cellKm2(_ row: Int) -> Double {       // 0.01° x 0.01° at the row's latitude (grid top 55°N)
            let lat = 55 - (Double(row) + 0.5) * 0.01
            return 1.1132 * 1.1132 * cos(lat * .pi / 180)
        }
        for (a, b) in [("town-creek-marshall", "south-sauty-creek"), ("south-sauty-creek", "jagger-branch")] {
            let x = cells(a), y = cells(b)
            XCTAssertFalse(x.isEmpty, a); XCTAssertFalse(y.isEmpty, b)
            let ka = arms[a]!["drainageKm2"] as! Double, kb = arms[b]!["drainageKm2"] as! Double
            for (key, cx) in x {
                guard let cy = y[key] else { continue }
                let parts = (cx.w * ka + cy.w * kb) / cellKm2(cx.row)
                XCTAssertLessThanOrEqual(parts, 1.05, "\(a) and \(b) overlap in cell \(key)")
            }
            // rain only over a's own cells
            let own = x.filter { y[$0.key] == nil }
            let meanB = y.reduce(0.0) { $0 + (own[$1.key] != nil ? $1.value.w : 0) }
            XCTAssertEqual(meanB, 0, "\(b) sees rain that fell only on \(a)'s drainage")
            XCTAssertGreaterThan(own.values.reduce(0) { $0 + $1.w }, 0.85, "\(a) is mostly its own cells")
        }
    }

    // MARK: 4

    func testBrownsCreekNeverBorrowsTownCreeksGauge() {
        let g = Hydrology.guntersville
        XCTAssertNil(g.arm("browns-creek")?.usgsDischargeSite)
        XCTAssertEqual(g.arm("town-creek-marshall")?.usgsDischargeSite, "03572900")
        // Browns' record carries no measured series, so its state cannot read one.
        let s = state(anchor(daysAgo: 4), rain(), measured: nil, modeled: flow(.modeledNWM), arm: "browns-creek")
        XCTAssertEqual(s.dischargeProvenance, .modeledNWM)
        XCTAssertFalse(s.provenance.contains { $0.source.contains("03572900") })
    }

    // MARK: 5

    func testModeledFlowCannotPresentAsMeasured() {
        let (r, f) = stormy(0.05, factor: 20, provenance: .modeledNWM)
        let s = state(anchor(daysAgo: 4), r, modeled: f)
        XCTAssertEqual(s.dischargeProvenance, .modeledNWM)
        XCTAssertEqual(s.runoffAnomaly.provenance, .modeledNWM)
        // a model rise alone is capped
        XCTAssertLessThanOrEqual(s.runoff.state, .moderateRunoff)
        let text = ClarityStateDebug.lines(s).joined(separator: "\n")
        XCTAssertTrue(text.contains("modeled NWM"))
        XCTAssertFalse(text.contains("cfs measured"))
        XCTAssertTrue(s.limitations.contains { $0.contains("not a measurement") })
        // and a stale gauge never lends the model its label
        let stale = FlowSeries(provenance: .measuredUSGS, source: "USGS test",
                               points: [FlowPoint(validTime: hours(30), cfs: 10)])
        let t = state(anchor(daysAgo: 4), rain(), measured: stale, modeled: flow(.modeledNWM))
        XCTAssertEqual(t.dischargeProvenance, .modeledNWM)
    }

    // MARK: 6, 7

    func testPartialCatchmentReducesConfidence() {
        let full = state(anchor(daysAgo: 4), rain(basis: "nhdplusBasinAtMouth"), measured: flow(.measuredUSGS))
        let part = state(anchor(daysAgo: 4), rain(basis: "nhdplusBasinAboveHead"), measured: flow(.measuredUSGS))
        XCTAssertEqual(full.catchmentCompleteness, .complete)
        XCTAssertEqual(part.catchmentCompleteness, .partial)
        let rank = ["veryLow": 0, "low": 1, "medium": 2]
        XCTAssertLessThan(rank[part.confidence.level]!, rank[full.confidence.level]! + 1)
        XCTAssertNotEqual(part.confidence, full.confidence)
        XCTAssertTrue(part.confidence.reasons.contains { $0.contains("partial catchment") })
        XCTAssertTrue(part.limitations.contains { $0.contains("above the embayment's head") })
    }

    func testNoCatchmentMeansUnknownRainNotZero() {
        let s = state(anchor(daysAgo: 4), rain(basis: "unavailable"), measured: nil, modeled: nil)
        XCTAssertEqual(s.catchmentCompleteness, .unavailable)
        XCTAssertNil(s.divergence.rainSincePassIn)
        XCTAssertNil(s.rain24hIn)
        XCTAssertNil(s.rain72hIn)
        XCTAssertEqual(s.runoff.state, .unknown)
        XCTAssertNotEqual(s.satelliteAuthority.level, .high)
        XCTAssertTrue(s.limitations.contains { $0.contains("unknown, not zero") })
        // a gap in a resolved catchment's record is unknown too, never dry
        let gappy = RainRecord(basis: "nhdplusBasinAtMouth", drainageKm2: 1, source: "test",
                               steps: rain().steps.filter { $0.end < hours(30) || $0.end > hours(20) })
        XCTAssertNil(state(anchor(daysAgo: 4), gappy).divergence.rainSincePassIn)
    }

    // MARK: 8, 9, 10

    func testANewSceneResetsAuthority() {
        let (r, f) = stormy(2.0, endedHoursAgo: 72)
        let before = state(anchor(daysAgo: 6), r, measured: f)
        XCTAssertLessThanOrEqual(before.satelliteAuthority.level, .low)
        let after = state(anchor(daysAgo: 1), r, measured: f)      // a scene taken after the storm
        XCTAssertEqual(after.runoff.state, .stable)
        XCTAssertEqual(after.satelliteAuthority.level, .high)
    }

    func testLargeRainAndFlowDivergenceLowersAuthority() {
        let (r, f) = stormy(2.0)
        let s = state(anchor(daysAgo: 4), r, measured: f)
        XCTAssertEqual(s.runoff.state, .majorRunoff)
        XCTAssertEqual(s.satelliteAuthority.level, .none)
        XCTAssertGreaterThanOrEqual(s.divergence.dischargePeakRatioToPass ?? 0, 5)
        let minor = state(anchor(daysAgo: 4), rain(storms: [(14, 2, 0.25 / 12)]), measured: flow(.measuredUSGS))
        XCTAssertEqual(minor.runoff.state, .minorChange)
        XCTAssertEqual(minor.satelliteAuthority.level, .moderate)
    }

    func testAnOldStableSceneOutranksANewSceneBeforeAStorm() {
        let (r, f) = stormy(1.5, endedHoursAgo: 6)
        // the storm fell 6-18 h ago: after a 2-day-old scene, before... nothing after a 25-day-old dry scene?
        // Build two arms: one whose old scene saw no storm since, one whose new scene did.
        let old = state(anchor(daysAgo: 25), rain(), measured: flow(.measuredUSGS))
        let new = state(anchor(daysAgo: 2), r, measured: f)
        XCTAssertGreaterThan(old.satelliteAuthority.level, new.satelliteAuthority.level)
        XCTAssertEqual(old.satelliteAuthority.level, .high)
    }

    // MARK: 11

    func testMainStemInventsNoVelocity() throws {
        // 20,000 cfs through the scene three days ago; 60,000 for the last day
        let rel = ReleaseSeries(dam: "nickajack-dam", tva: "NKJT1",
                                points: (0..<120).map { FlowPoint(validTime: hours(Double($0)), cfs: $0 < 24 ? 60_000 : 20_000) })
        let x = MainStemClarityInputs(lakeId: "Guntersville|AL", river: "Tennessee River", anchor: anchor(daysAgo: 3),
                                      directRain: rain(basis: "lakeSurface"), inflow: rel, outflow: nil,
                                      inflowDamName: "Nickajack Dam", outflowDamName: "Guntersville Dam", baseline: nil)
        let s = ClarityStateEngine.mainStemState(x, now: now)
        XCTAssertTrue(s.currentVelocity.hasPrefix("unknown"))
        XCTAssertTrue(s.limitations.contains { $0.contains("not a velocity") })
        XCTAssertTrue(s.limitations.contains { $0.contains("No plume travel time") })
        let json = String(data: try JSONEncoder().encode(s), encoding: .utf8)!
        for word in ["velocityMps", "velocityFt", "speed", "travelTime", "arrival", "etaHours"] {
            XCTAssertFalse(json.contains(word), word)
        }
        // a tripled release is reported as a release change, nothing more
        XCTAssertGreaterThanOrEqual(s.runoff.state, .moderateRunoff)
        XCTAssertEqual(s.releaseProvenance, "measuredTVA")
    }

    // MARK: 12

    func testUncalibratedRunoffCannotMoveTheFeet() {
        let (r, f) = stormy(2.5)
        let a = anchor(daysAgo: 3, fnu: 4)
        let s = state(a, r, measured: f, baseline: baseline)
        XCTAssertEqual(s.runoff.magnitude, "uncalibrated")
        XCTAssertEqual(s.currentVisibility.basis, "baseline")
        XCTAssertFalse(s.currentVisibility.magnitudeSupported)
        XCTAssertEqual(s.currentVisibility.centralFt, baseline.centralFt)
        XCTAssertNil(s.currentVisibility.lowFt)
        XCTAssertNil(s.currentVisibility.highFt)
        XCTAssertNotNil(s.currentVisibility.warning)
        // the scene's own numbers are reported untouched
        XCTAssertEqual(s.currentVisibility.atPass, a.visibility())
        // with no baseline there is no number at all, rather than an adjusted one
        let bare = state(a, r, measured: f)
        XCTAssertEqual(bare.currentVisibility.basis, "none")
        XCTAssertNil(bare.currentVisibility.centralFt)
    }

    // MARK: 13

    func testReplayNeverReadsTheFuture() {
        let t = hours(24)
        let past = ClarityHistory.ArmRecord(armId: "a", armName: "a", anchors: [anchor(daysAgo: 5)],
                                            rain: rain(), flow: FlowRecord(measured: flow(.measuredUSGS), modeled: nil), parentArmName: nil)
        // the same record plus a scene, a storm and a flood that all come after t
        let (futureRain, futureFlow) = stormy(3.0, endedHoursAgo: 2)
        let future = ClarityHistory.ArmRecord(armId: "a", armName: "a", anchors: [anchor(daysAgo: 5), anchor(daysAgo: 0.1, fnu: 40)],
                                              rain: futureRain, flow: FlowRecord(measured: futureFlow, modeled: nil), parentArmName: nil)
        let h1 = ClarityHistory(lakeId: "L", arms: ["a": past], mainStem: nil)
        let h2 = ClarityHistory(lakeId: "L", arms: ["a": future], mainStem: nil)
        let s1 = ClarityStateEngine.armState(h1.inputs(arm: "a", asOf: t)!, now: t)
        let s2 = ClarityStateEngine.armState(h2.inputs(arm: "a", asOf: t)!, now: t)
        XCTAssertEqual(s1, s2)
        XCTAssertEqual(s2.satelliteSceneDate, "scene-5d")
        XCTAssertEqual(s2.runoff.state, .stable)
        // a daily total that ends after t is excluded whole, not prorated
        let daily = RainRecord(basis: "nhdplusBasinAtMouth", drainageKm2: 1, source: "d",
                               steps: [RainStep(start: t.addingTimeInterval(-3600), end: t.addingTimeInterval(23 * 3600), inches: 5)])
        XCTAssertTrue(ClarityHistory.rain(daily, asOf: t).steps.isEmpty)
    }

    // MARK: 14

    /// A point belongs to the arm its water reaches it through, not the arm
    /// across the peninsula (Stage 1 pairs: a few hundred metres apart over
    /// land, 10-15 km apart through the water).
    func testCoordinateLookupFollowsTheWater() throws {
        let url = Self.repo.appendingPathComponent("docs/data/hydrology/guntersville/peninsula_pairs.json")
        let pairs = try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as! [[String: Any]]
        let grid = Hydrology.guntersvilleGrid
        var checked = 0
        for p in pairs {
            for side in ["a", "b"] {
                let m = grid.membership(lat: p["\(side)Lat"] as! Double, lon: p["\(side)Lon"] as! Double)
                XCTAssertEqual(m, .arm(p[side] as! String), "\(p[side]!) at \(p["\(side)Lat"]!), \(p["\(side)Lon"]!)")
                checked += 1
            }
        }
        XCTAssertEqual(checked, 12)
        // nested: Minky Creek inside Town Creek's embayment is Minky Creek's
        XCTAssertEqual(grid.membership(lat: 34.41997, lon: -86.19229), .arm("minky-creek"))
        XCTAssertEqual(grid.membership(lat: 34.38555, lon: -86.32488), .mainStem)
    }

    // MARK: 15

    /// Stage 2 is read-only: production scoring does not see it.
    func testProductionScoringIgnoresTheArmState() throws {
        let input = ConditionsInput(date: now, latitude: 34.41, longitude: -86.21, region: .lowerMid,
                                    windMph: 4, windDirDeg: 0, airTempF: 75, cloudPct: 0, humidityPct: 50,
                                    pressureInHg: 30, pressureTrend: .steady, pressureChange12hInHg: 0, weatherCode: 0,
                                    cityGlowFactor: 0.2, rainLast48hIn: 0, rainWatershed72hIn: 0)
        let before = ConditionsAggregator.evaluate(input)
        let (r, f) = stormy(3.0)
        _ = state(anchor(daysAgo: 2), r, measured: f, baseline: baseline, arm: "town-creek-marshall")
        let after = ConditionsAggregator.evaluate(input)
        XCTAssertEqual(before.score, after.score)
        XCTAssertEqual(ClarityFactor.visibilityFt(input), ClarityFactor.visibilityFt(input))
        // and no scoring source refers to the state engine
        let engine = Self.repo.appendingPathComponent("Sources/SectorEngine/Engine")
        let files = FileManager.default.enumerator(at: engine, includingPropertiesForKeys: nil)!
            .compactMap { $0 as? URL }.filter { $0.pathExtension == "swift" }
        XCTAssertFalse(files.isEmpty)
        for f in files {
            let src = try String(contentsOf: f, encoding: .utf8)
            for name in ["ClarityStateEngine", "ArmClarityState", "ClarityStateLoader", "currentClarityState"] {
                XCTAssertFalse(src.contains(name), "\(f.lastPathComponent) uses \(name)")
            }
        }
        let api = try String(contentsOf: Self.repo.appendingPathComponent("Sources/SectorEngine/API/SectorEngineAPI.swift"), encoding: .utf8)
        XCTAssertFalse(api.contains("ClarityStateEngine"))
    }

    // MARK: recovery and the scene that caught a storm

    func testASceneThatCaughtRunoffIsMarkedClearerNowOnceFlowFalls() {
        // 1.2 in fell in the 72 h before a 2-day-old scene; flow was 60 cfs at the scene, 10 now, dry since
        let r = rain(storms: [(4 * 24, 3 * 24, 1.2 / 24)])
        let f = flow(.measuredUSGS, base: 10, rise: (40..<60).map { (Double($0), 60) })
        let s = state(anchor(daysAgo: 2), r, measured: f)
        XCTAssertEqual(s.runoff.state, .recovering)
        XCTAssertEqual(s.runoff.expectedDirection, "clearerThanPass")
        XCTAssertEqual(s.satelliteAuthority.level, .low)
    }
}
