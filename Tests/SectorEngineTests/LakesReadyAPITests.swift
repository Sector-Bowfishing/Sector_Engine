//
//  LakesReadyAPITests.swift
//  SectorEngineTests
//
//  Sector_Engine #156: `GET /lakes/ready` lists the lakes with a usable CUSTOMER-lane copy. Flag off by default; no reader
//  means an empty list; statuses and freshness come from the #144 readers; reads never leave `customer/lakes`. The golden
//  response (verification/fixtures/phone-contract/lakes-ready-v1.golden.json) is synthetic and checked against
//  contracts/phone/lakes-ready-v1.json here and in verification/test_lakes_ready_contract.py.
//

import XCTest
@testable import SectorEngine

final class LakesReadyAPITests: XCTestCase {

    // MARK: fixtures

    /// Serves whole nodes by path and records every path it is asked for.
    final class Recording: BrainOutputReader, @unchecked Sendable {
        let nodes: [String: String]
        private let lock = NSLock()
        private var _paths: [String] = []
        var paths: [String] { lock.lock(); defer { lock.unlock() }; return _paths }
        init(_ nodes: [String: String]) { self.nodes = nodes }
        private func record(_ path: String) { lock.lock(); _paths.append(path); lock.unlock() }
        func get(_ path: String) async throws -> Data? {
            record(path)
            return nodes[path].map { Data($0.utf8) }
        }
    }
    struct ReadError: Error {}
    struct Failing: BrainOutputReader { func get(_ path: String) async throws -> Data? { throw ReadError() } }

    static let now = ISO8601DateFormatter().date(from: "2026-11-10T15:30:00Z")!
    static let on = LakesReadyConfig(enabled: true)
    static let levelOn = LakeLevelEligibility(enabled: true, eligibleLakeIds: LakeLevelEligibility.validatedLakeIds)
    static let levelOff = LakeLevelEligibility(enabled: false, eligibleLakeIds: LakeLevelEligibility.validatedLakeIds)

    static func clarity(_ lakeId: String, status: String, observedAt: String, freshUntil: String) -> String {
        """
        {"schema":"sector-customer-clarity-v1","lakeId":"\(lakeId)","status":"\(status)","centralFt":2.0,"lowFt":1.0,"highFt":3.0,
         "confidence":"medium","observedAt":"\(observedAt)","freshUntil":"\(freshUntil)","runner":"pulse","publishId":"p-1"}
        """
    }
    static func waterTemp(_ lakeId: String, status: String, kind: String, observedAt: String, freshUntil: String) -> String {
        """
        {"schema":"sector-customer-water-temp-v1","lakeId":"\(lakeId)","status":"\(status)","valueF":60.0,"kind":"\(kind)",
         "observedAt":"\(observedAt)","freshUntil":"\(freshUntil)","runner":"cloud","publishId":"p-1"}
        """
    }
    static func level(_ lakeId: String, status: String, observationTime: String, freshUntil: String, trend: String = "STABLE") -> String {
        """
        {"schema":"sector-customer-lake-level-v1","lakeId":"\(lakeId)","status":"\(status)","elevationFt":1000.0,"datum":"NGVD29",
         "observationTime":"\(observationTime)","sourceAgeHours":0.5,"trend":"\(trend)","change24hFt":0.1,
         "freshUntil":"\(freshUntil)","brainId":"lake-brain","sourceRelease":"r1","writtenAt":"\(observationTime)"}
        """
    }

    /// The golden scenario: every status the readers know, plus stale, future-dated, unvalidated and off-directory copies.
    static let subtree: String = {
        let berlin = "Berlin Lake|OH", canyon = "Canyon Lake|TX", flathead = "Flathead Lake|MT"
        let gunters = "Guntersville|AL", martin = "Lake Martin|AL"
        return """
        {
          "\(BrainPlatform.lakeKey(berlin))": {
            "clarity": \(clarity(berlin, status: "AVAILABLE", observedAt: "2026-11-10T14:00:00.250Z", freshUntil: "2026-11-10T20:00:00Z")),
            "waterTemp": \(waterTemp(berlin, status: "UNKNOWN", kind: "measured", observedAt: "2026-11-10T14:00:00Z", freshUntil: "2026-11-10T20:00:00Z")),
            "level": \(level(berlin, status: "AVAILABLE", observationTime: "2026-11-10T15:00:00Z", freshUntil: "2026-11-11T03:00:00Z")),
            "generationBinding": {"schema":"sector-customer-generation-binding-v1","lakeId":"\(berlin)"}
          },
          "\(BrainPlatform.lakeKey(canyon))": {
            "clarity": \(clarity(canyon, status: "AVAILABLE", observedAt: "2026-11-08T12:00:00Z", freshUntil: "2026-11-09T12:00:00Z")),
            "waterTemp": \(waterTemp(canyon, status: "ESTIMATE", kind: "modeled", observedAt: "2026-11-10T12:00:00Z", freshUntil: "2026-11-10T18:00:00Z")),
            "level": \(level(canyon, status: "ESTIMATE", observationTime: "2026-11-10T13:00:00Z", freshUntil: "2026-11-11T01:00:00Z", trend: "RISING"))
          },
          "\(BrainPlatform.lakeKey(flathead))": {
            "clarity": \(clarity(flathead, status: "ESTIMATE", observedAt: "2026-11-10T06:00:00Z", freshUntil: "2026-11-11T06:00:00Z"))
          },
          "\(BrainPlatform.lakeKey(gunters))": {
            "clarity": \(clarity(gunters, status: "AVAILABLE", observedAt: "2026-11-09T06:00:00Z", freshUntil: "2026-11-10T06:00:00Z")),
            "waterTemp": \(waterTemp(gunters, status: "UNKNOWN", kind: "measured", observedAt: "2026-11-10T14:00:00Z", freshUntil: "2026-11-10T20:00:00Z")),
            "level": \(level(gunters, status: "AVAILABLE", observationTime: "2026-11-10T15:00:00Z", freshUntil: "2026-11-11T03:00:00Z"))
          },
          "\(BrainPlatform.lakeKey(martin))": {
            "waterTemp": \(waterTemp(martin, status: "AVAILABLE", kind: "measured", observedAt: "2026-11-10T17:00:00Z", freshUntil: "2026-11-10T23:00:00Z"))
          },
          "Not_A_Lake_XX": {
            "clarity": \(clarity("Not A Lake|XX", status: "AVAILABLE", observedAt: "2026-11-10T14:00:00Z", freshUntil: "2026-11-10T20:00:00Z"))
          }
        }
        """
    }()

    static func goldenURL() -> URL {
        PhoneContractTests.root.appendingPathComponent("verification/fixtures/phone-contract/lakes-ready-v1.golden.json")
    }
    static let contractFile = "contracts/phone/lakes-ready-v1.json"

    func run(_ reader: BrainOutputReader?, config: LakesReadyConfig = on, level: LakeLevelEligibility = levelOn) async
        -> LakesReadyResponse? {
        await LakesReadyAPI.response(config: config, reader: reader, levelEligibility: level, now: Self.now)
    }

    // MARK: flag

    func testFlagIsOffByDefault() {
        XCTAssertFalse(LakesReadyConfig.fromEnvironment([:]).enabled)
        XCTAssertFalse(LakesReadyConfig.fromEnvironment([LakesReadyConfig.envKey: "true"]).enabled)
        XCTAssertTrue(LakesReadyConfig.fromEnvironment([LakesReadyConfig.envKey: "1"]).enabled)
    }

    func testFlagOffAnswersNothingAndReadsNothing() async {
        let r = Recording(["customer/lakes": Self.subtree])
        let out = await run(r, config: LakesReadyConfig(enabled: false))
        XCTAssertNil(out, "off: no response (the server registers no route: 404)")
        XCTAssertEqual(r.paths, [])
    }

    // MARK: no reader / no copies

    func testFlagOnWithNoReaderIsAnEmptyList() async throws {
        let got = await run(nil)

        let out = try XCTUnwrap(got)
        XCTAssertEqual(out, LakesReadyResponse(version: 1, generatedAt: "2026-11-10T15:30:00Z", lakes: []))
        let json = String(decoding: try SectorEngineAPI.makeEncoder().encode(out), as: UTF8.self)
        XCTAssertEqual(json, #"{"generatedAt":"2026-11-10T15:30:00Z","lakes":[],"version":1}"#)
    }

    func testNoCopiesAFailedReadOrJunkAreAnEmptyList() async throws {
        for reader: BrainOutputReader in [Recording([:]), Failing(), Recording(["customer/lakes": "[1,2]"]),
                                          Recording(["customer/lakes": "{\"k\":\"not an object\"}"])] {
            let got = await run(reader)

            let out = try XCTUnwrap(got)
            XCTAssertEqual(out.lakes, [])
            XCTAssertEqual(out.version, 1)
        }
    }

    // MARK: statuses and freshness

    func testMixedCopiesListOnlyReadyLayers() async throws {
        let got = await run(Recording(["customer/lakes": Self.subtree]))

        let out = try XCTUnwrap(got)
        XCTAssertEqual(out.lakes.map(\.lakeId), ["Berlin Lake|OH", "Canyon Lake|TX", "Flathead Lake|MT"])

        let berlin = out.lakes[0]
        XCTAssertEqual(berlin.name, "Berlin Lake")
        XCTAssertEqual(berlin.centroid, ReadyLakeCentroid(lat: 41.03, lon: -81.0))
        XCTAssertEqual(berlin.layers.clarity, ReadyLayer(status: "LIVE", asOf: "2026-11-10T14:00:00Z"), "fractional seconds dropped")
        XCTAssertNil(berlin.layers.waterTemp, "UNKNOWN is not ready")
        XCTAssertEqual(berlin.layers.level, ReadyLayer(status: "LIVE", asOf: "2026-11-10T15:00:00Z"))

        let canyon = out.lakes[1]
        XCTAssertNil(canyon.layers.clarity, "stale is not ready")
        XCTAssertEqual(canyon.layers.waterTemp, ReadyLayer(status: "ESTIMATE", asOf: "2026-11-10T12:00:00Z"))
        XCTAssertEqual(canyon.layers.level, ReadyLayer(status: "ESTIMATE", asOf: "2026-11-10T13:00:00Z"))

        XCTAssertEqual(out.lakes[2].layers, ReadyLakeLayers(clarity: ReadyLayer(status: "ESTIMATE", asOf: "2026-11-10T06:00:00Z"),
                                                            waterTemp: nil, level: nil))
        // Guntersville: stale clarity, UNKNOWN temp, and a fresh level that is not on the validated list → not listed.
        // Lake Martin: a time 90 min in the future → not listed. Not_A_Lake_XX: not in the directory → not listed.
    }

    func testLevelNeedsTheLakeLevelGates() async throws {
        let got = await run(Recording(["customer/lakes": Self.subtree]), level: Self.levelOff)

        let out = try XCTUnwrap(got)
        XCTAssertEqual(out.lakes.map(\.lakeId), ["Berlin Lake|OH", "Canyon Lake|TX", "Flathead Lake|MT"])
        XCTAssertTrue(out.lakes.allSatisfy { $0.layers.level == nil })
    }

    func testStatusMapping() {
        let now = Self.now
        XCTAssertEqual(LakesReadyAPI.layer("AVAILABLE", "2026-11-10T15:00:00Z", now: now)?.status, "LIVE")
        XCTAssertEqual(LakesReadyAPI.layer("ESTIMATE", "2026-11-10T15:00:00Z", now: now)?.status, "ESTIMATE")
        XCTAssertNil(LakesReadyAPI.layer("UNKNOWN", "2026-11-10T15:00:00Z", now: now))
        XCTAssertNil(LakesReadyAPI.layer("SOMETHING_NEW", "2026-11-10T15:00:00Z", now: now))
        XCTAssertNil(LakesReadyAPI.layer("AVAILABLE", nil, now: now))
        XCTAssertNil(LakesReadyAPI.layer("AVAILABLE", "yesterday", now: now))
        XCTAssertNil(LakesReadyAPI.layer("AVAILABLE", "2026-11-10T16:00:00Z", now: now), "beyond the 10 min future skew")
        XCTAssertEqual(LakesReadyAPI.layer("AVAILABLE", "2026-11-10T15:35:00Z", now: now)?.asOf, "2026-11-10T15:35:00Z")
        XCTAssertEqual(LakesReadyAPI.layer("AVAILABLE", "2026-11-10T10:00:00-05:00", now: now)?.asOf, "2026-11-10T15:00:00Z")
    }

    // MARK: path refusal

    func testReadsOnlyTheCustomerLakesSubtree() async throws {
        let r = Recording(["customer/lakes": Self.subtree])
        _ = await run(r)
        XCTAssertEqual(r.paths, ["customer/lakes"])
        XCTAssertTrue(r.paths.allSatisfy { $0.hasPrefix("customer/") && !$0.contains("states") && !$0.hasPrefix("brains") })
    }

    func testInternalStateIsNeverRead() async throws {
        // A reader holding only Brain INTERNAL state: nothing is listed, because nothing reads those paths.
        let r = Recording(["lakes/Berlin_Lake_OH/states": "{\"waterClarity\":{\"status\":\"AVAILABLE\"}}",
                           "brains/lake-brain/status": "{\"readiness\":\"BETA\"}"])
        let got = await run(r)

        let out = try XCTUnwrap(got)
        XCTAssertEqual(out.lakes, [])
        XCTAssertEqual(r.paths, ["customer/lakes"])
    }

    func testSnapshotRefusesEveryOtherPath() async throws {
        let snap = try XCTUnwrap(CustomerLakesSnapshot(subtree: Data(Self.subtree.utf8)))
        let k = BrainPlatform.lakeKey("Berlin Lake|OH")
        let clarity = try await snap.get("customer/lakes/\(k)/clarity")
        XCTAssertNotNil(clarity)
        let missing = try await snap.get("customer/lakes/\(BrainPlatform.lakeKey("Flathead Lake|MT"))/level")
        XCTAssertNil(missing, "an absent copy is nil, not an error")
        for bad in ["lakes/\(k)/states", "brains/lake-brain/status", "customer/wind/outlookModel",
                    "customer/lakes/\(k)/generationBinding", "customer/lakes/\(k)/clarity/centralFt", "customer/lakes//clarity",
                    "customer/lakes", "/customer/lakes/\(k)/clarity", "customer/lakes/\(k)/states"] {
            do { _ = try await snap.get(bad); XCTFail("read \(bad)") } catch {}
        }
    }

    func testRTDBReaderIsAskedForTheSubtreeOnly() async throws {
        final class URLs: @unchecked Sendable {
            private var _list: [String] = []; private let lock = NSLock()
            func add(_ s: String) { lock.lock(); _list.append(s); lock.unlock() }
            var list: [String] { lock.lock(); defer { lock.unlock() }; return _list }
        }
        let seen = URLs()
        let body = Data(Self.subtree.utf8)
        let reader = RTDBCustomerCopyReader(fetch: { url, _ in
            seen.add(url.absoluteString)
            return (200, body)
        }, token: { "t" })
        let got = await run(reader)

        let out = try XCTUnwrap(got)
        XCTAssertEqual(out.lakes.count, 3)
        XCTAssertEqual(seen.list, ["\(BrainPlatform.databaseURL)/customer/lakes.json"])
    }

    // MARK: cache

    final class Clock: @unchecked Sendable { var t = Date(timeIntervalSince1970: 0) }

    /// Fails while `failing` is set, then serves the subtree; counts reads.
    final class Flaky: BrainOutputReader, @unchecked Sendable {
        private let lock = NSLock()
        private var _reads = 0, _failing = true
        var reads: Int { lock.lock(); defer { lock.unlock() }; return _reads }
        func setFailing(_ v: Bool) { lock.lock(); _failing = v; lock.unlock() }
        private func next() -> Bool { lock.lock(); defer { lock.unlock() }; _reads += 1; return _failing }
        func get(_ path: String) async throws -> Data? {
            if next() { throw ReadError() }
            return Data(LakesReadyAPITests.subtree.utf8)
        }
    }

    func testSnapshotCacheReadsOncePerTTL() async throws {
        let clock = Clock()
        let base = Recording(["customer/lakes": Self.subtree])
        let cache = LakesReadySnapshotCache(reader: base, ttl: 60, clock: { clock.t })
        let a = await LakesReadyAPI.response(config: Self.on, cache: cache, levelEligibility: Self.levelOn, now: Self.now)
        let b = await LakesReadyAPI.response(config: Self.on, cache: cache, levelEligibility: Self.levelOn, now: Self.now)
        XCTAssertEqual(a?.lakes.count, 3)
        XCTAssertEqual(a, b)
        XCTAssertEqual(base.paths, ["customer/lakes"])
        clock.t = clock.t.addingTimeInterval(61)
        _ = await cache.snapshot()
        XCTAssertEqual(base.paths.count, 2)
    }

    func testSnapshotCacheDoesNotKeepAFailedRead() async throws {
        let flaky = Flaky()
        let cache = LakesReadySnapshotCache(reader: flaky, ttl: 60, clock: { Date(timeIntervalSince1970: 0) })
        let failed = await LakesReadyAPI.response(config: Self.on, cache: cache, levelEligibility: Self.levelOn, now: Self.now)
        XCTAssertEqual(failed?.lakes, [], "a failed read is an empty list")
        flaky.setFailing(false)
        let ok = await LakesReadyAPI.response(config: Self.on, cache: cache, levelEligibility: Self.levelOn, now: Self.now)
        XCTAssertEqual(ok?.lakes.count, 3, "the next request reads again within the TTL")
        XCTAssertEqual(flaky.reads, 2)
    }

    func testFlagOffWithACacheReadsNothing() async {
        let base = Recording(["customer/lakes": Self.subtree])
        let cache = LakesReadySnapshotCache(reader: base)
        let out = await LakesReadyAPI.response(config: LakesReadyConfig(enabled: false), cache: cache, now: Self.now)
        XCTAssertNil(out)
        XCTAssertEqual(base.paths, [])
    }

    // MARK: lossy keys and junk copies

    func testACopyUnderADirectoryKeyWithAnotherLakeIdIsNotListed() async throws {
        // Same key as "Berlin Lake|OH" (keys are lossy), different stored lakeId: the readers refuse it.
        let key = BrainPlatform.lakeKey("Berlin Lake|OH")
        XCTAssertEqual(BrainPlatform.lakeKey("Berlin Lake OH"), key)
        let tree = """
        {"\(key)": {"clarity": \(Self.clarity("Berlin Lake OH", status: "AVAILABLE", observedAt: "2026-11-10T14:00:00Z",
                                                  freshUntil: "2026-11-10T20:00:00Z"))}}
        """
        let got = await run(Recording(["customer/lakes": tree]))
        XCTAssertEqual(try XCTUnwrap(got).lakes, [])
    }

    func testNonObjectCopiesAreIgnored() async throws {
        let k = BrainPlatform.lakeKey("Flathead Lake|MT")
        let tree = """
        {"\(k)": {"clarity": 5, "waterTemp": "x", "level": [1], "other": {}}, "\(BrainPlatform.lakeKey("Berlin Lake|OH"))": 7}
        """
        let got = await run(Recording(["customer/lakes": tree]))
        XCTAssertEqual(try XCTUnwrap(got).lakes, [])
    }

    // MARK: contract and golden

    func testGoldenMatchesTheEngineOutput() async throws {
        let got = await run(Recording(["customer/lakes": Self.subtree]))

        let out = try XCTUnwrap(got)
        let produced = try JSONSerialization.jsonObject(with: SectorEngineAPI.makeEncoder().encode(out))
        let golden = try JSONSerialization.jsonObject(with: Data(contentsOf: Self.goldenURL()))
        XCTAssertNil(PhoneContractTests.difference(golden, produced), "regenerate the golden from this scenario if the change is intended")
    }

    func testGoldenAndOutputMeetTheContract() async throws {
        let fields = try PhoneContractTests.loadContract(Self.contractFile)
        let golden = try JSONSerialization.jsonObject(with: Data(contentsOf: Self.goldenURL()))
        XCTAssertEqual(PhoneContractTests.validate(golden, fields), [])
        for r: BrainOutputReader? in [nil, Recording(["customer/lakes": Self.subtree])] {
            let got = await run(r)

            let out = try XCTUnwrap(got)
            let doc = try JSONSerialization.jsonObject(with: SectorEngineAPI.makeEncoder().encode(out))
            XCTAssertEqual(PhoneContractTests.validate(doc, fields), [])
        }
    }

    /// Every contract path has evidence in the golden, and the Engine emits nothing the contract does not describe.
    func testGoldenExercisesEveryContractPathAndNothingElse() throws {
        let fields = try PhoneContractTests.loadContract(Self.contractFile)
        var seen = Set<String>()
        func walk(_ v: Any, _ path: String) {
            if v is NSNull { return }
            if !path.isEmpty { seen.insert(path) }
            if let o = v as? [String: Any] { for (k, c) in o { walk(c, path.isEmpty ? k : "\(path).\(k)") } }
            else if let a = v as? [Any] { for e in a { walk(e, path + "[]") } }
        }
        walk(try JSONSerialization.jsonObject(with: Data(contentsOf: Self.goldenURL())), "")
        seen.remove("lakes[]")
        XCTAssertEqual(seen, Set(fields.keys))
    }

    func testValidatorCatchesBreakingChanges() throws {
        let fields = try PhoneContractTests.loadContract(Self.contractFile)
        let base = try JSONSerialization.jsonObject(with: Data(contentsOf: Self.goldenURL())) as! [String: Any]
        func lake0(_ mutate: (inout [String: Any]) -> Void) -> [String: Any] {
            var doc = base, lakes = base["lakes"] as! [[String: Any]]
            mutate(&lakes[0]); doc["lakes"] = lakes
            return doc
        }
        var v = base; v["version"] = "1"
        XCTAssertFalse(PhoneContractTests.validate(v, fields).isEmpty)
        var g = base; g["generatedAt"] = "2026-11-10T15:30:00.000Z"
        XCTAssertFalse(PhoneContractTests.validate(g, fields).isEmpty)
        var n = base; n["lakes"] = NSNull()
        XCTAssertFalse(PhoneContractTests.validate(n, fields).isEmpty)
        XCTAssertFalse(PhoneContractTests.validate(lake0 { $0.removeValue(forKey: "centroid") }, fields).isEmpty)
        XCTAssertFalse(PhoneContractTests.validate(lake0 { $0["centroid"] = ["lat": 1.0] }, fields).isEmpty)
        XCTAssertFalse(PhoneContractTests.validate(lake0 { $0["layers"] = ["clarity": ["status": "LIVE"]] }, fields).isEmpty)
        XCTAssertTrue(PhoneContractTests.validate(lake0 { $0["layers"] = [String: Any]() }, fields).isEmpty, "every layer is optional")
        XCTAssertTrue(PhoneContractTests.validate(lake0 { $0["newField"] = 1 }, fields).isEmpty, "additive field must be allowed")
    }
}
