//
//  WaterTempStage2ETests.swift
//  SectorEngineTests
//
//  Stage 2E production correctness: ONE resolved water-temperature state that
//  the score, the response and the forecast all take (shown == scored), and a
//  "today" that is the LAKE's calendar day, never the server's. Science frozen:
//  these tests check selection and dates, not temperature accuracy.
//

import XCTest
#if canImport(CoreLocation)
import CoreLocation
#endif
@testable import SectorEngine

final class WaterTempStage2ETests: XCTestCase {

    private let iso = ISO8601DateFormatter()
    private func t(_ s: String) -> Date { iso.date(from: s)! }
    private let chicago = TimeZone(identifier: "America/Chicago")!
    private let now = ISO8601DateFormatter().date(from: "2026-07-15T03:00:00Z")!   // 22:00 CDT Jul 14
    private let coord = CLLocationCoordinate2D(latitude: 33.5, longitude: -80.4)

    private func reading(ageHours: Double, miles: Double? = nil, provider: String = "USGS") -> WaterLevelReading {
        var r = WaterLevelReading(siteCode: "02171000", siteName: "LAKE MARION", parameterCode: "00010",
                                  parameterName: "Temperature, water", value: 30.0, unit: "deg C",
                                  dateTime: now.addingTimeInterval(-ageHours * 3600),
                                  latitude: 33.5, longitude: -80.4, trend: .steady, change: 0)
        r.distanceMiles = miles
        r.provider = provider
        return r
    }
    private func model(_ f: Double = 80.0) -> WaterTempModel {
        var m = WaterTempModel(currentF: f, series: [])
        m.currentLocalDate = "2026-07-14"; m.timeZoneIdentifier = "America/Chicago"
        return m
    }
    private func input(_ state: ResolvedWaterTemperatureState) -> ConditionsInput {
        ConditionsInputBuilder.build(coordinate: coord, date: now, weather: nil, water: nil, discharge: nil,
                                     waterTempC: nil, modeledWaterTempF: nil, turbidity: nil,
                                     resolvedWaterTemp: state)
    }

    // MARK: - Resolver cases (Part B / N)

    func testCase1FreshMeasurementIsShownAndScored() {
        let s = WaterTemperatureResolver.resolve(measurement: reading(ageHours: 2), model: model(), at: now)
        XCTAssertEqual(s.kind, .measured)
        XCTAssertEqual(s.valueF!, 86.0, accuracy: 1e-9)
        XCTAssertEqual(input(s).waterTempF!, 86.0, accuracy: 1e-9)
        XCTAssertFalse(input(s).waterTempEstimated)
        XCTAssertEqual(SectorEngineAPI.waterTempDTO(state: s)?.source, "gauge")
    }

    func testCase2IntermediateAgeMeasurementResolvesToModelForBoth() {
        let s = WaterTemperatureResolver.resolve(measurement: reading(ageHours: 10), model: model(), at: now)
        XCTAssertEqual(s.kind, .modeled)
        XCTAssertEqual(s.valueF, 80.0)
        XCTAssertTrue(s.qualityFlags.contains { $0.hasPrefix("measurementStale") })
        XCTAssertEqual(input(s).waterTempF, 80.0)
        XCTAssertEqual(SectorEngineAPI.waterTempDTO(state: s)?.source, "model")
        XCTAssertEqual(SectorEngineAPI.waterTempDTO(state: s)?.valueF, 80.0)
    }

    func testCase3StaleMeasurementResolvesIdentically() {
        let s = WaterTemperatureResolver.resolve(measurement: reading(ageHours: 100), model: model(), at: now)
        XCTAssertEqual(s.kind, .modeled)
        XCTAssertEqual(SectorEngineAPI.waterTempDTO(state: s)?.valueF, input(s).waterTempF)
    }

    func testCase4NoMeasurementUsesModelForBoth() {
        let s = WaterTemperatureResolver.resolve(measurement: nil, model: model(77), at: now)
        XCTAssertEqual(s.kind, .modeled)
        XCTAssertEqual(s.lakeLocalDate, "2026-07-14")
        XCTAssertEqual(input(s).waterTempF, 77)
        XCTAssertTrue(input(s).waterTempEstimated)
    }

    func testCase5NothingAvailableIsUnknownNotAFabricatedValue() {
        let s = WaterTemperatureResolver.resolve(measurement: nil, model: nil, at: now)
        XCTAssertEqual(s.kind, .unavailable)
        XCTAssertNil(s.valueF)
        XCTAssertNil(SectorEngineAPI.waterTempDTO(state: s))
        XCTAssertNil(input(s).waterTempF, "no weather either: nothing to score, nothing invented")
        // When the score uses its existing air fallback, the state DTO says so explicitly.
        let dto = SectorEngineAPI.waterTempStateDTO(s, model: nil, scoredValueF: 64)
        XCTAssertNil(dto.valueF)
        XCTAssertEqual(dto.scoredFrom, "airTemperatureFallback")
        XCTAssertEqual(dto.kind, "unavailable")
    }

    func testFarMeasurementIsNotThisWater() {
        let s = WaterTemperatureResolver.resolve(measurement: reading(ageHours: 1, miles: 20), model: model(), at: now)
        XCTAssertEqual(s.kind, .modeled)
        XCTAssertTrue(s.qualityFlags.contains { $0.hasPrefix("measurementTooFar") })
    }

    func testCWMSSensorIsLabelledAsSuch() {
        let s = WaterTemperatureResolver.resolve(measurement: reading(ageHours: 1, provider: "USACE CWMS"),
                                                 model: model(), at: now)
        XCTAssertEqual(s.sourceKind, .cwmsLakeSensor)
    }

    // MARK: - Shown == scored invariant (Part E)

    /// For every age (fresh, at the boundary, inside the old 72 h display
    /// window, beyond it) and with/without a model: the response DTO, the state
    /// DTO and the score input agree on value, kind and source.
    func testShownEqualsScoredAcrossAgesAndInputs() {
        let ages: [Double?] = [nil, 0, 2, 5.99, 6.0, 6.01, 10, 48, 71.9, 73, 500]
        for age in ages {
            for m in [nil, model()] as [WaterTempModel?] {
                let meas = age.map { reading(ageHours: $0) }
                let state = WaterTemperatureResolver.resolve(measurement: meas, model: m, at: now)
                let scored = input(state)
                // The raw path through the builder makes the same decision.
                let raw = ConditionsInputBuilder.build(coordinate: coord, date: now, weather: nil, water: nil,
                                                       discharge: nil, waterTempC: meas,
                                                       modeledWaterTempF: m?.currentF, turbidity: nil)
                let label = "age \(String(describing: age)) model \(m != nil)"
                XCTAssertEqual(raw.waterTempF, scored.waterTempF, label)
                XCTAssertEqual(raw.waterTempEstimated, scored.waterTempEstimated, label)
                let legacy = SectorEngineAPI.waterTempDTO(state: state)
                let full = SectorEngineAPI.waterTempStateDTO(state, model: m, scoredValueF: scored.waterTempF)
                XCTAssertEqual(legacy?.valueF, scored.waterTempF, label)
                XCTAssertEqual(full.valueF, scored.waterTempF, label)
                XCTAssertEqual(full.scoredValueF, full.valueF, label)
                XCTAssertEqual(state.isMeasured, !scored.waterTempEstimated && scored.waterTempF != nil, label)
                XCTAssertEqual(legacy?.source == "gauge", state.kind == .measured, label)
                XCTAssertEqual(full.sourceId, state.sourceId, label)
                XCTAssertEqual(full.lakeLocalDate, state.lakeLocalDate, label)
            }
        }
    }

    // MARK: - Provenance cannot contradict itself (Part J)

    func testProvenanceIsSelfConsistent() {
        let measured = WaterTemperatureResolver.resolve(measurement: reading(ageHours: 1), model: model(), at: now)
        XCTAssertNotNil(measured.observedAt); XCTAssertNotNil(measured.sourceId)
        XCTAssertNil(measured.modelVersion, "a measurement never carries the model as its source")
        XCTAssertEqual(measured.spatialSupport, "point")
        XCTAssertEqual(measured.ageHours!, 1, accuracy: 1e-6)

        let modeled = WaterTemperatureResolver.resolve(measurement: nil, model: model(), at: now)
        XCTAssertNil(modeled.observedAt, "a model day is not an observation")
        XCTAssertNil(modeled.sourceId); XCTAssertNotNil(modeled.modelVersion)
        XCTAssertEqual(modeled.spatialSupport, "lakeWide")
        XCTAssertNil(modeled.ageHours)
    }

    /// A measurement's local date comes from its own instant in the lake's
    /// zone — an evening reading after the UTC rollover is still that day.
    func testMeasuredLocalDateIsTheLakesDay() {
        let s = WaterTemperatureResolver.resolve(measurement: reading(ageHours: 1), model: model(), at: now)
        XCTAssertEqual(s.lakeLocalDate, "2026-07-14")   // observed 21:00 CDT Jul 14 = 02:00Z Jul 15
    }

    // MARK: - Lake-local date (Parts F–I)

    func testLakeLocalDateMatrixCentral() {
        let cases: [(String, String)] = [
            ("2026-01-15T05:59:00Z", "2026-01-14"),   // 23:59 CST
            ("2026-01-15T06:00:00Z", "2026-01-15"),   // 00:00 CST
            ("2026-07-15T04:59:00Z", "2026-07-14"),   // 23:59 CDT
            ("2026-07-15T05:00:00Z", "2026-07-15"),   // 00:00 CDT
            ("2026-10-08T04:30:00Z", "2026-10-07"),   // 23:30 CDT, UTC already Oct 8
            ("2026-10-07T05:30:00Z", "2026-10-07"),   // 00:30 CDT
            ("2026-01-15T05:30:00Z", "2026-01-14"),   // 23:30 CST
            ("2026-01-15T06:30:00Z", "2026-01-15"),   // 00:30 CST
            ("2026-03-08T07:59:00Z", "2026-03-08"),   // 01:59 CST, spring-forward day
            ("2026-03-08T08:00:00Z", "2026-03-08"),   // 03:00 CDT (02:00 skipped)
            ("2026-03-09T04:59:00Z", "2026-03-08"),   // 23:59 CDT
            ("2026-03-09T05:00:00Z", "2026-03-09"),
            ("2026-11-01T06:30:00Z", "2026-11-01"),   // 01:30 CDT (first 01:30)
            ("2026-11-01T07:30:00Z", "2026-11-01"),   // 01:30 CST (repeated hour)
            ("2026-11-02T05:59:00Z", "2026-11-01"),   // 23:59 CST
            ("2026-11-02T06:00:00Z", "2026-11-02"),
        ]
        for (instant, expected) in cases {
            XCTAssertEqual(LakeLocalDate.string(for: t(instant), in: chicago), expected, instant)
        }
    }

    func testLakeLocalDateIsNotCentralOnly() {
        let la = TimeZone(identifier: "America/Los_Angeles")!
        let ny = TimeZone(identifier: "America/New_York")!
        XCTAssertEqual(LakeLocalDate.string(for: t("2026-10-08T06:30:00Z"), in: la), "2026-10-07")  // 23:30 PDT
        XCTAssertEqual(LakeLocalDate.string(for: t("2026-10-08T07:00:00Z"), in: la), "2026-10-08")
        XCTAssertEqual(LakeLocalDate.string(for: t("2026-10-08T03:30:00Z"), in: ny), "2026-10-07")  // 23:30 EDT
        XCTAssertEqual(LakeLocalDate.string(for: t("2026-10-08T04:00:00Z"), in: ny), "2026-10-08")
    }

    func testZoneSourceOrderAndFallback() {
        XCTAssertEqual(LakeLocalDate.timeZone(identifier: "America/Denver", utcOffsetSeconds: -21600)?.identifier,
                       "America/Denver")
        XCTAssertEqual(LakeLocalDate.timeZone(identifier: nil, utcOffsetSeconds: -18000)?.secondsFromGMT(), -18000)
        XCTAssertNil(LakeLocalDate.timeZone(identifier: nil, utcOffsetSeconds: nil))
    }

    // MARK: - Current vs forecast day selection (Part H)

    private func series(_ dates: [String]) -> [WaterTempDay] {
        dates.enumerated().map { i, d in
            WaterTempDay(date: Date(timeIntervalSince1970: Double(i) * 86_400), waterF: 70 + Double(i),
                         airF: 60, localDate: d)
        }
    }

    func testTodayHoldsThroughTheWholeLocalDayAndRollsAtLocalMidnight() {
        let s = series(["2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09"])
        func pick(_ i: String) -> String? {
            WaterTemperatureService.currentDay(in: s, now: t(i), lakeTimeZone: chicago)?.localDate
        }
        XCTAssertEqual(pick("2026-10-07T05:00:00Z"), "2026-10-07")   // 00:00 CDT
        XCTAssertEqual(pick("2026-10-07T17:00:00Z"), "2026-10-07")   // noon
        XCTAssertEqual(pick("2026-10-08T04:59:00Z"), "2026-10-07")   // 23:59 CDT (UTC is Oct 8)
        XCTAssertEqual(pick("2026-10-08T05:00:00Z"), "2026-10-08")   // local midnight
        // Forecast day +1 keeps its own label and is not current.
        let i = s.firstIndex { $0.localDate == pick("2026-10-07T17:00:00Z") }!
        XCTAssertEqual(s[i + 1].localDate, "2026-10-08")
    }

    /// Hour by hour across both DST changes: every lake date is current for a
    /// contiguous run, none is skipped, none repeats.
    func testDSTNeitherSkipsNorDuplicatesTheDailyState() {
        for (start, dates) in [("2026-03-07T06:00:00Z", ["2026-03-07", "2026-03-08", "2026-03-09", "2026-03-10"]),
                               ("2026-10-31T05:00:00Z", ["2026-10-31", "2026-11-01", "2026-11-02", "2026-11-03"])] {
            let s = series(dates)
            var seen: [String] = []
            var hoursPerDay: [String: Int] = [:]
            var instant = t(start)
            for _ in 0..<(24 * 3) {
                let d = WaterTemperatureService.currentDay(in: s, now: instant, lakeTimeZone: chicago)!.localDate!
                if seen.last != d { seen.append(d) }
                hoursPerDay[d, default: 0] += 1
                instant = instant.addingTimeInterval(3600)
            }
            XCTAssertEqual(seen, Array(dates.prefix(seen.count)), "\(start)")
            XCTAssertEqual(Set(seen).count, seen.count, "no lake day current twice")
            let dstDay = dates[1]
            XCTAssertEqual(hoursPerDay[dstDay], dstDay.hasSuffix("03-08") ? 23 : 25, "DST day length \(dstDay)")
        }
    }

    // MARK: - DTO back-compat (Part O)

    func testModelDTOAddsLocalDatesWithoutBreakingOldClients() throws {
        let old = #"{"currentF":80,"series":[{"date":0,"waterF":80,"airF":70}]}"#
        let dto = try JSONDecoder().decode(WaterTempModelDTO.self, from: Data(old.utf8))
        XCTAssertNil(dto.currentLocalDate); XCTAssertNil(dto.series[0].localDate)
        var m = WaterTempModel(currentF: 80, series: [WaterTempDay(date: Date(timeIntervalSince1970: 0),
                                                                   waterF: 80, airF: 70, localDate: "2026-10-07")])
        m.currentLocalDate = "2026-10-07"; m.timeZoneIdentifier = "America/Chicago"
        let out = SectorEngineAPI.waterTempModelDTO(m)
        XCTAssertEqual(out.currentLocalDate, "2026-10-07")
        XCTAssertEqual(out.timeZone, "America/Chicago")
        XCTAssertEqual(out.series[0].localDate, "2026-10-07")
    }
}
