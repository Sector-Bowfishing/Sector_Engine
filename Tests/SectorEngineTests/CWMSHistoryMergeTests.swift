//
//  CWMSHistoryMergeTests.swift
//  SectorEngineTests
//
//  CWMS observed history used to carry outflow only, so every observation's
//  `reservoirFt` was nil and a USACE lake (Lanier) or a SWPA dam enriched from
//  CWMS (Bull Shoals) never got a pool trend — the level tile showed the pool
//  with no direction. The pool series is now merged into that history. These
//  tests pin the merge rule and prove the merged history drives the builder's
//  `reservoirTrend12hFt`.
//

import XCTest
#if canImport(CoreLocation)
import CoreLocation
#endif
@testable import SectorEngine

final class CWMSHistoryMergeTests: XCTestCase {

    private let t = ISODate.parse("2026-09-14T22:00:00Z")!
    private let lanier = CLLocationCoordinate2D(latitude: 34.20, longitude: -83.98)

    private func hours(_ h: Double) -> TimeInterval { h * 3600 }

    /// Hourly outflow t-12h … t, 700 → 4790 cfs (a generation pulse).
    private func outflow() -> [GenerationObservation] {
        (0...12).map { i in
            GenerationObservation(at: t.addingTimeInterval(hours(Double(i - 12))),
                                  dischargeCfs: 700 + Double(i) * (4790 - 700) / 12,
                                  reservoirFt: nil, tailwaterFt: nil)
        }
    }

    private func generation(history: [GenerationObservation],
                            reservoirFt: Double? = 1065.00) -> DamGeneration {
        let dam = GenerationDam(id: "USACE-lanier", operatorID: .usace, name: "Lanier (Sidney Lanier)",
                                latitude: 34.22, longitude: -84.07, river: "USACE Mobile",
                                lakeNameOverride: "Lanier (Sidney Lanier)")
        return DamGeneration(dam: dam, distanceMiles: 5.3, windows: [],
                             dischargeCfs: history.last?.dischargeCfs, dischargeTrend12hCfs: nil,
                             reservoirElevationFt: reservoirFt, tailwaterElevationFt: nil,
                             observedAt: t, history: history)
    }

    func testPoolPointsMergeIntoHistoryAndDriveTrend() throws {
        let pool: [(Date, Double)] = [
            (t.addingTimeInterval(hours(-12)), 1065.03),
            (t.addingTimeInterval(hours(-6) + 10 * 60), 1065.01),
            (t, 1065.00),
        ]
        // Out of order on purpose: CWMS pages aren't guaranteed sorted.
        let merged = CWMSObservedService.mergeHistory(outflow: Array(outflow().reversed()), pool: pool)

        XCTAssertEqual(merged.map(\.at), merged.map(\.at).sorted(), "history is oldest → newest")
        XCTAssertEqual(merged.count, 13, "every pool point landed on an outflow hour; nothing appended")
        XCTAssertEqual(merged.map(\.dischargeCfs), outflow().map(\.dischargeCfs), "outflow values untouched")

        let byHour = Dictionary(uniqueKeysWithValues: merged.map { ($0.at, $0.reservoirFt) })
        XCTAssertEqual(byHour[t.addingTimeInterval(hours(-12))], 1065.03)
        XCTAssertEqual(byHour[t.addingTimeInterval(hours(-6))], 1065.01,
                       "a pool reading 10 min off the hour belongs to that hour's observation")
        XCTAssertEqual(byHour[t], 1065.00)
        XCTAssertEqual(merged.compactMap(\.reservoirFt).count, 3, "no pool value invented for other hours")

        let input = ConditionsInputBuilder.build(coordinate: lanier, date: t, weather: nil,
                                                 water: nil, discharge: nil, waterTempC: nil,
                                                 turbidity: nil, generation: generation(history: merged))
        let trend = try XCTUnwrap(input.reservoirTrend12hFt, "merged CWMS history must yield a pool trend")
        XCTAssertEqual(trend, -0.03, accuracy: 1e-9)
        XCTAssertEqual(input.reservoirElevationFt, 1065.00)
    }

    func testOutflowOnlyHistoryStillHasNoPoolTrend() {
        // The pre-merge shape: proves the trend above comes from the merge.
        let input = ConditionsInputBuilder.build(coordinate: lanier, date: t, weather: nil,
                                                 water: nil, discharge: nil, waterTempC: nil,
                                                 turbidity: nil, generation: generation(history: outflow()))
        XCTAssertNil(input.reservoirTrend12hFt)
    }

    func testPoolPointsWithNoOutflowNearbyAreAppended() {
        // Outflow with a three-hour gap (t-4h … t-2h missing), as when a district
        // drops a few hourly posts.
        let gapped = outflow().filter { $0.at < t.addingTimeInterval(hours(-4)) || $0.at > t.addingTimeInterval(hours(-2)) }
        let pool: [(Date, Double)] = [
            (t.addingTimeInterval(hours(-14)), 1065.20),              // before the outflow record
            (t.addingTimeInterval(hours(-3)), 1065.05),               // in the gap: 2 h from any outflow
            (t.addingTimeInterval(hours(-1) - 29 * 60), 1065.02),     // 29 min before t-1h: merged
        ]
        let merged = CWMSObservedService.mergeHistory(outflow: gapped, pool: pool)

        XCTAssertEqual(gapped.count, 10)
        XCTAssertEqual(merged.count, 12, "two appended, one merged")
        XCTAssertEqual(merged.map(\.at), merged.map(\.at).sorted())
        XCTAssertEqual(merged.first?.at, t.addingTimeInterval(hours(-14)))
        XCTAssertEqual(merged.first?.reservoirFt, 1065.20)
        XCTAssertNil(merged.first?.dischargeCfs, "an appended pool point carries no invented outflow")
        let inGap = merged.first { $0.at == t.addingTimeInterval(hours(-3)) }
        XCTAssertEqual(inGap?.reservoirFt, 1065.05)
        XCTAssertNil(inGap?.dischargeCfs)
        let hourBefore = merged.first { $0.at == t.addingTimeInterval(hours(-1)) }
        XCTAssertEqual(hourBefore?.reservoirFt, 1065.02)
        XCTAssertNotNil(hourBefore?.dischargeCfs)
    }

    func testProjectWithPoolButNoOutflowGetsPoolTrend() throws {
        let pool: [(Date, Double)] = stride(from: -12.0, through: 0, by: 1).map {
            (t.addingTimeInterval(hours($0)), 1065.00 - $0 * 0.4 / 12)   // 1065.40 → 1065.00
        }
        let merged = CWMSObservedService.mergeHistory(outflow: [], pool: pool)
        XCTAssertEqual(merged.count, 13)
        XCTAssertTrue(merged.allSatisfy { $0.dischargeCfs == nil })

        let input = ConditionsInputBuilder.build(coordinate: lanier, date: t, weather: nil,
                                                 water: nil, discharge: nil, waterTempC: nil,
                                                 turbidity: nil, generation: generation(history: merged))
        XCTAssertEqual(try XCTUnwrap(input.reservoirTrend12hFt), -0.4, accuracy: 1e-9)
    }

    func testNearestSubHourlyPoolReadingWinsTheHour() {
        // 15-minute pool against hourly outflow: several readings fall inside one
        // hour's window, and the one nearest the hour is that hour's pool.
        let flow = [GenerationObservation(at: t, dischargeCfs: 4790, reservoirFt: nil, tailwaterFt: nil)]
        let pool: [(Date, Double)] = [
            (t.addingTimeInterval(-15 * 60), 1065.10),
            (t.addingTimeInterval(5 * 60), 1065.02),
            (t.addingTimeInterval(15 * 60), 1065.00),
        ]
        let merged = CWMSObservedService.mergeHistory(outflow: flow, pool: pool)
        XCTAssertEqual(merged.count, 1, "readings inside the window are absorbed, not duplicated")
        XCTAssertEqual(merged.first?.reservoirFt, 1065.02)
        XCTAssertEqual(merged.first?.dischargeCfs, 4790)
    }

    func testTailwaterTempSurvivesPerCallerDistance() {
        // Adapters cache one reading per dam and re-stamp the distance per caller;
        // the CWMS tailwater temperature must not be dropped on the way.
        var g = generation(history: outflow())
        g.tailwaterTempF = 52
        XCTAssertEqual(g.withDistance(0.5).tailwaterTempF, 52)
        XCTAssertEqual(g.withDistance(0.5).distanceMiles, 0.5)
    }
}
