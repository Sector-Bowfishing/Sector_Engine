//
//  WaterTemperatureBrainTests.swift
//  SectorEngineTests
//
//  The water-temp Brain is an integration layer: these tests pin that it
//  publishes exactly what production resolves (no new science), keeps unknowns
//  absent, keeps readiness / validation / health apart, writes only its own
//  RTDB keys, and that a store failure stays inside the job.
//

import XCTest
#if canImport(CoreLocation)
import CoreLocation
#endif
@testable import SectorEngine

final class WaterTemperatureBrainTests: XCTestCase {

    private let now = ISO8601DateFormatter().date(from: "2026-07-15T03:00:00Z")!   // 22:00 CDT Jul 14
    private var gunt: DirectoryLake { LakeDirectory.all.first { $0.id == "Guntersville|AL" }! }
    private var sensorLake: DirectoryLake { LakeDirectory.all.first { $0.tempSensor?.hasPrefix("usgs:") == true }! }

    private func reading(ageHours: Double, provider: String = "USGS") -> WaterLevelReading {
        var r = WaterLevelReading(siteCode: "02193900", siteName: "THURMOND", parameterCode: "00010",
                                  parameterName: "Temperature, water", value: 30.0, unit: "deg C",
                                  dateTime: now.addingTimeInterval(-ageHours * 3600),
                                  latitude: 33.66, longitude: -82.2, trend: .rising, change: 0.6)
        r.provider = provider
        return r
    }
    private func day(_ d: String, _ f: Double) -> WaterTempDay {
        WaterTempDay(date: ISO8601DateFormatter().date(from: d + "T12:00:00Z")!, waterF: f, airF: f - 5, localDate: d)
    }
    private func model() -> WaterTempModel {
        var m = WaterTempModel(currentF: 80.0, series: [day("2026-07-13", 79.4), day("2026-07-14", 80.0),
                                                        day("2026-07-15", 80.5), day("2026-07-16", 81.0)])
        m.currentLocalDate = "2026-07-14"; m.timeZoneIdentifier = "America/Chicago"
        return m
    }
    private func state(_ lake: DirectoryLake, measurement: WaterLevelReading?, model: WaterTempModel?, origin: String? = "lakeSensor") -> WaterTemperatureBrain.State {
        let x = WaterTemperatureBrain.LakeInputs(lake: lake, measurement: measurement, measurementOrigin: measurement == nil ? nil : origin,
                                                 model: model, modelFetchFailed: model == nil)
        let r = WaterTemperatureResolver.resolve(measurement: measurement, model: model, at: now)
        return WaterTemperatureBrain.state(from: x, resolved: r, now: now, processingVersion: "test")
    }

    // MARK: lake keys (canonical registry, no second scheme)

    func testLakeKeyMatchesEngineStorageSlug() {
        XCTAssertEqual(BrainPlatform.lakeKey("Guntersville|AL"), "Guntersville_AL")
        XCTAssertEqual(BrainPlatform.lakeKey("Eufaula / W.F. George|AL"), "Eufaula_W_F_George_AL")
        XCTAssertEqual(BrainPlatform.lakeKey("Lake St. Clair|MI"), "Lake_St_Clair_MI")
    }

    func testEveryDirectoryLakeHasAUniqueRTDBKey() {
        XCTAssertEqual(LakeDirectory.all.count, 621)
        XCTAssertTrue(BrainPlatform.keyCollisions(LakeDirectory.all.map(\.id)).isEmpty)
        for l in LakeDirectory.all {
            XCTAssertNil(BrainPlatform.lakeKey(l.id).rangeOfCharacter(from: CharacterSet(charactersIn: ".$#[]/")), l.id)
        }
    }

    // MARK: state = production's resolved state, verbatim

    func testModeledStateMirrorsResolverAndKeepsUnknownsAbsent() throws {
        let s = state(gunt, measurement: nil, model: model())
        XCTAssertEqual(s.kind, "modeled")
        XCTAssertEqual(s.observationType, "MODELED")
        XCTAssertEqual(s.currentTempF, 80.0)
        XCTAssertEqual(s.lakeLocalDate, "2026-07-14")
        XCTAssertEqual(s.trend24hF, 0.6)
        XCTAssertEqual(s.trendBasis, "model:dailyChange(lakeLocal)")
        XCTAssertNil(s.sensorTrend)
        XCTAssertNil(s.lastObservationAt)
        XCTAssertNil(s.depthM)
        XCTAssertNil(s.measuredMinusModelF)
        XCTAssertEqual(s.forecast?.map(\.at), ["2026-07-15", "2026-07-16"])
        XCTAssertEqual(s.provenance.readiness, "BETA")
        XCTAssertEqual(s.provenance.modelVersion, WaterTemperatureResolver.modelVersion)
        // unknown fields are ABSENT in the JSON (RTDB null), never a default
        let json = String(decoding: try BrainJSON.encode(s), as: UTF8.self)
        for key in ["depthM", "lastObservationAt", "sensorTrend", "measuredMinusModelF", "confidence"] {
            XCTAssertFalse(json.contains("\"\(key)\""), key)
        }
    }

    func testMeasuredStateIsTheMeasurementAndTheForecastIsGaugeAnchoredLikeProduction() {
        let s = state(sensorLake, measurement: reading(ageHours: 2), model: model())
        XCTAssertEqual(s.kind, "measured")
        XCTAssertEqual(s.observationType, "OBSERVED")
        XCTAssertEqual(s.currentTempF, 86.0)                     // 30 °C
        XCTAssertEqual(s.measuredMinusModelF, 6.0)
        XCTAssertEqual(s.modelCurrentF, 80.0)
        XCTAssertEqual(s.forecast?.first?.tempF, 86.5)           // 80.5 + (86 − 80): ConditionsForecast gaugeAnchorF
        XCTAssertEqual(s.sensorTrend, "rising")
        XCTAssertEqual(s.sourceAgeHours, 2.0)
        XCTAssertEqual(s.provenance.readiness, "PRODUCTION")
        XCTAssertTrue(s.provenance.qualityFlags?.contains("forecastGaugeAnchored") == true)
        XCTAssertFalse(s.stale)
    }

    func testStaleSensorFallsBackToModelAndIsFlaggedNotHidden() {
        let s = state(sensorLake, measurement: reading(ageHours: 9), model: model())
        XCTAssertEqual(s.kind, "modeled")
        XCTAssertEqual(s.currentTempF, 80.0)
        XCTAssertTrue(s.evidenceStale)
        XCTAssertTrue(s.stale)
        XCTAssertTrue(s.provenance.qualityFlags?.contains { $0.hasPrefix("measurementStale") } == true)
        XCTAssertTrue(s.provenance.qualityFlags?.contains("lakeSensorNoFreshReading") == true)
    }

    func testNothingAvailableIsUnknownNotZero() {
        let s = state(gunt, measurement: nil, model: nil)
        XCTAssertEqual(s.kind, "unavailable")
        XCTAssertEqual(s.observationType, "UNKNOWN")
        XCTAssertNil(s.currentTempF)
        XCTAssertNil(s.forecast)
        XCTAssertNil(s.trend24hF)
        XCTAssertTrue(s.provenance.qualityFlags?.contains("modelUnavailable") == true)
    }

    // MARK: readiness ≠ validation ≠ health

    func testReadinessIsEvidenceClassOnly() {
        let counts = Dictionary(grouping: LakeDirectory.all, by: { WaterTemperatureBrain.readiness(for: $0).rawValue }).mapValues(\.count)
        XCTAssertEqual(counts["PRODUCTION"], LakeDirectory.all.filter { $0.tempSensor != nil }.count)
        XCTAssertEqual(counts["PRODUCTION", default: 0] + counts["BETA", default: 0], 621)
        // a protected development lake is BETA (served) while its VALIDATION says insufficient truth
        XCTAssertEqual(WaterTemperatureBrain.readiness(for: gunt), .beta)
        let v = WaterTemperatureBrain.protectedLakeValidation(WaterTemperatureBrain.protectedLakes.first { $0.lakeId == "Wilson|AL" }!)
        XCTAssertEqual(v.status, "INSUFFICIENT_TRUTH")
        XCTAssertNil(v.metrics["rmseF"]!)                         // not scored → unknown, not a number
    }

    func testProtectedLakesAreCanonicalDirectoryIds() {
        for p in WaterTemperatureBrain.protectedLakes {
            XCTAssertTrue(LakeDirectory.all.contains { $0.id == p.lakeId }, p.lakeId)
        }
    }

    func testHealthRuleIsRuntimeOnly() {
        XCTAssertEqual(WaterTemperatureBrainRunner.health(lakes: 621, unavailable: 0, modelFailures: 3, writeFailed: false), "HEALTHY")
        XCTAssertEqual(WaterTemperatureBrainRunner.health(lakes: 621, unavailable: 40, modelFailures: 40, writeFailed: false), "WARNING")
        XCTAssertEqual(WaterTemperatureBrainRunner.health(lakes: 621, unavailable: 200, modelFailures: 200, writeFailed: false), "DEGRADED")
        XCTAssertEqual(WaterTemperatureBrainRunner.health(lakes: 621, unavailable: 0, modelFailures: 0, writeFailed: true), "FAILED")
    }

    // MARK: registry: candidate exposed, never promoted

    func testRegistryExposesResearchCandidateWithoutPromotingIt() {
        var r = WaterTemperatureBrainRunResult()
        r.health = "HEALTHY"; r.readinessCounts = ["BETA": 592, "PRODUCTION": 29]
        let e = WaterTemperatureBrainRunner.registryEntry(result: r, now: now, options: .init(), fullFleet: true, lastError: nil)
        XCTAssertEqual(e.brainId, "water-temp")
        XCTAssertEqual(e.activeProductionModel?.modelVersion, WaterTemperatureResolver.modelVersion)
        XCTAssertEqual(e.activeProductionModel?.assimilation, "none")
        XCTAssertEqual(e.researchCandidate?.certified, false)
        XCTAssertEqual(e.versions?.first?.status, "CURRENT")
        XCTAssertEqual(e.versions?.first?.version, WaterTemperatureResolver.modelVersion)
        XCTAssertEqual(e.versions?.filter { $0.status == "CURRENT" }.count, 1)
        XCTAssertEqual(e.staleAfterHours, 6)
    }

    func testActivityOnFirstRegistrationAndOnHealthChange() {
        var r = WaterTemperatureBrainRunResult(); r.health = "HEALTHY"
        let cur = WaterTemperatureBrainRunner.registryEntry(result: r, now: now, options: .init(), fullFleet: true, lastError: nil)
        XCTAssertEqual(WaterTemperatureBrainRunner.activity(previous: nil, current: cur, now: now).map(\.kind), ["brain-registered"])
        var prev = cur; prev.health = "DEGRADED"
        XCTAssertEqual(WaterTemperatureBrainRunner.activity(previous: prev, current: cur, now: now).map(\.kind), ["health-change"])
        XCTAssertTrue(WaterTemperatureBrainRunner.activity(previous: cur, current: cur, now: now).isEmpty)
    }

    func testEventKeysSortByTime() {
        let a = BrainPlatform.eventKey(now, suffix: "x"), b = BrainPlatform.eventKey(now.addingTimeInterval(0.002), suffix: "a")
        XCTAssertLessThan(a, b)
    }

    // MARK: writes: only water-temp keys; one atomic update per chunk; failure stays in the job

    final class RecordingStore: BrainStore, @unchecked Sendable {
        var updates: [[String: Data]] = []
        var fail = false
        func update(_ paths: [String: Data]) async throws {
            if fail { throw BrainStoreError(description: "boom") }
            updates.append(paths)
        }
        func get(_ path: String) async throws -> Data? { nil }
        func delete(_ path: String) async throws {}
        func shallowKeys(_ path: String) async throws -> [String] { [] }
    }

    func testMultiPathBodyIsValidJSON() throws {
        let body = try BrainJSON.multiPathBody(["a/b": Data("1".utf8), "c": Data("{\"x\":null}".utf8)])
        let obj = try JSONSerialization.jsonObject(with: body) as? [String: Any]
        XCTAssertEqual(obj?.keys.sorted(), ["a/b", "c"])
    }

    func testPartialRunWritesOnlyWaterTempOwnedPathsAndNoFleetRegistry() async throws {
        let store = RecordingStore()
        var o = WaterTemperatureBrainRunOptions(); o.lakeIds = ["NoSuchLake|ZZ"]       // offline: no lakes match
        let r = await WaterTemperatureBrainRunner.run(store: store, options: o, now: now)
        XCTAssertEqual(r.lakes, 0)
        let paths = store.updates.flatMap(\.keys)
        XCTAssertFalse(paths.contains { $0.hasPrefix("brains/") }, "partial runs never overwrite the fleet registry")
        for p in paths {
            let ok = p.hasPrefix("validation/water-temp") || p.hasSuffix("/validation/water-temp")
                || p.contains("/waterTemp") || p.contains("/water-temp") || p.hasSuffix("/lakeId")
                || p.hasSuffix("/generatedAt") || p.hasSuffix("/snapshotVersion") || p.hasSuffix("/lastUpdatedAt")
                || p.hasSuffix("/waterTemperature")
            XCTAssertTrue(ok, "unexpected path \(p)")
        }
    }

    func testStoreFailureIsReportedNotThrown() async {
        let store = RecordingStore(); store.fail = true
        var o = WaterTemperatureBrainRunOptions(); o.lakeIds = ["NoSuchLake|ZZ"]
        let r = await WaterTemperatureBrainRunner.run(store: store, options: o, now: now)
        XCTAssertEqual(r.health, "FAILED")
        XCTAssertNotNil(r.writeError)
        XCTAssertFalse(r.ok)
    }
}
