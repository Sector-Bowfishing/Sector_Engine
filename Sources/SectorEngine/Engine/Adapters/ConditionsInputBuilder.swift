//
//  ConditionsInputBuilder.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Adapter layer: turns the app's already-fetched readings (WeatherService /
//  WaterLevelService) plus locally-computed astronomy into the engine's
//  normalized ConditionsInput. Synchronous — all astronomy is local math and
//  the TVA generation read arrives with the other readings — so callers fetch
//  concurrently, then build + evaluate without another await. §2 / §4.
//
//  This is the only conditions file that touches app/framework types
//  (CoreLocation, WeatherReading, WaterLevelReading); the engine proper stays
//  Foundation-only.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

public enum ConditionsInputBuilder {

    private static let hPaToInHg = 0.0295299830714

    /// Default light-pollution assumption (0 = pristine dark … 1 = heavy skyglow)
    /// until a real light-pollution layer exists. Mid-low: most bowfishing waters
    /// are rural-ish. Drives whether cloud cancels the moon. §5.3.
    public static var defaultCityGlow: Double = 0.3

    /// USGS gages go offline; a reading hours old must not be trusted as "now".
    /// Beyond these ages a reading is dropped (the dependent factor drops + the
    /// missing-data confidence penalty applies). Stage/discharge move fast; temp
    /// and turbidity move slowly, so they get a longer leash.
    public static var stageDischargeMaxAgeHours: Double = 3
    public static var tempTurbidityMaxAgeHours: Double = 6

    /// Turbidity is hyper-local — it describes THIS water body, not the region.
    /// USGS turbidity coverage is sparse, so `nearestTurbidity` will happily
    /// return a gage tens of miles away on a different river; a clear reading
    /// from another watershed then silently overrides the local rain signal.
    /// Beyond this distance we drop the gage and let the rain-decay fallback
    /// drive clarity (and confidence drops for the missing gage). Proxy for
    /// same-waterbody matching until a real hydro-network layer exists. §5.1.
    public static var maxTurbidityDistanceMiles: Double = 10

    /// Water temperature is hyper-local too. A live 00010 gage tens of miles off
    /// on a different river isn't "this water's temp"; beyond this we drop it and
    /// fall to the modeled estimate, which at least tracks THIS location's air.
    /// Matches turbidity's same-waterbody proxy.
    public static var maxWaterTempDistanceMiles: Double = 15

    /// Build a normalized input for one night at `coordinate`, plus a record of
    /// where each value came from.
    ///
    /// The provenance is assembled from decisions this function ALREADY makes —
    /// which readings were dropped as stale, which as too distant, whether the
    /// water temperature came from a gage or the model — and previously threw
    /// away. Nothing in the scoring path reads it, so it cannot move a score.
    ///
    /// - waterTemp: a USGS 00010 reading in **°C** (converted here), or nil.
    static func buildDetailed(coordinate: CLLocationCoordinate2D,
                      date: Date = Date(),
                      weather: WeatherReading?,
                      water: WaterLevelReading?,
                      discharge: WaterLevelReading?,
                      waterTempC: WaterLevelReading?,
                      modeledWaterTempF: Double? = nil,
                      turbidity: WaterLevelReading?,
                      generation: DamGeneration? = nil,
                      alertWindFloorMph: Double? = nil,
                      severeWarningLabel: String? = nil,
                      forecastDayIndex: Int = 0,
                      cityGlow: Double? = nil,
                      rainWatershed72hIn: Double? = nil)
                      -> (input: ConditionsInput, provenance: EnvironmentProvenance) {

        let lat = coordinate.latitude, lon = coordinate.longitude
        let region = RegionResolver.region(latitude: lat, longitude: lon)

        var prov: [String: EnvironmentProvenance.Entry] = [:]
        func record(_ variable: String, _ origin: EnvironmentProvenance.Origin,
                    observedAt: Date? = nil,
                    coverage: EnvironmentProvenance.Coverage = .unknown,
                    quality: Double) {
            prov[variable] = .init(variable: variable, origin: origin,
                                   observedAt: observedAt, ingestedAt: date,
                                   coverage: coverage, quality: quality)
        }

        /// A gage reading, kept only if fresh and near enough — and recorded
        /// either way, because "there was a reading but it was 6 hours old" is a
        /// different fact from "there is no gage here".
        func usable(_ r: WaterLevelReading?, as variable: String,
                    maxAgeHours: Double, maxMiles: Double? = nil) -> WaterLevelReading? {
            guard let r else {
                record(variable, .unavailable(.noSourceExists), quality: 0)
                return nil
            }
            let ageHours = date.timeIntervalSince(r.dateTime) / 3600
            if ageHours > maxAgeHours {
                record(variable, .unavailable(.tooOld(hours: ageHours)),
                       observedAt: r.dateTime, quality: 0)
                return nil
            }
            if let cap = maxMiles, let miles = r.distanceMiles, miles > cap {
                record(variable, .unavailable(.tooFar(miles: miles)),
                       observedAt: r.dateTime, quality: 0)
                return nil
            }
            // Freshness and proximity both erode usefulness; neither is binary
            // once inside the cap.
            let freshness = 1 - min(1, ageHours / maxAgeHours)
            let nearness = maxMiles.flatMap { cap in
                r.distanceMiles.map { 1 - min(1, $0 / cap) }
            } ?? 1
            record(variable, .measured(siteCode: r.siteCode), observedAt: r.dateTime,
                   coverage: .point(latitude: r.latitude, longitude: r.longitude,
                                    radiusMiles: r.distanceMiles),
                   quality: max(0.1, 0.5 + 0.3 * freshness + 0.2 * nearness))
            return r
        }

        let water = usable(water, as: "stageFt", maxAgeHours: stageDischargeMaxAgeHours)
        let discharge = usable(discharge, as: "dischargeCfs",
                               maxAgeHours: stageDischargeMaxAgeHours)
        // Fresh AND nearby, same as turbidity — a temp gage on another watershed
        // is not this water. Beyond the cap we use the modeled estimate.
        let waterTempC = usable(waterTempC, as: "waterTempF",
                                maxAgeHours: tempTurbidityMaxAgeHours,
                                maxMiles: maxWaterTempDistanceMiles)
        // Turbidity also has to be *nearby* — a fresh reading from another
        // watershed is worse than useless because it overrides the rain signal.
        let turbidity = usable(turbidity, as: "turbidityFNU",
                               maxAgeHours: tempTurbidityMaxAgeHours,
                               maxMiles: maxTurbidityDistanceMiles)

        // Astronomy (local, no network).
        let sun = Astronomy.sunEvents(on: date, lat: lat, lon: lon)
        let moonIllum = Astronomy.moonIllumination(on: date) * 100
        let moonRS = Astronomy.moonRiseSet(on: date, lat: lat, lon: lon)

        // Fishing window: from true dark (or sunset + ~80 min) to sunrise.
        //
        // ⚠️ `sun.sunrise` is TODAY's sunrise, which by definition has already
        // happened once it's dark — so the naive window ended ~15 hours BEFORE
        // it started. `moonAltitudeFraction` has a `guard end > start` that
        // then sampled one instant instead of the night, and that instant was
        // usually before moonrise → presence 0.000 → "moon down" → Darkness
        // scored Prime on nights the moon was up and 80% lit.
        // The night runs into TOMORROW: roll the end forward a day whenever it
        // isn't after the start.
        let windowStart = sun.astronomicalDusk
            ?? sun.sunset.map { $0.addingTimeInterval(80 * 60) }
        let rawWindowEnd = sun.sunrise
            ?? windowStart?.addingTimeInterval(8 * 3600)
        let windowEnd: Date? = {
            guard let start = windowStart, let end = rawWindowEnd else { return rawWindowEnd }
            return end > start ? end : end.addingTimeInterval(24 * 3600)
        }()
        let moonAltFrac: Double
        if let s = windowStart, let e = windowEnd {
            moonAltFrac = Astronomy.moonAltitudeFraction(from: s, to: e, lat: lat, lon: lon)
        } else {
            moonAltFrac = 0
        }

        // Fog risk: the smallest air–dewpoint spread forecast during the window.
        // Fog forms as the air cools to its dew point; the tightest spread of the
        // night is when it's most likely. Read off the same hourly series the
        // detail sheet uses, so the fog factor and the humidity sheet agree.
        let fogSpreadF: Double? = {
            guard let s = windowStart, let e = windowEnd, let hrs = weather?.hourlyConditions
            else { return nil }
            let spreads = hrs
                .filter { $0.date >= s && $0.date <= e }
                .compactMap { h -> Double? in
                    guard let t = h.tempF, let dp = h.dewPointF else { return nil }
                    return t - dp
                }
            return spreads.min()
        }()

        // Water temperature: prefer a live nearby gage (°C → °F). Otherwise the
        // MODELED estimate — a 5-day thermal lag of daily-mean air temp, which
        // is what ~90% of users see because lake temp gages barely exist. Only
        // if even that's unavailable do we fall back to raw air temp. Anything
        // but the gage is flagged estimated (damps spawn, lowers confidence). §3.
        let liveWaterTempF = waterTempC.map { $0.value * 9 / 5 + 32 }
        let airF = weather?.temperature
        let waterTempF = liveWaterTempF ?? modeledWaterTempF ?? airF
        let waterTempEstimated = liveWaterTempF == nil && waterTempF != nil
        // Overwrite the gage entry only when the gage did NOT win, so the record
        // names the layer that actually produced the number.
        if liveWaterTempF == nil {
            if modeledWaterTempF != nil {
                record("waterTempF", .modelled("thermalLagEWMA k=\(WaterTemperatureService.defaultK)"),
                       coverage: .lakeWide, quality: 0.55)
            } else if airF != nil {
                record("waterTempF", .derived("airTemperatureFallback"),
                       coverage: .lakeWide, quality: 0.2)
            }
        }

        let isTailwater = TailwaterRegistry.isTailwater(latitude: lat, longitude: lon)

        // Generation is kept whenever we have it for today, tailwater or not.
        //
        // It USED to be discarded unless `isTailwater`, which needs the spot to
        // sit inside the dam's downstream cone. Pick Pickwick Lake and you're on
        // the RESERVOIR — outside that cone — so the engine threw away the
        // generation the snapshot had already fetched, the tile fell through to
        // "Lake / pond", and the row underneath cheerfully showed Pickwick
        // running 2 units. Same screen, two answers.
        //
        // `isTailwater` still decides how much it MATTERS (see CurrentFactor);
        // it no longer decides whether we know.
        let generation = forecastDayIndex == 0 ? generation : nil
        // The dam's own release beats a USGS gage that may be tens of miles
        // downstream of the powerhouse — but only BELOW the dam. On the
        // reservoir the release isn't this water's discharge, so it must not
        // stand in for the gage.
        let dischargeCfs = (isTailwater ? generation?.dischargeCfs : nil) ?? discharge?.value
        let dischargeTrend = (isTailwater ? generation?.dischargeTrend12hCfs : nil) ?? discharge?.change

        // Strongest GUST forecast during the shootable window. A steady 6 mph
        // night that gusts to 22 intermittently kills the downward sightline and
        // blows the boat off the fish — it must score below a flat 6 mph night,
        // which it couldn't when gust was always nil. §5.4.
        let windGustMph: Double? = {
            guard let s = windowStart, let e = windowEnd, let hrs = weather?.hourlyConditions else { return nil }
            return hrs.filter { $0.date >= s && $0.date <= e }.compactMap(\.gustMph).max()
        }()

        // Reservoir POOL trend from the dam's OWN history — the real level of the
        // water you're standing on, not a USGS river-stage gage tens of miles
        // off. Only when the history actually carries pool elevations (TVA does;
        // CWMS observed-only carries discharge but not a pool series). §5.6.
        let reservoirTrend12hFt: Double? = {
            guard let g = generation else { return nil }
            let pts = g.history.compactMap { o in o.reservoirFt.map { (o.at, $0) } }.sorted { $0.0 < $1.0 }
            guard pts.count >= 2, let last = pts.last else { return nil }
            let cutoff = last.0.addingTimeInterval(-12 * 3600)
            guard let baseline = pts.last(where: { $0.0 <= cutoff }) ?? pts.first, baseline.0 != last.0 else { return nil }
            return last.1 - baseline.1
        }()

        // Generation level resolved across the REMAINING fishing window, not the
        // instant `now`. A dam off at 5 PM but scheduled to run heavy 9 PM–5 AM
        // will blow out the whole night — sampling only `now` reads it Prime,
        // which is wrong AND dangerous (the high-gen gate never fires). §5.7.
        let windowGenLevel = representativeGenerationLevel(
            generation,
            from: windowStart.map { Swift.max($0, date) },
            to: windowEnd, at: date)

        // A live NWS severe-wind WARNING outranks the smoothed forecast wind: a
        // Tornado / Severe Thunderstorm / High Wind Warning means dangerous gusts
        // happening NOW that the hourly model routinely misses. Applied HERE in the
        // shared builder — not post-hoc on the gauge — so every surface (gauge,
        // 7-night tonight, lake alerts, trips) scores the same night identically.
        let windMph = Swift.max(weather?.windSpeed ?? 0, alertWindFloorMph ?? 0)
        let effectiveGust = alertWindFloorMph.map { Swift.max(windGustMph ?? 0, $0) } ?? windGustMph

        // Weather is one model grid cell. Measured at Guntersville: identical
        // wind and cloud at 0 m, 200 m and 1 km, changing only at ~5 km — so
        // `lakeWide` is a finding, not a shortcut.
        if let w = weather {
            record("weather", .modelled("openMeteo"), observedAt: w.time,
                   coverage: .grid(approxKm: 3), quality: 0.8)
        } else {
            record("weather", .unavailable(.fetchFailed), quality: 0)
        }
        if let rain = rainWatershed72hIn {
            record("rainWatershed72hIn", .measured(siteCode: "MRMS"),
                   coverage: .watershed(approxMiles: 24),
                   quality: rain >= 0 ? 0.7 : 0.7)
        } else {
            record("rainWatershed72hIn", .unavailable(.fetchFailed), quality: 0)
        }
        if let g = generation {
            record("generationLevel", .measured(siteCode: g.dam.id),
                   observedAt: g.history.last?.at, coverage: .lakeWide,
                   quality: g.hasSchedule ? 0.9 : 0.6)
        } else {
            record("generationLevel", .unavailable(.notApplicableHere), quality: 0)
        }
        if severeWarningLabel != nil {
            record("severeWarningLabel", .measured(siteCode: "NWS"),
                   coverage: .lakeWide, quality: 1.0)
        }

        let input = ConditionsInput(
            date: date, latitude: lat, longitude: lon, region: region,
            windMph: windMph,
            windGustMph: effectiveGust,
            windDirDeg: weather?.windDirection ?? 0,
            airTempF: airF ?? 60,
            cloudPct: weather?.cloudCover ?? 0,
            humidityPct: Double(weather?.humidity ?? 50),
            pressureInHg: (weather?.pressure ?? 1016) * hPaToInHg,
            // Score off the NWS 3-hour tendency (the same trend the pressure
            // detail sheet + chart show), NOT the 12h endpoint delta — otherwise a
            // dip-and-recover day reads "steady/Prime" in the score while the sheet
            // (and chart) clearly show it rising. Keeps the two consistent.
            pressureTrend: movement(weather?.displayPressureTrend),
            pressureChange12hInHg: (weather?.pressureChange ?? 0) * hPaToInHg,
            weatherCode: weather?.weatherCode ?? 0,
            precipitationInchNow: weather?.precipitation ?? 0,
            severeWarningLabel: severeWarningLabel,
            cityGlowFactor: cityGlow ?? defaultCityGlow,
            waterTempF: waterTempF,
            waterTempEstimated: waterTempEstimated,
            stageFt: water?.value,
            stageTrend12hFt: water?.change,
            dischargeCfs: dischargeCfs,
            dischargeTrend12hCfs: dischargeTrend,
            turbidityFNU: turbidity?.value,
            turbidityType: .unknown,
            rainLast48hIn: weather?.recentRainfall ?? 0,
            rainWatershed72hIn: rainWatershed72hIn,
            rainDataAvailable: rainWatershed72hIn != nil || weather != nil,
            isTailwater: isTailwater,
            reservoirElevationFt: generation?.reservoirElevationFt,
            reservoirTrend12hFt: reservoirTrend12hFt,
            fogSpreadF: fogSpreadF,
            generationLevel: windowGenLevel,
            hasGenerationForecast: generation?.hasSchedule ?? false,
            sunset: sun.sunset, sunrise: sun.sunrise,
            civilDusk: sun.civilDusk, astronomicalDusk: sun.astronomicalDusk,
            moonIllumPct: moonIllum, moonrise: moonRS.rise, moonset: moonRS.set,
            moonAltitudeAtWindow: moonAltFrac,
            windowStart: windowStart, windowEnd: windowEnd,
            hasTurbidityGage: turbidity != nil,
            forecastDayIndex: forecastDayIndex)

        return (input, EnvironmentProvenance(entries: prov))
    }

    /// The scoring path's entry point — unchanged behaviour, provenance discarded.
    static func build(coordinate: CLLocationCoordinate2D,
                      date: Date = Date(),
                      weather: WeatherReading?,
                      water: WaterLevelReading?,
                      discharge: WaterLevelReading?,
                      waterTempC: WaterLevelReading?,
                      modeledWaterTempF: Double? = nil,
                      turbidity: WaterLevelReading?,
                      generation: DamGeneration? = nil,
                      alertWindFloorMph: Double? = nil,
                      severeWarningLabel: String? = nil,
                      forecastDayIndex: Int = 0,
                      cityGlow: Double? = nil,
                      rainWatershed72hIn: Double? = nil) -> ConditionsInput {
        buildDetailed(coordinate: coordinate, date: date, weather: weather,
                      water: water, discharge: discharge, waterTempC: waterTempC,
                      modeledWaterTempF: modeledWaterTempF, turbidity: turbidity,
                      generation: generation, alertWindFloorMph: alertWindFloorMph,
                      severeWarningLabel: severeWarningLabel,
                      forecastDayIndex: forecastDayIndex, cityGlow: cityGlow,
                      rainWatershed72hIn: rainWatershed72hIn).input
    }

    /// The generation level that best represents the REMAINING fishing window.
    /// Samples the forward schedule hour by hour (unit counts): ≥2 h of heavy
    /// flow flags the night heavy (blown out + the gate fires); otherwise the
    /// level that dominates the window (moderate stacks fish and wins ties, since
    /// it's the best of it); otherwise settled. Falls back to the observed
    /// instant when no schedule covers the window (e.g. a CWMS observed-only dam).
    static func representativeGenerationLevel(_ g: DamGeneration?,
                                              from: Date?, to: Date?,
                                              at now: Date) -> GenerationLevel? {
        guard let g else { return nil }
        guard let start = from, let end = to, end > start else { return g.level(at: now) }
        var highHours = 0, modHours = 0, lowHours = 0, sawSchedule = false
        var t = start
        while t <= end {
            if let units = g.generators(at: t) {
                sawSchedule = true
                if units >= 3 { highHours += 1 }
                else if units >= 1 { modHours += 1 }
                else { lowHours += 1 }
            }
            t = t.addingTimeInterval(3600)
        }
        guard sawSchedule else { return g.level(at: now) }  // schedule doesn't cover the window
        // Blown out only when there's no SAFE (non-heavy) stretch to fish — heavy
        // generation across the whole window is dangerous fast water and the gate
        // should fire. If a safe window exists, score the night by its BEST safe
        // flow (moderate stacks fish); the per-hour window curve still shows the
        // heavy hours as low. This keeps a "heavy early, settles late" night from
        // reading blown-out when its late window is prime.
        let safeHours = modHours + lowHours
        if safeHours < 2 { return .high }
        if modHours >= 2 { return .moderate }
        return .low
    }

    private static func movement(_ t: PressureTrend?) -> PressureMovement {
        switch t {
        case .rising:  return .rising
        case .falling: return .falling
        default:       return .steady
        }
    }
}
