import XCTest
@testable import SectorEngine

/// Clarity Fusion Stage 5: the prepared world the routes read instead of a live build.
final class PreparedClarityTests: XCTestCase {

    let now = ISO8601DateFormatter().date(from: "2026-09-28T21:00:00Z")!
    let index = ClarityRegionsIndex.guntersville

    func scene(_ date: String, code: UInt8, value: UInt8 = 120, dist: UInt8 = 0, hoursAgo: Double = 30) -> ClaritySceneCells {
        ClaritySceneCells(ref: ClaritySceneRef(date: date, time: now.addingTimeInterval(-hoursAgo * 3600), platform: "sentinel-2b", source: "t"),
                          value: [UInt8](repeating: value, count: index.count),
                          code: [UInt8](repeating: code, count: index.count),
                          dist: [UInt8](repeating: dist, count: index.count))
    }

    func context(_ state: RunoffClass, sceneHoursAgo: Double = 30) -> ClarityRegionContext {
        ClarityRegionContext(kind: .arm, id: "a", name: "A", scene: ClaritySceneRef(date: "d", time: now.addingTimeInterval(-sceneHoursAgo * 3600),
                                                                                    platform: nil, source: "t"),
                             anchorStrength: .strong, anchorNote: nil,
                             runoff: RunoffState(state: state, expectedDirection: "sameAsPass", magnitude: "uncalibrated", evidence: []),
                             rainSinceSceneIn: 0, rainRecordThrough: now, flowProvenance: "measuredUSGS", flowSource: "USGS 1",
                             flowChangeRatio: 1, catchmentCompleteness: .complete, limitations: [])
    }

    func world(regions: [ClarityRegionContext?], sceneFor: [Int?], scenes: [ClaritySceneCells]) -> CurrentClarityWorld {
        CurrentClarityWorld(lakeId: "Guntersville|AL", now: now, index: index,
                            composite: ClarityComposite(index: index, scenes: scenes, sceneForRegion: sceneFor),
                            regions: regions, notes: [])
    }

    func testAPreparedCompositeReadsBackExactly() throws {
        let a = scene("2026-09-17", code: 255, value: 90), b = scene("2026-09-20", code: 1, value: 140, dist: 12)
        var sceneFor = [Int?](repeating: 1, count: index.regionIds.count)
        sceneFor[0] = 0; sceneFor[1] = nil
        let comp = ClarityComposite(index: index, scenes: [a, b], sceneForRegion: sceneFor)
        let back = try ClarityComposite(index: index, refs: comp.refs, sceneForRegion: sceneFor, encoded: comp.encoded())
        XCTAssertEqual(back.value, comp.value); XCTAssertEqual(back.code, comp.code); XCTAssertEqual(back.dist, comp.dist)
        XCTAssertEqual(back.encoded(), comp.encoded())
        for i in stride(from: 0, to: index.count, by: 1_013) { XCTAssertEqual(back.evidence(atCell: i), comp.evidence(atCell: i)) }
        // a world.json of another hour cannot be paired with this composite
        var other = sceneFor; other[2] = 0
        XCTAssertThrowsError(try ClarityComposite(index: index, refs: comp.refs, sceneForRegion: other, encoded: comp.encoded())) {
            XCTAssertEqual($0 as? ClarityComposite.DecodeError, .sceneMismatch)
        }
        XCTAssertThrowsError(try ClarityComposite(index: index, refs: comp.refs, sceneForRegion: sceneFor,
                                                  encoded: Array(comp.encoded().dropLast(10))))
    }

    func testAPreparedWorldIsCurrentThenStaleThenExpired() throws {
        let w = world(regions: [context(.stable)], sceneFor: [0], scenes: [scene("d", code: 255)])
        let p = PreparedClarityWorld(world: w, provenance: .init(hydrologyThrough: now, newestScene: "d", oldestScene: "d",
                                                                 engineCommit: nil, buildSeconds: 40),
                                     files: .init(composite: "c.bin", compositeGzip: "c.bin.gz", compositeBytes: 1,
                                                  compositeGzipBytes: 1, changes: nil))
        XCTAssertEqual(p.freshness(at: now.addingTimeInterval(3_600)), .current)
        XCTAssertEqual(p.freshness(at: now.addingTimeInterval(2 * 3_600)), .current)
        XCTAssertEqual(p.freshness(at: now.addingTimeInterval(2 * 3_600 + 1)), .stale)
        XCTAssertEqual(p.freshness(at: now.addingTimeInterval(12 * 3_600 + 1)), .expired)
        // current: as built
        XCTAssertEqual(p.regions(at: now.addingTimeInterval(600)), w.regions)
        // stale: the drainage was not re-checked, so it is unknown and nothing reads High
        let late = now.addingTimeInterval(5 * 3_600)
        let stale = p.regions(at: late)
        XCTAssertEqual(stale[0]?.runoff.state, .unknown)
        XCTAssertTrue(stale[0]!.limitations.last!.contains("the hourly update is late"))
        let e = CurrentClarityResolver.estimate(lakeId: "g", lat: 0, lon: 0, region: stale[0], zone: nil,
                                                cell: ClarityCellEvidence(kind: .direct, fnu: 4, distanceToObservedM: 0), now: late)
        XCTAssertLessThan(e.confidence, .high)
        // runoff already found is kept as it is
        let major = PreparedClarityWorld.unchecked(context(.majorRunoff), since: now)
        XCTAssertEqual(major.runoff.state, .majorRunoff)
    }

    func testAPreparedWorldRoundTripsThroughItsJSON() throws {
        let w = world(regions: [context(.stable), nil, context(.recovering)], sceneFor: [0, nil, 0], scenes: [scene("d", code: 255)])
        let p = PreparedClarityWorld(world: w, provenance: .init(hydrologyThrough: now, newestScene: "d", oldestScene: "d",
                                                                 engineCommit: "abc", buildSeconds: 41.5),
                                     files: .init(composite: "composite-\(w.etag).bin", compositeGzip: "composite-\(w.etag).bin.gz",
                                                  compositeBytes: 2, compositeGzipBytes: 1, changes: "changes.json"))
        let e = JSONEncoder(); e.dateEncodingStrategy = .iso8601
        let back = try PreparedClarityStore.decoder.decode(PreparedClarityWorld.self, from: e.encode(p))
        XCTAssertEqual(back, p)
        XCTAssertEqual(back.outcomes, w.outcomeTable())
        XCTAssertEqual(back.etag, w.etag)
    }

    func testAReportsChangeIsMeasuredFromTheHourAtOrBeforeIt() {
        func change(_ s: RunoffClass) -> HydrologicChange {
            HydrologicChange(state: s, expectedDirection: "unknown", magnitude: "uncalibrated", rainSinceObservationIn: nil,
                             rainRecordThrough: nil, flowChangeRatio: nil, flowProvenance: "unavailable", flowSource: nil,
                             authorityCap: CurrentClarityResolver.Rules.hydrologicCap(s), evidence: [])
        }
        let h = { (k: Double) in self.now.addingTimeInterval(-k * 3600) }
        let c = PreparedClarityChanges(schema: PreparedClarityChanges.schemaId, lakeId: "g", builtAt: now,
                                       regions: ["a": [.init(since: h(2), change: change(.moderateRunoff)),
                                                       .init(since: h(1), change: change(.minorChange)),
                                                       .init(since: h(0), change: change(.stable))]])
        XCTAssertEqual(c.change(region: "a", since: h(1.5))?.state, .moderateRunoff, "14:30 is measured from 14:00, never 15:00")
        XCTAssertEqual(c.change(region: "a", since: h(1))?.state, .minorChange)
        XCTAssertEqual(c.change(region: "a", since: h(0.2))?.state, .minorChange, "12 minutes ago is measured from the hour before")
        XCTAssertEqual(c.change(region: "a", since: h(0))?.state, .stable)
        XCTAssertNil(c.change(region: "a", since: h(3)), "older than the prepared hours: the route reads live")
        XCTAssertNil(c.change(region: "b", since: h(1)))
    }

    func testTheOverviewDescribesTheLakeNotAPoint() {
        // half the regions read directly under a stable drainage, the rest changed since
        let n = index.regionIds.count
        let regions: [ClarityRegionContext?] = (0..<n).map { $0 % 2 == 0 ? context(.stable) : context(.majorRunoff) }
        let w = world(regions: regions, sceneFor: [Int?](repeating: 0, count: n), scenes: [scene("d", code: 255)])
        let o = w.lakeSummary(path: "/x").overview!
        XCTAssertEqual(o.waterCells, index.count)
        XCTAssertEqual(o.supportedPct + o.changedPct + o.unsupportedPct, 1, accuracy: 0.002)
        XCTAssertGreaterThan(o.supportedPct, 0); XCTAssertGreaterThan(o.changedPct, 0)
        XCTAssertEqual(o.supportedFtP10, o.supportedFtP90, "one value everywhere")
        XCTAssertTrue(o.headline.contains("of the water has a current estimate"), o.headline)
        XCTAssertFalse(o.headline.contains("Clear"), "no lake-wide category word")
        XCTAssertNil(o.byConfidence["High"], "two user-facing tiers")
        // grass is never supported
        let grass = world(regions: [context(.stable)], sceneFor: [0], scenes: [scene("d", code: 3, dist: 2)])
        XCTAssertEqual(grass.lakeSummary(path: "/x").overview!.supportedPct, 0)
    }

    func testTheLakeSummaryNamesItsFreshnessAndTheWordsForEachTier() {
        let w = world(regions: [context(.stable)], sceneFor: [0], scenes: [scene("d", code: 255)])
        let s = w.lakeSummary(path: "/x")
        XCTAssertEqual(s.freshness, .live)
        XCTAssertNil(s.preparedAt)
        XCTAssertEqual(s.confidenceLabels?["high"], "Moderate")
        XCTAssertEqual(s.confidenceLabels?["low"], "Low")
    }
}
