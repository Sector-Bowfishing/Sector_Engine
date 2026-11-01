import XCTest
@testable import SectorEngine

/// Sector_Ops #43: the Lake level/trend customer path fails closed at every gate.
final class LakeLevelOutputTests: XCTestCase {
    struct Reader: BrainOutputReader {
        let nodes: [String: String]
        func get(_ path: String) async throws -> Data? { nodes[path].map { Data($0.utf8) } }
    }

    static let lake = "wheeler-lake-al"
    static let on = LakeLevelEligibility(enabled: true, eligibleLakeIds: [lake])

    static func state(kind: String = "OBSERVED", capability: String = "DIRECT_OPERATOR_POOL", stale: Bool = false,
                      lakeId: String = lake, elevation: String = "555.62") -> String {
        """
        {"lakeId":"\(lakeId)","schemaVersion":1,"kind":"\(kind)","sourceCapability":"\(capability)","currentElevationFt":\(elevation),
         "datum":"NGVD29","observationTime":"2026-11-01T20:00:00Z","sourceAgeHours":1.2,"change":{"h24":-0.15},
         "levelState":"IN_ZONE","trendState":"FALLING","historicalState":"NORMAL","floodPoolState":"NORMAL","baselineStatus":"SUFFICIENT",
         "freshness":{"generatedAt":"2026-11-01T20:30:00Z","freshUntil":"2026-11-01T21:20:00Z","nextCheckAt":"2026-11-01T21:20:00Z",
                      "stale":\(stale),"refreshReason":"cadence"},
         "provenance":{},"futureField":1}
        """
    }

    static func reader(readiness: String = "BETA", state: String = state()) -> Reader {
        Reader(nodes: ["brains/lake-brain/status": "\"\(readiness)\"", "lakes/wheeler_lake_al/states/lake": state])
    }

    func out(_ e: LakeLevelEligibility = on, _ r: BrainOutputReader? = reader()) async -> LakeLevelOutput {
        await LakeLevelOutputAPI.output(lakeId: Self.lake, eligibility: e, reader: r)
    }

    func testShippedDefaultsAreUnknownEverywhere() async {
        let shipped = LakeLevelEligibility.fromEnvironment([:])
        XCTAssertFalse(shipped.enabled)
        XCTAssertTrue(LakeLevelEligibility.validatedLakeIds.isEmpty)
        let o = await out(shipped)
        XCTAssertEqual(o.status, LakeLevelOutput.unknown)
        XCTAssertEqual(o.reason, LakeLevelOutputAPI.notEnabled)
        XCTAssertNil(o.elevationFt)
        // The flag alone opens nothing while the validated list is empty.
        let flagged = await out(LakeLevelEligibility.fromEnvironment(["SECTOR_LAKE_LEVEL_OUTPUT": "1"]))
        XCTAssertEqual(flagged.reason, LakeLevelOutputAPI.notValidatedHere)
    }

    func testEachGateFailsClosed() async {
        let notListed = await out(LakeLevelEligibility(enabled: true, eligibleLakeIds: ["other"]))
        XCTAssertEqual(notListed.reason, LakeLevelOutputAPI.notValidatedHere)
        let noReader = await out(Self.on, nil)
        XCTAssertEqual(noReader.reason, LakeLevelOutputAPI.noReader)
        let calibration = await out(Self.on, Self.reader(readiness: "CALIBRATION"))
        XCTAssertEqual(calibration.reason, LakeLevelOutputAPI.notBeta)
        let missing = await out(Self.on, Reader(nodes: ["brains/lake-brain/status": "\"BETA\""]))
        XCTAssertEqual(missing.reason, LakeLevelOutputAPI.noPublication)
        let otherLake = await out(Self.on, Self.reader(state: Self.state(lakeId: "wheeler-lake-tn")))
        XCTAssertEqual(otherLake.reason, LakeLevelOutputAPI.noPublication)
        let stale = await out(Self.on, Self.reader(state: Self.state(stale: true)))
        XCTAssertEqual(stale.reason, LakeLevelOutputAPI.stale)
        let noValue = await out(Self.on, Self.reader(state: Self.state(elevation: "null")))
        XCTAssertEqual(noValue.reason, LakeLevelOutputAPI.stale)
        let modeled = await out(Self.on, Self.reader(state: Self.state(kind: "PROXY", capability: "MODELED")))
        XCTAssertEqual(modeled.reason, LakeLevelOutputAPI.noSource)
        for o in [notListed, noReader, calibration, missing, otherLake, stale, noValue, modeled] {
            XCTAssertEqual(o.status, LakeLevelOutput.unknown)
            XCTAssertNil(o.elevationFt)
            XCTAssertNil(o.trend)
        }
    }

    func testObservedLevelIsAvailable() async {
        let o = await out()
        XCTAssertEqual(o.status, LakeLevelOutput.available)
        XCTAssertNil(o.reason)
        XCTAssertEqual(o.elevationFt, 555.62)
        XCTAssertEqual(o.trend, "FALLING")
        XCTAssertEqual(o.change24hFt, -0.15)
        XCTAssertEqual(o.freshUntil, "2026-11-01T21:20:00Z")
        XCTAssertNil(o.limitation)
    }

    func testNearbyGaugeIsAnEstimate() async {
        let o = await out(Self.on, Self.reader(state: Self.state(kind: "PROXY", capability: "NEARBY_GAUGE_PROXY")))
        XCTAssertEqual(o.status, LakeLevelOutput.estimate)
        XCTAssertEqual(o.reason, LakeLevelOutputAPI.nearbyGauge)
        XCTAssertEqual(o.limitation, LakeLevelOutputAPI.nearbyGaugeLimitation)
    }
}
