//
//  EnvironmentProvenanceTests.swift
//  SectorEngineTests
//
//  The provenance record is only safe to add if it cannot move a score. These
//  tests hold that line: `build` and `buildDetailed().input` must be identical
//  for the same arguments, including the awkward cases where a reading is
//  dropped for age or distance.
//

import XCTest
#if canImport(CoreLocation)
import CoreLocation
#endif
@testable import SectorEngine

final class EnvironmentProvenanceTests: XCTestCase {

    private let coord = CLLocationCoordinate2D(latitude: 34.42, longitude: -86.29)
    private let now = Date(timeIntervalSince1970: 1_790_000_000)

    private func weather(_ at: Date) -> WeatherReading {
        WeatherReading(temperature: 74, conditionDescription: "Clear",
                       conditionSymbol: "moon.stars", windSpeed: 6, windDirection: 180,
                       precipitation: 0, recentRainfall: 0.2, humidity: 70,
                       pressure: 1016, pressureTrend: .steady, pressureChange: 0.3,
                       cloudCover: 30, weatherCode: 1, time: at)
    }

    private func reading(_ code: String, _ param: String, value: Double,
                         ageHours: Double, miles: Double?) -> WaterLevelReading {
        WaterLevelReading(siteCode: code, siteName: "Test \(code)",
                          parameterCode: param, parameterName: param,
                          value: value, unit: "u",
                          dateTime: now.addingTimeInterval(-ageHours * 3600),
                          latitude: 34.4, longitude: -86.3,
                          trend: .steady, change: 0,
                          history: [], distanceMiles: miles)
    }

    // MARK: Parity — the whole point

    func testBuildMatchesBuildDetailedExactly() {
        let cases: [(String, WaterLevelReading?, WaterLevelReading?)] = [
            ("both fresh and near",
             reading("A", "00010", value: 24, ageHours: 1, miles: 2),
             reading("B", "63680", value: 12, ageHours: 1, miles: 2)),
            ("temp stale",
             reading("A", "00010", value: 24, ageHours: 40, miles: 2),
             reading("B", "63680", value: 12, ageHours: 1, miles: 2)),
            ("turbidity too far",
             reading("A", "00010", value: 24, ageHours: 1, miles: 2),
             reading("B", "63680", value: 12, ageHours: 1, miles: 99)),
            ("both missing", nil, nil),
        ]
        for (label, temp, turb) in cases {
            let plain = ConditionsInputBuilder.build(
                coordinate: coord, date: now, weather: weather(now),
                water: reading("W", "00065", value: 594, ageHours: 0.5, miles: 1),
                discharge: reading("D", "00060", value: 12000, ageHours: 0.5, miles: 1),
                waterTempC: temp, modeledWaterTempF: 76, turbidity: turb,
                rainWatershed72hIn: 0.3)
            let detailed = ConditionsInputBuilder.buildDetailed(
                coordinate: coord, date: now, weather: weather(now),
                water: reading("W", "00065", value: 594, ageHours: 0.5, miles: 1),
                discharge: reading("D", "00060", value: 12000, ageHours: 0.5, miles: 1),
                waterTempC: temp, modeledWaterTempF: 76, turbidity: turb,
                rainWatershed72hIn: 0.3).input
            XCTAssertEqual(plain, detailed, "input diverged for: \(label)")

            let a = ConditionsAggregator.evaluate(plain, config: .default)
            let b = ConditionsAggregator.evaluate(detailed, config: .default)
            XCTAssertEqual(a.score, b.score, "score diverged for: \(label)")
            XCTAssertEqual(a.confidence, b.confidence, "confidence diverged for: \(label)")
        }
    }

    // MARK: The record itself

    func testStaleReadingIsRecordedAsTooOldNotMissing() {
        let p = ConditionsInputBuilder.buildDetailed(
            coordinate: coord, date: now, weather: weather(now),
            water: nil, discharge: nil,
            waterTempC: reading("A", "00010", value: 24, ageHours: 40, miles: 1),
            modeledWaterTempF: 76, turbidity: nil).provenance

        // The gage entry is replaced by the layer that actually produced the
        // number — but the fact that a stale gage existed must still be visible
        // somewhere, so the water-temp entry names the model, not the gage.
        guard let entry = p["waterTempF"] else { return XCTFail("no waterTempF entry") }
        if case .modelled(let name) = entry.origin {
            XCTAssertTrue(name.contains("thermalLag"))
        } else {
            XCTFail("expected modelled origin, got \(entry.origin)")
        }
        XCTAssertEqual(entry.coverage, EnvironmentProvenance.Coverage.lakeWide)
    }

    func testDistantTurbidityGageIsRecordedAsTooFar() {
        let p = ConditionsInputBuilder.buildDetailed(
            coordinate: coord, date: now, weather: weather(now),
            water: nil, discharge: nil, waterTempC: nil, modeledWaterTempF: 76,
            turbidity: reading("B", "63680", value: 12, ageHours: 1, miles: 99)).provenance

        guard let entry = p["turbidityFNU"] else { return XCTFail("no turbidityFNU entry") }
        guard case .unavailable(.tooFar(let miles)) = entry.origin else {
            return XCTFail("expected tooFar, got \(entry.origin)")
        }
        XCTAssertEqual(miles, 99, accuracy: 0.001)
        XCTAssertFalse(entry.isAvailable)
    }

    func testLiveGageWinsAndIsRecordedAsMeasured() {
        let p = ConditionsInputBuilder.buildDetailed(
            coordinate: coord, date: now, weather: weather(now),
            water: nil, discharge: nil,
            waterTempC: reading("A", "00010", value: 24, ageHours: 0.2, miles: 1),
            modeledWaterTempF: 76, turbidity: nil).provenance

        guard let entry = p["waterTempF"] else { return XCTFail("no waterTempF entry") }
        guard case .measured(let site) = entry.origin else {
            return XCTFail("expected measured, got \(entry.origin)")
        }
        XCTAssertEqual(site, "A")
        XCTAssertTrue(entry.isMeasured)
        XCTAssertGreaterThan(entry.quality, 0.7, "fresh and near should score high")
    }

    func testMissingSourceIsDistinctFromFailedFetch() {
        let p = ConditionsInputBuilder.buildDetailed(
            coordinate: coord, date: now, weather: nil,
            water: nil, discharge: nil, waterTempC: nil, turbidity: nil).provenance

        XCTAssertEqual(p["stageFt"]?.origin, EnvironmentProvenance.Origin.unavailable(.noSourceExists))
        XCTAssertEqual(p["weather"]?.origin, EnvironmentProvenance.Origin.unavailable(.fetchFailed))
        XCTAssertFalse(p.unavailable.isEmpty)
        XCTAssertEqual(p.measuredCount, 0)
    }

    // MARK: Thermal constant

    func testThermalLagDefaultIsUnchanged() {
        // The per-arm extension varies k. The Conditions default must not move.
        XCTAssertEqual(WaterTemperatureService.defaultK, 0.20, accuracy: 1e-12)
    }
}

/// One set of band cut-points, not two. These were defined independently in
/// `ConditionsBand` and `NightScore.rating` and kept in step by hand.
final class BandConsolidationTests: XCTestCase {
    func testBandAndRatingAgreeAtEveryScore() {
        for score in 0...100 {
            let band = ConditionsBand(score: score)
            XCTAssertEqual(band.rawValue, band.rating.rawValue,
                           "band and rating disagree at \(score)")
        }
    }

    func testCutPointsAreWhereTheSpecSaysTheyAre() {
        XCTAssertEqual(ConditionsBand(score: 80), .prime)
        XCTAssertEqual(ConditionsBand(score: 79), .good)
        XCTAssertEqual(ConditionsBand(score: 65), .good)
        XCTAssertEqual(ConditionsBand(score: 64), .fair)
        XCTAssertEqual(ConditionsBand(score: 50), .fair)
        XCTAssertEqual(ConditionsBand(score: 49), .poor)
    }
}

/// The lake-scoped snapshot's keying — the thing that turns ~53,000 upstream
/// reads into 9.
final class LakeEnvironmentKeyingTests: XCTestCase {

    private func lake(_ id: String) -> DirectoryLake? {
        LakeDirectory.all.first { $0.id == id }
    }

    func testEveryPointOnALakeSharesOneKey() {
        guard let g = lake("Guntersville|AL") else { return XCTFail("directory lacks Guntersville") }
        // Real segment anchors: the dam, mid-lake, and the upper end.
        let anchors = [(34.4234, -86.3923), (34.4391, -86.2185),
                       (34.6459, -85.9575), (34.8912, -85.6833)]
        let keys = Set(anchors.map {
            LakeEnvironmentProvider.cacheKey(lake: g, latitude: $0.0, longitude: $0.1)
        })
        XCTAssertEqual(keys.count, 1, "one lake must mean one acquisition, got \(keys)")
        XCTAssertEqual(keys.first, "lake:Guntersville|AL")
    }

    func testOffLakeFallsBackToACoordinateKey() {
        let a = LakeEnvironmentProvider.cacheKey(lake: nil, latitude: 34.73, longitude: -85.98)
        let b = LakeEnvironmentProvider.cacheKey(lake: nil, latitude: 34.74, longitude: -85.98)
        XCTAssertTrue(a.hasPrefix("pt:"))
        XCTAssertNotEqual(a, b, "distinct river spots must not collide")
    }

    func testSamplePointsInTheSameCellCollapse() {
        // Two points 200 m apart return the same model grid values; fetching
        // both proves nothing and costs a round trip.
        let deduped = LakeEnvironmentProvider.dedupe([
            (latitude: 34.4200, longitude: -86.2900),
            (latitude: 34.4218, longitude: -86.2900),   // ~200 m north
            (latitude: 34.6459, longitude: -85.9575),   // genuinely elsewhere
        ])
        XCTAssertEqual(deduped.count, 2)
    }

    func testNearestSampleWins() {
        let input = ConditionsInput(
            date: Date(), latitude: 0, longitude: 0, region: .south,
            windMph: 0, windDirDeg: 0, airTempF: 60, cloudPct: 0, humidityPct: 50,
            pressureInHg: 30, pressureTrend: .steady, pressureChange12hInHg: 0,
            weatherCode: 0, cityGlowFactor: 0.3)
        let snap = LakeEnvironmentSnapshot(
            lakeId: "Guntersville|AL", lakeName: "Guntersville", cacheKey: "lake:Guntersville|AL",
            samples: [
                .init(latitude: 34.42, longitude: -86.39, input: input, provenance: .init()),
                .init(latitude: 34.89, longitude: -85.68, input: input, provenance: .init()),
            ],
            fetchedAt: Date(), ttl: 300)

        let lower = snap.sample(nearLatitude: 34.44, longitude: -86.35)
        XCTAssertEqual(lower?.latitude ?? 0, 34.42, accuracy: 0.001)
        let upper = snap.sample(nearLatitude: 34.86, longitude: -85.70)
        XCTAssertEqual(upper?.latitude ?? 0, 34.89, accuracy: 0.001)
    }

    func testFreshnessRespectsTTL() {
        let now = Date()
        let input = ConditionsInput(
            date: now, latitude: 0, longitude: 0, region: .south,
            windMph: 0, windDirDeg: 0, airTempF: 60, cloudPct: 0, humidityPct: 50,
            pressureInHg: 30, pressureTrend: .steady, pressureChange12hInHg: 0,
            weatherCode: 0, cityGlowFactor: 0.3)
        let snap = LakeEnvironmentSnapshot(
            lakeId: nil, lakeName: nil, cacheKey: "k",
            samples: [.init(latitude: 0, longitude: 0, input: input, provenance: .init())],
            fetchedAt: now, ttl: 300)
        XCTAssertTrue(snap.isFresh(at: now.addingTimeInterval(299)))
        XCTAssertFalse(snap.isFresh(at: now.addingTimeInterval(301)))
    }
}

/// A gage has to be describing the water you are standing in.
///
/// Guntersville's nearest discharge sensor is Paint Rock River, 14 miles off on
/// another watershed, reading about 9 cfs. Without a cap the engine presented
/// that as the flow of a 67,900-acre reservoir and the Current factor scored it.
final class DischargeProximityTests: XCTestCase {

    private let coord = CLLocationCoordinate2D(latitude: 34.42, longitude: -86.29)
    private let now = Date(timeIntervalSince1970: 1_790_000_000)

    private func reading(miles: Double) -> WaterLevelReading {
        WaterLevelReading(siteCode: "03574500", siteName: "PAINT ROCK RIVER",
                          parameterCode: "00060", parameterName: "Discharge",
                          value: 9.33, unit: "ft^3/s",
                          dateTime: now.addingTimeInterval(-600),
                          latitude: 34.62, longitude: -86.31,
                          trend: .steady, change: 0, history: [], distanceMiles: miles)
    }

    private func build(_ r: WaterLevelReading?) -> (ConditionsInput, EnvironmentProvenance) {
        let out = ConditionsInputBuilder.buildDetailed(
            coordinate: coord, date: now,
            weather: WeatherReading(temperature: 74, conditionDescription: "Clear",
                conditionSymbol: "moon", windSpeed: 6, windDirection: 180,
                precipitation: 0, recentRainfall: 0, humidity: 70, pressure: 1016,
                pressureTrend: .steady, pressureChange: 0, cloudCover: 30,
                weatherCode: 1, time: now),
            water: nil, discharge: r, waterTempC: nil, modeledWaterTempF: 76,
            turbidity: nil)
        return (out.input, out.provenance)
    }

    func testAnOffWatershedGageIsDroppedAndSaysWhy() {
        let (input, prov) = build(reading(miles: 14.1))
        XCTAssertNil(input.dischargeCfs, "a creek 14 miles away is not the lake's flow")
        guard case .unavailable(.tooFar(let miles))? = prov["dischargeCfs"]?.origin else {
            return XCTFail("expected tooFar, got \(String(describing: prov["dischargeCfs"]?.origin))")
        }
        XCTAssertEqual(miles, 14.1, accuracy: 0.001)
    }

    func testANearbyGageStillCounts() {
        let (input, prov) = build(reading(miles: 3.0))
        XCTAssertEqual(input.dischargeCfs ?? 0, 9.33, accuracy: 0.001)
        XCTAssertTrue(prov["dischargeCfs"]?.isMeasured ?? false)
    }

    /// The cap sits between turbidity's and water temperature's, because all
    /// three answer the same question.
    func testTheCapIsInTheSameFamilyAsTheOthers() {
        XCTAssertGreaterThan(ConditionsInputBuilder.maxDischargeDistanceMiles,
                             ConditionsInputBuilder.maxTurbidityDistanceMiles)
        XCTAssertLessThan(ConditionsInputBuilder.maxDischargeDistanceMiles,
                          ConditionsInputBuilder.maxWaterTempDistanceMiles)
    }

    /// Dropping the reading must leave the factor dormant, not zeroed — a zero
    /// would read as slack water, which is a claim.
    func testDroppedDischargeIsAbsentNotZero() {
        let (input, _) = build(reading(miles: 40))
        XCTAssertNil(input.dischargeCfs)
        XCTAssertNil(input.dischargeTrend12hCfs)
    }
}
