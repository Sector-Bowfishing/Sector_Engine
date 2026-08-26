//
//  ConditionsAggregatorTests.swift
//  SectorTests
//
//  The §12 acceptance criteria for the Bowfishing Conditions Engine v2 — the
//  twelve end-to-end scenarios that gate the rework. Uses the shared CE.input
//  builder from ConditionsFactorTests.
//

import XCTest
import CoreLocation
@testable import SectorEngine

final class ConditionsAggregatorTests: XCTestCase {

    private func eval(_ i: ConditionsInput) -> ConditionsResult { ConditionsAggregator.evaluate(i) }

    // 1. Blown-out gate: 120 FNU, everything else perfect → ≤25, Poor, gate surfaced.
    func test01_blownOutGate() {
        let r = eval(CE.input(turbidity: 120))
        XCTAssertLessThanOrEqual(r.score, 25)
        XCTAssertEqual(r.band, .poor)
        XCTAssertTrue(r.isCapped)
        XCTAssertTrue(r.primaryGate?.reason.contains("blown out") ?? false)
        XCTAssertTrue(r.topReasons.first?.contains("Capped") ?? false)
    }

    // 2. Spawn night beats a clear calm non-spawn night (identical clarity/wind).
    func test02_spawnBeatsNonSpawn() {
        let spawn = eval(CE.input(date: CE.utc(2024, 5, 15, 2), waterTemp: 65))   // carp spawn, South
        let cold  = eval(CE.input(date: CE.utc(2024, 3, 15, 2), waterTemp: 55))   // March, cold
        XCTAssertGreaterThan(spawn.score, cold.score + 10)
        XCTAssertEqual(spawn.regime, .spawn)
        XCTAssertEqual(spawn.spawnSpeciesName, "Common carp")
        XCTAssertNotEqual(cold.regime, .spawn)
    }

    // 3. Full moon overridden in spawn regime; drags a non-spawn night down.
    func test03_fullMoonOverriddenInSpawn() {
        let spawnFullMoon = eval(CE.input(waterTemp: 65, moonIllum: 100, moonAlt: 0.9, cloud: 0))
        let noSpawnFullMoon = eval(CE.input(date: CE.utc(2024, 3, 15, 2), waterTemp: 55,
                                            moonIllum: 100, moonAlt: 0.9, cloud: 0))
        XCTAssertGreaterThanOrEqual(spawnFullMoon.score, 60)          // still Good/Prime
        XCTAssertEqual(spawnFullMoon.regime, .spawn)
        XCTAssertGreaterThan(spawnFullMoon.score, noSpawnFullMoon.score)
    }

    // 4. Moon-altitude logic: 100% illum but moon set for the window → dark water.
    func test04_moonAltitude() {
        let down = DarknessFactor.score(CE.input(moonIllum: 100, moonAlt: 0.05, cloud: 0))
        let up   = DarknessFactor.score(CE.input(moonIllum: 100, moonAlt: 0.95, cloud: 0))
        XCTAssertGreaterThan(down.score, 80)
        XCTAssertGreaterThan(down.score, up.score + 40)
    }

    // 5. Cloud cancels moon away from the city, not near it (darkness factor).
    func test05_cloudCancelsMoonRuralOnly() {
        let rural = DarknessFactor.score(CE.input(moonIllum: 100, moonAlt: 0.9, cloud: 90, cityGlow: 0.0))
        let city  = DarknessFactor.score(CE.input(moonIllum: 100, moonAlt: 0.9, cloud: 90, cityGlow: 1.0))
        XCTAssertGreaterThan(rural.score, 70)
        XCTAssertLessThan(city.score, 45)
    }

    // 6. Tailwater generation cap: high gen ≤30 + "seams" card; low gen Prime-eligible + "roam".
    func test06_tailwaterGenerationCap() {
        let high = eval(CE.input(lat: 35.10, lon: -85.23, isTail: true, genLevel: .high, hasGenFc: true))
        let low  = eval(CE.input(lat: 35.10, lon: -85.23, isTail: true, genLevel: .low,  hasGenFc: true))
        XCTAssertLessThanOrEqual(high.score, 30)
        XCTAssertTrue(high.whereToLook.contains { $0.body.contains("seams") })
        XCTAssertGreaterThanOrEqual(low.score, 80)
        XCTAssertTrue(low.whereToLook.contains { $0.title.contains("roaming") || $0.body.contains("roam") })
    }

    // 6b. Severe-weather safety gate: an active NWS warning caps a Prime-looking
    // night. This is the fix for the score reading 81/PRIME with a squall line
    // overhead — the forecast-only storm gate missed it; a warning does not.
    func test06b_severeWarningGate() {
        // Dark, calm, clear, warm water — would otherwise score Good/Prime.
        let base = CE.input(wind: 2, waterTemp: 78, moonIllum: 0, cloud: 15)
        let clear = eval(base)
        XCTAssertGreaterThanOrEqual(clear.score, 65)
        let warned = eval(CE.input(wind: 2, waterTemp: 78, moonIllum: 0, cloud: 15,
                                   severeWarning: "Severe Thunderstorm Warning"))
        XCTAssertLessThanOrEqual(warned.score, 30)
        XCTAssertLessThan(warned.score, clear.score)
        XCTAssertTrue(warned.primaryGate?.reason.contains("Severe Thunderstorm Warning") ?? false)
    }

    // Fog gate: a Prime-looking night that fogs in (tight air–dewpoint spread) caps
    // hard; a moderate spread soft-caps below Prime; a wide spread doesn't gate. This
    // is the fix for a foggy night still reading 81/GOOD.
    func testFogGate() {
        // Dark, calm, clear, warm water — would otherwise score Good/Prime.
        let base = { (spread: Double?) in
            CE.input(wind: 2, waterTemp: 78, moonIllum: 0, cloud: 15, fogSpread: spread)
        }
        let clear = eval(base(8))                          // wide margin — no fog
        XCTAssertGreaterThanOrEqual(clear.score, 65)       // still Good/Prime
        XCTAssertFalse(clear.primaryGate?.reason.contains("Fog") ?? false)

        let foggy = eval(base(1.5))                        // fog likely
        XCTAssertLessThanOrEqual(foggy.score, 35)
        XCTAssertTrue(foggy.isCapped)
        XCTAssertTrue(foggy.primaryGate?.reason.contains("Fog likely") ?? false)
        XCTAssertLessThan(foggy.score, clear.score)

        let patchy = eval(base(3))                         // patchy fog late
        XCTAssertLessThanOrEqual(patchy.score, 62)         // never Prime
        XCTAssertGreaterThan(patchy.score, foggy.score)    // softer than fog-likely
    }

    // The fog gate only fires with a dewpoint series — a nil spread never gates on fog
    // (raw RH alone is too noisy; it stays a factor-only nudge).
    func testFogGateNeedsDewpointSeries() {
        let noSeries = eval(CE.input(wind: 2, waterTemp: 78, moonIllum: 0, cloud: 15, fogSpread: nil))
        XCTAssertFalse(noSeries.primaryGate?.reason.contains("Fog") ?? false)
    }

    // 6c. Code-independent rain gate: rain measurably falling NOW caps the night
    // even when the categorical weather code isn't a storm code (Open-Meteo's code
    // routinely mislabels or lags active rain).
    func test06c_rainNowGate() {
        // weatherCode 3 (overcast) is NOT a storm code, so the storm gate can't fire.
        let dry = eval(CE.input(wind: 2, waterTemp: 78, moonIllum: 0, cloud: 20, weatherCode: 3, precipNow: 0))
        XCTAssertGreaterThanOrEqual(dry.score, 65)
        let raining = eval(CE.input(wind: 2, waterTemp: 78, moonIllum: 0, cloud: 20, weatherCode: 3, precipNow: 0.2))
        XCTAssertLessThanOrEqual(raining.score, 40)
        XCTAssertTrue(raining.primaryGate?.reason.contains("Rain falling now") ?? false)
    }

    // 7. Algal vs sediment: same FNU, algal scores worse (~2× visibility hit).
    func test07_algalVsSediment() {
        let algal = eval(CE.input(turbidity: 40, turbType: .algal))
        let sed   = eval(CE.input(turbidity: 40, turbType: .sediment))
        XCTAssertLessThan(algal.score, sed.score)
    }

    // 8. Tier-3 (freshwater drum) never triggers Spawn regime / never recommended.
    func test08_tier3NeverSpawns() {
        let r = eval(CE.input(date: CE.utc(2024, 6, 15, 2), waterTemp: 70))
        XCTAssertNotEqual(r.spawnSpeciesName, "Freshwater drum")
        // A drum-only temperature/season can't create a spawn regime.
        let drumOnly = SpawnFactor.score(CE.input(date: CE.utc(2024, 6, 15, 2), waterTemp: 70))
        XCTAssertNotEqual(drumOnly.species?.name, "Freshwater drum")
    }

    // 9. Legality: protected species never auto-recommended; "check" species disclaim.
    func test09_legality() {
        for month in 3...8 {
            let r = eval(CE.input(date: CE.utc(2024, month, 15, 2), lat: 30, lon: -95, waterTemp: 62))
            XCTAssertNotEqual(r.spawnSpeciesName, "Paddlefish")
            XCTAssertNotEqual(r.spawnSpeciesName, "American shad")
        }
        // Alligator gar (check) leading → disclaimer flagged + present in the card.
        let gar = eval(CE.input(date: CE.utc(2024, 4, 25, 2), lat: 29.7, lon: -95.0,
                                waterTemp: 74, stageTrend: 0.9))
        if gar.spawnSpeciesName == "Alligator gar" {
            XCTAssertTrue(gar.spawnNeedsDisclaimer)
            XCTAssertTrue(gar.whereToLook.contains { $0.kind == .spawn && $0.body.contains("Verify") })
        }
    }

    // 10. Confidence: degraded data → Low; full live spawn data → High.
    func test10_confidence() {
        let low = eval(CE.input(waterTemp: 60, tempEst: true, turbidity: nil, hasTurbGage: false, fcDay: 6))
        XCTAssertEqual(low.confidenceBand, ConfidenceBand.low)
        let high = eval(CE.input(waterTemp: 65))
        XCTAssertEqual(high.confidenceBand, ConfidenceBand.high)
    }

    // 11. Missing data renormalizes: drop water temp → fewer factors, score sane, confidence drops.
    func test11_missingDataRenormalizes() {
        let full = eval(CE.input(waterTemp: 72))
        let dropped = eval(CE.input(waterTemp: nil))
        XCTAssertLessThan(dropped.factors.count, full.factors.count)   // spawn + waterTemp gone
        XCTAssertTrue((0...100).contains(dropped.score))
        XCTAssertLessThan(dropped.confidence, full.confidence)         // estimated/absent temp penalty
        // Active weights still sum to ~100 after renormalization.
        let sum = dropped.factors.reduce(0) { $0 + $1.weightPct }
        XCTAssertEqual(sum, 100, accuracy: 2)
    }

    // Consolidation regression: the tonight-window curve now runs through the same
    // engine as the gauge, so no hour can ever beat a gate-capped gauge, and a
    // clear night's best hour beats a blown-out night's. Also proves the 7-night
    // outlook goes through the engine (carries confidence).
    @MainActor
    func test16_forecastRunsThroughEngine() {
        let now = Date()
        let capped = Self.engineBase(turbidity: 120, now: now)   // blown out → Poor gauge
        let clear = Self.engineBase(turbidity: 5, now: now)      // clear
        let coord = CLLocationCoordinate2D(latitude: capped.latitude, longitude: capped.longitude)
        let r = Self.makeForecast(around: now)

        let cappedGauge = ConditionsAggregator.evaluate(capped).score
        let fcCapped = ConditionsForecastService.compute(r: r, base: capped, coordinate: coord, now: now)
        let fcClear = ConditionsForecastService.compute(r: r, base: clear, coordinate: coord, now: now)

        let cappedHours = fcCapped.tonight?.hours ?? []
        XCTAssertFalse(cappedHours.isEmpty, "tonight curve should be populated")
        XCTAssertTrue(cappedHours.allSatisfy { $0.score <= cappedGauge },
                      "no window hour may exceed the gate-capped gauge (\(cappedGauge))")

        let cappedMax = cappedHours.map(\.score).max() ?? 0
        let clearMax = fcClear.tonight?.hours.map(\.score).max() ?? 0
        XCTAssertGreaterThan(clearMax, cappedMax, "a clear night's best hour beats a blown-out night's")

        XCTAssertFalse(fcClear.nights.isEmpty, "7-night outlook should be produced")
        XCTAssertTrue(fcClear.nights.allSatisfy { (0...100).contains($0.score) && (0...100).contains($0.confidence) })
    }

    // MARK: forecast test fixtures

    private static func engineBase(turbidity: Double?, now: Date, hasGage: Bool = true) -> ConditionsInput {
        let lat = 34.0, lon = -86.0
        let sun = Astronomy.sunEvents(on: now, lat: lat, lon: lon)
        return ConditionsInput(
            date: now, latitude: lat, longitude: lon, region: .south,
            windMph: 2, windDirDeg: 180, airTempF: 75, cloudPct: 5, humidityPct: 60,
            pressureInHg: 30.0, pressureTrend: .steady, pressureChange12hInHg: 0, weatherCode: 0,
            precipitationInchNow: 0, cityGlowFactor: 0.3,
            waterTempF: 72, waterTempEstimated: false,
            turbidityFNU: turbidity, turbidityType: .unknown,
            sunset: sun.sunset, sunrise: sun.sunrise, civilDusk: sun.civilDusk, astronomicalDusk: sun.astronomicalDusk,
            moonIllumPct: Astronomy.moonIllumination(on: now) * 100, moonAltitudeAtWindow: 0.3,
            windowStart: sun.astronomicalDusk, windowEnd: sun.sunrise, hasTurbidityGage: hasGage)
    }

    /// `rain` maps a day offset relative to `now` (matching the -1...6 fixture
    /// range) to that day's precipitation_sum in inches.
    private static func makeForecast(around now: Date, rain: [Int: Double] = [:]) -> ForecastResponse {
        let cal = Calendar.current
        let hf = DateFormatter(); hf.locale = Locale(identifier: "en_US_POSIX"); hf.dateFormat = "yyyy-MM-dd'T'HH:mm"; hf.timeZone = .current
        let df = DateFormatter(); df.locale = Locale(identifier: "en_US_POSIX"); df.dateFormat = "yyyy-MM-dd"; df.timeZone = .current

        var times: [String] = [], winds: [Double?] = [], clouds: [Double?] = [], precs: [Double?] = [], codes: [Int?] = []
        for h in -6...30 {
            guard let d = cal.date(byAdding: .hour, value: h, to: now) else { continue }
            let hour = cal.date(bySetting: .minute, value: 0, of: d) ?? d
            times.append(hf.string(from: hour)); winds.append(2); clouds.append(0); precs.append(0); codes.append(0)
        }
        var days: [String] = [], dayRain: [Double?] = []
        for day in -1...6 {
            if let d = cal.date(byAdding: .day, value: day, to: now) {
                days.append(df.string(from: d)); dayRain.append(rain[day] ?? 0)
            }
        }
        let n = days.count
        let hourly = ForecastResponse.Hourly(time: times, wind_speed_10m: winds, cloud_cover: clouds,
                                             precipitation: precs, weather_code: codes)
        let daily = ForecastResponse.Daily(time: days,
                                           sunrise: days.map { $0 + "T06:00" }, sunset: days.map { $0 + "T20:00" },
                                           wind_speed_10m_max: Array(repeating: 2, count: n),
                                           weather_code: Array(repeating: 0, count: n),
                                           precipitation_sum: dayRain,
                                           cloud_cover_mean: Array(repeating: 0, count: n))
        return ForecastResponse(hourly: hourly, daily: daily)
    }

    // Regression: forecast rain must muddy that night's clarity. buildNights used
    // to leave rainLast48hIn frozen at today's observed value, so for no-gage
    // spots a soaking-wet forecast day scored identical to a bone-dry one.
    @MainActor
    func test18_futureRainMuddiesFutureClarity() {
        let now = Date()
        let base = Self.engineBase(turbidity: nil, now: now, hasGage: false)  // clarity runs on the rain fallback
        let coord = CLLocationCoordinate2D(latitude: base.latitude, longitude: base.longitude)

        let dry = ConditionsForecastService.compute(r: Self.makeForecast(around: now),
                                                    base: base, coordinate: coord, now: now)
        let wet = ConditionsForecastService.compute(r: Self.makeForecast(around: now, rain: [3: 2.0]),
                                                    base: base, coordinate: coord, now: now)
        guard dry.nights.count > 4, wet.nights.count > 4 else { return XCTFail("outlook too short") }

        func claritySub(_ n: NightScore) -> Int {
            n.factors.first { $0.key == FactorKey.clarity.rawValue }?.sub ?? -1
        }
        // 2" of rain on day +3 must tank that night's clarity and overall score.
        XCTAssertLessThan(claritySub(wet.nights[3]), claritySub(dry.nights[3]),
                          "a rainy forecast day must lower that night's clarity")
        XCTAssertLessThan(wet.nights[3].score, dry.nights[3].score,
                          "a rainy forecast day must lower that night's score")
        // And the mud lingers into the next night's recent-rain window.
        XCTAssertLessThan(claritySub(wet.nights[4]), claritySub(dry.nights[4]),
                          "runoff must still muddy the night after the rain")
    }

    // Regression (audit 2026-08-06): TONIGHT (nights[0]) MUST equal the live
    // gauge for the same location. It used to be scored from night-AVERAGED
    // forecast weather (evaluate(ni)) and so disagreed with the hero gauge and
    // the lake score strip (evaluate(base)); the outlook sheet papered over that
    // with a wrong-location graft, so a lake showed tonight=25 in its mini-card
    // and 87 in the sheet. Now the mini-card, sheet, strip and gauge share ONE
    // number because buildNights scores tonight from the same base.
    @MainActor
    func test20_tonightNightMatchesLiveGauge() {
        let now = Date()
        let base = Self.engineBase(turbidity: 5, now: now)
        let coord = CLLocationCoordinate2D(latitude: base.latitude, longitude: base.longitude)
        let fc = ConditionsForecastService.compute(r: Self.makeForecast(around: now),
                                                   base: base, coordinate: coord, now: now)
        let gauge = ConditionsAggregator.evaluate(base).score
        guard let tonight = fc.nights.first else { return XCTFail("no tonight night") }
        XCTAssertEqual(tonight.score, gauge,
                       "forecast tonight (nights[0]) must equal the live gauge score")
    }

    // Regression: the common no-gage case must not saturate green. A flawless
    // night on unknown water is capped by the estimated seeability ceiling and
    // reads below the same night with a real clear-water gage reading.
    func test19_noGageNightCantSaturate() {
        let noGage = eval(CE.input(turbidity: nil, hasTurbGage: false))
        let gage = eval(CE.input(turbidity: 2))

        XCTAssertLessThanOrEqual(Double(noGage.score),
                                 100 * ConditionsConfig.default.seeability.estimatedClarityComponentCap,
                                 "estimated clarity must cap the whole score")
        XCTAssertGreaterThan(gage.score, noGage.score, "measured clear water must beat unknown water")

        let claritySub = noGage.factors.first { $0.key == .clarity }?.score ?? 100
        XCTAssertLessThanOrEqual(Double(claritySub), ConditionsConfig.default.clarity.estimatedScoreCap)
    }

    // Regression: a turbidity gage in another watershed must NOT drive clarity.
    // Warrior, AL borrowed a gin-clear reading (1.6 FNU) from a gage 16 mi away
    // on the Cahaba River, which pinned clarity to Prime and buried the rain
    // signal. Beyond the distance cap the gage is dropped → clarity falls back
    // to the rain-decay estimate (and confidence drops for the missing gage).
    func test20_farTurbidityGageIsNotBorrowed() {
        let coord = CLLocationCoordinate2D(latitude: 33.8129, longitude: -86.8097)
        func turb(_ miles: Double) -> WaterLevelReading {
            WaterLevelReading(siteCode: "02423130", siteName: "CAHABA RIVER NEAR TRUSSVILLE",
                              parameterCode: "63680", parameterName: "Turbidity, FNU",
                              value: 1.6, unit: "FNU", dateTime: Date(),
                              latitude: 33.62, longitude: -86.60, trend: .steady, change: 0,
                              history: [], distanceMiles: miles)
        }
        let near = ConditionsInputBuilder.build(coordinate: coord, weather: nil, water: nil,
                                                discharge: nil, waterTempC: nil, turbidity: turb(3))
        let far = ConditionsInputBuilder.build(coordinate: coord, weather: nil, water: nil,
                                               discharge: nil, waterTempC: nil, turbidity: turb(16))

        XCTAssertEqual(near.turbidityFNU, 1.6)
        XCTAssertTrue(near.hasTurbidityGage, "a gage within the cap is used")
        XCTAssertNil(far.turbidityFNU, "a 16-mi gage in another basin must not be borrowed")
        XCTAssertFalse(far.hasTurbidityGage, "far gage dropped → no-gage → rain drives clarity + confidence drops")
    }

    // 12. Weight sets each sum to 1.0 in every regime.
    func test12_weightsSumToOne() {
        let w = ConditionsConfig.default.weights
        XCTAssertEqual(w.normal.sumExcludingHumidity, 1.0, accuracy: 1e-9)
        XCTAssertEqual(w.spawn.sumExcludingHumidity, 1.0, accuracy: 1e-9)
        XCTAssertEqual(w.tailwater.sumExcludingHumidity, 1.0, accuracy: 1e-9)
    }

    // Regression: the model must not saturate. A windy, murky, estimated-temp
    // night (the common no-gage case) cannot read Prime just because the other
    // factors default high — the seeability ceiling caps it.
    func test13_visibilityCeilingPreventsSaturation() {
        let murkyWindy = eval(CE.input(wind: 16, waterTemp: 80, tempEst: true,
                                       turbidity: nil, rain48: 1.2))
        XCTAssertLessThan(murkyWindy.score, 75, "can't see + chop must not score Prime")
        XCTAssertNotEqual(murkyWindy.band, .prime)

        // And a genuinely good calm/clear night should still beat it by a lot.
        let calmClear = eval(CE.input(wind: 2, waterTemp: 72, tempEst: false, turbidity: 5))
        XCTAssertGreaterThan(calmClear.score, murkyWindy.score + 20)
    }

    // A spawn call resting on an estimated (no-gage) water temp must never read
    // "High" confidence — we can't vouch for a spawn we're guessing the temp for.
    func test17_estimatedSpawnConfidenceNotHigh() {
        let r = eval(CE.input(date: CE.utc(2024, 5, 15, 2), waterTemp: 65, tempEst: true))
        if r.regime == .spawn {
            XCTAssertNotEqual(r.confidenceBand, ConfidenceBand.high)
        }
        // A live-gage spawn in a strong window still can.
        let live = eval(CE.input(date: CE.utc(2024, 5, 15, 2), waterTemp: 65, tempEst: false))
        XCTAssertEqual(live.confidenceBand, ConfidenceBand.high)
    }

    // Regression: a lone storm weather-code (Open-Meteo false positive) must NOT
    // gate the score; only a corroborated storm (real precip or heavy cloud) does.
    func test15_stormGateRequiresCorroboration() {
        let phantom = eval(CE.input(turbidity: 5, moonIllum: 0, cloud: 0,
                                    weatherCode: 95, precipNow: 0))
        XCTAssertFalse(phantom.gates.contains { $0.reason.contains("Thunderstorm") },
                       "clear, dry night with a false storm code must not be gated")
        XCTAssertGreaterThan(phantom.score, 40)

        let realByRain = eval(CE.input(cloud: 20, weatherCode: 95, precipNow: 0.1))
        XCTAssertTrue(realByRain.gates.contains { $0.reason.contains("Thunderstorm") })

        let realByCloud = eval(CE.input(cloud: 90, weatherCode: 95, precipNow: 0))
        XCTAssertTrue(realByCloud.gates.contains { $0.reason.contains("Thunderstorm") })
    }

    // Regression (gage-less leak): a COLD night on a gage-less lake must not read
    // Prime. The cold-water gate used to fire only on a LIVE temp, so a modeled/air
    // 40°F estimate on an otherwise flawless clear-calm-dark night blended to
    // green. An estimated cold temp now caps (softer than the live gate — it's a
    // guess); a warm estimate is left alone so the common case isn't over-capped.
    func test21_estimatedColdWaterCapsGagelessNight() {
        let g = ConditionsConfig.default.gates
        let coldEstimate = eval(CE.input(waterTemp: 40, tempEst: true, turbidity: 5))
        XCTAssertLessThanOrEqual(coldEstimate.score, Int(g.coldWaterEstimatedCap),
                                 "a gage-less cold night must not read above Fair")
        XCTAssertTrue(coldEstimate.gates.contains { $0.reason.contains("cold") })
        // A LIVE cold gage still caps harder than the estimate.
        let coldLive = eval(CE.input(waterTemp: 40, tempEst: false, turbidity: 5))
        XCTAssertLessThanOrEqual(coldLive.score, Int(g.coldWaterCap))
        // A WARM estimate is not gated — the fix must not over-cap the common case.
        let warmEstimate = eval(CE.input(waterTemp: 72, tempEst: true, turbidity: 5))
        XCTAssertFalse(warmEstimate.gates.contains { $0.reason.contains("cold") })
    }

    // Regression: spawn must not fire on a guessed (estimated) water temp the way
    // it does on a real gage reading.
    func test14_estimatedTempDampsSpawn() {
        let gage = SpawnFactor.score(CE.input(date: CE.utc(2024, 5, 15, 2), waterTemp: 65, tempEst: false))
        let est  = SpawnFactor.score(CE.input(date: CE.utc(2024, 5, 15, 2), waterTemp: 65, tempEst: true))
        XCTAssertGreaterThan(gage.intensity, est.intensity)
    }
}
