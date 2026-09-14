//
//  SectorEngineAPI.swift
//  SectorEngine
//
//  The single PUBLIC entry point. Everything else in the module stays internal;
//  clients (the server, iOS, Android, web) call this and get a Codable response.
//  Same pipeline the app runs: snapshot → input → evaluate → forecast.
//
//  Phase 6: the response is the FULL render payload — the computed result
//  (score, band, per-factor breakdown, gates, where-to-look), the tonight window
//  with its hourly curve, the 7-night outlook with per-night breakdowns, AND the
//  raw live readings (weather, water, generation, alerts, moon) the clients still
//  compose their tiles and window-sheet guidance from. Clients keep only
//  presentation (icons, tints, tier words, moon graphics, prose, timezone-local
//  formatting) and the ephemeris; the scoring + fetching live here.
//
//  Back-compat: this is a strict SUPERSET of the Phase 4/5 payload — every field
//  those clients decode (score, band, topReasons, tonight{headline,windowStart,
//  windowEnd,peak}, nights[{date,score,rating,moonIllumination,windMax,
//  weatherCode,precip}]) keeps its exact name and shape. New fields are additive;
//  decoders ignore what they don't know.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

// MARK: - Response

/// The render-ready payload every client (iOS, Android, web) receives.
public struct ConditionsResponse: Codable, Equatable, Sendable {
    // Headline + breakdown (from ConditionsResult)
    public let score: Int
    public let band: String            // Poor | Fair | Good | Prime
    public let regime: String          // normal | spawn | tailwater
    public let confidence: Int
    public let confidenceBand: String  // Low | Med | High
    public let topReasons: [String]
    public let closingLine: String
    public let spawnSpeciesName: String?
    public let spawnNeedsDisclaimer: Bool
    public let baseline: Double
    public let dormantFactors: [DormantFactorDTO]
    public let factors: [FactorDTO]
    public let gates: [GateDTO]
    public let whereToLook: [WhereToLookDTO]

    // Live readings for the tiles + window-sheet guidance (from the snapshot)
    public let weather: WeatherDTO?
    public let water: WaterDTO?         // gage height / level
    public let discharge: WaterDTO?     // cfs
    public let generation: GenerationDTO?
    public let waterTempModel: WaterTempModelDTO?
    public let moonIllumination: Double // 0…1, for "now"
    public let alerts: [AlertDTO]

    // Tonight window + 7-night outlook
    public let tonight: TonightDTO?
    public let nights: [NightDTO]

    /// MRMS radar-gauge rainfall behind the clarity estimate — the real recent
    /// rain (watershed-aggregated) plus a daily series for the sightline chart.
    /// nil when MRMS was unavailable (clarity fell back to Open-Meteo).
    public let clarityRain: ClarityRainDTO?

    /// The USGS gauges behind the clarity estimate (turbidity + discharge) — site
    /// identity, latest reading, trend and distance so the app can show and open
    /// them. `driving` marks the gauge that actually informs the estimate.
    public let clarityGauges: [GaugeDTO]

    /// The canonical directory lake this coordinate scores as, when one is within
    /// range — the single source of lake identity + naming for every surface and
    /// both apps. Lets clients dedupe "the same water, two names" (a saved lake vs
    /// a free-text trip spot) by `id`, and show one canonical name. nil offshore or
    /// away from any known lake. Optional so pre-update clients still decode.
    public let resolvedLake: ResolvedLakeDTO?

    /// Inputs that are missing or unreliable in THIS render: an upstream that
    /// timed out ("generation", "turbidity"…), "alerts" when NWS couldn't be
    /// reached (so "no alerts" isn't a promise), "forecast" when the 7-night
    /// didn't finish. Empty means complete. Additive — older clients ignore it —
    /// and a degraded render is only cached briefly on the server.
    public let degradedInputs: [String]

    public let generatedAt: Date
}

/// Canonical lake identity from the engine's directory — the authority the two
/// client-side directory copies should defer to.
public struct ResolvedLakeDTO: Codable, Equatable, Sendable {
    public let id: String       // "Name|ST" — stable identity for cross-surface dedup
    public let name: String     // canonical display name (e.g. "Nickajack Lake")
    public let state: String    // primary state code
}

/// A USGS gauge surfaced to the app so the user can check the source behind the
/// clarity estimate. Maps to an NWIS site page via `siteCode`.
public struct GaugeDTO: Codable, Equatable, Sendable {
    public let siteCode: String          // USGS site number
    public let siteName: String
    public let parameterCode: String     // 63680 turbidity | 00060 discharge
    public let parameterName: String
    public let role: String              // "turbidity" | "discharge"
    public let value: Double
    public let unit: String
    public let trend: String             // rising | falling | steady
    public let change: Double
    public let distanceMiles: Double?
    public let latitude: Double
    public let longitude: Double
    public let driving: Bool             // actually informs the clarity estimate
}

/// Recent rainfall driving the clarity estimate, from NOAA MRMS via IEM.
public struct ClarityRainDTO: Codable, Equatable, Sendable {
    public let watershed72hIn: Double     // aggregated across the surrounding watershed
    public let point72hIn: Double         // at the coordinate itself
    public let source: String             // "mrms"
    public let daily: [RainDayDTO]        // point, oldest → newest (~14 days)
}

public struct RainDayDTO: Codable, Equatable, Sendable {
    public let date: Date
    public let inches: Double
}

// MARK: - Breakdown DTOs

public struct FactorDTO: Codable, Equatable, Sendable {
    public let key: String        // FactorKey rawValue: clarity|spawn|darkness|wind|waterTemp|level|current|pressure|sky|humidity
    public let score: Int         // 0…100 sub-score
    public let weightPct: Int     // active (renormalized) weight, %
    public let label: String      // human value, e.g. "0.6 ft viz"
    public let why: String
    public let contribution: Double  // signed points off the 50 baseline
}

/// A factor not in play tonight (spawn out of season), for the "not in play" group.
public struct DormantFactorDTO: Codable, Equatable, Sendable {
    public let key: String
    public let label: String
    public let reason: String
}

public struct GateDTO: Codable, Equatable, Sendable {
    public let reason: String
    public let cap: Int
}

public struct WhereToLookDTO: Codable, Equatable, Sendable {
    public let kind: String       // spawn|current|wind|level|clarity|darkness|temp
    public let title: String
    public let body: String
}

// MARK: - Live reading DTOs

public struct WeatherDTO: Codable, Equatable, Sendable {
    public let temperature: Double        // °F
    public let conditionDescription: String
    public let conditionSymbol: String    // SF Symbol name (iOS renders; Android maps)
    public let windSpeed: Double          // mph
    public let windDirection: Int         // degrees, 0 = N
    public let precipitation: Double      // inches, now
    public let recentRainfall: Double     // inches, past ~3 days
    public let humidity: Int              // %
    public let pressure: Double           // hPa
    public let pressureTrend: String      // rising | falling | steady
    public let pressureChange: Double     // signed hPa over the lookback
    public let cloudCover: Double         // %
    public let weatherCode: Int           // WMO
    // Hourly barometric series (past + near-future), chronological. Powers the
    // pressure detail sheet's trend chart. Empty when hourly data was unavailable.
    public let pressureHourly: [PressureSampleDTO]
    // Hourly conditions series (temp/humidity/wind/gust/dir/dewpoint/cloud/precip),
    // past + near-future. Powers the Wind / Temperature / Humidity / Sky / rain
    // detail charts. Empty when hourly data was unavailable.
    public let hourlyConditions: [ConditionsHourlyDTO]
}

/// One hourly barometric reading. `hPa` is millibars; clients convert to inHg.
public struct PressureSampleDTO: Codable, Equatable, Sendable {
    public let time: Date
    public let hPa: Double
}

/// One hourly weather sample — feeds the wind / temperature / humidity / sky / rain
/// trend charts. Every metric is nullable (a gap in the upstream data).
public struct ConditionsHourlyDTO: Codable, Equatable, Sendable {
    public let time: Date
    public let tempF: Double?
    public let humidity: Double?
    public let windMph: Double?
    public let gustMph: Double?
    public let windDir: Double?
    public let dewPointF: Double?
    public let cloudPct: Double?
    public let precipIn: Double?
}

public struct WaterDTO: Codable, Equatable, Sendable {
    public let value: Double
    public let unit: String
    public let trend: String              // rising | falling | steady
    public let change: Double             // signed, in `unit`
    public let history: [Double]          // oldest → newest, for a sparkline
}

public struct GenerationDTO: Codable, Equatable, Sendable {
    public let damName: String
    public let river: String
    public let operatorId: String       // TVA | SWPA | USACE — clients render the authority label
    public let latitude: Double
    public let longitude: Double
    public let distanceMiles: Double
    public let dischargeCfs: Double?
    public let dischargeTrend12hCfs: Double?
    public let reservoirElevationFt: Double?
    public let tailwaterElevationFt: Double?
    public let observedAt: Date?
    public let windows: [GenerationWindowDTO]

    public struct GenerationWindowDTO: Codable, Equatable, Sendable {
        public let start: Date
        public let end: Date
        public let generators: Int
        public let isMinimum: Bool
        public let unitsAreDerived: Bool
        public let timeZoneIdentifier: String   // the DAM's zone; clients format in it
    }
}

/// Modeled surface water temp — the current estimate plus the daily series that
/// drives the water-temp detail chart (most waters have no live temp gage).
public struct WaterTempModelDTO: Codable, Equatable, Sendable {
    public let currentF: Double
    public let series: [Day]

    public struct Day: Codable, Equatable, Sendable {
        public let date: Date
        public let waterF: Double
        public let airF: Double
    }
}

public struct AlertDTO: Codable, Equatable, Sendable {
    public let id: String
    public let event: String
    public let severity: String           // extreme | severe | moderate | minor | unknown
    public let headline: String
    public let details: String
    public let ends: Date?
}

// MARK: - Forecast DTOs

public struct TonightDTO: Codable, Equatable, Sendable {
    public let headline: String           // kept for back-compat; new clients derive from timestamps in device tz
    public let windowStart: Date?
    public let windowEnd: Date?
    public let peak: Date?
    public let sunset: Date?
    public let sunrise: Date?
    public let displayStart: Date?
    public let displayEnd: Date?
    public let hours: [HourDTO]            // the chart curve, 6 PM → 6 AM

    public struct HourDTO: Codable, Equatable, Sendable {
        public let date: Date
        public let score: Int
    }
}

public struct NightDTO: Codable, Equatable, Sendable {
    public let date: Date
    public let score: Int
    public let rating: String             // Poor | Fair | Good | Prime
    public let moonIllumination: Double
    public let windMax: Double            // mph
    public let weatherCode: Int
    public let precip: Double             // inches
    public let precipProbability: Int?    // 0…100 % chance of rain; nil when unknown
    public let confidence: Int
    public let regime: String
    public let topReasons: [String]
    public let factors: [NightFactorDTO]
    // The night-detail hour-by-hour ribbon + exact moonset. Optional so a
    // pre-update client still decodes; empty/nil when not computed.
    public let hourly: [HourPointDTO]?
    public let moonset: Date?

    public struct NightFactorDTO: Codable, Equatable, Sendable {
        public let key: String            // FactorKey rawValue (forecast vocabulary)
        public let detail: String         // human value, e.g. "74% lit"
        public let sub: Int               // 0…100
        public let weight: Int            // active regime weight, %
    }

    public struct HourPointDTO: Codable, Equatable, Sendable {
        public let hour: Date
        public let score: Int
        public let windMph: Double
        public let moonUp: Bool
        public let fogRisk: Int           // 0 none, 1 low, 2 high
    }
}

/// One slim per-coordinate result from the batch endpoint. `score`/`band` are nil
/// when that coordinate had no live data to score.
public struct BatchScore: Codable, Equatable, Sendable {
    public let lat: Double
    public let lon: Double
    public let score: Int?
    public let band: String?
}

// MARK: - Entry point

public enum SectorEngineAPI: Sendable {

    /// Budget for the 7-night forecast. It awaits the same snapshot the gauge does
    /// (generation alone may take 12s) PLUS its own Open-Meteo fetch and a full
    /// re-score, so the old 13s left ~1s of headroom: a slow generation fetch
    /// silently dropped Tonight and the whole outlook from an otherwise good
    /// render. 18s still returns well inside the clients' 45s and Cloud Run's 60s.
    static let forecastBudgetSeconds: Double = 18

    /// Score a coordinate for `date`: the gauge score + full breakdown + 7-night
    /// outlook + tonight's window + the live readings for the tiles. Returns nil
    /// when the point can't be scored honestly — no weather (see
    /// `ConditionsSnapshot.canScore`). The server answers that with a 503.
    /// - Parameter fresh: pull-to-refresh — refetch the snapshot and forecast
    ///   instead of reusing cached ones.
    public static func conditions(lat: Double, lon: Double, date: Date = Date(),
                                  fresh: Bool = false) async -> ConditionsResponse? {
        let coord = CLLocationCoordinate2D(latitude: lat, longitude: lon)

        // Start the 7-night forecast alongside the snapshot — its own snapshot
        // read coalesces onto this one inside the provider, so nothing is fetched
        // twice. It's an unstructured Task (not `async let`) so the no-weather
        // path below can return a 503 immediately instead of waiting out the
        // forecast's budget; the forecast still finishes and warms its cache.
        let forecastTask = Task {
            await withDeadline(forecastBudgetSeconds, "forecast") {
                await ConditionsForecastService.forecast(for: coord, now: date, force: fresh)
            }
        }

        let snap = await ConditionsSnapshotProvider.shared.snapshot(for: coord, force: fresh)
        guard snap.canScore else {
            Log.warning("render unavailable: no weather",
                        ["lat": .double(lat), "lon": .double(lon),
                         "degraded": .strings(snap.degradedInputs)])
            return nil
        }

        let input = ConditionsInputBuilder.build(
            coordinate: coord, date: date,
            weather: snap.weather, water: snap.water, discharge: snap.discharge,
            waterTempC: snap.waterTemp, modeledWaterTempF: snap.waterTempModel?.currentF,
            turbidity: snap.turbidity, generation: snap.generation,
            alertWindFloorMph: snap.alertWindFloorMph,
            severeWarningLabel: snap.severeWarningLabel,
            rainWatershed72hIn: snap.mrms?.watershed72hIn)
        // Tuning comes from Firebase Remote Config (cached; falls back to the
        // compiled defaults). Change a weight in the console → both phones see it.
        let config = await RemoteConfigStore.shared.current()
        let result = ConditionsAggregator.evaluate(input, config: config)

        let forecast = await forecastTask.value
        var degraded = snap.degradedInputs
        if forecast == nil { degraded.append("forecast") }
        if !degraded.isEmpty {
            Log.notice("render degraded",
                       ["lat": .double(lat), "lon": .double(lon), "degraded": .strings(degraded.sorted())])
        }

        return ConditionsResponse(
            score: result.score,
            band: result.band.rawValue,
            regime: result.regime.rawValue,
            confidence: result.confidence,
            confidenceBand: result.confidenceBand.rawValue,
            topReasons: result.topReasons,
            closingLine: result.closingLine,
            spawnSpeciesName: result.spawnSpeciesName,
            spawnNeedsDisclaimer: result.spawnNeedsDisclaimer,
            baseline: result.baseline,
            dormantFactors: result.dormantFactors.map {
                DormantFactorDTO(key: $0.key.rawValue, label: $0.label, reason: $0.reason)
            },
            factors: result.factors.map {
                FactorDTO(key: $0.key.rawValue, score: $0.score,
                          weightPct: $0.weightPct, label: $0.label, why: $0.why,
                          contribution: $0.contribution)
            },
            gates: result.gates.map { GateDTO(reason: $0.reason, cap: $0.cap) },
            whereToLook: result.whereToLook.map {
                WhereToLookDTO(kind: $0.kind.rawValue, title: $0.title, body: $0.body)
            },
            weather: snap.weather.map(Self.weatherDTO),
            water: snap.water.map(Self.waterDTO),
            discharge: snap.discharge.map(Self.waterDTO),
            generation: snap.generation.map(Self.generationDTO),
            waterTempModel: snap.waterTempModel.map(Self.waterTempModelDTO),
            moonIllumination: Astronomy.moonIllumination(on: date),
            alerts: snap.alerts.map(Self.alertDTO),
            tonight: forecast?.tonight.map(Self.tonightDTO),
            nights: (forecast?.nights ?? []).map(Self.nightDTO),
            clarityRain: snap.mrms.map { m in
                ClarityRainDTO(watershed72hIn: m.watershed72hIn, point72hIn: m.point72hIn,
                               source: "mrms",
                               daily: m.daily.map { RainDayDTO(date: $0.date, inches: $0.inches) })
            },
            clarityGauges: [
                snap.turbidity.map { Self.gaugeDTO($0, role: "turbidity",
                    driving: ($0.distanceMiles ?? .infinity) <= ConditionsInputBuilder.maxTurbidityDistanceMiles) },
                snap.discharge.map { Self.gaugeDTO($0, role: "discharge", driving: true) },
            ].compactMap { $0 },
            // Nearest known lake to the scored point — the canonical identity clients
            // dedupe + name by. 25 mi so a point anywhere on a long reservoir still
            // resolves to that reservoir, not a nearer neighbour off-water.
            resolvedLake: LakeDirectory.nearest(to: coord, withinMiles: 25).map {
                ResolvedLakeDTO(id: $0.id, name: $0.name, state: $0.state)
            },
            degradedInputs: degraded.sorted(),
            generatedAt: Date())
    }

    /// Just the gauge score + band for a coordinate — snapshot + evaluate, NO
    /// forecast (the expensive part). Powers the My Lakes list rings, where only
    /// the number matters. Returns nil when there's no live data to score.
    public static func score(lat: Double, lon: Double, date: Date = Date()) async -> (score: Int, band: String)? {
        let coord = CLLocationCoordinate2D(latitude: lat, longitude: lon)
        let snap = await ConditionsSnapshotProvider.shared.snapshot(for: coord)
        guard snap.canScore else { return nil }
        let input = ConditionsInputBuilder.build(
            coordinate: coord, date: date,
            weather: snap.weather, water: snap.water, discharge: snap.discharge,
            waterTempC: snap.waterTemp, modeledWaterTempF: snap.waterTempModel?.currentF,
            turbidity: snap.turbidity, generation: snap.generation,
            alertWindFloorMph: snap.alertWindFloorMph,
            severeWarningLabel: snap.severeWarningLabel,
            rainWatershed72hIn: snap.mrms?.watershed72hIn)
        let result = ConditionsAggregator.evaluate(input, config: await RemoteConfigStore.shared.current())
        return (result.score, result.band.rawValue)
    }

    /// Most points one batch request scores. With `maxConcurrent` 6 and each point
    /// bounded by `batchPointBudgetSeconds`, 12 points finish inside ~24s — a
    /// 50-point request could otherwise hold an instance for minutes.
    public static let batchMaxPoints = 12
    static let batchPointBudgetSeconds: Double = 12

    /// Score many coordinates in one request (My Lakes list). Bounded concurrency so
    /// a long list can't fan out into a burst of upstream fetches; identical/nearby
    /// coordinates coalesce + cache in the snapshot provider. Order is not preserved
    /// — each result carries its own lat/lon so the client can match them up. A
    /// point that can't be scored in its budget comes back with a nil score.
    public static func batch(points: [(lat: Double, lon: Double)],
                             date: Date = Date(), maxConcurrent: Int = 6) async -> [BatchScore] {
        var results: [BatchScore] = []
        var next = 0
        await withTaskGroup(of: BatchScore.self) { group in
            func addTask() {
                guard next < points.count else { return }
                let p = points[next]; next += 1
                group.addTask {
                    let s = await withDeadline(batchPointBudgetSeconds, "batch.score") {
                        await score(lat: p.lat, lon: p.lon, date: date).map { BatchScore(lat: p.lat, lon: p.lon, score: $0.score, band: $0.band) }
                    }
                    return s ?? BatchScore(lat: p.lat, lon: p.lon, score: nil, band: nil)
                }
            }
            for _ in 0..<min(maxConcurrent, points.count) { addTask() }
            for await r in group { results.append(r); addTask() }
        }
        return results
    }

    // MARK: Mappers

    private static func weatherDTO(_ w: WeatherReading) -> WeatherDTO {
        WeatherDTO(
            temperature: w.temperature, conditionDescription: w.conditionDescription,
            conditionSymbol: w.conditionSymbol, windSpeed: w.windSpeed,
            windDirection: w.windDirection, precipitation: w.precipitation,
            recentRainfall: w.recentRainfall, humidity: w.humidity,
            pressure: w.pressure, pressureTrend: pressureTrendString(w.pressureTrend),
            pressureChange: w.pressureChange, cloudCover: w.cloudCover, weatherCode: w.weatherCode,
            pressureHourly: w.pressureHistory.map { PressureSampleDTO(time: $0.date, hPa: $0.hPa) },
            hourlyConditions: w.hourlyConditions.map {
                ConditionsHourlyDTO(time: $0.date, tempF: $0.tempF, humidity: $0.humidity,
                    windMph: $0.windMph, gustMph: $0.gustMph, windDir: $0.windDir,
                    dewPointF: $0.dewPointF, cloudPct: $0.cloudPct, precipIn: $0.precipIn)
            })
    }

    private static func waterDTO(_ r: WaterLevelReading) -> WaterDTO {
        WaterDTO(value: r.value, unit: r.unit, trend: waterTrendString(r.trend),
                 change: r.change, history: r.history)
    }

    private static func gaugeDTO(_ r: WaterLevelReading, role: String, driving: Bool) -> GaugeDTO {
        GaugeDTO(siteCode: r.siteCode, siteName: r.siteName,
                 parameterCode: r.parameterCode, parameterName: r.parameterName,
                 role: role, value: r.value, unit: r.unit,
                 trend: waterTrendString(r.trend), change: r.change,
                 distanceMiles: r.distanceMiles, latitude: r.latitude, longitude: r.longitude,
                 driving: driving)
    }

    private static func generationDTO(_ g: DamGeneration) -> GenerationDTO {
        GenerationDTO(
            damName: g.dam.name, river: g.dam.river,
            operatorId: g.dam.operatorID.rawValue,
            latitude: g.dam.latitude, longitude: g.dam.longitude,
            distanceMiles: g.distanceMiles,
            dischargeCfs: g.dischargeCfs, dischargeTrend12hCfs: g.dischargeTrend12hCfs,
            reservoirElevationFt: g.reservoirElevationFt, tailwaterElevationFt: g.tailwaterElevationFt,
            observedAt: g.observedAt,
            windows: g.windows.map {
                GenerationDTO.GenerationWindowDTO(
                    start: $0.start, end: $0.end, generators: $0.generators,
                    isMinimum: $0.isMinimum, unitsAreDerived: $0.unitsAreDerived,
                    timeZoneIdentifier: $0.timeZone.identifier)
            })
    }

    private static func waterTempModelDTO(_ m: WaterTempModel) -> WaterTempModelDTO {
        WaterTempModelDTO(
            currentF: m.currentF,
            series: m.series.map { WaterTempModelDTO.Day(date: $0.date, waterF: $0.waterF, airF: $0.airF) })
    }

    private static func alertDTO(_ a: WeatherAlert) -> AlertDTO {
        AlertDTO(id: a.id, event: a.event, severity: severityString(a.severity),
                 headline: a.headline, details: a.details, ends: a.ends)
    }

    private static func tonightDTO(_ t: TonightWindow) -> TonightDTO {
        TonightDTO(
            headline: t.headline, windowStart: t.windowStart, windowEnd: t.windowEnd,
            peak: t.peak, sunset: t.sunset, sunrise: t.sunrise,
            displayStart: t.displayStart, displayEnd: t.displayEnd,
            hours: t.hours.map { TonightDTO.HourDTO(date: $0.date, score: $0.score) })
    }

    private static func nightDTO(_ n: NightScore) -> NightDTO {
        NightDTO(
            date: n.date, score: n.score, rating: n.rating.rawValue,
            moonIllumination: n.moonIllumination, windMax: n.windMax,
            weatherCode: n.weatherCode, precip: n.precip,
            precipProbability: n.precipProbability, confidence: n.confidence,
            regime: n.regime.rawValue, topReasons: n.topReasons,
            factors: n.factors.map {
                NightDTO.NightFactorDTO(key: $0.key, detail: $0.detail, sub: $0.sub, weight: $0.weight)
            },
            hourly: n.hourly.map {
                NightDTO.HourPointDTO(hour: $0.hour, score: $0.score, windMph: $0.windMph,
                                      moonUp: $0.moonUp, fogRisk: $0.fogRisk)
            },
            moonset: n.moonset)
    }

    private static func pressureTrendString(_ t: PressureTrend) -> String {
        switch t { case .rising: return "rising"; case .falling: return "falling"; case .steady: return "steady" }
    }
    private static func waterTrendString(_ t: WaterTrend) -> String {
        switch t { case .rising: return "rising"; case .falling: return "falling"; case .steady: return "steady" }
    }
    private static func severityString(_ s: AlertSeverity) -> String {
        switch s {
        case .extreme: return "extreme"; case .severe: return "severe"
        case .moderate: return "moderate"; case .minor: return "minor"; case .unknown: return "unknown"
        }
    }
}
