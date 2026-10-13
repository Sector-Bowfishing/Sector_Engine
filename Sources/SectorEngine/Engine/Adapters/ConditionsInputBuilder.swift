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

public enum ConditionsInputBuilder: Sendable {

    private static let hPaToInHg = 0.0295299830714

    /// Default light-pollution assumption (0 = pristine dark … 1 = heavy skyglow)
    /// until a real light-pollution layer exists. Mid-low: most bowfishing waters
    /// are rural-ish. Drives whether cloud cancels the moon. §5.3.
    public static let defaultCityGlow: Double = 0.3

    /// USGS gages go offline; a reading hours old must not be trusted as "now".
    /// Beyond these ages a reading is dropped (the dependent factor drops + the
    /// missing-data confidence penalty applies). Stage/discharge move fast; temp
    /// and turbidity move slowly, so they get a longer leash.
    public static let stageDischargeMaxAgeHours: Double = 3
    public static let tempTurbidityMaxAgeHours: Double = 6

    /// Turbidity is hyper-local — it describes THIS water body, not the region.
    /// A clear reading from another watershed silently overrides the local rain
    /// signal, so beyond this distance the gage is dropped and the rain-decay
    /// fallback drives clarity (and confidence drops for the missing gage). §5.1.
    ///
    /// Which water a gage measures is now decided upstream by GaugeSelector (role
    /// + water context); this cap is the second line of defense, for the legacy
    /// nearest path and for any caller that hands the builder a raw reading.
    public static let maxTurbidityDistanceMiles: Double = 10

    /// Water temperature is hyper-local too. A live 00010 gage tens of miles off
    /// on a different river isn't "this water's temp"; beyond this we drop it and
    /// fall to the modeled estimate, which at least tracks THIS location's air.
    /// Also a second line of defense behind GaugeSelector — except for a gage the
    /// selector proved sits on this lake's own pool, which may be farther (see
    /// `GaugeSelector.matchedPoolTempMaxMiles`).
    public static let maxWaterTempDistanceMiles: Double = 15

    /// Whether a reading survives the builder's own caps: freshness for every
    /// input, plus plausibility and distance for temp and distance for turbidity.
    /// Shared with the API's clarityGauges so "driving" means exactly "this
    /// builder would use it".
    static func passesCaps(_ r: WaterLevelReading, kind: GaugeKind, at date: Date) -> Bool {
        let maxAgeHours = kind == .level || kind == .discharge ? stageDischargeMaxAgeHours : tempTurbidityMaxAgeHours
        // Drop stale gage readings so an offline/old gage can't drive the score.
        guard date.timeIntervalSince(r.dateTime) <= maxAgeHours * 3600 else { return false }
        switch kind {
        case .level, .discharge:
            return true
        case .turbidity:
            // A fresh reading from another watershed is worse than useless
            // because it overrides the rain signal.
            if let miles = r.distanceMiles, miles > maxTurbidityDistanceMiles { return false }
            return true
        case .waterTemp:
            // A reading outside surface-water range is a broken sensor or a hot
            // spring (Quapaw Spring's 153 °F drove Lake Catherine), whichever path
            // produced it.
            guard GaugeSelector.plausibleTempF.contains(r.value * 9 / 5 + 32) else { return false }
            let cap = r.acceptance == .matchedPool ? GaugeSelector.matchedPoolTempMaxMiles : maxWaterTempDistanceMiles
            if let miles = r.distanceMiles, miles > cap { return false }
            return true
        }
    }

    /// Build a normalized input for one night at `coordinate`.
    /// - waterTemp: a USGS 00010 reading in **°C** (converted here), or nil.
    /// - waterContext: the water the snapshot resolved the point to. It decides
    ///   whether the generation feed's pool and tailwater temp describe this
    ///   water. nil (the gauge-selection kill switch, and callers that predate
    ///   it) keeps the pre-selection behavior.
    static func build(coordinate: CLLocationCoordinate2D,
                      date: Date = Date(),
                      weather: WeatherReading?,
                      water: WaterLevelReading?,
                      discharge: WaterLevelReading?,
                      waterTempC: WaterLevelReading?,
                      modeledWaterTempF: Double? = nil,
                      turbidity: WaterLevelReading?,
                      generation: DamGeneration? = nil,
                      waterContext: WaterContext? = nil,
                      alertWindFloorMph: Double? = nil,
                      severeWarningLabel: String? = nil,
                      forecastDayIndex: Int = 0,
                      cityGlow: Double? = nil,
                      rainWatershed72hIn: Double? = nil) -> ConditionsInput {

        let lat = coordinate.latitude, lon = coordinate.longitude
        let region = RegionResolver.region(latitude: lat, longitude: lon)

        let water = water.flatMap { passesCaps($0, kind: .level, at: date) ? $0 : nil }
        let discharge = discharge.flatMap { passesCaps($0, kind: .discharge, at: date) ? $0 : nil }
        // Fresh, plausible AND nearby — a temp gage on another watershed is not
        // this water. Without one we use the modeled estimate.
        let waterTempC = waterTempC.flatMap { passesCaps($0, kind: .waterTemp, at: date) ? $0 : nil }
        let turbidity = turbidity.flatMap { passesCaps($0, kind: .turbidity, at: date) ? $0 : nil }

        // Astronomy (local, no network), for the fishing night in progress at the
        // lake — not the UTC day of `date`. On a UTC server "now" at 7 PM Central
        // is already tomorrow, so keying on it scored TOMORROW night's dusk, moon
        // and window for every evening user; after midnight the night that's
        // actually underway is last night's.
        let offset = weather?.utcOffsetSeconds ?? OpenMeteoTime.solarOffsetSeconds(longitude: lon)
        let nightNoon = OpenMeteoTime.fishingNightNoon(date, utcOffsetSeconds: offset)
        let sun = Astronomy.sunEvents(on: nightNoon, lat: lat, lon: lon)
        let moonRS = Astronomy.moonRiseSet(on: nightNoon, lat: lat, lon: lon)

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
        // Illumination at the start of the window, the same moment the 7-night
        // outlook uses (its 9 PM evening), so tonight's moon reads alike on both.
        let moonIllum = Astronomy.moonIllumination(on: windowStart ?? nightNoon) * 100
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
        // it no longer decides whether we know. Whether its POOL and tailwater
        // temp describe this water is the water context's call (below).
        let generation = forecastDayIndex == 0 ? generation : nil
        let generationDescribesWater = waterContext?.matches(generation) ?? false

        // Water temperature: prefer a live gage the snapshot selected (°C → °F).
        // Below a dam with no accepted gage, the dam's own CWMS tailwater
        // thermometer is live too — the air-driven model runs 20 °F+ warm on a
        // cold release. Otherwise the MODELED estimate — a 5-day thermal lag of
        // daily-mean air temp, which is what ~90% of users see because lake temp
        // gages barely exist. Only if even that's unavailable do we fall back to
        // raw air temp. Anything but a live reading is flagged estimated (damps
        // spawn, lowers confidence). §3.
        let tailwaterTempF: Double? = {
            guard waterContext?.isBelowDam == true, generationDescribesWater,
                  let f = generation?.tailwaterTempF, GaugeSelector.plausibleTempF.contains(f) else { return nil }
            return f
        }()
        let liveWaterTempF = waterTempC.map { $0.value * 9 / 5 + 32 } ?? tailwaterTempF
        let airF = weather?.temperature
        let waterTempF = liveWaterTempF ?? modeledWaterTempF ?? airF
        let waterTempEstimated = liveWaterTempF == nil && waterTempF != nil

        let isTailwater = TailwaterRegistry.isTailwater(latitude: lat, longitude: lon)
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
        // CWMS observed history now has its pool series merged in). §5.6.
        let poolTrend12hFt: Double? = {
            guard let g = generation else { return nil }
            let pts = g.history.compactMap { o in o.reservoirFt.map { (o.at, $0) } }.sorted { $0.0 < $1.0 }
            guard pts.count >= 2, let last = pts.last else { return nil }
            let cutoff = last.0.addingTimeInterval(-12 * 3600)
            guard let baseline = pts.last(where: { $0.0 <= cutoff }) ?? pts.first, baseline.0 != last.0 else { return nil }
            return last.1 - baseline.1
        }()

        // Whose pool the level factor may show. Below a dam the pool is the water
        // BEHIND the dam, so a tailwater tile must never carry it. On a lake only
        // that lake's own dam feed counts — Lake Taneycomo's nearest feed is Table
        // Rock, ~200 ft higher. Open water keeps the label (a nearby dam's pool is
        // context) but never its trend, which would score another water's level.
        // No context: the pre-selection behavior.
        let reservoirElevationFt: Double?
        let reservoirTrend12hFt: Double?
        switch waterContext {
        case nil:
            (reservoirElevationFt, reservoirTrend12hFt) = (generation?.reservoirElevationFt, poolTrend12hFt)
        case .belowDam?:
            (reservoirElevationFt, reservoirTrend12hFt) = (nil, nil)
        case .lake?:
            (reservoirElevationFt, reservoirTrend12hFt) = generationDescribesWater
                ? (generation?.reservoirElevationFt, poolTrend12hFt) : (nil, nil)
        case .open?:
            (reservoirElevationFt, reservoirTrend12hFt) = (generation?.reservoirElevationFt, nil)
        }

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

        return ConditionsInput(
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
            reservoirElevationFt: reservoirElevationFt,
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
