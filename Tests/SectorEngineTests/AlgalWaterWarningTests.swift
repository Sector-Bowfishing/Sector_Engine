import XCTest
@testable import SectorEngine

/// Clarity Stage 8: the algal-water reliability warning (master beta).
final class AlgalWaterWarningTests: XCTestCase {

    let now = ISO8601DateFormatter().date(from: "2026-09-28T21:00:00Z")!
    let index = ClarityRegionsIndex.guntersville

    func code(_ ndci: Double) -> UInt8 { UInt8((((ndci - AlgalWaterRule.lo) / AlgalWaterRule.step).rounded()) + 1) }

    func scene(_ date: String, platform: String?, code c: UInt8 = 255, value: UInt8 = 120, ndci: UInt8?) -> ClaritySceneCells {
        let n = index.count
        return ClaritySceneCells(ref: ClaritySceneRef(date: date, time: now.addingTimeInterval(-30 * 3600), platform: platform, source: "t"),
                                 value: [UInt8](repeating: value, count: n), code: [UInt8](repeating: c, count: n),
                                 dist: [UInt8](repeating: 0, count: n), ndci: ndci.map { [UInt8](repeating: $0, count: n) })
    }

    func stable() -> ClarityRegionContext {
        ClarityRegionContext(kind: .arm, id: "a", name: "A", scene: ClaritySceneRef(date: "d", time: now.addingTimeInterval(-30 * 3600),
                                                                                    platform: "sentinel-2b", source: "t"),
                             anchorStrength: .strong, anchorNote: nil,
                             runoff: RunoffState(state: .stable, expectedDirection: "sameAsPass", magnitude: "uncalibrated", evidence: []),
                             rainSinceSceneIn: 0, rainRecordThrough: now, flowProvenance: "measuredUSGS", flowSource: "USGS 1",
                             flowChangeRatio: 1, catchmentCompleteness: .complete, limitations: [])
    }

    func world(_ s: ClaritySceneCells) -> CurrentClarityWorld {
        let n = index.regionIds.count
        return CurrentClarityWorld(lakeId: "Guntersville|AL", now: now, index: index,
                                   composite: ClarityComposite(index: index, scenes: [s], sceneForRegion: [Int?](repeating: 0, count: n)),
                                   regions: [ClarityRegionContext?](repeating: stable(), count: n), notes: [])
    }

    func testTheRuleSitsExactlyOnItsThreshold() {
        XCTAssertEqual(code(0.03), AlgalWaterRule.thresholdCode)
        XCTAssertEqual(AlgalWaterRule.decode(AlgalWaterRule.thresholdCode), 0.03)
        XCTAssertFalse(AlgalWaterRule.fires(code: code(0.03)), "NDCI > 0.03, not >=")
        XCTAssertTrue(AlgalWaterRule.fires(code: code(0.0325)))
        XCTAssertFalse(AlgalWaterRule.fires(code: code(0.0)))
        XCTAssertFalse(AlgalWaterRule.fires(code: 0), "no NDCI is no warning")
        XCTAssertNil(AlgalWaterRule.decode(0))
        XCTAssertTrue(AlgalWaterRule.appliesTo(platform: "sentinel-2c"))
        XCTAssertFalse(AlgalWaterRule.appliesTo(platform: "landsat-9"), "never Landsat")
        XCTAssertFalse(AlgalWaterRule.appliesTo(platform: nil))
    }

    func testCellsWithAndWithoutNDCIReadBackAndOldFilesStillDecode() throws {
        // a scene file written before Stage 8: no NDC1 block
        let n = index.count
        func file(_ nd: [UInt8]?) -> [UInt8] {
            var b = Array("SCC1".utf8)
            func u32(_ v: UInt32) { var x = v.littleEndian; withUnsafeBytes(of: &x) { b.append(contentsOf: $0) } }
            u32(UInt32(n)); u32(index.hash)
            b += [UInt8](repeating: 100, count: n) + [UInt8](repeating: 255, count: n) + [UInt8](repeating: 0, count: n)
            if let nd { b += Array("NDC1".utf8) + nd }
            return b
        }
        let ref = ClaritySceneRef(date: "d", time: now, platform: "sentinel-2b", source: "t")
        let old = try ClaritySceneCells(ref: ref, data: file(nil), index: index)
        XCTAssertNil(old.ndci)
        let new = try ClaritySceneCells(ref: ref, data: file([UInt8](repeating: 150, count: n)), index: index)
        XCTAssertEqual(new.ndci?.count, n); XCTAssertEqual(new.value, old.value); XCTAssertEqual(new.code, old.code)
        // the composite round-trips its NDCI; one without NDCI writes none
        let sceneFor = [Int?](repeating: 0, count: index.regionIds.count)
        let with = ClarityComposite(index: index, scenes: [new], sceneForRegion: sceneFor)
        let back = try ClarityComposite(index: index, refs: with.refs, sceneForRegion: sceneFor, encoded: with.encoded())
        XCTAssertEqual(back.ndci, with.ndci); XCTAssertEqual(back.value, with.value)
        let without = ClarityComposite(index: index, scenes: [old], sceneForRegion: sceneFor)
        XCTAssertNil(without.ndci)
        XCTAssertEqual(with.encoded().count, without.encoded().count + 4 + n, "only the tagged block is added")
        XCTAssertEqual(Array(with.encoded().prefix(without.encoded().count)), without.encoded(),
                       "a pre-Stage-8 reader sees exactly the bytes it always did")
    }

    func testAFiredWarningCapsAuthorityAndSaysWhyButLeavesTheNumberAndTheTable() {
        let plain = world(scene("d", platform: "sentinel-2b", ndci: nil))
        let algal = world(scene("d", platform: "sentinel-2b", ndci: code(0.08)))
        let i = 5_000
        let a = plain.estimate(cell: i, lat: 0, lon: 0), b = algal.estimate(cell: i, lat: 0, lon: 0)
        XCTAssertNil(a.algalWarning)
        XCTAssertTrue(a.magnitudeSupported); XCTAssertGreaterThan(a.confidence, .low, "the test needs a Moderate cell")
        let w = try! XCTUnwrap(b.algalWarning)
        XCTAssertTrue(w.fired); XCTAssertEqual(w.ndci, 0.08, accuracy: 0.0026)
        XCTAssertEqual(b.confidence, .low); XCTAssertEqual(b.authority, .low)
        XCTAssertEqual(w.originalConfidence, a.confidence); XCTAssertEqual(w.displayedConfidence, .low)
        XCTAssertEqual(b.display.confidenceText, ClarityConfidence.low.presentedLabel)
        XCTAssertTrue(b.display.notes.first?.hasPrefix(AlgalWaterRule.headline) == true)
        XCTAssertNil(b.category, "no report band claimed under the warning")
        // the number, its range and the map's value are the sediment model's, unchanged
        XCTAssertEqual(b.centralFt, a.centralFt); XCTAssertEqual(b.lowFt, a.lowFt); XCTAssertEqual(b.highFt, a.highFt)
        XCTAssertEqual(b.display.valueText, a.display.valueText)
        XCTAssertEqual(algal.composite.value, plain.composite.value)
        // the outcome table (what Huntability and the map's evidence read) is untouched
        XCTAssertEqual(algal.outcomeTable(), plain.outcomeTable())
        XCTAssertEqual(w.originalCentralFt, a.centralFt)
        // the lake says how much water is under it
        XCTAssertEqual(algal.lakeSummary(path: "/x").overview?.algalWarningPct ?? 0, algal.lakeSummary(path: "/x").overview!.supportedPct, accuracy: 0.001)
        XCTAssertNil(plain.lakeSummary(path: "/x").overview?.algalWarningPct)
    }

    func testBelowTheThresholdOrOnLandsatNothingChangesButTheDiagnostics() {
        let i = 5_000
        let plain = world(scene("d", platform: "sentinel-2b", ndci: nil)).estimate(cell: i, lat: 0, lon: 0)
        let clean = world(scene("d", platform: "sentinel-2b", ndci: code(0.01))).estimate(cell: i, lat: 0, lon: 0)
        XCTAssertEqual(clean.algalWarning?.fired, false)
        XCTAssertEqual(clean.confidence, plain.confidence); XCTAssertEqual(clean.display, plain.display)
        XCTAssertEqual(clean.category, plain.category)
        let landsat = world(scene("d", platform: "landsat-9", ndci: code(0.2))).estimate(cell: i, lat: 0, lon: 0)
        XCTAssertNil(landsat.algalWarning, "the rule is Sentinel-2 only")
        XCTAssertEqual(landsat.confidence, plain.confidence)
    }

    func testTheEstimateStillEncodesAndAnOldClientIgnoresTheWarning() throws {
        let e = world(scene("d", platform: "sentinel-2b", ndci: code(0.1))).estimate(cell: 5_000, lat: 0, lon: 0)
        let enc = JSONEncoder(); enc.dateEncodingStrategy = .iso8601
        let data = try enc.encode(e)
        let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
        XCTAssertEqual(try dec.decode(CurrentClarityEstimate.self, from: data), e)
        let plain = try enc.encode(world(scene("d", platform: "sentinel-2b", ndci: nil)).estimate(cell: 5_000, lat: 0, lon: 0))
        XCTAssertFalse(String(decoding: plain, as: UTF8.self).contains("algalWarning"), "absent, not null, when there is no NDCI")
    }
}
