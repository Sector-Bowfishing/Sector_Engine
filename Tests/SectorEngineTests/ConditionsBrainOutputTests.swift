import XCTest
@testable import SectorEngine

/// Sector_Ops #53 spec §4/§5: the four conditions-consolidation readers read only their CUSTOMER-lane copy and fail closed at every gate.
final class ConditionsBrainOutputTests: XCTestCase {
    struct Reader: BrainOutputReader {
        let nodes: [String: String]
        func get(_ path: String) async throws -> Data? { nodes[path].map { Data($0.utf8) } }
    }
    struct ReadError: Error {}
    struct Failing: BrainOutputReader {
        func get(_ path: String) async throws -> Data? { throw ReadError() }
    }

    static let lake = "Guntersville|AL"
    static let now = ISO8601DateFormatter().date(from: "2026-11-10T15:30:00Z")!

    static func clarity(schema: String = ClarityBrainOutputAPI.copySchema, lakeId: String = lake, status: String = "AVAILABLE",
                        central: String = "2.25", freshUntil: String = "2026-11-10T16:00:00Z", observedAt: String = "2026-11-10T15:00:00Z") -> String {
        """
        {"schema":"\(schema)","lakeId":"\(lakeId)","status":"\(status)","centralFt":\(central),"lowFt":1.5,"highFt":3.0,"confidence":"medium",
         "observedAt":"\(observedAt)","freshUntil":"\(freshUntil)","runner":"pulse","publishId":"7def2674","futureField":1}
        """
    }

    static func waterTemp(schema: String = WaterTempBrainOutputAPI.copySchema, lakeId: String = lake, status: String = "AVAILABLE",
                          value: String = "64.2", kind: String = "measured", freshUntil: String = "2026-11-10T21:00:00Z") -> String {
        """
        {"schema":"\(schema)","lakeId":"\(lakeId)","status":"\(status)","valueF":\(value),"kind":"\(kind)","observedAt":"2026-11-10T15:00:00Z",
         "freshUntil":"\(freshUntil)","runner":"cloud","publishId":"p-1"}
        """
    }

    static func binding(schema: String = GenerationBindingOutputAPI.copySchema, lakeId: String = lake, status: String? = nil,
                        damName: String = "Guntersville Dam") -> String {
        let s = status.map { "\"status\":\"\($0)\"," } ?? ""
        return """
        {"schema":"\(schema)","lakeId":"\(lakeId)",\(s)"operatorId":"tva","damId":"tva:GUH","damName":"\(damName)","tvaCode":"GUH",
         "updatedAt":"2026-10-13T00:00:00Z"}
        """
    }

    static func wind(schema: String = WindOutlookModelOutputAPI.copySchema, tonight: String = "best_match", later: String = "ncep_nbm_conus",
                     updatedAt: String = "2026-11-05T12:00:00Z", status: String? = nil) -> String {
        let s = status.map { "\"status\":\"\($0)\"," } ?? ""
        return """
        {"schema":"\(schema)",\(s)"tonight":"\(tonight)","nights2to7":"\(later)","decidedBy":"owner (Sector_Ops #44)","evidence":"W1 NBM SUPPORTED",
         "updatedAt":"\(updatedAt)"}
        """
    }

    func clarityOut(_ copy: String?, reader: Bool = true) async -> ClarityBrainOutput {
        let r: BrainOutputReader? = reader ? Reader(nodes: copy.map { [ClarityBrainOutputAPI.copyPath(Self.lake): $0] } ?? [:]) : nil
        return await ClarityBrainOutputAPI.output(lakeId: Self.lake, reader: r, now: Self.now)
    }

    func waterTempOut(_ copy: String?, reader: Bool = true) async -> WaterTempBrainOutput {
        let r: BrainOutputReader? = reader ? Reader(nodes: copy.map { [WaterTempBrainOutputAPI.copyPath(Self.lake): $0] } ?? [:]) : nil
        return await WaterTempBrainOutputAPI.output(lakeId: Self.lake, reader: r, now: Self.now)
    }

    func bindingOut(_ copy: String?, reader: Bool = true) async -> GenerationBindingOutput {
        let r: BrainOutputReader? = reader ? Reader(nodes: copy.map { [GenerationBindingOutputAPI.copyPath(Self.lake): $0] } ?? [:]) : nil
        return await GenerationBindingOutputAPI.output(lakeId: Self.lake, reader: r, now: Self.now)
    }

    func windOut(_ copy: String?, reader: Bool = true) async -> WindOutlookModelOutput {
        let r: BrainOutputReader? = reader ? Reader(nodes: copy.map { [WindOutlookModelOutputAPI.copyPath: $0] } ?? [:]) : nil
        return await WindOutlookModelOutputAPI.output(reader: r, now: Self.now)
    }

    func testCopyPathsAreTheCustomerLaneOnly() {
        XCTAssertEqual(ClarityBrainOutputAPI.copyPath(Self.lake), "customer/lakes/Guntersville_AL/clarity")
        XCTAssertEqual(WaterTempBrainOutputAPI.copyPath(Self.lake), "customer/lakes/Guntersville_AL/waterTemp")
        XCTAssertEqual(GenerationBindingOutputAPI.copyPath(Self.lake), "customer/lakes/Guntersville_AL/generationBinding")
        XCTAssertEqual(WindOutlookModelOutputAPI.copyPath, "customer/wind/outlookModel")
    }

    // MARK: clarity

    func testClarityAvailableMatchesSpecShape() async throws {
        let o = await clarityOut(Self.clarity())
        XCTAssertEqual(o.status, "AVAILABLE")
        XCTAssertNil(o.reason)
        XCTAssertEqual(o.centralFt, 2.25); XCTAssertEqual(o.lowFt, 1.5); XCTAssertEqual(o.highFt, 3.0)
        XCTAssertEqual(o.confidence, "medium"); XCTAssertEqual(o.runner, "pulse"); XCTAssertEqual(o.publishId, "7def2674")
        let json = try JSONSerialization.jsonObject(with: SectorEngineAPI.makeEncoder().encode(o)) as! [String: Any]
        XCTAssertEqual(Set(json.keys), ["lakeId", "status", "centralFt", "lowFt", "highFt", "confidence", "observedAt", "freshUntil", "runner", "publishId"])
        let estimate = await clarityOut(Self.clarity(status: "ESTIMATE"))
        XCTAssertEqual(estimate.status, "ESTIMATE")
    }

    func testClarityGatesFailClosed() async {
        let cases: [(ClarityBrainOutput, String)] = [
            (await clarityOut(Self.clarity(), reader: false), BrainCopyReason.noReader),
            (await clarityOut(nil), BrainCopyReason.noPublication),
            (await clarityOut(Self.clarity(schema: "sector-customer-clarity-v2")), BrainCopyReason.schemaMismatch),
            (await clarityOut("{\"lakeId\":\"x\"}"), BrainCopyReason.schemaMismatch),
            (await clarityOut(Self.clarity(lakeId: "Guntersville|TN")), BrainCopyReason.lakeIdMismatch),
            (await clarityOut(Self.clarity(freshUntil: "2026-11-10T15:29:59Z")), BrainCopyReason.stale),
            (await clarityOut(Self.clarity(observedAt: "yesterday")), BrainCopyReason.stale),
            (await clarityOut(Self.clarity(status: "UNKNOWN")), BrainCopyReason.noSource),
            (await clarityOut(Self.clarity(status: "SOMETHING_NEW")), BrainCopyReason.noSource),
            (await clarityOut(Self.clarity(central: "null")), BrainCopyReason.noValue),
        ]
        for (o, reason) in cases {
            XCTAssertEqual(o.status, "UNKNOWN", reason)
            XCTAssertEqual(o.reason, reason)
            XCTAssertNil(o.centralFt)
            XCTAssertNil(o.observedAt)
        }
        let thrown = await ClarityBrainOutputAPI.output(lakeId: Self.lake, reader: Failing(), now: Self.now)
        XCTAssertEqual(thrown.reason, BrainCopyReason.noPublication)
    }

    func testReadersNeverReadBrainInternalState() async {
        let internalOnly = Reader(nodes: ["lakes/Guntersville_AL/states/waterClarity": Self.clarity(),
                                          "lakes/Guntersville_AL/states/waterTemp": Self.waterTemp()])
        let c = await ClarityBrainOutputAPI.output(lakeId: Self.lake, reader: internalOnly, now: Self.now)
        let t = await WaterTempBrainOutputAPI.output(lakeId: Self.lake, reader: internalOnly, now: Self.now)
        XCTAssertEqual(c.reason, BrainCopyReason.noPublication)
        XCTAssertEqual(t.reason, BrainCopyReason.noPublication)
    }

    // MARK: water temp

    func testWaterTempAvailableMatchesSpecShape() async throws {
        let o = await waterTempOut(Self.waterTemp())
        XCTAssertEqual(o.status, "AVAILABLE"); XCTAssertEqual(o.valueF, 64.2); XCTAssertEqual(o.kind, "measured")
        let json = try JSONSerialization.jsonObject(with: SectorEngineAPI.makeEncoder().encode(o)) as! [String: Any]
        XCTAssertEqual(Set(json.keys), ["lakeId", "status", "valueF", "kind", "observedAt", "freshUntil", "runner", "publishId"])
        let modeled = await waterTempOut(Self.waterTemp(status: "ESTIMATE", kind: "modeled"))
        XCTAssertEqual(modeled.status, "ESTIMATE")
    }

    func testWaterTempGatesFailClosed() async {
        let cases: [(WaterTempBrainOutput, String)] = [
            (await waterTempOut(Self.waterTemp(), reader: false), BrainCopyReason.noReader),
            (await waterTempOut(nil), BrainCopyReason.noPublication),
            (await waterTempOut(Self.waterTemp(schema: "sector-customer-lake-level-v1")), BrainCopyReason.schemaMismatch),
            (await waterTempOut(Self.waterTemp(lakeId: "Wheeler|AL")), BrainCopyReason.lakeIdMismatch),
            (await waterTempOut(Self.waterTemp(freshUntil: "2026-11-10T15:00:00Z")), BrainCopyReason.stale),
            (await waterTempOut(Self.waterTemp(status: "UNKNOWN")), BrainCopyReason.noSource),
            (await waterTempOut(Self.waterTemp(value: "null")), BrainCopyReason.noValue),
            (await waterTempOut(Self.waterTemp(kind: "satellite")), BrainCopyReason.noValue),
        ]
        for (o, reason) in cases {
            XCTAssertEqual(o.status, "UNKNOWN", reason)
            XCTAssertEqual(o.reason, reason)
            XCTAssertNil(o.valueF)
        }
    }

    // MARK: generation binding

    func testGenerationBindingAvailable() async {
        let o = await bindingOut(Self.binding())
        XCTAssertEqual(o.status, "AVAILABLE"); XCTAssertEqual(o.damName, "Guntersville Dam"); XCTAssertEqual(o.tvaCode, "GUH")
        XCTAssertNil(o.cwmsOffice)
    }

    func testGenerationBindingGatesFailClosed() async {
        let cases: [(GenerationBindingOutput, String)] = [
            (await bindingOut(Self.binding(), reader: false), BrainCopyReason.noReader),
            (await bindingOut(nil), BrainCopyReason.noPublication),
            (await bindingOut(Self.binding(schema: "sector-customer-generation-binding-v0")), BrainCopyReason.schemaMismatch),
            (await bindingOut(Self.binding(lakeId: "Wheeler|AL")), BrainCopyReason.lakeIdMismatch),
            (await bindingOut(Self.binding(status: "UNKNOWN")), BrainCopyReason.noSource),
            (await bindingOut(Self.binding(damName: "")), BrainCopyReason.noValue),
        ]
        for (o, reason) in cases {
            XCTAssertEqual(o.status, "UNKNOWN", reason)
            XCTAssertEqual(o.reason, reason)
            XCTAssertNil(o.damId)
        }
    }

    // MARK: wind outlook model

    func testWindOutlookModelAvailable() async {
        let o = await windOut(Self.wind())
        XCTAssertEqual(o.status, "AVAILABLE"); XCTAssertEqual(o.tonight, "best_match"); XCTAssertEqual(o.nights2to7, "ncep_nbm_conus")
        XCTAssertNil(o.reason)
    }

    func testWindOutlookModelGatesFailClosed() async {
        let cases: [(WindOutlookModelOutput, String)] = [
            (await windOut(Self.wind(), reader: false), BrainCopyReason.noReader),
            (await windOut(nil), BrainCopyReason.noPublication),
            (await windOut(Self.wind(schema: "sector-customer-wind-model-v1")), BrainCopyReason.schemaMismatch),
            (await windOut(Self.wind(updatedAt: "2026-10-27T15:29:59Z")), BrainCopyReason.stale),       // 14 days + 1 s
            (await windOut(Self.wind(updatedAt: "not a date")), BrainCopyReason.stale),
            (await windOut(Self.wind(status: "UNKNOWN")), BrainCopyReason.noSource),
            (await windOut(Self.wind(tonight: "ncep_nbm_conus")), BrainCopyReason.noValue),             // WS-5: tonight stays best_match
            (await windOut(Self.wind(later: "gfs_global")), BrainCopyReason.noValue),
        ]
        for (o, reason) in cases {
            XCTAssertEqual(o.status, "UNKNOWN", reason)
            XCTAssertEqual(o.reason, reason)
            XCTAssertNil(o.nights2to7)
        }
        let edge = await windOut(Self.wind(updatedAt: "2026-10-27T15:30:00Z"))                         // exactly 14 days: still fresh
        XCTAssertEqual(edge.status, "AVAILABLE")
    }
}
