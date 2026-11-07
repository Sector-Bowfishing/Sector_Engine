//
//  ConditionsTileWiring.swift
//  SectorEngine
//
//  Conditions consolidation, the wiring step (Sector_Ops #53, docs/architecture/conditions/CONDITIONS_CONSOLIDATION_SPEC_V1.md
//  §1, §4): each tile's new source, put through `TileShadow.resolve` under that tile's own flag. Every flag defaults to `off`,
//  and with every flag `off` no new source is called and the response is exactly today's.
//
//  Per tile (`shadow` = old served, new computed DETACHED and logged as `[tile-shadow]`; `serve` = new served when AVAILABLE
//  and the breaker is closed, otherwise old with tileSources status FALLBACK):
//
//    humidity, pressure,     new: NWS/NBM (`NWSWeatherService`), one fetch shared by the five tiles of a request.
//    temperature, sky, wind  shadow: one `[tile-shadow]` line per tile through `NWSWeatherParity`.
//                            serve: ONLY that tile's fields in `weather` are replaced, in build 28 units (°F, %, hPa, mph,
//                            WMO code + the WeatherService SF Symbol vocabulary). A field NWS has no fresh value for keeps
//                            Open-Meteo's (per field). No primary value from NWS → the tile falls back. `pressureHourly`,
//                            `hourlyConditions`, precipitation and the SCORE stay on Open-Meteo.
//    waterLevel              new: the Lake Brain copy (`LakeLevelOutputAPI`), served ONLY in the additive `lakeLevel`, and
//                            only for a lake on `LakeLevelEligibility.validatedLakeIds`. `water` is never written.
//    clarity                 new: the Water Clarity Brain copy (`ClarityBrainOutputAPI`), served in the additive
//                            `clarityBrain`. In serve it ALSO feeds the clarity factor (`ConditionsInput.clarityBrainVisibilityFt`),
//                            which CHANGES THE SCORE. `clarityVisibility` keeps stating the Engine's own estimate.
//    waterTemp               new: the Water Temp Brain copy (`WaterTempBrainOutputAPI`), served ONLY in the additive
//                            `waterTempBrain`. `waterTempModel`, `waterTemp` and `waterTempState` are never written.
//    generation              new: the Lake Brain dam binding (`GenerationBindingOutputAPI`). serve: when the binding is
//                            AVAILABLE and names a dam the Engine's operators publish, `generation` is that dam's live
//                            generation (the fetch stays in the Engine) with `bindingSource: lake-brain`; otherwise today's
//                            `TailwaterRegistry`/nearest-dam answer with `bindingSource: engine-registry`. shadow: logs the
//                            dam chosen by each (no generation fetch). The score keeps today's dam.
//    windOutlookModel        new: the Wind Brain decision (`WindOutlookModelOutputAPI`). serve: its `nights2to7` model replaces
//                            the env `SECTOR_WIND_FORECAST_MODEL` choice for the outlook's future nights; tonight stays
//                            best_match (WS-5). Otherwise the env choice. shadow: logs env vs Brain.
//
//  Brain copies are read through the configured `BrainOutputReader` (`BrainOutputReaderConfig`). With none (the default)
//  every copy is UNKNOWN, so every Brain-backed tile serves today's path even in `serve`.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

// MARK: - Sources

/// The new sources the wired tiles read, injectable for tests.
struct ConditionsTileProviders: Sendable {
    var reader: BrainOutputReader?
    var nwsReading: @Sendable (_ lat: Double, _ lon: Double) async -> NWSWeatherReading?
    /// The Engine-registry dam a Lake Brain binding names, or nil when no operator the Engine reads publishes it.
    var boundDam: @Sendable (_ binding: GenerationBindingOutput) async -> GenerationDamRef?
    /// Live generation for a bound dam (serve only). `current` is today's answer for the request, reused when it is the
    /// same dam, so no second fetch is made.
    var boundGeneration: @Sendable (_ dam: GenerationDamRef, _ lat: Double, _ lon: Double,
                                    _ current: GenerationRef?) async -> GenerationRef?
    var now: @Sendable () -> Date
    var breaker: TileBreakerRegistry
    var shadowRunner: TileShadowRunner
    var log: @Sendable (String) -> Void
    /// The existing lake-level gates (`SECTOR_LAKE_LEVEL_OUTPUT` + the validated list); `lakeLevel` needs them AND the flag.
    var lakeLevelEligibility: LakeLevelEligibility = .fromEnvironment()

    /// The production sources. The reader comes from `BrainOutputReaderConfig` (none by default).
    static let live = ConditionsTileProviders(
        reader: BrainOutputReaderConfig.reader(),
        nwsReading: { lat, lon in
            await NWSWeatherService.shared.reading(near: CLLocationCoordinate2D(latitude: lat, longitude: lon))
        },
        boundDam: { binding in
            GenerationBindingMatch.dam(for: binding, in: await GenerationService.shared.allDams()).map(GenerationDamRef.init)
        },
        boundGeneration: { dam, lat, lon, current in
            if let current, current.value.dam.id == dam.value.id { return current }
            let miles = LakeDirectory.miles(CLLocationCoordinate2D(latitude: lat, longitude: lon), dam.value.coordinate)
            return await GenerationService.shared.generation(for: dam.value, distanceMiles: miles).map(GenerationRef.init)
        },
        now: { Date() },
        breaker: .shared,
        shadowRunner: .shared,
        log: { print($0) })
}

/// Immutable wrappers so the generation values can cross the detached shadow task (`TileShadow.resolve` needs `Sendable`).
struct GenerationDamRef: @unchecked Sendable, Equatable { let value: GenerationDam }
struct GenerationRef: @unchecked Sendable, Equatable { let value: DamGeneration }

/// Which registry dam a Lake Brain binding names: same operator, and the binding's `damId` (or its `tvaCode`) is the
/// operator-scoped dam id the Engine uses. Pure.
enum GenerationBindingMatch {
    static func dam(for b: GenerationBindingOutput, in dams: [GenerationDam]) -> GenerationDam? {
        guard b.status == LakeLevelOutput.available, let op = b.operatorId, let damId = b.damId else { return nil }
        return dams.first { d in
            d.operatorID.rawValue == op && (d.id == damId || (b.tvaCode.map { !$0.isEmpty && d.id == $0 } ?? false))
        }
    }

    static func key(_ dam: GenerationDam) -> String { "\(dam.operatorID.rawValue):\(dam.id)" }
}

/// One value computed once and shared by every caller (the five weather tiles share one NWS fetch).
actor SharedOnce<T: Sendable> {
    private let make: @Sendable () async -> T
    private var task: Task<T, Never>?
    init(_ make: @escaping @Sendable () async -> T) { self.make = make }
    func value() async -> T {
        if let task { return await task.value }
        let t = Task { await make() }
        task = t
        return await t.value
    }
}

// MARK: - Wiring

enum ConditionsTileWiring {

    static let nwsSource = "nws-nbm"
    static let lakeBrainSource = "lake-brain"
    static let bindingSource = "lake-brain-bindings"
    static let bindingSourceEngine = "engine-registry"
    static let bindingSourceBrain = "lake-brain"

    /// A Brain copy's status in `tileSources` vocabulary. Only AVAILABLE is ever served.
    static func status(_ s: String) -> TileStatus {
        switch s {
        case LakeLevelOutput.available: return .available
        case LakeLevelOutput.estimate: return .estimate
        default: return .unknown
        }
    }

    static func date(_ s: String?) -> Date? { s.flatMap(LakeLevelOutputAPI.isoDate) }

    // MARK: windOutlookModel (before the forecast runs)

    struct WindModelDecision: Sendable, Equatable {
        /// The outlook model for the future nights: nil = best_match.
        let model: String?
        /// The Wind Brain's decision was served (serve, AVAILABLE, breaker closed).
        let servedNew: Bool
        /// The Brain's entry when served; nil otherwise (the response labels today's entry once the forecast is known).
        let entry: TileSourceDTO?

        static let today = WindModelDecision(model: WindForecastModel.current, servedNew: false, entry: nil)
    }

    static func windOutlookModel(mode: TileMode, context: TileRequestContext,
                                 providers: ConditionsTileProviders) async -> WindModelDecision {
        guard mode != .off else { return .today }
        let envModel = WindForecastModel.current ?? WindOutlookModelOutputAPI.tonightModel
        let reader = providers.reader, now = providers.now
        let placeholder = TileSourceDTO(flag: mode.rawValue, path: TilePath.engine.rawValue,
                                        source: "open-meteo-" + envModel.replacingOccurrences(of: "_", with: "-"),
                                        status: TileStatus.available.rawValue)
        let r = await TileShadow.resolve(
            tile: .windOutlookModel, mode: mode, old: envModel, oldEntry: placeholder, context: context,
            new: { () -> TileNewValue<String> in
                let o = await WindOutlookModelOutputAPI.output(reader: reader, now: now())
                return TileNewValue(value: o.status == LakeLevelOutput.available ? o.nights2to7 : nil, status: status(o.status),
                                    path: .brain, source: WindOutlookModelOutputAPI.brainSource)
            },
            compare: { old, new in TileComparison(old: old.map(TileLogValue.string) ?? .null,
                                                  new: new.map(TileLogValue.string) ?? .null) },
            breaker: providers.breaker, shadowRunner: providers.shadowRunner, log: providers.log)
        guard r.servedNew, let chosen = r.value else { return .today }
        return WindModelDecision(model: chosen == WindOutlookModelOutputAPI.tonightModel ? nil : chosen,
                                 servedNew: true, entry: r.entry)
    }

    /// Whether the Wind Brain's model was actually served: decided in serve, and either it is the env model (today's forecast
    /// already runs on it) or the forecast on the Brain's model came back.
    static func windServed(_ d: WindModelDecision, brainForecastArrived: Bool) -> Bool {
        d.servedNew && (d.model == WindForecastModel.current || brainForecastArrived)
    }

    /// The windOutlookModel `tileSources` entry when the Brain's model was served (UNKNOWN when the outlook came back empty);
    /// nil otherwise, so `TileSources.build` labels today's entry (FALLBACK in serve).
    static func windEntry(_ d: WindModelDecision, served: Bool, outlookNights: Int) -> TileSourceDTO? {
        guard served, var e = d.entry else { return nil }
        if outlookNights == 0 { e.status = TileStatus.unknown.rawValue }
        return e
    }

    // MARK: clarity (before the score is evaluated)

    struct ClarityTileValue: Sendable, Equatable {
        var centralFt: Double?
        var brain: ClarityBrainOutput?
    }

    struct ClarityResult: Sendable, Equatable {
        let entry: TileSourceDTO
        /// The served copy (serve, AVAILABLE, breaker closed); nil otherwise.
        let served: ClarityBrainOutput?
        /// What the clarity factor runs on when the copy was served.
        var factorFt: Double? { served?.centralFt }
    }

    static func clarity(mode: TileMode, lakeId: String?, oldCentralFt: Double?, oldEntry: TileSourceDTO,
                        context: TileRequestContext, providers: ConditionsTileProviders) async -> ClarityResult {
        let reader = providers.reader, now = providers.now
        let r = await TileShadow.resolve(
            tile: .clarity, mode: mode, old: oldCentralFt.map { ClarityTileValue(centralFt: $0, brain: nil) },
            oldEntry: oldEntry, context: context,
            new: { () -> TileNewValue<ClarityTileValue> in
                guard let lakeId else { return TileNewValue(value: nil, status: .unknown, path: .brain, source: ClarityBrainOutputAPI.brainSource) }
                let o = await ClarityBrainOutputAPI.output(lakeId: lakeId, reader: reader, now: now())
                return TileNewValue(value: ClarityTileValue(centralFt: o.centralFt, brain: o), status: status(o.status),
                                    path: .brain, source: ClarityBrainOutputAPI.brainSource, observedAt: date(o.observedAt),
                                    freshUntil: date(o.freshUntil), runner: o.runner, publishId: o.publishId)
            },
            compare: { old, new in TileComparison.numeric(old?.centralFt, new?.centralFt) },
            breaker: providers.breaker, shadowRunner: providers.shadowRunner, log: providers.log)
        return ClarityResult(entry: r.entry, served: r.servedNew ? r.value?.brain : nil)
    }

    // MARK: Tiles applied to the built response

    /// What the response-time tiles need from today's path.
    struct LiveInputs {
        /// Today's Open-Meteo reading (for the shadow parity line); nil when there was no weather.
        var weather: WeatherReading?
        /// Today's generation answer (nearest dam / TailwaterRegistry).
        var generation: DamGeneration?
        var lat: Double
        var lon: Double
    }

    /// Applies the weather, waterLevel, waterTemp and generation tiles to `response` and returns their `tileSources`
    /// entries. `legacy` is today's entry per tile (`TileSources.legacy`). Only fields the spec names are written.
    static func applyResponseTiles(to response: inout ConditionsResponse, legacy: [TileKey: TileSourceDTO],
                                   inputs: LiveInputs, flags: TileFlags, context: TileRequestContext,
                                   providers: ConditionsTileProviders) async -> [TileKey: TileSourceDTO] {
        let lakeId = context.lakeId
        var modes: [TileKey: TileMode] = [:]
        for t in TileKey.allCases { modes[t] = flags.mode(for: t, lakeId: lakeId) }
        let weatherModes = modes.filter { weatherTiles.contains($0.key) }
        let levelMode = modes[.waterLevel]!, tempMode = modes[.waterTemp]!, genMode = modes[.generation]!

        // Today's values, read before the concurrent steps so none of them touches `response`.
        let oldWeather = response.weather, oldWaterF = response.waterTemp?.valueF, oldWater = response.water?.value
        let genPresent = response.generation != nil, oldGeneration = inputs.generation.map(GenerationRef.init)
        let lat = inputs.lat, lon = inputs.lon, oldReading = inputs.weather
        let levelEntry = legacy[.waterLevel]!, tempEntry = legacy[.waterTemp]!, genEntry = legacy[.generation]!

        // Concurrent, as unstructured tasks: an `async let` group here aborts the Linux runtime ("freed pointer was not the
        // last allocation", the same failure ConditionsSnapshot documents for revs 00041-00042; reproduced by this suite).
        let weather = Task { await weatherTiles(old: oldWeather, oldReading: oldReading, modes: weatherModes, legacy: legacy,
                                                context: context, lat: lat, lon: lon, providers: providers) }
        let level = Task { await waterLevel(mode: levelMode, lakeId: lakeId, oldGaugeValue: oldWater,
                                            oldEntry: levelEntry, context: context, providers: providers) }
        let temp = Task { await waterTemp(mode: tempMode, lakeId: lakeId, oldValueF: oldWaterF,
                                          oldEntry: tempEntry, context: context, providers: providers) }
        let gen = Task { await generation(mode: genMode, lakeId: lakeId, old: oldGeneration, oldPresent: genPresent,
                                          oldEntry: genEntry, context: context, lat: lat, lon: lon, providers: providers) }

        let w = await weather.value, l = await level.value, t = await temp.value, g = await gen.value
        var entries = w.entries
        response.weather = w.weather
        entries[.waterLevel] = l.entry
        if let served = l.served { response.lakeLevel = served }
        entries[.waterTemp] = t.entry
        if let served = t.served { response.waterTempBrain = served }
        entries[.generation] = g.entry
        if let served = g.served {
            var dto = SectorEngineAPI.generationDTO(served.value)
            dto.bindingSource = bindingSourceBrain
            response.generation = dto
        } else if genMode == .serve, response.generation != nil {
            response.generation?.bindingSource = bindingSourceEngine
        }
        return entries
    }

    // MARK: weather tiles

    static let weatherTiles: [TileKey] = [.humidity, .pressure, .temperature, .sky, .wind]

    /// One weather tile's fields. Today's value carries Open-Meteo's; the new value carries NWS's with Open-Meteo per
    /// field where NWS has no fresh value, plus the NWS reading itself for the shadow parity line.
    struct WeatherTileValue: Sendable, Equatable {
        var humidity: Int?
        var pressure: Double?
        var pressureTrend: String?
        var pressureChange: Double?
        var temperature: Double?
        var cloudCover: Double?
        var weatherCode: Int?
        var conditionSymbol: String?
        var conditionDescription: String?
        var windSpeed: Double?
        var windDirection: Int?
        var nws: NWSWeatherReading? = nil

        init(_ w: WeatherDTO) {
            humidity = w.humidity; pressure = w.pressure; pressureTrend = w.pressureTrend; pressureChange = w.pressureChange
            temperature = w.temperature; cloudCover = w.cloudCover; weatherCode = w.weatherCode
            conditionSymbol = w.conditionSymbol; conditionDescription = w.conditionDescription
            windSpeed = w.windSpeed; windDirection = w.windDirection
        }
    }

    /// A value newer than now − `NWSWeatherService.observationMaxAge` and not more than 10 minutes in the future; else nil.
    static func fresh<T>(_ v: NWSValue<T>?, now: Date) -> NWSValue<T>? {
        guard let v, v.observedAt >= now.addingTimeInterval(-NWSWeatherService.observationMaxAge),
              v.observedAt <= now.addingTimeInterval(BrainCopyRead.maxFutureSkew) else { return nil }
        return v
    }

    /// The NWS value for one tile over today's fields (per-field fallback to Open-Meteo). UNKNOWN when NWS has no fresh
    /// value for the tile's primary field: humidity, pressure, temperature, wind speed; for sky, cloud cover or the
    /// weather code. The weather code, its SF Symbol and its description always move together.
    static func nwsValue(_ tile: TileKey, nws: NWSWeatherReading?, old: WeatherDTO, now: Date) -> TileNewValue<WeatherTileValue> {
        func unknown() -> TileNewValue<WeatherTileValue> { TileNewValue(value: nil, status: .unknown, path: .engine, source: nwsSource) }
        guard let nws else { return unknown() }
        var v = WeatherTileValue(old)
        v.nws = nws
        let observed: Date
        switch tile {
        case .humidity:
            guard let h = fresh(nws.humidity, now: now), (0...100).contains(h.value) else { return unknown() }
            v.humidity = h.value; observed = h.observedAt
        case .pressure:
            guard let p = fresh(nws.pressure, now: now), p.value.isFinite else { return unknown() }
            v.pressure = p.value; observed = p.observedAt
            if let trend = nws.pressureTrend, let change = nws.pressureChange, change.isFinite {
                v.pressureTrend = NWSWeatherParity.trendString(trend); v.pressureChange = change
            }
        case .temperature:
            guard let t = fresh(nws.temperature, now: now), t.value.isFinite else { return unknown() }
            v.temperature = t.value; observed = t.observedAt
        case .sky:
            let cloud = fresh(nws.cloudCover, now: now).flatMap { (0...100).contains($0.value) ? $0 : nil }
            var code: NWSValue<Int>? = nil
            if let c = fresh(nws.weatherCode, now: now), nws.conditionSymbol != nil, nws.conditionDescription != nil { code = c }
            guard cloud != nil || code != nil else { return unknown() }
            if let cloud { v.cloudCover = cloud.value }
            if let code, let symbol = nws.conditionSymbol, let text = nws.conditionDescription {
                v.weatherCode = code.value; v.conditionSymbol = symbol; v.conditionDescription = text
            }
            observed = code?.observedAt ?? cloud!.observedAt
        case .wind:
            guard let s = fresh(nws.windSpeed, now: now), s.value.isFinite, s.value >= 0 else { return unknown() }
            v.windSpeed = s.value; observed = s.observedAt
            if let d = fresh(nws.windDirection, now: now) { v.windDirection = d.value }
        default:
            return unknown()
        }
        return TileNewValue(value: v, status: .available, path: .engine, source: nwsSource, observedAt: observed)
    }

    /// `w` with ONLY `tile`'s fields taken from `v`.
    static func apply(_ tile: TileKey, _ v: WeatherTileValue, to w: WeatherDTO) -> WeatherDTO {
        var humidity = w.humidity, pressure = w.pressure, pressureTrend = w.pressureTrend, pressureChange = w.pressureChange
        var temperature = w.temperature, cloudCover = w.cloudCover, weatherCode = w.weatherCode
        var conditionSymbol = w.conditionSymbol, conditionDescription = w.conditionDescription
        var windSpeed = w.windSpeed, windDirection = w.windDirection
        switch tile {
        case .humidity: humidity = v.humidity ?? humidity
        case .pressure:
            pressure = v.pressure ?? pressure
            pressureTrend = v.pressureTrend ?? pressureTrend
            pressureChange = v.pressureChange ?? pressureChange
        case .temperature: temperature = v.temperature ?? temperature
        case .sky:
            cloudCover = v.cloudCover ?? cloudCover
            if let c = v.weatherCode, let s = v.conditionSymbol, let d = v.conditionDescription {
                weatherCode = c; conditionSymbol = s; conditionDescription = d
            }
        case .wind:
            windSpeed = v.windSpeed ?? windSpeed
            windDirection = v.windDirection ?? windDirection
        default: break
        }
        return WeatherDTO(temperature: temperature, conditionDescription: conditionDescription, conditionSymbol: conditionSymbol,
                          windSpeed: windSpeed, windDirection: windDirection, precipitation: w.precipitation,
                          recentRainfall: w.recentRainfall, humidity: humidity, pressure: pressure, pressureTrend: pressureTrend,
                          pressureChange: pressureChange, cloudCover: cloudCover, weatherCode: weatherCode,
                          pressureHourly: w.pressureHourly, hourlyConditions: w.hourlyConditions)
    }

    /// Today's reading rebuilt from the served DTO, for the parity line when the snapshot's reading is not at hand.
    static func reading(from w: WeatherDTO, at time: Date) -> WeatherReading {
        let trend: PressureTrend = w.pressureTrend == "rising" ? .rising : w.pressureTrend == "falling" ? .falling : .steady
        return WeatherReading(temperature: w.temperature, conditionDescription: w.conditionDescription,
                              conditionSymbol: w.conditionSymbol, windSpeed: w.windSpeed, windDirection: w.windDirection,
                              precipitation: w.precipitation, recentRainfall: w.recentRainfall, humidity: w.humidity,
                              pressure: w.pressure, pressureTrend: trend, pressureChange: w.pressureChange,
                              cloudCover: w.cloudCover, weatherCode: w.weatherCode, time: time,
                              pressureHistory: w.pressureHourly.map { PressureSample(date: $0.time, hPa: $0.hPa) })
    }

    static func weatherTiles(old: WeatherDTO?, oldReading: WeatherReading?, modes: [TileKey: TileMode],
                             legacy: [TileKey: TileSourceDTO], context: TileRequestContext, lat: Double, lon: Double,
                             providers: ConditionsTileProviders) async -> (weather: WeatherDTO?, entries: [TileKey: TileSourceDTO]) {
        var served = old
        var entries: [TileKey: TileSourceDTO] = [:]
        // No Open-Meteo base: nothing to patch, so no new source (serve reports UNKNOWN, as today's tile is blank).
        let fetchNWS = providers.nwsReading
        let shared = SharedOnce<NWSWeatherReading?> { await fetchNWS(lat, lon) }
        let now = providers.now
        let mode = { (t: TileKey) in modes[t] ?? .off }

        // serve: ONE NWS fetch under ONE new-path deadline, shared by every served weather tile. The first tile whose breaker
        // lets it try starts it (so an open breaker on every tile means no fetch at all); the others get the same answer at
        // once. The tiles of a request see the same reading or all fall back together, and weather waits at most one deadline.
        let serveReading = SharedOnce<NWSWeatherReading?> {
            // A little inside each tile's own new-path deadline, so the first tile never times out on an answer the rest serve.
            await withDeadline(TileShadow.newPathDeadlineSeconds - 0.2, "nws-weather-serve") { await shared.value() } ?? nil
        }

        for tile in weatherTiles {
            var newSource: (@Sendable () async -> TileNewValue<WeatherTileValue>)? = nil
            // shadow tiles pass no provider: resolve serves old and labels the entry; the ONE shadow job below logs them.
            if let base = old, mode(tile) == .serve {
                newSource = { @Sendable in nwsValue(tile, nws: await serveReading.value(), old: base, now: now()) }
            }
            let r = await TileShadow.resolve(
                tile: tile, mode: mode(tile), old: old.map(WeatherTileValue.init), oldEntry: legacy[tile]!, context: context,
                new: newSource,
                compare: { _, _ in TileComparison(old: .null, new: .null) },
                breaker: providers.breaker, shadowRunner: providers.shadowRunner, log: providers.log)
            entries[tile] = r.entry
            if r.servedNew, let v = r.value, let base = served { served = apply(tile, v, to: base) }
        }

        // shadow: ONE detached job per request (one runner slot, never blocking the response) awaits the shared NWS reading
        // under the new-path deadline and writes one NWSWeatherParity `[tile-shadow]` line per shadowed tile. A timeout logs
        // the lines with `new` null.
        let shadowTiles = weatherTiles.filter { mode($0) == .shadow }
        if let base = old, !shadowTiles.isEmpty {
            let parityOld = oldReading ?? reading(from: base, at: now())
            let log = providers.log
            await providers.shadowRunner.launch {
                let n = await withDeadline(TileShadow.newPathDeadlineSeconds, "tile-shadow-weather") { await shared.value() } ?? nil
                let parity = NWSWeatherParity.compare(old: parityOld, new: n)
                for tile in shadowTiles {
                    guard let p = parity.first(where: { $0.tile == tile.rawValue }) else { continue }
                    log(NWSWeatherParity.logLine(p, lakeId: context.lakeId, latR: context.latR, lonR: context.lonR))
                }
            }
        }
        return (served, entries)
    }

    // MARK: waterLevel

    struct LevelTileValue: Sendable, Equatable {
        var gaugeValue: Double?
        var lake: LakeLevelOutput?
    }

    static func waterLevel(mode: TileMode, lakeId: String?, oldGaugeValue: Double?, oldEntry: TileSourceDTO,
                           context: TileRequestContext, providers: ConditionsTileProviders)
        async -> (entry: TileSourceDTO, served: LakeLevelOutput?) {
        let reader = providers.reader, now = providers.now
        // Every existing lake-level gate still applies: the owner's SECTOR_LAKE_LEVEL_OUTPUT switch and the validated-lake list
        // (spec §4: eligible lakes only). The tile flag is one more gate in front of them, never a way around them.
        let eligibility = providers.lakeLevelEligibility
        let r = await TileShadow.resolve(
            tile: .waterLevel, mode: mode, old: oldGaugeValue.map { LevelTileValue(gaugeValue: $0, lake: nil) },
            oldEntry: oldEntry, context: context,
            new: { () -> TileNewValue<LevelTileValue> in
                guard let lakeId else { return TileNewValue(value: nil, status: .unknown, path: .brain, source: lakeBrainSource) }
                let o = await LakeLevelOutputAPI.output(lakeId: lakeId, eligibility: eligibility, reader: reader, now: now())
                return TileNewValue(value: LevelTileValue(gaugeValue: nil, lake: o), status: status(o.status), path: .brain,
                                    source: lakeBrainSource, observedAt: date(o.observationTime), freshUntil: date(o.freshUntil))
            },
            // A gauge stage and a lake elevation are not on one datum: both are logged, no delta.
            compare: { old, new in TileComparison(old: old?.gaugeValue.map(TileLogValue.number) ?? .null,
                                                  new: new?.lake?.elevationFt.map(TileLogValue.number) ?? .null) },
            breaker: providers.breaker, shadowRunner: providers.shadowRunner, log: providers.log)
        return (r.entry, r.servedNew ? r.value?.lake : nil)
    }

    // MARK: waterTemp

    struct WaterTempTileValue: Sendable, Equatable {
        var valueF: Double?
        var brain: WaterTempBrainOutput?
    }

    static func waterTemp(mode: TileMode, lakeId: String?, oldValueF: Double?, oldEntry: TileSourceDTO,
                          context: TileRequestContext, providers: ConditionsTileProviders)
        async -> (entry: TileSourceDTO, served: WaterTempBrainOutput?) {
        let reader = providers.reader, now = providers.now
        let r = await TileShadow.resolve(
            tile: .waterTemp, mode: mode, old: oldValueF.map { WaterTempTileValue(valueF: $0, brain: nil) },
            oldEntry: oldEntry, context: context,
            new: { () -> TileNewValue<WaterTempTileValue> in
                guard let lakeId else {
                    return TileNewValue(value: nil, status: .unknown, path: .brain, source: WaterTempBrainOutputAPI.brainSource)
                }
                let o = await WaterTempBrainOutputAPI.output(lakeId: lakeId, reader: reader, now: now())
                return TileNewValue(value: WaterTempTileValue(valueF: o.valueF, brain: o), status: status(o.status),
                                    path: .brain, source: WaterTempBrainOutputAPI.brainSource, observedAt: date(o.observedAt),
                                    freshUntil: date(o.freshUntil), runner: o.runner, publishId: o.publishId)
            },
            compare: { old, new in TileComparison.numeric(old?.valueF, new?.valueF) },
            breaker: providers.breaker, shadowRunner: providers.shadowRunner, log: providers.log)
        return (r.entry, r.servedNew ? r.value?.brain : nil)
    }

    // MARK: generation

    struct GenerationTileValue: Sendable, Equatable {
        /// "OPERATOR:damId" of the dam chosen.
        var damKey: String?
        var generation: GenerationRef?
    }

    static func generation(mode: TileMode, lakeId: String?, old: GenerationRef?, oldPresent: Bool, oldEntry: TileSourceDTO,
                           context: TileRequestContext, lat: Double, lon: Double, providers: ConditionsTileProviders)
        async -> (entry: TileSourceDTO, served: GenerationRef?) {
        let reader = providers.reader, now = providers.now
        let boundDam = providers.boundDam, boundGeneration = providers.boundGeneration
        let oldValue: GenerationTileValue? = old.map { GenerationTileValue(damKey: GenerationBindingMatch.key($0.value.dam), generation: $0) }
            ?? (oldPresent ? GenerationTileValue(damKey: nil, generation: nil) : nil)
        let fetch = mode == .serve   // shadow only compares the dam chosen; it never fetches generation
        let r = await TileShadow.resolve(
            tile: .generation, mode: mode, old: oldValue, oldEntry: oldEntry, context: context,
            new: { () -> TileNewValue<GenerationTileValue> in
                func unknown() -> TileNewValue<GenerationTileValue> {
                    TileNewValue(value: nil, status: .unknown, path: .brain, source: bindingSource)
                }
                guard let lakeId else { return unknown() }
                let b = await GenerationBindingOutputAPI.output(lakeId: lakeId, reader: reader, now: now())
                guard b.status == LakeLevelOutput.available, let op = b.operatorId, let damId = b.damId else { return unknown() }
                let dam = await boundDam(b)
                guard fetch else {
                    let key = dam.map { GenerationBindingMatch.key($0.value) } ?? "\(op):\(damId)"
                    return TileNewValue(value: GenerationTileValue(damKey: key, generation: nil), status: .available,
                                        path: .brain, source: bindingSource)
                }
                guard let dam, let g = await boundGeneration(dam, lat, lon, old) else { return unknown() }
                return TileNewValue(value: GenerationTileValue(damKey: GenerationBindingMatch.key(dam.value), generation: g),
                                    status: .available, path: .brain, source: bindingSource,
                                    observedAt: g.value.observedAt.flatMap {
                                        SectorEngineAPI.tileObservedAt(operatorID: g.value.dam.operatorID, observedAt: $0)
                                    })
            },
            compare: { old, new in TileComparison(old: old?.damKey.map(TileLogValue.string) ?? .null,
                                                  new: new?.damKey.map(TileLogValue.string) ?? .null) },
            breaker: providers.breaker, shadowRunner: providers.shadowRunner, log: providers.log)
        return (r.entry, r.servedNew ? r.value?.generation : nil)
    }
}
