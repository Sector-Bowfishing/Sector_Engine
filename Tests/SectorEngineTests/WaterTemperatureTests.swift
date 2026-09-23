//
//  WaterTemperatureTests.swift
//  SectorEngineTests
//
//  The water-temperature model is the most consequential modeled number in the
//  app: it drives the waterTemp factor and gates whether Fish Intelligence's
//  biological state resolves at all. It has no gauge behind it on most waters,
//  so these tests are the only thing standing between a constant and a lake
//  that reads 6 °F wrong all summer.
//
//  The last test is a REGRESSION AGAINST REAL MEASURED WATER — 120 days of Lake
//  Marion, SC (USGS 02171000), a shallow warm reservoir of the same class as
//  Guntersville, paired with the weather that drove it. If someone "simplifies"
//  the constants back toward air temperature, that test fails with a number.
//

import XCTest
@testable import SectorEngine

final class WaterTemperatureTests: XCTestCase {

    private func day(_ i: Int) -> Date { Date(timeIntervalSince1970: 86_400 * Double(i)) }

    /// Roll the model over a constant-weather series and return the last value.
    private func settle(airF: Double, solarMJ: Double?, windKph: Double?,
                        humidityPct: Double?, days: Int = 400) -> Double {
        let eq = WaterTemperatureService.equilibriumF(
            airF: airF, solarMJ: solarMJ, windKph: windKph, humidityPct: humidityPct)
        let series = WaterTemperatureService.integrate(
            (0..<days).map { (date: day($0), airF: airF, equilibriumF: eq) })
        return series.last!.waterF
    }

    // MARK: - The physics each term encodes

    func testLiquidWaterNeverFreezes() {
        // North Dakota in January. The old air-only model predicted a 12 °F lake.
        let winter = (0..<120).map { i -> (date: Date, airF: Double, equilibriumF: Double) in
            let air = -10.0
            return (day(i), air, WaterTemperatureService.equilibriumF(
                airF: air, solarMJ: 3.0, windKph: 18, humidityPct: 70))
        }
        let series = WaterTemperatureService.integrate(winter)
        let coldest = series.map(\.waterF).min()!
        XCTAssertGreaterThanOrEqual(coldest, WaterTemperatureService.freezingF,
            "water cannot be colder than ice — got \(coldest) °F")
    }

    func testASunlitLakeSettlesWarmerThanTheAir() {
        // The reason the old model ran cold: a lake absorbs shortwave and sits
        // above the daily-MEAN air temperature, most strongly in summer.
        let summer = settle(airF: 80, solarMJ: 26, windKph: 8, humidityPct: 75)
        XCTAssertGreaterThan(summer, 80.0,
            "a sunlit summer lake settles above air temp, got \(summer)")
        let winter = settle(airF: 40, solarMJ: 6, windKph: 8, humidityPct: 75)
        XCTAssertGreaterThan(winter, 40.0)
        // …and the lift is larger in summer, because the sun is.
        XCTAssertGreaterThan(summer - 80, winter - 40,
            "solar lift must scale with sunlight, not be a flat offset")
    }

    func testWindOverDryAirCoolsAndWindOverSaturatedAirBarelyDoes() {
        let humid = settle(airF: 80, solarMJ: 26, windKph: 25, humidityPct: 95)
        let dry   = settle(airF: 80, solarMJ: 26, windKph: 25, humidityPct: 20)
        XCTAssertGreaterThan(humid - dry, 5.0,
            "evaporative cooling must depend on humidity, not wind alone "
            + "(humid \(humid) vs dry \(dry))")
        let calm = settle(airF: 80, solarMJ: 26, windKph: 2, humidityPct: 20)
        XCTAssertGreaterThan(calm, dry, "dry wind cools; calm dry air cools less")
    }

    func testThermalMemoryIsAboutElevenDaysNotFive() {
        // A step change in weather: how far has the lake closed the gap after τ?
        // One time constant is 63% by construction. τ = 1/k.
        let tau = Int((1.0 / WaterTemperatureService.k).rounded())
        XCTAssertEqual(tau, 11, "τ ≈ 11 days — see the calibration in the header")

        let start = settle(airF: 50, solarMJ: 10, windKph: 8, humidityPct: 70)
        let target = WaterTemperatureService.equilibriumF(
            airF: 80, solarMJ: 26, windKph: 8, humidityPct: 70)
        var tw = start
        for _ in 0..<tau { tw = max(32, tw + WaterTemperatureService.k * (target - tw)) }
        let closed = (tw - start) / (target - start)
        XCTAssertEqual(closed, 0.63, accuracy: 0.03,
            "one time constant should close ~63% of the gap, got \(closed)")
    }

    func testMissingEnergyInputsDegradeInsteadOfGoingCold() {
        // If the provider omits solar/wind/humidity we must NOT silently fall
        // back to bare air temperature — that is the cold bias this replaces.
        let degraded = WaterTemperatureService.equilibriumF(
            airF: 70, solarMJ: nil, windKph: nil, humidityPct: nil)
        XCTAssertEqual(degraded, 70 + WaterTemperatureService.airOnlyOffsetF)
        XCTAssertGreaterThan(degraded, 70, "the air-only path still carries an offset")
    }

    // MARK: - Regression against real measured water

    /// 120 days of Lake Marion, SC (USGS 02171000), 2025-06-18 → 2025-10-15.
    /// (dailyMeanAirF, shortwaveMJ, windKph, humidityPct, MEASURED waterF)
    private static let lakeMarion: [(Double, Double, Double, Double, Double)] = [
        (81.6, 25.3, 11.0, 79.0, 87.57),
        (81.1, 23.27, 14.6, 80.0, 85.74),
        (81.9, 27.39, 8.4, 73.0, 85.79),
        (81.7, 24.6, 6.4, 77.0, 84.56),
        (83.0, 27.08, 6.8, 74.0, 84.94),
        (83.8, 26.94, 7.4, 74.0, 85.82),
        (85.1, 23.83, 7.5, 73.0, 86.44),
        (85.8, 24.05, 4.0, 71.0, 86.53),
        (82.6, 27.37, 7.4, 71.0, 86.71),
        (83.1, 26.01, 10.7, 72.0, 86.9),
        (81.5, 25.06, 8.0, 76.0, 86.29),
        (82.5, 25.02, 8.4, 73.0, 86.08),
        (82.3, 26.16, 12.1, 74.0, 86.08),
        (80.3, 21.87, 13.8, 78.0, 86.5),
        (79.3, 16.09, 12.1, 84.0, 86.44),
        (80.3, 21.01, 6.2, 84.0, 86.38),
        (81.3, 24.68, 11.0, 77.0, 85.63),
        (77.6, 20.2, 19.5, 82.0, 85.12),
        (78.7, 17.72, 16.6, 81.0, 84.28),
        (82.8, 25.61, 9.5, 78.0, 84.68),
        (82.7, 19.0, 8.6, 82.0, 85.19),
        (80.7, 19.13, 10.2, 85.0, 85.19),
        (77.5, 17.82, 10.8, 87.0, 84.97),
        (78.0, 19.44, 9.7, 87.0, 84.58),
        (79.1, 18.93, 8.0, 84.0, 84.33),
        (82.0, 24.95, 4.9, 80.0, 85.52),
        (82.1, 23.39, 5.4, 82.0, 85.32),
        (81.7, 23.9, 9.8, 79.0, 85.53),
        (81.6, 19.05, 10.2, 81.0, 86.14),
        (83.5, 25.05, 11.0, 78.0, 86.59),
        (83.5, 24.22, 10.1, 82.0, 86.56),
        (85.7, 25.91, 10.9, 73.0, 86.88),
        (86.3, 25.66, 12.7, 68.0, 87.7),
        (85.8, 22.41, 8.1, 74.0, 89.25),
        (82.4, 18.67, 8.4, 84.0, 88.32),
        (80.8, 24.5, 12.2, 77.0, 86.35),
        (80.7, 20.18, 7.3, 84.0, 87.01),
        (84.5, 25.72, 8.3, 76.0, 87.66),
        (86.8, 25.8, 8.2, 71.0, 88.84),
        (89.1, 26.38, 7.8, 63.0, 90.99),
        (86.3, 23.6, 6.8, 73.0, 91.55),
        (83.9, 20.66, 4.5, 79.0, 90.78),
        (80.4, 12.85, 6.6, 90.0, 88.73),
        (83.4, 20.72, 8.1, 85.0, 88.85),
        (82.9, 23.12, 10.1, 81.0, 88.84),
        (76.8, 13.71, 12.0, 87.0, 87.51),
        (74.1, 13.51, 13.6, 73.0, 86.69),
        (73.3, 11.24, 10.5, 78.0, 85.65),
        (76.7, 16.34, 7.8, 89.0, 85.09),
        (76.1, 17.48, 8.1, 87.0, 84.94),
        (74.3, 11.03, 11.6, 83.0, 83.62),
        (75.7, 18.06, 12.5, 84.0, 82.62),
        (75.0, 18.4, 14.9, 88.0, 82.03),
        (75.4, 12.93, 14.9, 93.0, 81.75),
        (77.1, 13.99, 10.2, 93.0, 81.86),
        (81.0, 21.5, 6.0, 86.0, 82.09),
        (83.1, 23.37, 10.5, 83.0, 83.11),
        (80.1, 14.02, 7.6, 90.0, 83.12),
        (83.3, 23.0, 3.6, 85.0, 84.1),
        (81.1, 15.58, 4.6, 88.0, 84.74),
        (80.1, 22.51, 7.7, 80.0, 83.8),
        (82.2, 24.31, 3.6, 75.0, 84.0),
        (81.1, 22.31, 6.9, 80.0, 83.43),
        (79.9, 20.97, 13.1, 76.0, 81.58),
        (80.1, 19.38, 9.1, 76.0, 82.51),
        (75.8, 7.14, 9.5, 93.0, 81.76),
        (73.3, 7.86, 12.2, 91.0, 81.02),
        (77.6, 19.04, 8.9, 78.0, 81.47),
        (80.7, 23.02, 8.2, 74.0, 82.96),
        (77.6, 23.95, 9.3, 65.0, 82.36),
        (74.6, 24.27, 8.2, 58.0, 81.6),
        (74.1, 20.29, 5.5, 65.0, 80.61),
        (77.3, 24.49, 5.9, 65.0, 81.45),
        (73.6, 5.73, 5.8, 85.0, 80.69),
        (74.4, 22.71, 15.2, 68.0, 79.75),
        (71.1, 23.97, 14.4, 62.0, 78.94),
        (72.8, 24.38, 12.7, 62.0, 78.52),
        (72.8, 24.16, 7.6, 62.0, 78.81),
        (76.4, 23.3, 7.8, 70.0, 78.46),
        (78.8, 22.86, 6.8, 72.0, 78.67),
        (79.7, 22.82, 5.6, 76.0, 78.98),
        (76.8, 19.16, 8.6, 85.0, 80.66),
        (71.5, 20.97, 16.8, 67.0, 78.35),
        (70.8, 23.23, 15.1, 59.0, 77.99),
        (71.5, 14.07, 10.4, 76.0, 77.69),
        (73.7, 14.95, 8.9, 77.0, 77.51),
        (73.4, 21.83, 11.7, 72.0, 77.39),
        (72.1, 20.91, 13.2, 69.0, 77.15),
        (71.7, 23.29, 13.5, 60.0, 76.97),
        (72.7, 22.06, 11.5, 63.0, 76.72),
        (72.1, 22.6, 8.5, 62.0, 77.2),
        (72.7, 20.12, 7.5, 68.0, 77.52),
        (76.5, 21.64, 4.9, 71.0, 80.02),
        (77.6, 20.83, 5.0, 75.0, 78.59),
        (77.2, 20.12, 3.9, 76.0, 79.08),
        (75.5, 19.47, 10.6, 73.0, 77.1),
        (74.0, 18.28, 9.6, 73.0, 77.1),
        (75.9, 20.22, 7.4, 76.0, 78.27),
        (79.7, 19.83, 7.4, 78.0, 78.93),
        (81.2, 19.12, 10.8, 76.0, 78.96),
        (77.8, 16.3, 7.2, 86.0, 81.4),
        (74.8, 13.68, 5.2, 88.0, 79.95),
        (75.1, 13.57, 10.3, 84.0, 79.79),
        (72.1, 6.34, 17.8, 91.0, 78.61),
        (73.1, 12.62, 20.3, 84.0, 77.97),
        (72.0, 15.31, 15.6, 67.0, 77.03),
        (67.6, 18.99, 15.6, 67.0, 76.47),
        (67.7, 19.68, 14.3, 69.0, 75.77),
        (71.1, 17.16, 13.8, 75.0, 75.16),
        (73.5, 13.18, 15.4, 74.0, 74.97),
        (74.8, 16.77, 15.0, 76.0, 74.96),
        (73.6, 15.14, 8.6, 85.0, 75.12),
        (75.1, 15.83, 3.8, 84.0, 76.44),
        (68.9, 13.1, 18.0, 65.0, 75.02),
        (63.8, 8.4, 21.5, 70.0, 73.73),
        (60.3, 1.83, 22.5, 96.0, 71.91),
        (62.9, 2.35, 24.4, 97.0, 69.64),
        (64.3, 8.93, 14.8, 85.0, 69.1),
        (66.9, 14.95, 8.1, 78.0, 69.97),
        (66.3, 18.39, 10.4, 75.0, 69.65),    ]

    func testTracksRealMeasuredWaterOnAShallowSouthernReservoir() {
        let rows = Self.lakeMarion
        let days = rows.enumerated().map { i, r in
            (date: day(i), airF: r.0,
             equilibriumF: WaterTemperatureService.equilibriumF(
                airF: r.0, solarMJ: r.1, windKph: r.2, humidityPct: r.3))
        }
        let modeled = WaterTemperatureService.integrate(days).map(\.waterF)
        let observed = rows.map(\.4)

        // Skip the spin-up; the runtime fetches 45 past days for this reason.
        let from = 45
        var sq = 0.0, bias = 0.0
        for i in from..<modeled.count {
            let e = modeled[i] - observed[i]
            sq += e * e; bias += e
        }
        let n = Double(modeled.count - from)
        let rmse = (sq / n).squareRoot()
        let meanBias = bias / n

        XCTContext.runActivity(named: "Lake Marion fit") { _ in
            print(String(format: "RMSE %.2f F   bias %+.2f F   n %.0f", rmse, meanBias, n))
        }

        XCTAssertLessThan(rmse, 3.5, "modeled water drifted from the gauge: RMSE \(rmse) °F")

        // What shipped before, on the same window — air-only, k = 0.20, no floor.
        var tw = rows.prefix(7).map(\.0).reduce(0, +) / 7
        var oldSq = 0.0, oldBias = 0.0
        for (i, r) in rows.enumerated() {
            tw += 0.20 * (r.0 - tw)
            if i >= from {
                oldSq += (tw - r.4) * (tw - r.4)
                oldBias += tw - r.4
            }
        }
        let oldRMSE = (oldSq / n).squareRoot()
        let oldMeanBias = oldBias / n

        XCTAssertLessThan(rmse, oldRMSE - 1.0,
            "the new model must beat the old by more than a degree "
            + "(new \(rmse) vs old \(oldRMSE))")

        // Bias is asserted RELATIVE to the old model, not against a fixed number.
        // One lake's summer is not the global picture. Measured across all 17
        // gauges the mean bias is −0.10 °F and the worst month is −1.6 °F (old:
        // −3.67 °F mean, −6.05 °F worst, cold in all twelve months). A single
        // lake still sits a degree or two off that in either direction — Marion
        // runs warm in summer — so pin the IMPROVEMENT, not a knife-edge number.
        XCTAssertLessThan(abs(meanBias), abs(oldMeanBias) * 0.6,
            "systematic bias must be substantially reduced "
            + "(new \(meanBias) vs old \(oldMeanBias))")
        XCTAssertLessThan(abs(meanBias), 2.5, "absolute ceiling: \(meanBias) °F")
    }
}
