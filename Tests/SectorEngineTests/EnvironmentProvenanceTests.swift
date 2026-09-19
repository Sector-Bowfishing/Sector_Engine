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
