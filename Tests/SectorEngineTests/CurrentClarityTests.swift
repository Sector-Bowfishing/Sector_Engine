import XCTest
@testable import SectorEngine

/// Clarity Fusion Stage 4: the Current Clarity Engine's rules.
final class CurrentClarityTests: XCTestCase {

    let now = ISO8601DateFormatter().date(from: "2026-09-28T03:00:00Z")!

    func scene(hoursAgo h: Double) -> ClaritySceneRef {
        ClaritySceneRef(date: "2026-09-2x", time: now.addingTimeInterval(-h * 3600), platform: "sentinel-2b", source: "test")
    }

    func region(_ state: RunoffClass = .stable, direction: String = "sameAsPass", sceneHoursAgo: Double = 30,
                completeness: CatchmentCompleteness = .complete, flow: String = "modeledNWM",
                ratio: Double? = nil, rain: Double? = 0.0, name: String = "Town Creek (Marshall)") -> ClarityRegionContext {
        ClarityRegionContext(kind: .arm, id: "town-creek-marshall", name: name, scene: scene(hoursAgo: sceneHoursAgo),
                             anchorStrength: .strong, anchorNote: nil,
                             runoff: RunoffState(state: state, expectedDirection: direction, magnitude: "uncalibrated", evidence: []),
                             rainSinceSceneIn: rain, rainRecordThrough: now, flowProvenance: flow,
                             flowSource: flow == "measuredUSGS" ? "USGS 03572690" : "NWM reach 1", flowChangeRatio: ratio,
                             catchmentCompleteness: completeness, limitations: [])
    }

    let direct = ClarityCellEvidence(kind: .direct, fnu: 4.2, distanceToObservedM: 0)
    func filled(_ m: Double) -> ClarityCellEvidence {
        ClarityCellEvidence(kind: .filled, fnu: 4.2, distanceToObservedM: m, fillReason: "unreadable")
    }

    func estimate(_ r: ClarityRegionContext?, _ c: ClarityCellEvidence?, inSitu: InSituTurbidity? = nil,
                  legacy: LegacyClarityEstimate? = nil) -> CurrentClarityEstimate {
        CurrentClarityResolver.estimate(lakeId: "Guntersville|AL", lat: 34.4, lon: -86.2, region: r,
                                        zone: (id: 7, name: "head"), cell: c, inSitu: inSitu, legacy: legacy, now: now)
    }

    // MARK: The hierarchy

    func testADirectObservationOutranksADistantFill() {
        let r = region()
        let d = estimate(r, direct), f = estimate(r, filled(3_000))
        XCTAssertEqual(d.evidenceLevel, .directSatellite)
        XCTAssertEqual(f.evidenceLevel, .nearbySatellite)
        XCTAssertTrue(d.evidenceLevel < f.evidenceLevel)
        XCTAssertEqual(d.confidence, .high)
        XCTAssertEqual(f.confidence, .low, "a creek back 3 km from a reading is not known as well as a read cell")
        XCTAssertGreaterThan(f.highFt! / f.lowFt!, d.highFt! / d.lowFt!, "the fill's error widens its range")
        XCTAssertEqual(estimate(r, filled(300)).confidence, .moderate)
    }

    func testBeyondFiveKilometresSectorRefusesANumber() {
        let e = estimate(region(), filled(7_200))
        XCTAssertEqual(e.evidenceLevel, .none)
        XCTAssertFalse(e.magnitudeSupported)
        XCTAssertNil(e.centralFt); XCTAssertNil(e.lowFt); XCTAssertNil(e.highFt); XCTAssertNil(e.category)
        XCTAssertEqual(e.display.valueText, "No supported estimate")
        XCTAssertEqual(e.composition.first?.role, "rejected")
        let noPath = estimate(region(), ClarityCellEvidence(kind: .filled, fnu: 4, distanceToObservedM: .infinity))
        XCTAssertFalse(noPath.magnitudeSupported)
    }

    func testAGrassBedGetsNoSupportedMagnitude() {
        // Stage 5: values carried into beds erred 5 ft on 2020–24, so a bed is never given feet.
        let g = estimate(region(), ClarityCellEvidence(kind: .grassBed, fnu: 3, distanceToObservedM: 60))
        XCTAssertFalse(g.magnitudeSupported)
        XCTAssertNil(g.centralFt); XCTAssertNil(g.lowFt); XCTAssertNil(g.highFt); XCTAssertNil(g.category)
        XCTAssertNil(g.lastSupported, "carried-in feet are not shown as current, nor as last supported")
        XCTAssertEqual(g.evidenceLevel, .none)
        XCTAssertEqual(g.confidence, .none)
        XCTAssertEqual(g.observation?.cellEvidence, .grassBed)
        XCTAssertEqual(g.display.evidenceText, "Grass bed")
        XCTAssertEqual(g.composition.map(\.role), ["rejected"])
        let far = estimate(region(), ClarityCellEvidence(kind: .grassBed, fnu: 3, distanceToObservedM: 8_000))
        XCTAssertFalse(far.magnitudeSupported)
    }

    func testHighNeedsACurrentDirectReadOfAStableFullyRecordedDrainage() {
        // Stage 5, preregistered: High = direct cell, scene ≤ 72 h, stable, complete record.
        XCTAssertEqual(estimate(region(.stable, sceneHoursAgo: 30), direct).confidence, .high)
        XCTAssertEqual(estimate(region(.stable, sceneHoursAgo: 71), direct).confidence, .high)
        XCTAssertEqual(estimate(region(.stable, sceneHoursAgo: 73), direct).confidence, .moderate)
        XCTAssertEqual(estimate(region(.stable, sceneHoursAgo: 30), filled(300)).confidence, .moderate)
        XCTAssertEqual(estimate(region(.minorChange, sceneHoursAgo: 30), direct).confidence, .moderate)
        XCTAssertEqual(estimate(region(.stable, sceneHoursAgo: 30, completeness: .partial), direct).confidence, .moderate)
        XCTAssertEqual(estimate(region(.stable, sceneHoursAgo: 30, flow: "unavailable"), direct).confidence, .moderate)
        // authority is the evidence's and the drainage's; age takes confidence only
        XCTAssertEqual(estimate(region(.stable, sceneHoursAgo: 8 * 24), direct).authority, .high)
    }

    func testAnInSituSensorInTheSameZoneAnswersAndTheSatelliteBecomesContext() {
        let g = InSituTurbidity(site: "03572690", name: "Town Creek", fnu: 12, at: now.addingTimeInterval(-3_600), zone: 7)
        let e = estimate(region(), direct, inSitu: g)
        XCTAssertEqual(e.evidenceLevel, .inSitu)
        XCTAssertEqual(e.method, .instrumentMeasured)
        XCTAssertEqual(e.centralFt!, VisibilityModel.centralFt(fnu: 12), accuracy: 1e-9)
        XCTAssertEqual(e.composition.map(\.role), ["answer", "context"])
        // another zone's sensor, or a stale one, does not answer here
        let away = InSituTurbidity(site: "x", name: nil, fnu: 12, at: now.addingTimeInterval(-3_600), zone: 8)
        XCTAssertEqual(estimate(region(), direct, inSitu: away).evidenceLevel, .directSatellite)
        let stale = InSituTurbidity(site: "x", name: nil, fnu: 12, at: now.addingTimeInterval(-7 * 3_600), zone: 7)
        XCTAssertEqual(estimate(region(), direct, inSitu: stale).evidenceLevel, .directSatellite)
    }

    // MARK: Hydrology moves authority, never feet

    func testMajorHydrologicChangeLowersAuthorityButCannotAlterFeet() {
        let stable = estimate(region(.stable), direct)
        let major = estimate(region(.majorRunoff, direction: "murkierThanPass", ratio: 3.4, rain: 1.4), direct)
        XCTAssertEqual(major.evidenceLevel, .changedHistorical)
        XCTAssertEqual(major.authority, .none)
        XCTAssertFalse(major.magnitudeSupported)
        XCTAssertNil(major.centralFt, "no current number after major runoff")
        // the scene's own number, unchanged — no guessed feet subtracted
        XCTAssertEqual(major.lastSupported!.centralFt, stable.centralFt!, accuracy: 0)
        XCTAssertEqual(major.lastSupported!.lowFt, stable.lowFt!, accuracy: 0)
        XCTAssertEqual(major.lastSupported!.highFt, stable.highFt!, accuracy: 0)
        XCTAssertTrue(major.display.valueText.hasPrefix("Last supported estimate ~"))
        XCTAssertTrue(major.display.notes.contains("Current visibility change is not yet calibrated."))
        for s in [RunoffClass.moderateRunoff, .recovering] {
            let e = estimate(region(s, direction: "murkierThanPass"), direct)
            XCTAssertEqual(e.evidenceLevel, .changedHistorical, s.rawValue)
            XCTAssertEqual(e.confidence, .low, s.rawValue)
            XCTAssertEqual(e.lastSupported!.centralFt, stable.centralFt!, accuracy: 0, s.rawValue)
        }
    }

    func testStableConditionsRetainAnOlderObservation() {
        let e = estimate(region(.stable, sceneHoursAgo: 8 * 24), direct)
        XCTAssertEqual(e.evidenceLevel, .stableHistorical)
        XCTAssertTrue(e.magnitudeSupported)
        XCTAssertEqual(e.confidence, .moderate, "an older read keeps its number but is not High (Stage 5)")
        XCTAssertTrue(e.display.notes.first!.contains("the drainage has stayed as it was"))
    }

    func testMissingRainIsUnknownNotZero() {
        let e = estimate(region(.unknown, direction: "unknown", rain: nil), direct)
        XCTAssertNil(e.hydrologicChange!.rainSinceObservationIn)
        XCTAssertEqual(e.confidence, .moderate, "no record to show the drainage stayed the same")
        XCTAssertTrue(e.display.notes.contains { $0.contains("No record shows") })
        // the rain record itself: an unread interval is unknown, not dry
        let rec = RainRecord(basis: "nhdplusBasinAtMouth", drainageKm2: 10, source: "t",
                             steps: [RainStep(start: now.addingTimeInterval(-7_200), end: now.addingTimeInterval(-3_600), inches: nil),
                                     RainStep(start: now.addingTimeInterval(-3_600), end: now, inches: 0)])
        XCTAssertNil(rec.total(from: now.addingTimeInterval(-7_200), to: now))
    }

    func testModeledFlowIsNeverPresentedAsMeasured() {
        let m = estimate(region(.moderateRunoff, direction: "murkierThanPass", flow: "modeledNWM", ratio: 3.2), direct)
        let line = m.display.notes.first { $0.contains("flow") }!
        XCTAssertTrue(line.contains("modeled by the National Water Model, not measured"), line)
        XCTAssertFalse(line.contains("(×3.2, measured"), line)
        XCTAssertEqual(m.flowProvenance, "modeledNWM")
        let u = estimate(region(.moderateRunoff, direction: "murkierThanPass", flow: "measuredUSGS", ratio: 3.2), direct)
        XCTAssertTrue(u.display.notes.contains { $0.contains("measured, USGS 03572690") })
    }

    // MARK: Confidence never outruns authority

    func testLowAuthorityCannotDisplayAsHighConfidence() {
        let cells = [direct, filled(100), filled(900), filled(4_000), filled(9_000),
                     ClarityCellEvidence(kind: .grassBed, fnu: 3, distanceToObservedM: 50),
                     ClarityCellEvidence(kind: .none, fnu: nil, distanceToObservedM: nil)]
        for s in [RunoffClass.stable, .minorChange, .moderateRunoff, .majorRunoff, .recovering, .unknown] {
            for comp in [CatchmentCompleteness.complete, .partial, .unavailable] {
                for flow in ["measuredUSGS", "modeledNWM", "unavailable"] {
                    for c in cells {
                        let e = estimate(region(s, completeness: comp, flow: flow), c)
                        XCTAssertLessThanOrEqual(e.confidence, ClarityConfidence(e.authority), "\(s) \(comp) \(flow) \(c.kind)")
                        XCTAssertEqual(e.display.confidenceText, e.confidence.label)
                        if !e.magnitudeSupported { XCTAssertNil(e.centralFt) }
                        if e.confidence == .high { XCTAssertEqual(e.authority, .high) }
                    }
                }
            }
        }
        XCTAssertEqual(estimate(region(.stable, completeness: .partial), direct).confidence, .moderate)
        XCTAssertEqual(estimate(region(.stable, completeness: .unavailable), direct).confidence, .low)
    }

    // MARK: The legacy estimate

    func testTheLegacyEstimateIsNeverTheAnswer() {
        let legacy = LegacyClarityEstimate(model: "rain-decay-v0", centralFt: 4.0, source: "rain")
        XCTAssertTrue(legacy.label.hasPrefix("Legacy environmental estimate"))
        // with a scene: the satellite answers, the legacy number rides along labelled
        let e = estimate(region(), direct, legacy: legacy)
        XCTAssertEqual(e.primarySource, .satelliteObserved)
        XCTAssertNotEqual(e.centralFt, 4.0)
        XCTAssertEqual(e.legacyEnvironmentalEstimate, legacy)
        // without any evidence: no number at all — never the 4 ft fallback
        for c in [ClarityCellEvidence(kind: .none, fnu: nil, distanceToObservedM: nil), filled(8_000)] {
            let f = estimate(region(), c, legacy: legacy)
            XCTAssertNil(f.centralFt)
            XCTAssertFalse(f.composition.contains { $0.centralFt == 4.0 })
        }
        let off = estimate(nil, nil, legacy: legacy)
        XCTAssertFalse(off.supported); XCTAssertNil(off.centralFt)
    }

    func testTheConditionsEngineMarksItsRainDecayClarityAsLegacy() {
        // The only path still producing it: /conditions without a turbidity gauge.
        let input = ConditionsInput(date: now, latitude: 34.41, longitude: -86.21, region: .lowerMid,
                                    windMph: 4, windDirDeg: 0, airTempF: 75, cloudPct: 0, humidityPct: 50,
                                    pressureInHg: 30, pressureTrend: .steady, pressureChange12hInHg: 0, weatherCode: 0,
                                    cityGlowFactor: 0.2, rainLast48hIn: 0, rainWatershed72hIn: 0.2)
        XCTAssertFalse(input.hasTurbidityGage)
        let dto = SectorEngineAPI.clarityVisibilityDTO(input, turbidity: nil, mrms: nil, config: .default)
        XCTAssertEqual(dto.model, "rain-decay-v0")
        XCTAssertEqual(dto.source, "rainDecayModel")
        XCTAssertNil(dto.lowFt)
        XCTAssertEqual(LegacyClarityEstimate(model: dto.model, centralFt: dto.centralFt, source: dto.provenance).label.prefix(6), "Legacy")
    }

    static let repo = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()

    func testProductionScoringDoesNotReadTheCurrentClarityEngine() throws {
        // Adoption is a reviewed change: no scoring source refers to it yet.
        let engine = Self.repo.appendingPathComponent("Sources/SectorEngine/Engine")
        let files = FileManager.default.enumerator(at: engine, includingPropertiesForKeys: nil)!
            .compactMap { $0 as? URL }.filter { $0.pathExtension == "swift" }
        XCTAssertFalse(files.isEmpty)
        for f in files {
            let text = try String(contentsOf: f, encoding: .utf8)
            for name in ["CurrentClarity", "ClarityComposite", "ClarityRegionContext"] {
                XCTAssertFalse(text.contains(name), "\(f.lastPathComponent) reads \(name)")
            }
        }
    }

    func testTheLegacyClarityPathsAreExactlyTheKnownOnes() throws {
        // Every source that builds the 4.0 ft rain-decay estimate. A new
        // consumer of it fails here and has to be named (and justified).
        let src = Self.repo.appendingPathComponent("Sources")
        let files = FileManager.default.enumerator(at: src, includingPropertiesForKeys: nil)!
            .compactMap { $0 as? URL }.filter { $0.pathExtension == "swift" }
        var users: [String] = []
        for f in files where try String(contentsOf: f, encoding: .utf8).contains("fallbackBaseClearFt") {
            users.append(f.lastPathComponent)
        }
        XCTAssertEqual(Set(users), ["ClarityFactor.swift", "ConditionsConfig.swift"])
    }

    // MARK: Reports stay intervals, methods stay apart

    func testReportIntervalsRemainIntervals() {
        for c in ClarityCategory.allCases {
            let i = VisibilityInterval(c)
            XCTAssertEqual(i.lowFt, c.lowFt); XCTAssertEqual(i.highFt, c.highFt)
            XCTAssertEqual(i.label, c.label)
        }
        let data = try! JSONEncoder().encode(VisibilityInterval(.ft2to4))
        let json = try! JSONSerialization.jsonObject(with: data) as! [String: Double]
        XCTAssertEqual(json, ["lowFt": 2, "highFt": 4], "an interval, with no midpoint")
    }

    func testNightVisibilityIsNotSecchi() throws {
        XCTAssertNotEqual(VisibilityMethod.userReportedNightVisibility, .satelliteDerivedSecchi)
        let item = ClarityEvidenceItem(role: "context", level: .none, source: .userReported, method: .userReportedNightVisibility,
                                       detail: "2–4 ft under lights", centralFt: nil, lowFt: 2, highFt: 4, observedAt: now)
        let back = try JSONDecoder().decode(ClarityEvidenceItem.self, from: JSONEncoder().encode(item))
        XCTAssertEqual(back.method, .userReportedNightVisibility)
        XCTAssertNil(back.centralFt)
    }

    // MARK: The index, the composite and the map

    let index = ClarityRegionsIndex.guntersville

    func testTheIndexDecodesAndMatchesTheArmGraph() {
        XCTAssertEqual(index.count, 415_214)
        XCTAssertEqual(index.regionIds.first, "_mainStem")
        XCTAssertEqual(Set(index.regionIds.dropFirst()), Set(Hydrology.guntersville.arms.map(\.id)))
        XCTAssertEqual(index.zones.count, 130)
        // a cell's coordinate comes back to the same cell
        for i in stride(from: 0, to: index.count, by: 41_521) {
            let c = index.coordinate(of: i)!
            XCTAssertEqual(index.index(lat: c.lat, lon: c.lon), i)
        }
    }

    func testLandIsNotWater() {
        // Guntersville town's peninsula, between the main stem and Big Spring Creek
        XCTAssertNil(index.index(lat: 34.3585, lon: -86.2945))
        // Huntsville is outside the frame
        XCTAssertNil(index.index(lat: 34.73, lon: -86.59))
    }

    func synthetic(_ date: String, code: UInt8, dist: UInt8 = 0) -> ClaritySceneCells {
        ClaritySceneCells(ref: ClaritySceneRef(date: date, time: now.addingTimeInterval(-86_400), platform: nil, source: "t"),
                          value: [UInt8](repeating: 120, count: index.count),
                          code: [UInt8](repeating: code, count: index.count),
                          dist: [UInt8](repeating: dist, count: index.count))
    }

    func testEachRegionStandsOnItsOwnSceneAndNothingCrossesBetweenThem() {
        // Town Creek on an older clear scene; everything else on a newer one it could not read
        let old = synthetic("2026-09-17", code: 255)
        let new = synthetic("2026-09-20", code: 1, dist: 80)
        let town = index.regionIds.firstIndex(of: "town-creek-marshall")!
        var sceneFor = [Int?](repeating: 1, count: index.regionIds.count)
        sceneFor[town] = 0
        let comp = ClarityComposite(index: index, scenes: [old, new], sceneForRegion: sceneFor)
        var seenTown = 0, seenOther = 0
        for i in stride(from: 0, to: index.count, by: 97) {
            let e = comp.evidence(atCell: i)
            if Int(index.region[i]) == town { XCTAssertEqual(e.kind, .direct); seenTown += 1 }
            else { XCTAssertEqual(e.kind, .filled); XCTAssertEqual(e.distanceToObservedM!, 7_900, accuracy: 0.1); seenOther += 1 }
        }
        XCTAssertGreaterThan(seenTown, 10); XCTAssertGreaterThan(seenOther, 1_000)
        // the encoded composite carries the same choice per cell
        let bytes = comp.encoded()
        let n = index.count, header = 4 + 4 * 6 + index.maskRLE.count
        let sceneByte = bytes[header + 6 * n + (0..<n).first { Int(index.region[$0]) == town }!]
        XCTAssertEqual(sceneByte, 0)
    }

    func testTheMapTableIsTheResolversOwnDecision() {
        // For every region state and every kind of cell, the table the map
        // reads equals what the API returns for a real cell of that kind.
        let regions: [ClarityRegionContext?] = [region(.stable), region(.minorChange), region(.moderateRunoff),
                                                region(.majorRunoff), region(.unknown, completeness: .partial), nil]
        let comp = ClarityComposite(index: index, scenes: [synthetic("d", code: 255)], sceneForRegion: [0])
        let world = CurrentClarityWorld(lakeId: "Guntersville|AL", now: now, index: index, composite: comp,
                                        regions: regions, notes: [])
        let lake = world.lakeSummary(path: "/x")
        XCTAssertEqual(lake.outcomes.count, regions.count)
        for (r, ctx) in regions.enumerated() {
            for (code, dist) in [(UInt8(255), UInt8(0)), (1, 3), (2, 6), (1, 7), (1, 40), (1, 51), (1, 52), (3, 2), (3, 60), (1, 254), (0, 0)] {
                let cell = ClarityCellCode.evidence(value: 120, code: code, dist: dist)
                let key = CurrentClarityLake.evidenceKey(code: code, dist: dist)
                let api = CurrentClarityResolver.estimate(lakeId: "g", lat: 0, lon: 0, region: ctx, zone: nil, cell: ctx == nil ? nil : cell, now: now)
                let table = lake.outcomes[r][key]
                XCTAssertEqual(table.confidence, api.confidence, "region \(r) code \(code) dist \(dist)")
                XCTAssertEqual(table.magnitudeSupported, api.magnitudeSupported, "region \(r) code \(code) dist \(dist)")
                XCTAssertEqual(table.level, api.evidenceLevel, "region \(r) code \(code) dist \(dist)")
            }
        }
    }

    func testASceneFromAnotherIndexIsRefused() {
        var bad: [UInt8] = Array("SCC1".utf8)
        bad += [UInt8](withUnsafeBytes(of: UInt32(index.count).littleEndian) { Array($0) })
        bad += [UInt8](withUnsafeBytes(of: UInt32(0xDEADBEEF).littleEndian) { Array($0) })
        XCTAssertThrowsError(try ClaritySceneCells(ref: ClaritySceneRef(date: "d", time: now, platform: nil, source: "t"),
                                                   data: bad, index: index))
    }

    /// The numbers the phone reproduces (SectorTests/CurrentClarityTests
    /// asserts the same list): the map colours and the offline card use the
    /// phone's copy of the conversion, so it must be the engine's to the digit.
    static let golden: [(fnu: Double, observed: Bool, distanceM: Double?, central: Double, low: Double, high: Double)] = [
        (4.2, true, nil, 4.458740, 1.964320, 14.764275),
        (4.2, false, 300, 4.458740, 1.955406, 14.810387),
        (4.2, false, 2000, 4.458740, 1.940820, 14.886907),
        (2.0, false, 8000, 7.152631, 3.027365, 24.351744),
        (12.0, true, nil, 2.284460, 1.006430, 7.564557),
    ]
    static let goldenKeys: [(code: UInt8, dist: UInt8, key: Int)] = [
        (255, 0, 0), (1, 1, 1), (2, 6, 1), (1, 7, 2), (2, 51, 2), (1, 52, 3), (1, 254, 3),
        (3, 2, 4), (3, 51, 4), (3, 52, 5), (0, 0, 6),
    ]

    func testTheGoldenNumbersThePhoneReproduces() {
        for g in Self.golden {
            let e = VisibilityModel.estimate(fnu: g.fnu, source: g.observed ? .satelliteObserved : .satelliteEstimated,
                                             distanceToObservedM: g.distanceM)
            XCTAssertEqual(e.centralFt, g.central, accuracy: 1e-5)
            XCTAssertEqual(e.lowFt, g.low, accuracy: 1e-5)
            XCTAssertEqual(e.highFt, g.high, accuracy: 1e-5)
        }
        for k in Self.goldenKeys {
            XCTAssertEqual(CurrentClarityLake.evidenceKey(code: k.code, dist: k.dist), k.key, "code \(k.code) dist \(k.dist)")
        }
    }

    func testTheCellsEncodingDecodes() {
        XCTAssertNil(ClarityCellCode.fnu(0))
        XCTAssertEqual(ClarityCellCode.fnu(1)!, 0.5, accuracy: 1e-9)
        XCTAssertEqual(ClarityCellCode.fnu(254)!, 200, accuracy: 1e-6)
        XCTAssertEqual(ClarityCellCode.distanceM(1)!, 0)
        XCTAssertEqual(ClarityCellCode.distanceM(6)!, 500)
        XCTAssertEqual(ClarityCellCode.distanceM(254)!, .infinity)
    }
}
