import XCTest
@testable import SectorEngine

/// Sector_Ops #43, #44: the Lake level/trend customer path reads only the CUSTOMER-lane copy and fails closed at every gate.
final class LakeLevelOutputTests: XCTestCase {
    struct Reader: BrainOutputReader {
        let nodes: [String: String]
        func get(_ path: String) async throws -> Data? { nodes[path].map { Data($0.utf8) } }
    }

    static let lake = "wheeler-lake-al"
    static let on = LakeLevelEligibility(enabled: true, eligibleLakeIds: [lake])
    static let now = ISO8601DateFormatter().date(from: "2026-11-01T21:00:00Z")!

    static func copy(status: String = "AVAILABLE", schema: String = LakeLevelOutputAPI.copySchema, lakeId: String = lake,
                     elevation: String = "555.62", trend: String = "FALLING", freshUntil: String = "2026-11-01T21:20:00Z") -> String {
        """
        {"schema":"\(schema)","lakeId":"\(lakeId)","status":"\(status)","elevationFt":\(elevation),"datum":"NGVD29",
         "observationTime":"2026-11-01T20:00:00Z","sourceAgeHours":1.2,"trend":"\(trend)","change24hFt":-0.15,
         "freshUntil":"\(freshUntil)","brainId":"lake-brain","futureField":1}
        """
    }

    static func reader(_ copy: String = copy()) -> Reader {
        Reader(nodes: [LakeLevelOutputAPI.copyPath(lake): copy])
    }

    func out(_ e: LakeLevelEligibility = on, _ r: BrainOutputReader? = reader()) async -> LakeLevelOutput {
        await LakeLevelOutputAPI.output(lakeId: Self.lake, eligibility: e, reader: r, now: Self.now)
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

    func testReadsOnlyTheCustomerCopy() async {
        XCTAssertEqual(LakeLevelOutputAPI.copyPath(Self.lake), "customer/lakes/wheeler_lake_al/level")
        // Lake's INTERNAL state at its own path is never read, even when it is there.
        let internalOnly = Reader(nodes: ["lakes/wheeler_lake_al/states/lake": Self.copy()])
        let o = await out(Self.on, internalOnly)
        XCTAssertEqual(o.reason, LakeLevelOutputAPI.noPublication)
    }

    func testEachGateFailsClosed() async {
        let notListed = await out(LakeLevelEligibility(enabled: true, eligibleLakeIds: ["other"]))
        XCTAssertEqual(notListed.reason, LakeLevelOutputAPI.notValidatedHere)
        let noReader = await out(Self.on, nil)
        XCTAssertEqual(noReader.reason, LakeLevelOutputAPI.noReader)
        let missing = await out(Self.on, Reader(nodes: [:]))
        XCTAssertEqual(missing.reason, LakeLevelOutputAPI.noPublication)
        let otherLake = await out(Self.on, Self.reader(Self.copy(lakeId: "wheeler-lake-tn")))
        XCTAssertEqual(otherLake.reason, LakeLevelOutputAPI.noPublication)
        let otherSchema = await out(Self.on, Self.reader(Self.copy(schema: "sector-customer-lake-level-v2")))
        XCTAssertEqual(otherSchema.reason, LakeLevelOutputAPI.noPublication)
        let expired = await out(Self.on, Self.reader(Self.copy(freshUntil: "2026-11-01T20:59:00Z")))
        XCTAssertEqual(expired.reason, LakeLevelOutputAPI.stale)
        let noValue = await out(Self.on, Self.reader(Self.copy(elevation: "null")))
        XCTAssertEqual(noValue.reason, LakeLevelOutputAPI.stale)
        let unknownStatus = await out(Self.on, Self.reader(Self.copy(status: "UNKNOWN")))
        XCTAssertEqual(unknownStatus.reason, LakeLevelOutputAPI.noSource)
        let proxyNoTrend = await out(Self.on, Self.reader(Self.copy(status: "ESTIMATE", trend: "UNKNOWN")))
        XCTAssertEqual(proxyNoTrend.reason, LakeLevelOutputAPI.noSource)
        for o in [notListed, noReader, missing, otherLake, otherSchema, expired, noValue, unknownStatus, proxyNoTrend] {
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

    func testNearbyGaugeIsATrendOnlyEstimate() async {
        // Even if a copy carried a proxy elevation, the Engine never serves it (Cortex lake.md LC-06).
        let o = await out(Self.on, Self.reader(Self.copy(status: "ESTIMATE")))
        XCTAssertEqual(o.status, LakeLevelOutput.estimate)
        XCTAssertEqual(o.reason, LakeLevelOutputAPI.nearbyGauge)
        XCTAssertEqual(o.limitation, LakeLevelOutputAPI.nearbyGaugeLimitation)
        XCTAssertEqual(o.trend, "FALLING")
        XCTAssertNil(o.elevationFt)
        XCTAssertNil(o.change24hFt)
        XCTAssertNil(o.datum)
    }
}
