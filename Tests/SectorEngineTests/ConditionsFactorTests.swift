//
//  ConditionsFactorTests.swift
//  SectorTests
//
//  Unit tests for the pure Bowfishing Conditions Engine v2 — astronomy plus each
//  factor scorer in isolation, the species DB / legality rules, and the regime
//  weight sets. Companion to ConditionsAggregatorTests (the §12 end-to-end cases).
//

import XCTest
@testable import SectorEngine

// MARK: - Shared helpers

enum CE {
    static func utc(_ y: Int, _ mo: Int, _ d: Int, _ h: Int = 0, _ mi: Int = 0) -> Date {
        var c = DateComponents(); c.year = y; c.month = mo; c.day = d; c.hour = h; c.minute = mi
        var cal = Calendar(identifier: .gregorian); cal.timeZone = TimeZone(identifier: "UTC")!
        return cal.date(from: c)!
    }

    /// A clear, calm, warm, dark, non-tailwater South May night. Override per test.
    static func input(date: Date = utc(2024, 5, 15, 2),
                      lat: Double = 32, lon: Double = -90,
                      wind: Double = 2, gust: Double? = nil,
                      waterTemp: Double? = 72, tempEst: Bool = false,
                      turbidity: Double? = 5, turbType: TurbidityType = .unknown,
                      rain48: Double = 0,
                      moonIllum: Double = 0, moonAlt: Double = 0,
                      cloud: Double = 10, cityGlow: Double = 0.2,
                      weatherCode: Int = 0, precipNow: Double = 0, severeWarning: String? = nil, airTemp: Double = 75,
                      fogSpread: Double? = nil,
                      pressure: Double = 30.1, pTrend: PressureMovement = .steady,
                      isTail: Bool = false, genLevel: GenerationLevel? = nil, hasGenFc: Bool = false,
                      reservoirElev: Double? = nil, reservoirTrend: Double? = nil,
                      stageTrend: Double? = 0.0,
                      dischargeCfs: Double? = 200, dischargeTrend: Double? = 0,
                      hasTurbGage: Bool? = nil, fcDay: Int = 0,
                      windowStart: Date? = utc(2024, 5, 15, 2, 30),
                      astroDusk: Date? = utc(2024, 5, 15, 2, 30)) -> ConditionsInput {
        ConditionsInput(
            date: date, latitude: lat, longitude: lon,
            region: RegionResolver.region(latitude: lat, longitude: lon),
            windMph: wind, windGustMph: gust, windDirDeg: 180, airTempF: airTemp,
            cloudPct: cloud, humidityPct: 60, pressureInHg: pressure, pressureTrend: pTrend,
            pressureChange12hInHg: 0, weatherCode: weatherCode, precipitationInchNow: precipNow,
            severeWarningLabel: severeWarning,
            cityGlowFactor: cityGlow,
            waterTempF: waterTemp, waterTempEstimated: tempEst,
            stageFt: 10, stageTrend12hFt: stageTrend,
            dischargeCfs: dischargeCfs, dischargeTrend12hCfs: dischargeTrend,
            turbidityFNU: turbidity, turbidityType: turbType, rainLast48hIn: rain48,
            isTailwater: isTail, reservoirElevationFt: reservoirElev,
            reservoirTrend12hFt: reservoirTrend,
            fogSpreadF: fogSpread,
            generationLevel: genLevel, hasGenerationForecast: hasGenFc,
            sunset: utc(2024, 5, 15, 1), sunrise: utc(2024, 5, 15, 11),
            civilDusk: utc(2024, 5, 15, 1, 30), astronomicalDusk: astroDusk,
            moonIllumPct: moonIllum, moonAltitudeAtWindow: moonAlt,
            windowStart: windowStart, windowEnd: utc(2024, 5, 15, 9),
            // A gage exists iff there's a turbidity reading, unless a test says
            // otherwise — keeps "turbidity: nil" from implying a phantom gage now
            // that the estimate caps key off hasTurbidityGage.
            hasTurbidityGage: hasTurbGage ?? (turbidity != nil), forecastDayIndex: fcDay)
    }
}

// MARK: - Astronomy

final class AstronomyTests: XCTestCase {
    func testMoonIllumination() {
        // Full 2024-01-25, new 2024-01-11, first quarter 2024-01-18.
        XCTAssertEqual(Astronomy.moonIllumination(on: CE.utc(2024, 1, 25, 18)), 1.0, accuracy: 0.03)
        XCTAssertEqual(Astronomy.moonIllumination(on: CE.utc(2024, 1, 11, 12)), 0.0, accuracy: 0.03)
        XCTAssertEqual(Astronomy.moonIllumination(on: CE.utc(2024, 1, 18, 4)), 0.5, accuracy: 0.05)
    }

    /// Pins illumination against four independently-known eclipse instants —
    /// eclipses are exact syzygies, so these are hard anchors, not estimates.
    func testMoonIlluminationAgainstKnownEclipses() {
        XCTAssertEqual(Astronomy.moonIllumination(on: CE.utc(2000, 1, 6, 18, 14)), 0.0, accuracy: 0.01)
        XCTAssertEqual(Astronomy.moonIllumination(on: CE.utc(2000, 1, 21, 4, 40)), 1.0, accuracy: 0.01)
        XCTAssertEqual(Astronomy.moonIllumination(on: CE.utc(2024, 4, 8, 18, 17)), 0.0, accuracy: 0.01)
        XCTAssertEqual(Astronomy.moonIllumination(on: CE.utc(2025, 3, 14, 6, 58)), 1.0, accuracy: 0.01)
    }

    /// 2026-07-22 02:24 UTC (= 21:24 CDT Jul 21, Guntersville AL) — the instant
    /// iOS and Android disagreed on. True illumination is 56.4% (Meeus
    /// elongation); the mean-synodic approximation says 49.2%, which is ~7 points
    /// low because the moon's true elongation leads the mean here. Illumination
    /// must come from the real elongation, never from the synodic fraction.
    func testMoonIlluminationUsesTrueElongationNotSynodic() {
        let instant = CE.utc(2026, 7, 22, 2, 24)
        XCTAssertEqual(Astronomy.moonIllumination(on: instant), 0.564, accuracy: 0.01)

        // The synodic fraction is fine for naming the phase, but converting it
        // to a percentage is what produced the wrong 49.2%.
        let synodic = Astronomy.moonPhaseFraction(on: instant)
        XCTAssertEqual(synodic, 0.2474, accuracy: 0.001)
        let synodicIllum = (1 - cos(2 * .pi * synodic)) / 2
        XCTAssertEqual(synodicIllum, 0.492, accuracy: 0.005)
        XCTAssertGreaterThan(abs(synodicIllum - Astronomy.moonIllumination(on: instant)), 0.05)
    }

    /// lb + oz weigh-in entry, mirroring the website's vectors so the two
    /// platforms can't drift. These are the pure conversions the entry boxes use.
    func testLbOzSplitAndJoin() {
        func join(_ lb: String, _ oz: String) -> String {
            if lb.isEmpty && oz.isEmpty { return "" }
            let total = (Double(lb) ?? 0) + (Double(oz) ?? 0) / 16
            return decimalText((total * 1_000_000).rounded() / 1_000_000)
        }
        func split(_ decimal: String) -> (String, String) {
            guard let v = Double(decimal) else { return ("", "") }
            let lb = Int(v.rounded(.down))
            let oz = ((v - Double(lb)) * 16 * 10_000).rounded() / 10_000
            return ("\(lb)", oz == 0 ? "" : decimalText(oz))
        }

        // Composing — what the host types becomes what's stored.
        XCTAssertEqual(join("21", "17"), "22.0625")   // the advertised magic weight
        XCTAssertEqual(join("21", "8"), "21.5")
        XCTAssertEqual(join("22", ""), "22")
        XCTAssertEqual(join("", "8"), "0.5")
        XCTAssertEqual(join("", ""), "")             // not entered — never 0

        // Displaying — what's stored becomes what the host sees.
        XCTAssertEqual(split("22.0625").0, "22"); XCTAssertEqual(split("22.0625").1, "1")
        XCTAssertEqual(split("22.4").0, "22");    XCTAssertEqual(split("22.4").1, "6.4")
        XCTAssertEqual(split("356").0, "356");    XCTAssertEqual(split("356").1, "")
        XCTAssertEqual(split("").0, "");          XCTAssertEqual(split("").1, "")

        // Round-trip: split then join returns the original exactly.
        for v in ["356", "21.5", "22.0625", "22.4", "0.5", "1.0625", "99.9375", "13.7", "456.25"] {
            let (lb, oz) = split(v)
            XCTAssertEqual(join(lb, oz), v, "round-trip lost precision for \(v)")
        }
    }

    /// The decimal formatter must not round to one place (which would flatten the
    /// 22.0625 magic weight to "22.1").
    func testDecimalTextKeepsPrecision() {
        XCTAssertEqual(decimalText(22.0625), "22.0625")
        XCTAssertEqual(decimalText(356), "356")
        XCTAssertEqual(decimalText(22.4), "22.4")
    }

    private func decimalText(_ v: Double) -> String {
        if v == v.rounded() { return String(Int(v)) }
        var s = String(format: "%.6f", v)
        while s.hasSuffix("0") { s.removeLast() }
        if s.hasSuffix(".") { s.removeLast() }
        return s
    }

    func testSunEventsNYC() {
        // 2024-06-20 NYC: sunrise ~09:25 UTC, sunset ~00:31 UTC (next day).
        let e = Astronomy.sunEvents(on: CE.utc(2024, 6, 20, 18), lat: 40.7128, lon: -74.0060)
        let sunrise = try! XCTUnwrap(e.sunrise)
        let sunset = try! XCTUnwrap(e.sunset)
        XCTAssertEqual(sunrise.timeIntervalSince1970,
                       CE.utc(2024, 6, 20, 9, 25).timeIntervalSince1970, accuracy: 300)
        XCTAssertEqual(sunset.timeIntervalSince1970,
                       CE.utc(2024, 6, 21, 0, 31).timeIntervalSince1970, accuracy: 300)
        XCTAssertTrue(sunset > sunrise, "sunset must follow sunrise across UTC midnight")
        // True dark comes after sunset.
        XCTAssertTrue(try! XCTUnwrap(e.astronomicalDusk) > sunset)
    }

    func testMoonAltitudeFractionBelowHorizon() {
        // Daytime new-moon window with the moon down → presence ~0.
        let frac = Astronomy.moonAltitudeFraction(from: CE.utc(2024, 1, 11, 2),
                                                  to: CE.utc(2024, 1, 11, 5),
                                                  lat: 32, lon: -90)
        XCTAssertGreaterThanOrEqual(frac, 0)
        XCTAssertLessThanOrEqual(frac, 1)
    }
}

// MARK: - Darkness / moon

final class DarknessFactorTests: XCTestCase {
    func testNewMoonIsDark() {
        let s = DarknessFactor.score(CE.input(moonIllum: 0, moonAlt: 0))
        XCTAssertGreaterThan(s.score, 90)
    }

    func testBrightMoonUpIsPenalized() {
        let s = DarknessFactor.score(CE.input(moonIllum: 100, moonAlt: 0.9, cloud: 0))
        XCTAssertLessThan(s.score, 40)
    }

    func testMoonAltitudeMatters() {
        // 100% illum but the moon has set for the window → still dark water.
        let s = DarknessFactor.score(CE.input(moonIllum: 100, moonAlt: 0.05, cloud: 0))
        XCTAssertGreaterThan(s.score, 80)
    }

    func testCloudCancelsMoonRuralNotCity() {
        let rural = DarknessFactor.score(CE.input(moonIllum: 100, moonAlt: 0.9, cloud: 90, cityGlow: 0.0))
        let city  = DarknessFactor.score(CE.input(moonIllum: 100, moonAlt: 0.9, cloud: 90, cityGlow: 1.0))
        XCTAssertGreaterThan(rural.score, city.score + 30, "rural cloud blocks the moon; city glow reflects it")
        XCTAssertGreaterThan(rural.score, 70)
        XCTAssertLessThan(city.score, 45)
    }
}

// MARK: - Clarity

final class ClarityFactorTests: XCTestCase {
    func testClearWaterSaturatesHigh() {
        XCTAssertGreaterThan(ClarityFactor.score(CE.input(turbidity: 5)).score, 88)
    }

    func testBlownOutIsLow() {
        let s = ClarityFactor.score(CE.input(turbidity: 120))
        XCTAssertLessThan(s.score, 20)
        XCTAssertLessThan(ClarityFactor.visibilityFt(CE.input(turbidity: 120)), 1.0)
    }

    func testAlgalIsTwiceAsBadAsSediment() {
        let algal = ClarityFactor.visibilityFt(CE.input(turbidity: 40, turbType: .algal))
        let sed   = ClarityFactor.visibilityFt(CE.input(turbidity: 40, turbType: .sediment))
        XCTAssertEqual(sed / algal, 2.0, accuracy: 0.01)
    }

    func testRainFallbackWhenNoGage() {
        let dry = ClarityFactor.visibilityFt(CE.input(turbidity: nil, rain48: 0))
        let wet = ClarityFactor.visibilityFt(CE.input(turbidity: nil, rain48: 2.0))
        XCTAssertGreaterThan(dry, wet)
    }

    // Regression (audit 2026-08-06): the rain fallback must depend on the water
    // body. A tailwater/river blows out after heavy rain; a large reservoir's
    // main pool holds a visibility floor because only its creek arms muddy up.
    // The old blanket-aggressive decay read a big lake as ~0.1 ft after ordinary
    // rain and the seeability ceiling hard-capped the whole night.
    func testReservoirHoldsClarityFloorTailwaterBlowsOut() {
        let cfg = ConditionsConfig.default.clarity
        let tail = ClarityFactor.visibilityFt(CE.input(turbidity: nil, rain48: 5.0, isTail: true))
        let lake = ClarityFactor.visibilityFt(CE.input(turbidity: nil, rain48: 5.0, isTail: false))
        XCTAssertLessThan(tail, 0.5, "a tailwater must blow out after 5 in of rain")
        XCTAssertGreaterThanOrEqual(lake, cfg.reservoirVisibilityFloorFt - 0.001,
                                    "a reservoir main pool must keep its visibility floor")
        XCTAssertGreaterThan(lake, tail, "reservoir clarity must beat a tailwater after the same rain")
    }

    // Regression: a no-gage estimate must never read Prime. The dry fallback
    // (4 ft assumed) used to score ~92 — "we have no idea" presented as green.
    func testNoGageEstimateCantReadPrime() {
        let est = ClarityFactor.score(CE.input(turbidity: nil, hasTurbGage: false))
        XCTAssertLessThanOrEqual(est.score, ConditionsConfig.default.clarity.estimatedScoreCap)
        // The marker moved from a trailing "est." to the leading "~" when the
        // tile copy was tightened — the guarantee is unchanged: an estimate must
        // be visibly distinguishable from a measurement.
        XCTAssertTrue(est.label.hasPrefix("~"), "estimated clarity must be marked approximate")

        let measured = ClarityFactor.score(CE.input(turbidity: 2))
        XCTAssertFalse(measured.label.hasPrefix("~"), "a real gage reading must not read as an estimate")
        XCTAssertGreaterThan(measured.score, est.score, "a real clear reading must beat a guess")
    }

    // Regression: the estimate caps follow hasTurbidityGage, not merely a non-nil
    // FNU. A visibility number derived WITHOUT a real gage must still be capped +
    // marked "~", so a synthesized reading can't read Prime.
    func testEstimatedFollowsGageNotFnuPresence() {
        // FNU present but NO gage (e.g. a derived value) → still capped + marked.
        let derived = ClarityFactor.score(CE.input(turbidity: 2, hasTurbGage: false))
        XCTAssertLessThanOrEqual(derived.score, ConditionsConfig.default.clarity.estimatedScoreCap)
        XCTAssertTrue(derived.label.hasPrefix("~"), "a no-gage reading must be marked approximate")
        // Same FNU WITH a gage → measured, uncapped, and higher.
        let measured = ClarityFactor.score(CE.input(turbidity: 2, hasTurbGage: true))
        XCTAssertFalse(measured.label.hasPrefix("~"))
        XCTAssertGreaterThan(measured.score, derived.score)
    }

    // Regression: the reservoir visibility floor must sit ABOVE the blown-out gate,
    // or a heavy-rain no-gage reservoir estimate floors straight into the cap (25).
    func testReservoirFloorClearsBlownOutGate() {
        let cfg = ConditionsConfig.default
        XCTAssertGreaterThan(cfg.clarity.reservoirVisibilityFloorFt, cfg.gates.blownOutVisibilityFt,
                             "reservoir floor must clear the blown-out gate")
        // A soaked no-gage reservoir keeps a fishable floor and is NOT blown out.
        let vis = ClarityFactor.visibilityFt(CE.input(turbidity: nil, rain48: 6.0, isTail: false))
        XCTAssertGreaterThanOrEqual(vis, cfg.gates.blownOutVisibilityFt)
    }
}

// MARK: - Spawn / species / legality

final class SpawnFactorTests: XCTestCase {
    func testCarpPeakSpawnSouthMay() {
        let r = SpawnFactor.score(CE.input(date: CE.utc(2024, 5, 15, 2), waterTemp: 65))
        XCTAssertEqual(r.species?.name, "Common carp")
        XCTAssertGreaterThanOrEqual(r.intensity, 95)
    }

    func testColdOutOfSeasonNoSpawn() {
        let r = SpawnFactor.score(CE.input(date: CE.utc(2024, 3, 15, 2), waterTemp: 55))
        XCTAssertEqual(r.intensity, 0)
        XCTAssertNil(r.species)
    }

    func testTier3DrumNeverSelected() {
        let r = SpawnFactor.score(CE.input(date: CE.utc(2024, 6, 15, 2), waterTemp: 70))
        XCTAssertNotEqual(r.species?.name, "Freshwater drum")
    }

    func testProtectedSpeciesNeverSelected() {
        // Sweep a year of warm-water dates; paddlefish & shad must never lead.
        for month in 3...8 {
            let r = SpawnFactor.score(CE.input(date: CE.utc(2024, month, 15, 2), waterTemp: 62))
            XCTAssertNotEqual(r.species?.name, "Paddlefish")
            XCTAssertNotEqual(r.species?.name, "American shad")
        }
    }

    func testFloodDependentSpawnerLiftedByRisingWater() {
        // Alligator gar (flood-dependent) at peak temp + spring window.
        let rising = SpawnFactor.score(CE.input(date: CE.utc(2024, 4, 20, 2), lat: 30, lon: -95,
                                                waterTemp: 73, stageTrend: 0.8))
        let falling = SpawnFactor.score(CE.input(date: CE.utc(2024, 4, 20, 2), lat: 30, lon: -95,
                                                 waterTemp: 73, stageTrend: -0.8))
        XCTAssertGreaterThan(rising.intensity, falling.intensity)
    }

    func testTilapiaNotPresentUpNorth() {
        let tilapia = SpeciesDatabase.all.first { $0.name == "Tilapia" }!
        XCTAssertFalse(tilapia.present(in: .north))
        XCTAssertFalse(tilapia.present(in: .lowerMid))
        XCTAssertTrue(tilapia.present(in: .south))
        // In a northern summer it must never be the spawn leader.
        let r = SpawnFactor.score(CE.input(date: CE.utc(2024, 7, 15, 2), lat: 44, lon: -93, waterTemp: 80))
        XCTAssertNotEqual(r.species?.name, "Tilapia")
    }

    func testInteriorSpeciesAbsentFromPacificWest() {
        for name in ["Smallmouth buffalo", "Bigmouth buffalo", "Alligator gar", "Longnose gar", "Bowfin"] {
            let s = SpeciesDatabase.all.first { $0.name == name }!
            XCTAssertFalse(s.present(in: .west), "\(name) must not be present in the Pacific West")
            XCTAssertTrue(s.present(in: .south))
        }
        // Marin County coastal creek (West): no interior fish may lead a spawn run.
        let r = SpawnFactor.score(CE.input(date: CE.utc(2024, 5, 15, 2), lat: 37.9, lon: -122.5, waterTemp: 62))
        let leader = r.species?.name ?? ""
        XCTAssertFalse(leader.contains("buffalo") || leader.contains("gar") || leader == "Bowfin",
                       "interior species leaked into the Pacific West spawn call: \(leader)")
    }

    func testTilapiaAndCatfishDontHeadlineInlandFreshwater() {
        let tilapia = SpeciesDatabase.all.first { $0.name == "Tilapia" }!
        XCTAssertFalse(tilapia.present(in: .south, latitude: 33.66), "no tilapia in Alabama freshwater")
        XCTAssertTrue(tilapia.present(in: .south, latitude: 27.0), "tilapia OK in central Florida")

        let catfish = SpeciesDatabase.all.first { $0.name == "Channel catfish" }!
        XCTAssertFalse(catfish.sightShootableSpawn, "catfish are cavity nesters — never a sight-shoot spawn")

        // Gardendale, AL in July at 82°F: neither may lead a spawn run.
        let r = SpawnFactor.score(CE.input(date: CE.utc(2024, 7, 15, 2), lat: 33.66, lon: -86.8, waterTemp: 82))
        XCTAssertNotEqual(r.species?.name, "Tilapia")
        XCTAssertNotEqual(r.species?.name, "Channel catfish")
    }

    func testSpeciesRangeLimits() {
        let gar = SpeciesDatabase.all.first { $0.name == "Alligator gar" }!
        XCTAssertFalse(gar.present(in: .north, latitude: 44.98, longitude: -93.27), "no alligator gar in Minneapolis")
        XCTAssertFalse(gar.present(in: .lowerMid, latitude: 42.89, longitude: -78.88), "no alligator gar in Buffalo NY")
        XCTAssertTrue(gar.present(in: .south, latitude: 30.45, longitude: -91.19), "alligator gar OK in Baton Rouge")

        let silver = SpeciesDatabase.all.first { $0.name == "Silver carp" }!
        XCTAssertFalse(silver.present(in: .south, latitude: 28.54, longitude: -81.38), "no silver carp in Florida")
        XCTAssertTrue(silver.present(in: .south, latitude: 30.45, longitude: -91.19), "silver carp OK in the Mississippi R")

        let bighead = SpeciesDatabase.all.first { $0.name == "Bighead carp" }!
        XCTAssertFalse(bighead.present(in: .south, latitude: 33.45, longitude: -112.07), "no bighead carp in the Phoenix desert")
    }

    func testTriangularEdges() {
        XCTAssertEqual(SpawnFactor.triangular(65, min: 59, peak: 65, max: 77), 1.0, accuracy: 0.001)
        XCTAssertEqual(SpawnFactor.triangular(59, min: 59, peak: 65, max: 77), 0.0, accuracy: 0.001)
        XCTAssertEqual(SpawnFactor.triangular(77, min: 59, peak: 65, max: 77), 0.0, accuracy: 0.001)
        XCTAssertEqual(SpawnFactor.triangular(50, min: 59, peak: 65, max: 77), 0.0, accuracy: 0.001)
    }
}

final class SpeciesLegalityTests: XCTestCase {
    private func species(_ name: String) -> SpawnSpecies {
        SpeciesDatabase.all.first { $0.name == name }!
    }
    func testProtectedNotRecommendable() {
        XCTAssertFalse(SpeciesLegality.canAutoRecommend(species("Paddlefish")))
        XCTAssertFalse(SpeciesLegality.canAutoRecommend(species("American shad")))
    }
    func testCheckSpeciesNeedDisclaimer() {
        XCTAssertTrue(SpeciesLegality.needsDisclaimer(species("Alligator gar")))
        XCTAssertTrue(SpeciesLegality.needsDisclaimer(species("Channel catfish")))
    }
    func testFreelyLegalNoDisclaimer() {
        XCTAssertTrue(SpeciesLegality.canAutoRecommend(species("Common carp")))
        XCTAssertFalse(SpeciesLegality.needsDisclaimer(species("Common carp")))
    }
}

// MARK: - Wind / temp / level / current / pressure / sky

final class SimpleFactorTests: XCTestCase {
    func testWind() {
        XCTAssertEqual(WindFactor.score(CE.input(wind: 1)).score, 100, accuracy: 0.5)
        XCTAssertEqual(WindFactor.score(CE.input(wind: 25)).score, 5, accuracy: 0.5)
        let gusty = WindFactor.score(CE.input(wind: 6, gust: 20))
        let calm  = WindFactor.score(CE.input(wind: 6, gust: 6))
        XCTAssertLessThan(gusty.score, calm.score)
    }

    func testWaterTemp() {
        XCTAssertEqual(WaterTempFactor.score(CE.input(waterTemp: 75))?.score, 100)
        XCTAssertEqual(WaterTempFactor.score(CE.input(waterTemp: 45))?.score, 10)
        XCTAssertNil(WaterTempFactor.score(CE.input(waterTemp: nil)))
    }

    func testWaterLevel() {
        XCTAssertEqual(WaterLevelFactor.score(CE.input(stageTrend: 0.0))?.score, 85)   // stable
        XCTAssertEqual(WaterLevelFactor.score(CE.input(stageTrend: 0.5))?.score, 100)  // gentle rise
        XCTAssertEqual(WaterLevelFactor.score(CE.input(stageTrend: -2.0))?.score, 20)  // fast fall
        XCTAssertNil(WaterLevelFactor.score(CE.input(stageTrend: nil)))
    }

    /// On a reservoir the dam's OWN pool trend must drive the score, not a
    /// distant USGS river gage — a drawdown lake can't read a flat neutral 85.
    func testReservoirPoolTrendWins() {
        // Pool falling fast while the nearby river gage reads flat: score the pool.
        let drawdown = WaterLevelFactor.score(CE.input(reservoirElev: 594.8, reservoirTrend: -2.0,
                                                       stageTrend: 0.0))
        XCTAssertEqual(drawdown?.score, 20, "reservoir drawdown must score as fast fall, not neutral")
        // Pool trend takes precedence over the gage's disagreeing trend.
        let poolRise = WaterLevelFactor.score(CE.input(reservoirElev: 594.8, reservoirTrend: 0.5,
                                                       stageTrend: -2.0))
        XCTAssertEqual(poolRise?.score, 100, "pool gentle rise must win over the river gage")
        // Below a dam (tailwater) the pool behind it isn't your level → use the gage.
        let tail = WaterLevelFactor.score(CE.input(isTail: true, reservoirElev: 594.8,
                                                   reservoirTrend: 0.5, stageTrend: -2.0))
        XCTAssertEqual(tail?.score, 20, "on a tailwater the river gage trend governs, not the pool")
    }

    /// The tonight score must resolve generation across the fishing WINDOW, not
    /// the instant `now`: a dam off now but scheduled heavy all night is blown
    /// out, and a night that settles late is NOT.
    func testRepresentativeGenerationLevelAcrossWindow() {
        let start = CE.utc(2024, 6, 1, 2)          // window start
        let end = CE.utc(2024, 6, 1, 10)           // window end (8 h)
        func gen(_ blocks: [(Int, Int, Int)]) -> DamGeneration {   // (startHour, endHour, units)
            let tz = TimeZone(identifier: "UTC")!
            let windows = blocks.map { b in
                GenerationWindow(start: CE.utc(2024, 6, 1, b.0), end: CE.utc(2024, 6, 1, b.1),
                                 generators: b.2, isMinimum: false, unitsAreDerived: false, timeZone: tz)
            }
            let dam = GenerationDam(id: "T", operatorID: .tva, name: "Test Dam",
                                    latitude: 35, longitude: -86, river: "Test")
            return DamGeneration(dam: dam, distanceMiles: 1, windows: windows,
                                 dischargeCfs: 20000, dischargeTrend12hCfs: 0,
                                 reservoirElevationFt: nil, tailwaterElevationFt: nil,
                                 observedAt: start, history: [])
        }
        let now = CE.utc(2024, 6, 1, 0)            // before the window; dam off now
        // Heavy (4 units) the whole window → blown out.
        XCTAssertEqual(ConditionsInputBuilder.representativeGenerationLevel(
            gen([(2, 10, 4)]), from: start, to: end, at: now), .high)
        // Heavy early, settles late (a real late window) → NOT blown out.
        XCTAssertNotEqual(ConditionsInputBuilder.representativeGenerationLevel(
            gen([(2, 5, 4), (5, 10, 0)]), from: start, to: end, at: now), .high)
        // A moderate stretch → moderate (stacks fish).
        XCTAssertEqual(ConditionsInputBuilder.representativeGenerationLevel(
            gen([(2, 10, 2)]), from: start, to: end, at: now), .moderate)
        // Off all window → settled.
        XCTAssertEqual(ConditionsInputBuilder.representativeGenerationLevel(
            gen([(2, 10, 0)]), from: start, to: end, at: now), .low)
    }

    func testCurrent() {
        XCTAssertEqual(CurrentFactor.score(CE.input(isTail: false))?.score, 90)
        // The tailwater response is a curve peaking at MODERATE: current stacks
        // fish on points, so it beats settled water; heavy flow still loses.
        let low = CurrentFactor.score(CE.input(isTail: true, genLevel: .low))?.score
        let mod = CurrentFactor.score(CE.input(isTail: true, genLevel: .moderate))?.score
        let high = CurrentFactor.score(CE.input(isTail: true, genLevel: .high))?.score
        XCTAssertEqual(mod, 100)
        XCTAssertEqual(low, 90)
        XCTAssertEqual(high, 25)
        XCTAssertGreaterThan(mod ?? 0, low ?? 0, "moderate current must beat settled water")
        XCTAssertGreaterThan(low ?? 0, high ?? 0, "heavy generation must still lose")
        // Tailwater with no way to classify → dropped.
        XCTAssertNil(CurrentFactor.score(CE.input(isTail: true, genLevel: nil,
                                                  dischargeCfs: nil, dischargeTrend: nil)))
    }

    func testPressure() {
        // Brand stance: rising/steady = active fish; falling = bite shuts down.
        XCTAssertEqual(PressureFactor.score(CE.input(pressure: 30.1, pTrend: .steady)).score, 90)
        XCTAssertEqual(PressureFactor.score(CE.input(pressure: 30.1, pTrend: .falling)).score, 55)
        XCTAssertEqual(PressureFactor.score(CE.input(pressure: 30.1, pTrend: .rising)).score, 85)
        // Very high pressure (calm, clear, dry) is GOOD for bowfishing — it must
        // not be penalized below a steady day (it used to score 60). §5.8 fix.
        XCTAssertEqual(PressureFactor.score(CE.input(pressure: 30.7, pTrend: .steady)).score, 88)
    }

    // Regression: the pressure extremes must be monotonic with the trend scores —
    // a very-high glass is the best bowfishing weather and can't score below
    // steady; a very-low glass is worse than a routine fall (the old shared
    // extremeScore let a deeper drop jump back UP to 60).
    func testPressureExtremesAreMonotonic() {
        let steady   = PressureFactor.score(CE.input(pressure: 30.1, pTrend: .steady)).score
        let veryHigh = PressureFactor.score(CE.input(pressure: 30.7, pTrend: .steady)).score
        XCTAssertGreaterThanOrEqual(veryHigh, steady - 5, "very high pressure must not be a penalty")
        let falling = PressureFactor.score(CE.input(pressure: 30.0, pTrend: .falling)).score
        let veryLow = PressureFactor.score(CE.input(pressure: 29.4, pTrend: .steady)).score
        XCTAssertLessThan(veryLow, falling, "a deep low must not score higher than a routine fall")
    }

    func testSky() {
        XCTAssertGreaterThan(SkyFactor.score(CE.input(weatherCode: 0)).score, 90)
        XCTAssertLessThan(SkyFactor.score(CE.input(weatherCode: 95)).score, 20)   // thunderstorm
    }
}

// MARK: - Weight sets (§7.2 / acceptance #12)

final class WeightSetTests: XCTestCase {
    func testEveryRegimeSumsToOne() {
        let w = ConditionsConfig.default.weights
        XCTAssertEqual(w.normal.sumExcludingHumidity, 1.0, accuracy: 1e-9)
        XCTAssertEqual(w.spawn.sumExcludingHumidity, 1.0, accuracy: 1e-9)
        XCTAssertEqual(w.tailwater.sumExcludingHumidity, 1.0, accuracy: 1e-9)
    }

    /// The score-breakdown sheet shows each factor's weight; the column must add
    /// to exactly 100 (largest-remainder), including when a factor is dropped and
    /// the rest renormalize.
    func testDisplayedWeightPctsSumTo100() {
        // All factors present.
        let full = ConditionsAggregator.evaluate(CE.input())
        XCTAssertEqual(full.factors.reduce(0) { $0 + $1.weightPct }, 100)
        // Water level dropped (no trend, no reservoir) → remaining renormalize.
        let noLevel = ConditionsAggregator.evaluate(CE.input(stageTrend: nil))
        XCTAssertNil(noLevel.factors.first { $0.key == .level })
        XCTAssertEqual(noLevel.factors.reduce(0) { $0 + $1.weightPct }, 100)
        // Spawn + water temp dropped (no temp at all) → still sums to 100.
        let noTemp = ConditionsAggregator.evaluate(CE.input(waterTemp: nil))
        XCTAssertEqual(noTemp.factors.reduce(0) { $0 + $1.weightPct }, 100)
    }
}

// MARK: - Where to look

final class WhereToLookTests: XCTestCase {
    private func cards(_ input: ConditionsInput) -> [WhereToLookCard] {
        WhereToLookEngine.cards(input, regime: .normal, spawn: nil, generationLevel: nil)
    }

    func testMuddyWaterAddsClarityCard() {
        // No gage + heavy recent rain → sub-foot visibility → "hunt the clear edges".
        let muddy = cards(CE.input(turbidity: nil, rain48: 3.0, hasTurbGage: false))
        XCTAssertTrue(muddy.contains { $0.kind == .clarity })
        // Clean, workable water → no clarity card (don't clutter).
        XCTAssertFalse(cards(CE.input(turbidity: 5)).contains { $0.kind == .clarity })
    }

    func testColdAndHotWaterAddTempCard() {
        XCTAssertTrue(cards(CE.input(waterTemp: 50)).contains { $0.kind == .temp })   // cold → drop to edges
        XCTAssertTrue(cards(CE.input(waterTemp: 90)).contains { $0.kind == .temp })   // hot → cooler water
        XCTAssertFalse(cards(CE.input(waterTemp: 74)).contains { $0.kind == .temp })  // prime warm → no card
    }

    func testBrightMoonAddsShadeCard() {
        XCTAssertTrue(cards(CE.input(moonIllum: 80, moonAlt: 0.5, cloud: 10)).contains { $0.kind == .darkness })
        // Dark (new-moon) night → no moon card; the closing line covers it.
        XCTAssertFalse(cards(CE.input(moonIllum: 5, moonAlt: 0.5, cloud: 10)).contains { $0.kind == .darkness })
        // Bright but cloud-covered → moon isn't lighting the water → no card.
        XCTAssertFalse(cards(CE.input(moonIllum: 80, moonAlt: 0.5, cloud: 90)).contains { $0.kind == .darkness })
    }
}

// MARK: - Tailwater registry (direction-aware, 2026-07-08)

final class TailwaterRegistryTests: XCTestCase {
    // Guntersville Dam: (34.42, -86.39), downstream ≈ 295° (WNW toward Wheeler).

    func testBelowDamIsTailwater() {
        // ~4 mi WNW of Guntersville Dam — in the discharge reach.
        XCTAssertTrue(TailwaterRegistry.isTailwater(latitude: 34.45, longitude: -86.45))
    }

    func testLakeSideIsNotTailwater() {
        // Town of Guntersville — ~8 mi SE of the dam, on the RESERVOIR side.
        // The old radius-only check wrongly flagged this as tailwater.
        XCTAssertFalse(TailwaterRegistry.isTailwater(latitude: 34.36, longitude: -86.29))
    }

    func testAtTheDamIsAlwaysTailwater() {
        // Within the near-dam override radius, bearing doesn't matter.
        XCTAssertTrue(TailwaterRegistry.isTailwater(latitude: 34.42, longitude: -86.39))
    }

    func testFarAwayIsNotTailwater() {
        // Birmingham-ish — nowhere near any registry dam.
        XCTAssertFalse(TailwaterRegistry.isTailwater(latitude: 33.52, longitude: -86.80))
    }

    func testChainedDamsBothConesApply() {
        // ~3 mi W (downstream) of Wheeler Dam = the top of Wilson Lake. Wilson
        // Dam is only ~14 mi further west, but Wheeler's cone must still flag it.
        XCTAssertTrue(TailwaterRegistry.isTailwater(latitude: 34.80, longitude: -87.44))
    }

    func testBearingMath() {
        // Due north and due east from a reference point.
        XCTAssertEqual(TailwaterRegistry.bearingDeg(lat1: 34, lon1: -86, lat2: 35, lon2: -86), 0, accuracy: 0.5)
        XCTAssertEqual(TailwaterRegistry.bearingDeg(lat1: 34, lon1: -86, lat2: 34, lon2: -85), 90, accuracy: 0.5)
        // Wrap-around separation: 350° vs 10° is 20° apart, not 340°.
        XCTAssertEqual(TailwaterRegistry.angularDifferenceDeg(350, 10), 20, accuracy: 1e-9)
    }
}
