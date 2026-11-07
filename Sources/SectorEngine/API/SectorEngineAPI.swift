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
public struct ConditionsResponse: Codable, Equatable {
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
    public var weather: WeatherDTO?
    public let water: WaterDTO?         // gage height / level
    public let discharge: WaterDTO?     // cfs
    public var generation: GenerationDTO?
    public let waterTempModel: WaterTempModelDTO?
    /// THE water temperature — the one the score used and every surface should
    /// show: the lake's own gauge when it has one, else the model. nil when
    /// neither is available.
    public let waterTemp: WaterTempDTO?
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

    /// The clarity estimate as the canonical visibility interface states it
    /// (VisibilityModel secchi-power-v1): the central value the score uses, its
    /// 80% range where one is known, confidence, and where the number came from.
    /// Optional so pre-update clients still decode; appended so none of them breaks.
    public var clarityVisibility: ClarityVisibilityDTO? = nil

    /// THE resolved water-temperature state (Stage 2E): the single source
    /// decision the score ran on, with provenance. `waterTemp` above is a
    /// back-compat projection of this same state. Optional so pre-update
    /// clients still decode; appended so none of them breaks.
    public var waterTempState: WaterTempStateDTO? = nil

    /// The canonical directory lake this coordinate scores as, when one is within
    /// range — the single source of lake identity + naming for every surface and
    /// both apps. Lets clients dedupe "the same water, two names" (a saved lake vs
    /// a free-text trip spot) by `id`, and show one canonical name. nil offshore or
    /// away from any known lake. Optional so pre-update clients still decode.
    public let resolvedLake: ResolvedLakeDTO?

    public let generatedAt: Date
    /// Scoring semantics this response was produced with (`ConditionsScoreVersion.current`). Additive.
    public var scoreVersion: String? = nil
    /// Serving revision (Cloud Run `K_REVISION`) when known. Additive.
    public var engineRevision: String? = nil
    /// Per tile: flag mode, path, source, status and the data's own observation time (Sector_Ops #53, conditions
    /// consolidation spec §4). Keys: the ten `TileKey` raw values plus `moon`. Additive; nil only from callers that
    /// build a response without it.
    public var tileSources: [String: TileSourceDTO]? = nil
    /// The Lake Brain's level for the resolved lake (spec §4, `LakeLevelOutput` shape). Present only when the `waterLevel`
    /// tile is in `serve`, the lake is validated, and its copy is AVAILABLE. Never replaces `water`. Additive.
    public var lakeLevel: LakeLevelOutput? = nil
    /// The Water Clarity Brain's copy (spec §4). Present only when the `clarity` tile served it. Additive.
    public var clarityBrain: ClarityBrainOutput? = nil
    /// The Water Temp Brain's copy (spec §4). Present only when the `waterTemp` tile served it. Never replaces
    /// `waterTempModel`, `waterTemp` or `waterTempState`. Additive.
    public var waterTempBrain: WaterTempBrainOutput? = nil
}

/// Canonical lake identity from the engine's directory — the authority the two
/// client-side directory copies should defer to.
public struct ResolvedLakeDTO: Codable, Equatable {
    public let id: String       // "Name|ST" — stable identity for cross-surface dedup
    public let name: String     // canonical display name (e.g. "Nickajack Lake")
    public let state: String    // primary state code
}

/// A USGS gauge surfaced to the app so the user can check the source behind the
/// clarity estimate. Maps to an NWIS site page via `siteCode`.
public struct GaugeDTO: Codable, Equatable {
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

/// The clarity estimate with its uncertainty and provenance.
public struct ClarityVisibilityDTO: Codable, Equatable {
    public let centralFt: Double
    /// The 80% range; nil where no validated range exists (the rain-decay estimate).
    public let lowFt: Double?
    public let highFt: Double?
    public let confidence: String      // medium | low
    public let model: String           // secchi-power-v1 | rain-decay-v0
    public let source: String          // inSituGauge | rainDecayModel | noRainData
    public let provenance: String
    public let limitations: [String]
}

/// Recent rainfall driving the clarity estimate, from NOAA MRMS via IEM.
public struct ClarityRainDTO: Codable, Equatable {
    public let watershed72hIn: Double     // aggregated across the surrounding watershed
    public let point72hIn: Double         // at the coordinate itself
    public let source: String             // "mrms"
    public let daily: [RainDayDTO]        // point, oldest → newest (~14 days)
}

public struct RainDayDTO: Codable, Equatable {
    public let date: Date
    public let inches: Double
}

// MARK: - Breakdown DTOs

public struct FactorDTO: Codable, Equatable {
    public let key: String        // FactorKey rawValue: clarity|spawn|darkness|wind|waterTemp|level|current|pressure|sky|humidity
    public let score: Int         // 0…100 sub-score
    public let weightPct: Int     // active (renormalized) weight, %
    public let label: String      // human value, e.g. "0.6 ft viz"
    public let why: String
    public let contribution: Double  // signed points off the 50 baseline
}

/// A factor not in play tonight (spawn out of season), for the "not in play" group.
public struct DormantFactorDTO: Codable, Equatable {
    public let key: String
    public let label: String
    public let reason: String
}

public struct GateDTO: Codable, Equatable {
    public let reason: String
    public let cap: Int
}

public struct WhereToLookDTO: Codable, Equatable {
    public let kind: String       // spawn|current|wind|level|clarity|darkness|temp
    public let title: String
    public let body: String
}

// MARK: - Live reading DTOs

public struct WeatherDTO: Codable, Equatable {
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
public struct PressureSampleDTO: Codable, Equatable {
    public let time: Date
    public let hPa: Double
}

/// One hourly weather sample — feeds the wind / temperature / humidity / sky / rain
/// trend charts. Every metric is nullable (a gap in the upstream data).
public struct ConditionsHourlyDTO: Codable, Equatable {
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

public struct WaterDTO: Codable, Equatable {
    public let value: Double
    public let unit: String
    public let trend: String              // rising | falling | steady
    public let change: Double             // signed, in `unit`
    public let history: [Double]          // oldest → newest, for a sparkline
    // Additive (spec Amendment 2): the gauge this reading came from. Optional; build 28 ignores unknown keys.
    public var siteCode: String? = nil
    public var siteName: String? = nil
    /// Straight-line miles from the requested coordinate to the gauge.
    public var distanceMiles: Double? = nil
    /// The gauge reading's own time.
    public var observedAt: Date? = nil
}

public struct GenerationDTO: Codable, Equatable {
    public let damName: String
    public let river: String
    public let operatorId: String       // TVA | SWPA | USACE — clients render the authority label
    public let latitude: Double
    public let longitude: Double
    public let distanceMiles: Double
    public let dischargeCfs: Double?
    public let dischargeTrend12hCfs: Double?
    public let reservoirElevationFt: Double?
    /// Normal full pool of the lake behind the dam — `reservoirElevationFt`
    /// above it is water into the flood pool, below it a drawdown. nil when
    /// the lake has no managed pool on file or there's no pool reading.
    public let fullPoolFt: Double?
    public let tailwaterElevationFt: Double?
    public let observedAt: Date?
    public let windows: [GenerationWindowDTO]

    public struct GenerationWindowDTO: Codable, Equatable {
        public let start: Date
        public let end: Date
        public let generators: Int
        public let isMinimum: Bool
        public let unitsAreDerived: Bool
        public let timeZoneIdentifier: String   // the DAM's zone; clients format in it
    }

    /// Additive (spec §4): which binding chose this dam, `engine-registry` or `lake-brain`. Set only while the `generation`
    /// tile is in `serve`; omitted otherwise. Build 28 ignores unknown keys.
    public var bindingSource: String? = nil
}

/// The resolved water-temperature state — what every surface shows and what the
/// score ran on (one decision, `WaterTemperatureResolver`).
public struct WaterTempStateDTO: Codable, Equatable {
    public let kind: String               // measured | modeled | unavailable
    public let sourceKind: String         // usgsLakeSensor | cwmsLakeSensor | energyBalanceModel | none
    public let valueF: Double?            // nil when unavailable — never a stand-in
    public let unit: String               // degF
    public let sourceId: String?
    public let sourceName: String?
    public let observedAt: Date?          // measurement instant (nil for a model day)
    public let ageHours: Double?
    public let lakeLocalDate: String?     // "yyyy-MM-dd" in the lake's zone; nil if unknown
    public let lakeTimeZone: String?      // IANA zone the date is in
    public let distanceMiles: Double?
    public let depthM: Double?            // nil = depth not stated by the source
    public let spatialSupport: String     // point | lakeWide | none
    public let modelVersion: String?
    public let qualityFlags: [String]
    public let measurementMaxAgeHours: Double
    /// The value the conditions score actually used for water temperature and
    /// why: equal to valueF unless the state is unavailable, in which case the
    /// score's existing air-temperature fallback is named here explicitly.
    public let scoredValueF: Double?
    public let scoredFrom: String         // resolvedState | airTemperatureFallback | none
}

/// The water temperature the score ran on, and where it came from.
/// Back-compat projection of `WaterTempStateDTO` (same resolution).
public struct WaterTempDTO: Codable, Equatable {
    public let valueF: Double
    public let source: String            // gauge | model
    public let siteName: String?         // the lake gauge, when measured
    public let observedAt: Date?
    public let distanceMiles: Double?
}

/// Modeled surface water temp — the current estimate plus the daily series that
/// drives the water-temp detail chart (most waters have no live temp gage).
public struct WaterTempModelDTO: Codable, Equatable {
    public let currentF: Double
    public let series: [Day]
    /// Lake-local date `currentF` is for, and the lake's zone (additive, Stage 2E).
    public var currentLocalDate: String? = nil
    public var timeZone: String? = nil

    public struct Day: Codable, Equatable {
        public let date: Date
        public let waterF: Double
        public let airF: Double
        /// The day's lake-local calendar date ("yyyy-MM-dd"). Select days by
        /// this, never by `date` rendered in a device or server zone.
        public var localDate: String? = nil
    }
}

public struct AlertDTO: Codable, Equatable {
    public let id: String
    public let event: String
    public let severity: String           // extreme | severe | moderate | minor | unknown
    public let headline: String
    public let details: String
    public let ends: Date?
}

// MARK: - Forecast DTOs

public struct TonightDTO: Codable, Equatable {
    public let headline: String           // kept for back-compat; new clients derive from timestamps in device tz
    public let windowStart: Date?
    public let windowEnd: Date?
    public let peak: Date?
    public let sunset: Date?
    public let sunrise: Date?
    public let displayStart: Date?
    public let displayEnd: Date?
    public let hours: [HourDTO]            // the chart curve, 6 PM → 6 AM

    public struct HourDTO: Codable, Equatable {
        public let date: Date
        public let score: Int
    }
}

public struct NightDTO: Codable, Equatable {
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

    public struct NightFactorDTO: Codable, Equatable {
        public let key: String            // FactorKey rawValue (forecast vocabulary)
        public let detail: String         // human value, e.g. "74% lit"
        public let sub: Int               // 0…100
        public let weight: Int            // active regime weight, %
    }

    public struct HourPointDTO: Codable, Equatable {
        public let hour: Date
        public let score: Int
        public let windMph: Double
        public let moonUp: Bool
        public let fogRisk: Int           // 0 none, 1 low, 2 high
    }
}

/// One slim per-coordinate result from the batch endpoint. `score`/`band` are nil
/// when that coordinate had no live data to score.
public struct BatchScore: Codable, Equatable {
    public let lat: Double
    public let lon: Double
    public let score: Int?
    public let band: String?
}

// MARK: - Entry point

public enum SectorEngineAPI {

    /// The one JSON encoder every customer response uses. Released apps depend on these settings: iOS 4.1.0 build 28
    /// decodes dates with `.iso8601` (no fractional seconds), so changing them breaks shipped apps (Sector_Ops #53,
    /// contracts/phone). PhoneContractTests encodes with this same function.
    public static func makeEncoder() -> JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        return encoder
    }

    /// Score a coordinate for `date`: the gauge score + full breakdown + 7-night
    /// outlook + tonight's window + the live readings for the tiles. Returns nil
    /// when there's no live data to score (no weather + no gage).
    public static func conditions(lat: Double, lon: Double, date: Date = Date()) async -> ConditionsResponse? {
        await conditions(lat: lat, lon: lon, date: date, providers: .live)
    }

    /// `conditions` with the tile sources injectable (tests). Per-tile flags (`conditions_tiles_v1`) decide, tile by tile,
    /// whether a new source is computed and whether it is served (ConditionsTileWiring). Every flag defaults to `off`, and
    /// with every flag off no new source is called and the response is exactly today's.
    static func conditions(lat: Double, lon: Double, date: Date, providers: ConditionsTileProviders) async -> ConditionsResponse? {
        let coord = CLLocationCoordinate2D(latitude: lat, longitude: lon)
        // Nearest known lake to the scored point — the canonical identity clients dedupe + name by, and the lake the tile
        // flags' `lakes` lists and the Brain copies are keyed on. 25 mi so a point anywhere on a long reservoir still
        // resolves to that reservoir, not a nearer neighbour off-water.
        let resolvedLake = LakeDirectory.nearest(to: coord, withinMiles: 25)
        let context = TileRequestContext(lakeId: resolvedLake?.id, lat: lat, lon: lon)
        // Per-tile flags (conditions_tiles_v1) are read concurrently with everything else; every tile defaults to off.
        let flagsTask = Task { await TileFlagsStore.shared.current() }

        // Fire the gauge snapshot and the 7-night forecast concurrently — they're
        // independent, and the forecast's own snapshot fetch coalesces onto this
        // one inside the provider, so nothing is fetched twice.
        async let snapTask = ConditionsSnapshotProvider.shared.snapshot(for: coord)
        // Bounded like the snapshot: the 7-night fetch makes its own Open-Meteo
        // call (fetchForecastResponse), so it needs the same deadline or a stuck
        // weather host would hang the whole response through this path.
        // It always starts at once on today's (env) wind model, exactly as before the tile flags existed.
        async let forecastTask = withDeadline(13, "forecast") {
            await ConditionsForecastService.forecast(for: coord, now: date)
        }
        // windOutlookModel tile: the Wind Brain's decision, and — only when serve chose a model other than the env's — the
        // forecast on that model, started as soon as the decision is known. Flag off: no read, no second forecast.
        let windTask = Task { () -> (WindModelDecisionResult) in
            let flags = await flagsTask.value
            let decision = await ConditionsTileWiring.windOutlookModel(
                mode: flags.mode(for: .windOutlookModel, lakeId: context.lakeId), context: context, providers: providers)
            guard decision.servedNew, decision.model != WindForecastModel.current else {
                return WindModelDecisionResult(decision: decision, forecast: nil)
            }
            let f = await withDeadline(13, "forecast-wind-brain") {
                await ConditionsForecastService.forecast(for: coord, now: date, windModel: decision.model)
            }
            return WindModelDecisionResult(decision: decision, forecast: f ?? nil)
        }

        let snap = await snapTask
        guard snap.hasAnyLiveInput else { return nil }
        let flags = await flagsTask.value

        // Water temperature is resolved ONCE; the score and the response both take it.
        let waterTempState = snap.resolvedWaterTemp(at: date)
        var input = snap.engineInput(coordinate: coord, date: date, resolvedWaterTemp: waterTempState)
        // Tuning comes from Firebase Remote Config (cached; falls back to the
        // compiled defaults). Change a weight in the console → both phones see it.
        let config = await RemoteConfigStore.shared.current()

        // The Engine's own clarity statement, from today's input (it keeps that meaning in every flag mode).
        let clarityVisibility = Self.clarityVisibilityDTO(input, turbidity: snap.turbidity, mrms: snap.mrms, config: config)
        // clarity tile, before the score: in serve with the Brain copy AVAILABLE, the clarity factor runs on the copy's
        // centralFt (this CHANGES THE SCORE). Off/shadow: the input is untouched.
        let clarityFacts = LegacyTileFacts(claritySource: clarityVisibility.source,
                                           turbidityObservedAt: clarityVisibility.source == "inSituGauge" ? snap.turbidity?.dateTime : nil)
        let clarity = await ConditionsTileWiring.clarity(
            mode: flags.mode(for: .clarity, lakeId: context.lakeId), lakeId: context.lakeId,
            oldCentralFt: clarityVisibility.centralFt, oldEntry: TileSources.legacy(clarityFacts)[.clarity]!,
            context: context, providers: providers)
        if let ft = clarity.factorFt { input.clarityBrainVisibilityFt = ft }

        let result = ConditionsAggregator.evaluate(input, config: config)

        let envForecast = await forecastTask
        let wind = await windTask.value
        // The Brain's model is used only when its forecast came back; otherwise today's (env) forecast, labelled FALLBACK.
        let windServed = wind.decision.servedNew && (wind.decision.model == WindForecastModel.current || wind.forecast != nil)
        let forecast = (windServed ? wind.forecast : nil) ?? envForecast

        var response = ConditionsResponse(
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
            water: snap.water.map { Self.waterDTO($0, from: coord) },
            discharge: snap.discharge.map { Self.waterDTO($0, from: coord) },
            generation: snap.generation.map(Self.generationDTO),
            waterTempModel: snap.waterTempModel.map(Self.waterTempModelDTO),
            waterTemp: Self.waterTempDTO(state: waterTempState),
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
                // The nearest discharge gauge still feeds the current factor; it
                // drives clarity only when it IS this arm's own gauge.
                snap.discharge.map { d in
                    Self.gaugeDTO(d, role: "discharge", driving: d.siteCode == snap.clarityDischarge?.siteCode) },
                snap.clarityDischarge.flatMap { c in
                    c.siteCode == snap.discharge?.siteCode ? nil : Self.gaugeDTO(c, role: "discharge", driving: true) },
            ].compactMap { $0 },
            resolvedLake: resolvedLake.map {
                ResolvedLakeDTO(id: $0.id, name: $0.name, state: $0.state)
            },
            generatedAt: Date())
        response.clarityVisibility = clarityVisibility
        response.waterTempState = Self.waterTempStateDTO(waterTempState, model: snap.waterTempModel,
                                                         scoredValueF: input.waterTempF)
        response.scoreVersion = ConditionsScoreVersion.current
        response.engineRevision = ConditionsScoreVersion.engineRevision

        // The tiles applied to the built response (weather, waterLevel, waterTemp, generation), then tileSources for all.
        let facts = Self.legacyTileFacts(snap, waterTempState: waterTempState, clarity: response.clarityVisibility,
                                         outlookNights: response.nights.count)
        let legacy = TileSources.legacy(facts)
        var resolved = await ConditionsTileWiring.applyResponseTiles(
            to: &response, legacy: legacy,
            inputs: .init(weather: snap.weather, generation: snap.generation, lat: lat, lon: lon),
            flags: flags, context: context, providers: providers)
        resolved[.clarity] = clarity.entry
        if let served = clarity.served { response.clarityBrain = served }
        if windServed, var entry = wind.decision.entry {
            if response.nights.isEmpty { entry.status = TileStatus.unknown.rawValue }
            resolved[.windOutlookModel] = entry
        }
        response.tileSources = await TileSources.build(facts, flags: flags, context: context, resolved: resolved)
        return response
    }

    /// The windOutlookModel decision and, when it chose a model other than the env's, the forecast on that model.
    struct WindModelDecisionResult: @unchecked Sendable {   // immutable; ConditionsForecast is a value type
        let decision: ConditionsTileWiring.WindModelDecision
        let forecast: ConditionsForecast?
    }

    /// Today's facts behind each tile, for `tileSources` (TileSources.legacy).
    static func legacyTileFacts(_ snap: ConditionsSnapshot, waterTempState: ResolvedWaterTemperatureState,
                                clarity: ClarityVisibilityDTO?, outlookNights: Int) -> LegacyTileFacts {
        let g = snap.generation
        return LegacyTileFacts(
            weatherPresent: snap.weather != nil,
            outlookNights: outlookNights,
            windForecastModel: WindForecastModel.current,
            waterPresent: snap.water != nil,
            waterObservedAt: snap.water?.dateTime,
            claritySource: clarity?.source,
            turbidityObservedAt: clarity?.source == "inSituGauge" ? snap.turbidity?.dateTime : nil,
            waterTempKind: waterTempState.kind.rawValue,
            waterTempSourceKind: waterTempState.sourceKind.rawValue,
            waterTempObservedAt: waterTempState.kind == .measured ? waterTempState.observedAt : nil,
            generationPresent: g != nil,
            generationHasReading: g.map { $0.dischargeCfs != nil || $0.reservoirElevationFt != nil
                || $0.tailwaterElevationFt != nil || !$0.windows.isEmpty } ?? false,
            generationObservedAt: g.flatMap { tileObservedAt(operatorID: $0.dam.operatorID, observedAt: $0.observedAt) })
    }

    /// The generation tile's `observedAt` for `tileSources`: the dam's own observation time, or nil when there is none.
    /// Alabama Power publishes no observation time, so AlabamaPowerGenerationService stamps its FETCH time into
    /// `observedAt` (and it wins over a CWMS fill-in); that is not an observation, so it is not reported here. The
    /// frozen `generation.observedAt` field keeps its value.
    static func tileObservedAt(operatorID: GenerationOperator, observedAt: Date?) -> Date? {
        operatorID == .apc ? nil : observedAt
    }

    /// The canonical statement of the clarity number the score used.
    static func clarityVisibilityDTO(_ input: ConditionsInput, turbidity: WaterLevelReading?,
                                     mrms: MrmsPrecip?, config: ConditionsConfig) -> ClarityVisibilityDTO {
        let central = ClarityFactor.visibilityFt(input, config: config)
        if let fnu = input.turbidityFNU, input.hasTurbidityGage {
            let e = VisibilityModel.estimate(fnu: fnu, source: .inSituGauge, config: config)
            let algal = input.turbidityType == .algal
            let site = turbidity.map { "USGS \($0.siteCode) \($0.siteName)" } ?? "a USGS turbidity gauge"
            return ClarityVisibilityDTO(
                centralFt: central, lowFt: algal ? nil : e.lowFt, highFt: algal ? nil : e.highFt,
                confidence: e.confidence, model: VisibilityModel.modelId, source: "inSituGauge",
                provenance: String(format: "%@ measuring %.1f FNU", site, fnu),
                limitations: ["Visibility converted from turbidity (validated on 81,661 WQP pairs: median error 1.2 ft); the range is the conversion's 80% spread, not the gauge's."]
                    + (algal ? ["Algal turbidity halves the sightline; no validated range for it."] : []))
        }
        if !input.rainDataAvailable && input.rainWatershed72hIn == nil {
            return ClarityVisibilityDTO(centralFt: central, lowFt: nil, highFt: nil, confidence: "low",
                                        model: "rain-decay-v0", source: "noRainData",
                                        provenance: "No turbidity gauge and no rain data: a neutral workable estimate.",
                                        limitations: ["No measurement of any kind behind this number."])
        }
        let rain = input.rainWatershed72hIn.map { String(format: "MRMS rain over the surrounding area, %.2f in in 72 h", $0) }
            ?? String(format: "Open-Meteo rain at the point, %.2f in in 48 h", input.rainLast48hIn)
        let shave = input.clarityDischargeTrend12hCfs.map { $0 > 0 } == true ? "; this arm's own gauge is rising" : ""
        return ClarityVisibilityDTO(
            centralFt: central, lowFt: nil, highFt: nil, confidence: "low", model: "rain-decay-v0",
            source: "rainDecayModel", provenance: "Rain-decay estimate from \(rain)\(shave).",
            limitations: ["Not calibrated: the rain-decay curve is heuristic, so no range is stated.",
                          "One value for the spot: creek backs and open water are not told apart."])
    }

    /// Just the gauge score + band for a coordinate — snapshot + evaluate, NO
    /// forecast (the expensive part). Powers the My Lakes list rings, where only
    /// the number matters. Returns nil when there's no live data to score.
    public static func score(lat: Double, lon: Double, date: Date = Date()) async -> (score: Int, band: String)? {
        let coord = CLLocationCoordinate2D(latitude: lat, longitude: lon)
        let snap = await ConditionsSnapshotProvider.shared.snapshot(for: coord)
        guard snap.hasAnyLiveInput else { return nil }
        // Water temperature is resolved ONCE; the score and the response both take it.
        let waterTempState = snap.resolvedWaterTemp(at: date)
        let input = snap.engineInput(coordinate: coord, date: date, resolvedWaterTemp: waterTempState)
        let result = ConditionsAggregator.evaluate(input, config: await RemoteConfigStore.shared.current())
        return (result.score, result.band.rawValue)
    }

    /// Score many coordinates in one request (My Lakes list). Bounded concurrency so
    /// a long list can't fan out into a burst of upstream fetches; identical/nearby
    /// coordinates coalesce + cache in the snapshot provider. Order is not preserved
    /// — each result carries its own lat/lon so the client can match them up.
    public static func batch(points: [(lat: Double, lon: Double)],
                             date: Date = Date(), maxConcurrent: Int = 6) async -> [BatchScore] {
        var results: [BatchScore] = []
        var next = 0
        await withTaskGroup(of: BatchScore.self) { group in
            func addTask() {
                guard next < points.count else { return }
                let p = points[next]; next += 1
                group.addTask {
                    let s = await score(lat: p.lat, lon: p.lon, date: date)
                    return BatchScore(lat: p.lat, lon: p.lon, score: s?.score, band: s?.band)
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

    static func waterDTO(_ r: WaterLevelReading, from origin: CLLocationCoordinate2D) -> WaterDTO {
        var dto = WaterDTO(value: r.value, unit: r.unit, trend: waterTrendString(r.trend),
                           change: r.change, history: r.history)
        dto.siteCode = r.siteCode
        dto.siteName = r.siteName
        dto.distanceMiles = r.distanceMiles ?? CLLocation(latitude: origin.latitude, longitude: origin.longitude)
            .distance(from: CLLocation(latitude: r.latitude, longitude: r.longitude)) / 1609.34
        dto.observedAt = r.dateTime
        return dto
    }

    private static func gaugeDTO(_ r: WaterLevelReading, role: String, driving: Bool) -> GaugeDTO {
        GaugeDTO(siteCode: r.siteCode, siteName: r.siteName,
                 parameterCode: r.parameterCode, parameterName: r.parameterName,
                 role: role, value: r.value, unit: r.unit,
                 trend: waterTrendString(r.trend), change: r.change,
                 distanceMiles: r.distanceMiles, latitude: r.latitude, longitude: r.longitude,
                 driving: driving)
    }

    static func generationDTO(_ g: DamGeneration) -> GenerationDTO {
        GenerationDTO(
            damName: g.dam.name, river: g.dam.river,
            operatorId: g.dam.operatorID.rawValue,
            latitude: g.dam.latitude, longitude: g.dam.longitude,
            distanceMiles: g.distanceMiles,
            dischargeCfs: g.dischargeCfs, dischargeTrend12hCfs: g.dischargeTrend12hCfs,
            reservoirElevationFt: g.reservoirElevationFt, fullPoolFt: g.fullPoolFt,
            tailwaterElevationFt: g.tailwaterElevationFt,
            observedAt: g.observedAt,
            windows: g.windows.map {
                GenerationDTO.GenerationWindowDTO(
                    start: $0.start, end: $0.end, generators: $0.generators,
                    isMinimum: $0.isMinimum, unitsAreDerived: $0.unitsAreDerived,
                    timeZoneIdentifier: $0.timeZone.identifier)
            })
    }

    /// Back-compat projection of the resolved state — the same decision the
    /// score builder took, so the number shown is the number scored.
    static func waterTempDTO(state: ResolvedWaterTemperatureState) -> WaterTempDTO? {
        guard let v = state.valueF else { return nil }
        switch state.kind {
        case .measured:
            return WaterTempDTO(valueF: v, source: "gauge", siteName: state.sourceName,
                                observedAt: state.observedAt, distanceMiles: state.distanceMiles)
        case .modeled:
            return WaterTempDTO(valueF: v, source: "model", siteName: nil, observedAt: nil, distanceMiles: nil)
        case .unavailable:
            return nil
        }
    }

    /// The full resolved state for clients. `scoredValueF` is what the score
    /// actually used (`input.waterTempF`), so a client can prove shown == scored.
    static func waterTempStateDTO(_ s: ResolvedWaterTemperatureState, model: WaterTempModel?,
                                  scoredValueF: Double?) -> WaterTempStateDTO {
        let from: String
        if s.valueF != nil { from = "resolvedState" }
        else if scoredValueF != nil { from = "airTemperatureFallback" }
        else { from = "none" }
        return WaterTempStateDTO(
            kind: s.kind.rawValue, sourceKind: s.sourceKind.rawValue, valueF: s.valueF, unit: s.unit,
            sourceId: s.sourceId, sourceName: s.sourceName, observedAt: s.observedAt, ageHours: s.ageHours,
            lakeLocalDate: s.lakeLocalDate, lakeTimeZone: model?.timeZoneIdentifier,
            distanceMiles: s.distanceMiles, depthM: s.depthM, spatialSupport: s.spatialSupport,
            modelVersion: s.modelVersion, qualityFlags: s.qualityFlags,
            measurementMaxAgeHours: s.measurementMaxAgeHours,
            scoredValueF: scoredValueF, scoredFrom: from)
    }

    static func waterTempModelDTO(_ m: WaterTempModel) -> WaterTempModelDTO {
        var dto = WaterTempModelDTO(
            currentF: m.currentF,
            series: m.series.map {
                var d = WaterTempModelDTO.Day(date: $0.date, waterF: $0.waterF, airF: $0.airF)
                d.localDate = $0.localDate
                return d
            })
        dto.currentLocalDate = m.currentLocalDate
        dto.timeZone = m.timeZoneIdentifier
        return dto
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
