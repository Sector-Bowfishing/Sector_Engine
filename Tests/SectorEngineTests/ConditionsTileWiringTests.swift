//
//  ConditionsTileWiringTests.swift
//  SectorEngineTests
//
//  Conditions consolidation, the wiring step (Sector_Ops #53, spec §1/§4): every tile in off / shadow / serve, the
//  fallbacks, an open breaker, frozen fields untouched, and the phone contract (PhoneContractTests' validator + the vendored
//  build 28 decoder) with every flag off AND every flag in serve. All sources are injected fakes: no network, no real clock.
//

import XCTest
#if canImport(CoreLocation)
import CoreLocation
#endif
@testable import SectorEngine

final class ConditionsTileWiringTests: XCTestCase {

    // MARK: - Fixtures

    static let now = ISO8601DateFormatter().date(from: "2026-11-10T15:30:00Z")!
    static func iso(_ d: Date) -> String { ISO8601DateFormatter().string(from: d) }
    static let lake = "Guntersville|AL"
    /// On LakeLevelEligibility.validatedLakeIds.
    static let validatedLake = "Tygart Lake|WV"

    static func ctx(_ lakeId: String? = lake) -> TileRequestContext { TileRequestContext(lakeId: lakeId, lat: 34.4321, lon: -86.2549) }

    static func flags(_ mode: TileMode, _ tiles: [TileKey] = TileKey.allCases) -> TileFlags {
        TileFlags(tiles: Dictionary(uniqueKeysWithValues: tiles.map { ($0, TileFlags.Tile(mode: mode)) }))
    }

    static let weather = WeatherDTO(
        temperature: 61.0, conditionDescription: "Partly Cloudy", conditionSymbol: "cloud.sun.fill", windSpeed: 7.0,
        windDirection: 200, precipitation: 0, recentRainfall: 0.4, humidity: 61, pressure: 1016.0, pressureTrend: "steady",
        pressureChange: 0.3, cloudCover: 40, weatherCode: 2,
        pressureHourly: [PressureSampleDTO(time: now.addingTimeInterval(-3600), hPa: 1015.8)],
        hourlyConditions: [ConditionsHourlyDTO(time: now, tempF: 61, humidity: 61, windMph: 7, gustMph: nil, windDir: 200,
                                               dewPointF: 47, cloudPct: 40, precipIn: 0)])

    static func nwsValue<T>(_ v: T, age: TimeInterval = 600, origin: NWSValueOrigin = .observation) -> NWSValue<T> {
        NWSValue(value: v, observedAt: now.addingTimeInterval(-age), origin: origin, stationId: origin == .observation ? "KGAD" : nil)
    }

    static func nws(temperature: NWSValue<Double>? = nwsValue(58.0), humidity: NWSValue<Int>? = nwsValue(55),
                    pressure: NWSValue<Double>? = nwsValue(1019.4), trend: PressureTrend? = .rising, change: Double? = 2.1,
                    windSpeed: NWSValue<Double>? = nwsValue(9.2), windDirection: NWSValue<Int>? = nwsValue(230),
                    cloud: NWSValue<Double>? = nwsValue(75.0), code: NWSValue<Int>? = nwsValue(3),
                    symbol: String? = "cloud.fill", description: String? = "Overcast") -> NWSWeatherReading {
        NWSWeatherReading(fetchedAt: now, gridpoint: "HUN/76,30", temperature: temperature, humidity: humidity, pressure: pressure,
                          pressureKind: .seaLevel, seaLevelOffset: nil, pressureTrend: trend, pressureChange: change,
                          pressureTrend3h: trend, pressureChange3h: change, windSpeed: windSpeed, windDirection: windDirection,
                          cloudCover: cloud, weatherCode: code, conditionDescription: description, conditionSymbol: symbol,
                          nwsTextDescription: "Overcast", pressureHistory: [], hourlyConditions: [])
    }

    // Brain copies, fresh at `now`.
    static func copies(lakeId: String = lake, extra: [String: String] = [:]) -> [String: String] {
        let obs = iso(now.addingTimeInterval(-3600)), until = iso(now.addingTimeInterval(7200)), day = iso(now.addingTimeInterval(-86400))
        var out = [
            LakeLevelOutputAPI.copyPath(lakeId): """
            {"schema":"sector-customer-lake-level-v1","lakeId":"\(lakeId)","status":"AVAILABLE","elevationFt":1094.2,"datum":"NGVD29",
             "observationTime":"\(obs)","sourceAgeHours":1,"trend":"STABLE","change24hFt":0.1,"freshUntil":"\(until)"}
            """,
            ClarityBrainOutputAPI.copyPath(lakeId): """
            {"schema":"sector-customer-clarity-v1","lakeId":"\(lakeId)","status":"AVAILABLE","centralFt":2.25,"lowFt":1.5,"highFt":3.0,
             "confidence":"medium","observedAt":"\(obs)","freshUntil":"\(until)","runner":"pulse","publishId":"7def2674"}
            """,
            WaterTempBrainOutputAPI.copyPath(lakeId): """
            {"schema":"sector-customer-water-temp-v1","lakeId":"\(lakeId)","status":"AVAILABLE","valueF":64.2,"kind":"measured",
             "observedAt":"\(obs)","freshUntil":"\(until)","runner":"cloud","publishId":"a1b2c3"}
            """,
            GenerationBindingOutputAPI.copyPath(lakeId): """
            {"schema":"sector-customer-generation-binding-v1","lakeId":"\(lakeId)","operatorId":"TVA","damId":"NRST1",
             "damName":"Nickajack Dam","tvaCode":"NRST1","updatedAt":"\(day)"}
            """,
            WindOutlookModelOutputAPI.copyPath: """
            {"schema":"sector-customer-wind-outlook-model-v1","tonight":"best_match","nights2to7":"ncep_nbm_conus",
             "decidedBy":"wind-brain","evidence":"W1b","updatedAt":"\(day)"}
            """,
        ]
        for (k, v) in extra { out[k] = v }
        return out
    }

    static let todayDam = GenerationDam(id: "GUNT1", operatorID: .tva, name: "Guntersville Dam", latitude: 34.42, longitude: -86.39,
                                        river: "Tennessee")
    static let boundDam = GenerationDam(id: "NRST1", operatorID: .tva, name: "Nickajack Dam", latitude: 35.0, longitude: -85.62,
                                        river: "Tennessee")
    static func generation(_ dam: GenerationDam, cfs: Double) -> DamGeneration {
        DamGeneration(dam: dam, distanceMiles: 3, windows: [], dischargeCfs: cfs, dischargeTrend12hCfs: nil,
                      reservoirElevationFt: 595.1, tailwaterElevationFt: 560.2, observedAt: now.addingTimeInterval(-900), history: [])
    }

    private func providers(reader: BrainOutputReader? = nil, nws: NWSWeatherReading? = nil, calls: WCalls = WCalls(),
                   lines: WLines = WLines(), runner: TileShadowRunner = TileShadowRunner(),
                   breaker: TileBreakerRegistry = TileBreakerRegistry(log: { _ in }),
                   lakeLevelSwitch: Bool = true, nwsDelaySeconds: Double = 0) -> ConditionsTileProviders {
        var p = ConditionsTileProviders(
            reader: reader,
            nwsReading: { _, _ in
                calls.inc("nws")
                if nwsDelaySeconds > 0 { try? await Task.sleep(nanoseconds: UInt64(nwsDelaySeconds * 1e9)) }
                return nws
            },
            boundDam: { b in calls.inc("boundDam"); return GenerationBindingMatch.dam(for: b, in: [Self.todayDam, Self.boundDam]).map(GenerationDamRef.init) },
            boundGeneration: { dam, _, _, current in
                calls.inc("boundGeneration")
                if let current, current.value.dam.id == dam.value.id { return current }
                return GenerationRef(value: Self.generation(dam.value, cfs: 4100))
            },
            now: { Self.now }, breaker: breaker, shadowRunner: runner, log: { lines.append($0) })
        p.lakeLevelEligibility = LakeLevelEligibility(enabled: lakeLevelSwitch, eligibleLakeIds: LakeLevelEligibility.validatedLakeIds)
        return p
    }

    /// A golden /conditions response (decoded with the Engine's own type).
    static func golden(_ name: String = "guntersville-al.json") throws -> ConditionsResponse {
        let f = try XCTUnwrap(PhoneContractTests.goldenFiles().first { $0.lastPathComponent == name })
        let d = JSONDecoder(); d.dateDecodingStrategy = .iso8601
        return try d.decode(ConditionsResponse.self, from: Data(contentsOf: f))
    }

    static func legacy(_ r: ConditionsResponse) -> [TileKey: TileSourceDTO] {
        TileSources.legacy(LegacyTileFacts(weatherPresent: r.weather != nil, outlookNights: r.nights.count,
                                           waterPresent: r.water != nil, waterObservedAt: r.water?.observedAt,
                                           claritySource: r.clarityVisibility?.source,
                                           waterTempKind: r.waterTempState?.kind ?? "unavailable",
                                           waterTempSourceKind: r.waterTempState?.sourceKind ?? "none",
                                           generationPresent: r.generation != nil, generationHasReading: r.generation != nil))
    }

    /// Runs every wired step on `response` (clarity + the response-time tiles; the wind decision separately).
    private func wire(_ response: inout ConditionsResponse, flags: TileFlags, context: TileRequestContext,
              providers p: ConditionsTileProviders, generation: DamGeneration? = nil) async -> [TileKey: TileSourceDTO] {
        let legacy = Self.legacy(response)
        let mode = { (t: TileKey) in flags.mode(for: t, lakeId: context.lakeId) }
        let clarity = await ConditionsTileWiring.clarity(mode: mode(.clarity), lakeId: context.lakeId,
                                                         oldCentralFt: response.clarityVisibility?.centralFt,
                                                         oldEntry: legacy[.clarity]!, context: context, providers: p)
        var entries = await ConditionsTileWiring.applyResponseTiles(
            to: &response, legacy: legacy, inputs: .init(weather: nil, generation: generation, lat: 34.43, lon: -86.25),
            flags: flags, context: context, providers: p)
        entries[.clarity] = clarity.entry
        if let s = clarity.served { response.clarityBrain = s }
        return entries
    }

    private func base() -> ConditionsResponse {
        var r = try! Self.golden()
        r.weather = Self.weather
        return r
    }

    static let frozenKeys = ["water", "discharge", "waterTempModel", "waterTemp", "waterTempState", "clarityVisibility",
                             "score", "factors", "nights", "tonight"]

    static func json(_ r: ConditionsResponse) throws -> [String: Any] {
        try JSONSerialization.jsonObject(with: SectorEngineAPI.makeEncoder().encode(r)) as! [String: Any]
    }

    static func assertFrozenUntouched(_ before: ConditionsResponse, _ after: ConditionsResponse, file: StaticString = #filePath, line: UInt = #line) throws {
        let a = try json(before), b = try json(after)
        func canonical(_ v: Any?) throws -> String? {
            guard let v else { return nil }
            let data = try JSONSerialization.data(withJSONObject: ["v": v], options: [.sortedKeys])
            return String(decoding: data, as: UTF8.self)
        }
        for k in frozenKeys {
            XCTAssertEqual(try canonical(a[k]), try canonical(b[k]), "frozen field \(k) changed", file: file, line: line)
        }
    }

    // MARK: - Every flag off: identical output, no new source called

    func testAllOffChangesNothingAndCallsNothing() async throws {
        for f in try PhoneContractTests.goldenFiles() {
            let d = JSONDecoder(); d.dateDecodingStrategy = .iso8601
            let before = try d.decode(ConditionsResponse.self, from: Data(contentsOf: f))
            var after = before
            let calls = WCalls(), lines = WLines(), reader = WReader(nodes: Self.copies())
            let p = providers(reader: reader, nws: Self.nws(), calls: calls, lines: lines)
            let entries = await wire(&after, flags: .allOff, context: Self.ctx(before.resolvedLake?.id), providers: p)
            XCTAssertEqual(try SectorEngineAPI.makeEncoder().encode(after), try SectorEngineAPI.makeEncoder().encode(before), f.lastPathComponent)
            XCTAssertEqual(calls.all, [:], f.lastPathComponent)
            XCTAssertEqual(reader.reads, 0, f.lastPathComponent)
            XCTAssertTrue(lines.all.isEmpty, f.lastPathComponent)
            let legacy = Self.legacy(before)
            for (t, e) in entries { XCTAssertEqual(e, legacy[t], "\(f.lastPathComponent) \(t)") }
        }
        let wind = await ConditionsTileWiring.windOutlookModel(mode: .off, context: Self.ctx(), providers: providers(reader: WReader(nodes: Self.copies())))
        XCTAssertEqual(wind, .today)
    }

    // MARK: - Weather tiles

    func testWeatherShadowServesOldLogsParityOncePerTileAndFetchesOnce() async throws {
        var r = base()
        let before = r
        let calls = WCalls(), lines = WLines(), runner = TileShadowRunner()
        let p = providers(nws: Self.nws(), calls: calls, lines: lines, runner: runner)
        let entries = await wire(&r, flags: Self.flags(.shadow, ConditionsTileWiring.weatherTiles), context: Self.ctx(), providers: p)
        await runner.waitUntilIdle()
        XCTAssertEqual(r.weather, before.weather, "shadow serves old")
        XCTAssertEqual(calls.all["nws"], 1, "one NWS fetch shared by the five tiles")
        XCTAssertEqual(lines.all.count, 5)
        for t in ConditionsTileWiring.weatherTiles {
            XCTAssertEqual(entries[t]?.flag, "shadow"); XCTAssertEqual(entries[t]?.source, "open-meteo")
            XCTAssertTrue(lines.all.contains { $0.hasPrefix("[tile-shadow] ") && $0.contains(#""tile":"\#(t.rawValue)""#) }, t.rawValue)
        }
        let humidity = try XCTUnwrap(lines.all.first { $0.contains(#""tile":"humidity""#) })
        XCTAssertTrue(humidity.contains(#""old":61"#) && humidity.contains(#""new":55"#) && humidity.contains(#""delta":-6"#), humidity)
        XCTAssertTrue(humidity.contains(#""newSource":"nws-nbm""#) && humidity.contains(#""lakeId":"Guntersville|AL""#), humidity)
        let sky = try XCTUnwrap(lines.all.first { $0.contains(#""tile":"sky""#) })
        XCTAssertTrue(sky.contains(#""codeNew":3"#) && sky.contains(#""symbolNew":"cloud.fill""#), "parity detail: \(sky)")
    }

    func testWeatherServeReplacesOnlyThatTilesFields() async throws {
        let n = Self.nws()
        let expect: [TileKey: (WeatherDTO) -> [AnyHashable]] = [
            .humidity: { [$0.humidity] }, .temperature: { [$0.temperature] },
            .pressure: { [$0.pressure, $0.pressureTrend, $0.pressureChange] },
            .sky: { [$0.cloudCover, $0.weatherCode, $0.conditionSymbol, $0.conditionDescription] },
            .wind: { [$0.windSpeed, $0.windDirection] },
        ]
        let newValues: [TileKey: [AnyHashable]] = [
            .humidity: [55], .temperature: [58.0], .pressure: [1019.4, "rising", 2.1],
            .sky: [75.0, 3, "cloud.fill", "Overcast"], .wind: [9.2, 230],
        ]
        for tile in ConditionsTileWiring.weatherTiles {
            var r = base()
            let before = r
            let entries = await wire(&r, flags: Self.flags(.serve, [tile]), context: Self.ctx(), providers: providers(nws: n))
            let w = try XCTUnwrap(r.weather), old = try XCTUnwrap(before.weather)
            XCTAssertEqual(expect[tile]!(w), newValues[tile]!, tile.rawValue)
            for other in ConditionsTileWiring.weatherTiles where other != tile {
                XCTAssertEqual(expect[other]!(w), expect[other]!(old), "\(tile) must not touch \(other)")
            }
            XCTAssertEqual(w.pressureHourly, old.pressureHourly); XCTAssertEqual(w.hourlyConditions, old.hourlyConditions)
            XCTAssertEqual(w.precipitation, old.precipitation); XCTAssertEqual(w.recentRainfall, old.recentRainfall)
            let e = try XCTUnwrap(entries[tile])
            XCTAssertEqual([e.flag, e.path, e.source, e.status], ["serve", "engine", "nws-nbm", "AVAILABLE"], tile.rawValue)
            XCTAssertEqual(e.observedAt, Self.now.addingTimeInterval(-600))
            try Self.assertFrozenUntouched(before, r)
        }
    }

    func testWeatherServeFallsBackPerField() async throws {
        // Pressure without a trend keeps Open-Meteo's trend + change; wind without a direction keeps Open-Meteo's
        // direction; sky without a code keeps code, symbol and description together.
        let n = Self.nws(trend: nil, change: nil, windDirection: nil, code: nil, symbol: nil, description: nil)
        var r = base()
        _ = await wire(&r, flags: Self.flags(.serve, [.pressure, .wind, .sky]), context: Self.ctx(), providers: providers(nws: n))
        let w = try XCTUnwrap(r.weather)
        XCTAssertEqual(w.pressure, 1019.4); XCTAssertEqual(w.pressureTrend, "steady"); XCTAssertEqual(w.pressureChange, 0.3)
        XCTAssertEqual(w.windSpeed, 9.2); XCTAssertEqual(w.windDirection, 200)
        XCTAssertEqual(w.cloudCover, 75); XCTAssertEqual(w.weatherCode, 2); XCTAssertEqual(w.conditionSymbol, "cloud.sun.fill")
        XCTAssertEqual(w.conditionDescription, "Partly Cloudy")
    }

    func testWeatherServeFallsBackWhenNWSHasNothingFresh() async throws {
        let stale = Self.nws(temperature: Self.nwsValue(58.0, age: 3 * 3600), humidity: nil, pressure: nil,
                             windSpeed: Self.nwsValue(9.0, age: -3600), cloud: nil, code: nil)
        for n in [nil, stale] as [NWSWeatherReading?] {
            var r = base()
            let before = r
            let entries = await wire(&r, flags: Self.flags(.serve, ConditionsTileWiring.weatherTiles), context: Self.ctx(),
                                     providers: providers(nws: n))
            XCTAssertEqual(r.weather, before.weather, "no tile goes blank; Open-Meteo is served")
            for t in ConditionsTileWiring.weatherTiles {
                XCTAssertEqual(entries[t]?.status, "FALLBACK", t.rawValue); XCTAssertEqual(entries[t]?.source, "open-meteo")
            }
        }
    }

    func testWeatherWithoutOpenMeteoBaseStaysBlank() async throws {
        var r = base()
        r.weather = nil
        let calls = WCalls()
        let entries = await wire(&r, flags: Self.flags(.serve, ConditionsTileWiring.weatherTiles), context: Self.ctx(),
                                 providers: providers(nws: Self.nws(), calls: calls))
        XCTAssertNil(r.weather)
        XCTAssertNil(calls.all["nws"])
        for t in ConditionsTileWiring.weatherTiles { XCTAssertEqual(entries[t]?.status, "UNKNOWN") }
    }

    func testWeatherBreakerOpenServesOldWithoutFetching() async throws {
        let breaker = TileBreakerRegistry(now: { Self.now }, roll: { 0.99 }, log: { _ in })
        for _ in 0..<20 {   // 20 blank new samples vs a present old one: trips
            var r = base()
            _ = await wire(&r, flags: Self.flags(.serve, [.humidity]), context: Self.ctx(), providers: providers(nws: nil, breaker: breaker))
        }
        var r = base()
        let before = r
        let calls = WCalls()
        let entries = await wire(&r, flags: Self.flags(.serve, [.humidity]), context: Self.ctx(),
                                 providers: providers(nws: Self.nws(), calls: calls, breaker: breaker))
        XCTAssertEqual(r.weather, before.weather)
        XCTAssertNil(calls.all["nws"], "open breaker: NWS is not called")
        XCTAssertEqual(entries[.humidity]?.status, "FALLBACK")
    }

    func testWeatherShadowUsesOneRunnerSlot() async throws {
        var r = base()
        let lines = WLines(), runner = TileShadowRunner(maxConcurrent: 1)
        _ = await wire(&r, flags: Self.flags(.shadow, ConditionsTileWiring.weatherTiles), context: Self.ctx(),
                       providers: providers(nws: Self.nws(), lines: lines, runner: runner))
        await runner.waitUntilIdle()
        let dropped = await runner.dropped
        XCTAssertEqual(dropped, 0, "the five weather tiles share one shadow job")
        XCTAssertEqual(lines.all.count, 5)
    }

    func testWeatherServeWaitsOneDeadlineForAllTiles() async throws {
        // NWS slower than the 3 s new-path deadline: every weather tile falls back together, after ONE deadline (not five).
        var r = base()
        let before = r
        let started = Date()
        let entries = await wire(&r, flags: Self.flags(.serve, ConditionsTileWiring.weatherTiles), context: Self.ctx(),
                                 providers: providers(nws: Self.nws(), nwsDelaySeconds: 4.5))
        let elapsed = Date().timeIntervalSince(started)
        XCTAssertLessThan(elapsed, 4.4, "the weather step waited \(elapsed) s")
        XCTAssertEqual(r.weather, before.weather, "no mix of sources: every tile fell back")
        for t in ConditionsTileWiring.weatherTiles { XCTAssertEqual(entries[t]?.status, "FALLBACK", t.rawValue) }
    }

    // MARK: - waterLevel

    func testWaterLevelServeNeedsTheExistingLakeLevelSwitch() async throws {
        var r = base()
        let entries = await wire(&r, flags: Self.flags(.serve, [.waterLevel]), context: Self.ctx(Self.validatedLake),
                                 providers: providers(reader: WReader(nodes: Self.copies(lakeId: Self.validatedLake)), lakeLevelSwitch: false))
        XCTAssertNil(r.lakeLevel, "SECTOR_LAKE_LEVEL_OUTPUT off: the tile flag alone never opens lakeLevel")
        XCTAssertEqual(entries[.waterLevel]?.status, r.water == nil ? "UNKNOWN" : "FALLBACK")
        XCTAssertFalse(LakeLevelEligibility.fromEnvironment([:]).enabled, "the existing switch defaults off")
    }

    func testWaterLevelOffShadowServe() async throws {
        let lake = Self.validatedLake
        for mode in [TileMode.off, .shadow, .serve] {
            var r = base()
            let before = r
            let reader = WReader(nodes: Self.copies(lakeId: lake)), lines = WLines(), runner = TileShadowRunner()
            let entries = await wire(&r, flags: Self.flags(mode, [.waterLevel]), context: Self.ctx(lake),
                                     providers: providers(reader: reader, lines: lines, runner: runner))
            await runner.waitUntilIdle()
            try Self.assertFrozenUntouched(before, r)
            XCTAssertEqual(r.water, before.water, "water is frozen")
            switch mode {
            case .off:
                XCTAssertNil(r.lakeLevel); XCTAssertEqual(reader.reads, 0); XCTAssertEqual(entries[.waterLevel]?.flag, "off")
            case .shadow:
                XCTAssertNil(r.lakeLevel); XCTAssertEqual(entries[.waterLevel]?.source, "usgs-nearest-gauge")
                let line = try XCTUnwrap(lines.all.first { $0.contains(#""tile":"waterLevel""#) })
                XCTAssertTrue(line.contains(#""new":1094.2"#) && !line.contains("delta"), "no delta across datums: \(line)")
            case .serve:
                XCTAssertEqual(r.lakeLevel?.status, "AVAILABLE"); XCTAssertEqual(r.lakeLevel?.elevationFt, 1094.2)
                let e = try XCTUnwrap(entries[.waterLevel])
                XCTAssertEqual([e.flag, e.path, e.source, e.status], ["serve", "brain", "lake-brain", "AVAILABLE"])
                XCTAssertEqual(e.observedAt, Self.now.addingTimeInterval(-3600))
            }
        }
    }

    func testWaterLevelServeFallsBackOffTheValidatedListAndWithoutReader() async throws {
        for (lake, reader) in [(Self.lake, WReader(nodes: Self.copies())), (Self.validatedLake, nil)] as [(String, WReader?)] {
            var r = base()
            let entries = await wire(&r, flags: Self.flags(.serve, [.waterLevel]), context: Self.ctx(lake),
                                     providers: providers(reader: reader))
            XCTAssertNil(r.lakeLevel, lake)
            XCTAssertEqual(entries[.waterLevel]?.status, r.water == nil ? "UNKNOWN" : "FALLBACK", lake)
            XCTAssertEqual(entries[.waterLevel]?.source, "usgs-nearest-gauge")
        }
    }

    // MARK: - clarity

    func testClarityOffShadowServe() async throws {
        for mode in [TileMode.off, .shadow, .serve] {
            var r = base()
            let before = r
            let reader = WReader(nodes: Self.copies()), lines = WLines(), runner = TileShadowRunner()
            let entries = await wire(&r, flags: Self.flags(mode, [.clarity]), context: Self.ctx(),
                                     providers: providers(reader: reader, lines: lines, runner: runner))
            await runner.waitUntilIdle()
            try Self.assertFrozenUntouched(before, r)
            switch mode {
            case .off: XCTAssertNil(r.clarityBrain); XCTAssertEqual(reader.reads, 0)
            case .shadow:
                XCTAssertNil(r.clarityBrain)
                XCTAssertTrue(lines.all.contains { $0.contains(#""tile":"clarity""#) && $0.contains(#""new":2.25"#) })
            case .serve:
                XCTAssertEqual(r.clarityBrain?.centralFt, 2.25); XCTAssertEqual(r.clarityBrain?.status, "AVAILABLE")
                XCTAssertNil(r.clarityBrain?.reason)
                let e = try XCTUnwrap(entries[.clarity])
                XCTAssertEqual([e.path, e.source, e.status, e.runner, e.publishId], ["brain", "water-clarity-brain", "AVAILABLE", "pulse", "7def2674"])
            }
        }
    }

    func testClarityServeFeedsTheFactorAndFallsBack() async throws {
        let p = providers(reader: WReader(nodes: Self.copies()))
        let served = await ConditionsTileWiring.clarity(mode: .serve, lakeId: Self.lake, oldCentralFt: 4.0,
                                                        oldEntry: Self.legacy(base())[.clarity]!, context: Self.ctx(), providers: p)
        XCTAssertEqual(served.factorFt, 2.25)
        // The factor runs on it: this is the documented score change.
        var input = ConditionsInput(
            date: Self.now, latitude: 34.35, longitude: -86.30, region: .lowerMid,
            windMph: 2, windDirDeg: 180, airTempF: 75, cloudPct: 5, humidityPct: 60,
            pressureInHg: 30.0, pressureTrend: .steady, pressureChange12hInHg: 0, weatherCode: 0,
            cityGlowFactor: 0.2, waterTempF: 78, rainLast48hIn: 0, rainWatershed72hIn: 0.1,
            moonIllumPct: 50, moonAltitudeAtWindow: 0.3, hasTurbidityGage: false)
        let todayFt = ClarityFactor.visibilityFt(input)
        input.clarityBrainVisibilityFt = served.factorFt
        XCTAssertEqual(ClarityFactor.visibilityFt(input), 2.25)
        XCTAssertNotEqual(todayFt, 2.25)
        // Stale copy → old path, factor untouched.
        let stale = Self.copies(extra: [ClarityBrainOutputAPI.copyPath(Self.lake): """
            {"schema":"sector-customer-clarity-v1","lakeId":"\(Self.lake)","status":"AVAILABLE","centralFt":2.25,
             "observedAt":"2026-11-09T15:00:00Z","freshUntil":"2026-11-09T18:00:00Z"}
            """])
        let fell = await ConditionsTileWiring.clarity(mode: .serve, lakeId: Self.lake, oldCentralFt: 4.0,
                                                      oldEntry: Self.legacy(base())[.clarity]!, context: Self.ctx(),
                                                      providers: providers(reader: WReader(nodes: stale)))
        XCTAssertNil(fell.factorFt); XCTAssertNil(fell.served); XCTAssertEqual(fell.entry.status, "FALLBACK")
    }

    // MARK: - waterTemp

    func testWaterTempOffShadowServeNeverTouchesFrozenFields() async throws {
        for mode in [TileMode.off, .shadow, .serve] {
            var r = base()
            let before = r
            let reader = WReader(nodes: Self.copies()), runner = TileShadowRunner(), lines = WLines()
            let entries = await wire(&r, flags: Self.flags(mode, [.waterTemp]), context: Self.ctx(),
                                     providers: providers(reader: reader, lines: lines, runner: runner))
            await runner.waitUntilIdle()
            try Self.assertFrozenUntouched(before, r)
            XCTAssertEqual(r.waterTemp, before.waterTemp); XCTAssertEqual(r.waterTempModel, before.waterTempModel)
            XCTAssertEqual(r.waterTempState, before.waterTempState)
            switch mode {
            case .off: XCTAssertNil(r.waterTempBrain); XCTAssertEqual(reader.reads, 0)
            case .shadow: XCTAssertNil(r.waterTempBrain); XCTAssertTrue(lines.all.contains { $0.contains(#""new":64.2"#) })
            case .serve:
                XCTAssertEqual(r.waterTempBrain?.valueF, 64.2); XCTAssertEqual(r.waterTempBrain?.kind, "measured")
                XCTAssertEqual(entries[.waterTemp]?.source, "water-temp-brain"); XCTAssertEqual(entries[.waterTemp]?.runner, "cloud")
            }
        }
        var r = base()
        let entries = await wire(&r, flags: Self.flags(.serve, [.waterTemp]), context: Self.ctx(), providers: providers(reader: nil))
        XCTAssertNil(r.waterTempBrain)
        XCTAssertEqual(entries[.waterTemp]?.status, r.waterTemp == nil ? "UNKNOWN" : "FALLBACK")
    }

    // MARK: - generation

    func testGenerationServeUsesTheBoundDam() async throws {
        var r = base()
        let calls = WCalls()
        let entries = await wire(&r, flags: Self.flags(.serve, [.generation]), context: Self.ctx(),
                                 providers: providers(reader: WReader(nodes: Self.copies()), calls: calls),
                                 generation: Self.generation(Self.todayDam, cfs: 3200))
        XCTAssertEqual(r.generation?.damName, "Nickajack Dam"); XCTAssertEqual(r.generation?.dischargeCfs, 4100)
        XCTAssertEqual(r.generation?.bindingSource, "lake-brain")
        XCTAssertEqual(calls.all["boundGeneration"], 1)
        let e = try XCTUnwrap(entries[.generation])
        XCTAssertEqual([e.path, e.source, e.status], ["brain", "lake-brain-bindings", "AVAILABLE"])
    }

    func testGenerationServeFallsBackToTheRegistry() async throws {
        // No binding (no reader), a binding to a dam no operator publishes, and a withdrawn binding.
        let unknownDam = Self.copies(extra: [GenerationBindingOutputAPI.copyPath(Self.lake): """
            {"schema":"sector-customer-generation-binding-v1","lakeId":"\(Self.lake)","operatorId":"USACE","damId":"XYZ",
             "damName":"Somewhere Dam","updatedAt":"\(Self.iso(Self.now.addingTimeInterval(-3600)))"}
            """])
        for reader in [nil, WReader(nodes: unknownDam)] as [WReader?] {
            var r = base()
            let before = r
            let entries = await wire(&r, flags: Self.flags(.serve, [.generation]), context: Self.ctx(),
                                     providers: providers(reader: reader), generation: Self.generation(Self.todayDam, cfs: 3200))
            XCTAssertEqual(r.generation?.damName, before.generation?.damName)
            XCTAssertEqual(r.generation?.bindingSource, before.generation == nil ? nil : "engine-registry")
            XCTAssertEqual(entries[.generation]?.status, "FALLBACK")
            XCTAssertEqual(entries[.generation]?.source, "engine-generation-service")
        }
    }

    func testGenerationShadowLogsDamChosenWithoutFetching() async throws {
        var r = base()
        let before = r
        let calls = WCalls(), lines = WLines(), runner = TileShadowRunner()
        _ = await wire(&r, flags: Self.flags(.shadow, [.generation]), context: Self.ctx(),
                       providers: providers(reader: WReader(nodes: Self.copies()), calls: calls, lines: lines, runner: runner),
                       generation: Self.generation(Self.todayDam, cfs: 3200))
        await runner.waitUntilIdle()
        XCTAssertEqual(r.generation, before.generation, "shadow serves old, no bindingSource")
        XCTAssertNil(calls.all["boundGeneration"], "shadow never fetches generation")
        let line = try XCTUnwrap(lines.all.first)
        XCTAssertTrue(line.contains(#""old":"TVA:GUNT1""#) && line.contains(#""new":"TVA:NRST1""#), line)
    }

    func testGenerationOffNeverReads() async throws {
        var r = base()
        let before = r
        let reader = WReader(nodes: Self.copies())
        _ = await wire(&r, flags: Self.flags(.off, [.generation]), context: Self.ctx(), providers: providers(reader: reader),
                       generation: Self.generation(Self.todayDam, cfs: 3200))
        XCTAssertEqual(r.generation, before.generation)
        XCTAssertEqual(reader.reads, 0)
    }

    func testBindingMatchUsesOperatorAndDamOrTVACode() {
        func b(_ op: String, _ id: String, tva: String? = nil, status: String = "AVAILABLE") -> GenerationBindingOutput {
            GenerationBindingOutput(lakeId: Self.lake, status: status, reason: nil, operatorId: op, damId: id, damName: "x",
                                    cwmsOffice: nil, tvaCode: tva, updatedAt: nil)
        }
        let dams = [Self.todayDam, Self.boundDam]
        XCTAssertEqual(GenerationBindingMatch.dam(for: b("TVA", "NRST1"), in: dams)?.id, "NRST1")
        XCTAssertEqual(GenerationBindingMatch.dam(for: b("TVA", "tva-412", tva: "GUNT1"), in: dams)?.id, "GUNT1")
        XCTAssertNil(GenerationBindingMatch.dam(for: b("SWPA", "NRST1"), in: dams), "operator must match")
        XCTAssertNil(GenerationBindingMatch.dam(for: b("TVA", "NRST1", status: "UNKNOWN"), in: dams))
    }

    // MARK: - windOutlookModel

    func testWindOutlookModelModes() async throws {
        let reader = WReader(nodes: Self.copies())
        let off = await ConditionsTileWiring.windOutlookModel(mode: .off, context: Self.ctx(), providers: providers(reader: reader))
        XCTAssertEqual(off, .today); XCTAssertEqual(reader.reads, 0)

        let lines = WLines(), runner = TileShadowRunner()
        let shadow = await ConditionsTileWiring.windOutlookModel(mode: .shadow, context: Self.ctx(),
                                                                 providers: providers(reader: reader, lines: lines, runner: runner))
        await runner.waitUntilIdle()
        XCTAssertEqual(shadow, .today, "shadow keeps the env choice")
        XCTAssertTrue(lines.all.first?.contains(#""new":"ncep_nbm_conus""#) ?? false, "\(lines.all)")

        let serve = await ConditionsTileWiring.windOutlookModel(mode: .serve, context: Self.ctx(), providers: providers(reader: reader))
        XCTAssertTrue(serve.servedNew); XCTAssertEqual(serve.model, "ncep_nbm_conus")
        XCTAssertEqual(serve.entry?.source, "wind-brain"); XCTAssertEqual(serve.entry?.path, "brain")

        let bestMatch = WReader(nodes: Self.copies(extra: [WindOutlookModelOutputAPI.copyPath: """
            {"schema":"sector-customer-wind-outlook-model-v1","tonight":"best_match","nights2to7":"best_match","decidedBy":"wind-brain",
             "updatedAt":"\(Self.iso(Self.now.addingTimeInterval(-3600)))"}
            """]))
        let bm = await ConditionsTileWiring.windOutlookModel(mode: .serve, context: Self.ctx(), providers: providers(reader: bestMatch))
        XCTAssertTrue(bm.servedNew); XCTAssertNil(bm.model, "best_match is sent as no model")

        let noReader = await ConditionsTileWiring.windOutlookModel(mode: .serve, context: Self.ctx(), providers: providers(reader: nil))
        XCTAssertEqual(noReader, .today, "no reader → env choice")
    }

    func testWindOutcomeLabelsWhatWasServed() {
        let entry = TileSourceDTO(flag: "serve", path: "brain", source: "wind-brain", status: "AVAILABLE")
        let brain = ConditionsTileWiring.WindModelDecision(model: "ncep_nbm_conus", servedNew: true, entry: entry)
        let sameAsEnv = ConditionsTileWiring.WindModelDecision(model: WindForecastModel.current, servedNew: true, entry: entry)
        // A different model is served only when its forecast came back; otherwise today's (FALLBACK via TileSources.build).
        XCTAssertTrue(ConditionsTileWiring.windServed(brain, brainForecastArrived: true))
        XCTAssertEqual(ConditionsTileWiring.windServed(brain, brainForecastArrived: false), brain.model == WindForecastModel.current)
        XCTAssertTrue(ConditionsTileWiring.windServed(sameAsEnv, brainForecastArrived: false), "env model: today's forecast already is it")
        XCTAssertFalse(ConditionsTileWiring.windServed(.today, brainForecastArrived: true))
        XCTAssertEqual(ConditionsTileWiring.windEntry(brain, served: true, outlookNights: 7), entry)
        XCTAssertEqual(ConditionsTileWiring.windEntry(brain, served: true, outlookNights: 0)?.status, "UNKNOWN")
        XCTAssertNil(ConditionsTileWiring.windEntry(brain, served: false, outlookNights: 7))
    }

    func testForecastTonightStaysBestMatchUnderAnyModel() {
        // The overlay only writes future nights (WS-5): unchanged by this PR, asserted here because serve now chooses the model.
        XCTAssertTrue(WindForecastModel.allowed.contains("ncep_nbm_conus"))
        XCTAssertFalse(WindForecastModel.allowed.contains("best_match"), "best_match is never sent as a model parameter")
    }

    // MARK: - tileSources

    func testTileSourcesUsesResolvedEntriesAndKeepsAllKeys() async {
        let wired = TileSourceDTO(flag: "serve", path: "brain", source: "lake-brain", status: "AVAILABLE")
        let out = await TileSources.build(LegacyTileFacts(weatherPresent: true), flags: Self.flags(.serve), context: Self.ctx(),
                                          resolved: [.waterLevel: wired])
        XCTAssertEqual(out["waterLevel"], wired)
        XCTAssertEqual(out["humidity"]?.status, "FALLBACK", "a tile without a resolved entry still reports today's path")
        XCTAssertEqual(Set(out.keys), Set(TileKey.allCases.map(\.rawValue) + ["moon"]))
    }

    func testOldPathEntryMatchesResolve() {
        let e = TileSourceDTO(flag: "off", path: "engine", source: "x", status: "AVAILABLE")
        XCTAssertEqual(TileShadow.oldPathEntry(e, mode: .off, oldPresent: true), e)
        XCTAssertEqual(TileShadow.oldPathEntry(e, mode: .shadow, oldPresent: true).flag, "shadow")
        XCTAssertEqual(TileShadow.oldPathEntry(e, mode: .serve, oldPresent: true).status, "FALLBACK")
        XCTAssertEqual(TileShadow.oldPathEntry(e, mode: .serve, oldPresent: false).status, "UNKNOWN")
    }

    // MARK: - Phone contract: every flag off AND every flag in serve

    func testPhoneContractHoldsWithEveryFlagInServe() async throws {
        let fields = try PhoneContractTests.loadContract()
        let decoder = JSONDecoder(); decoder.dateDecodingStrategy = .iso8601
        for f in try PhoneContractTests.goldenFiles() {
            let before = try decoder.decode(ConditionsResponse.self, from: Data(contentsOf: f))
            var after = before
            // A validated lake so every Brain copy, lakeLevel included, is served.
            let lake = Self.validatedLake
            let todayGen = before.generation.map { _ in Self.generation(Self.todayDam, cfs: 3200) }
            let entries = await wire(&after, flags: Self.flags(.serve), context: Self.ctx(lake),
                                     providers: providers(reader: WReader(nodes: Self.copies(lakeId: lake)), nws: Self.nws()),
                                     generation: todayGen)
            after.tileSources = await TileSources.build(LegacyTileFacts(weatherPresent: after.weather != nil), flags: Self.flags(.serve),
                                                        context: Self.ctx(lake), resolved: entries)
            let bytes = try SectorEngineAPI.makeEncoder().encode(after)
            XCTAssertNoThrow(try decoder.decode(Build28.Response.self, from: bytes), "\(f.lastPathComponent): build 28 cannot decode serve output")
            let doc = try JSONSerialization.jsonObject(with: bytes)
            let errors = PhoneContractTests.validate(doc, fields)
            XCTAssertTrue(errors.isEmpty, "\(f.lastPathComponent) in serve: \(errors.prefix(5))")
            try Self.assertFrozenUntouched(before, after)
            XCTAssertNotNil(after.lakeLevel, f.lastPathComponent)
            XCTAssertNotNil(after.clarityBrain, f.lastPathComponent)
            XCTAssertNotNil(after.waterTempBrain, f.lastPathComponent)
            if before.weather != nil { XCTAssertEqual(after.weather?.humidity, 55, f.lastPathComponent) }
            if before.generation != nil { XCTAssertEqual(after.generation?.bindingSource, "lake-brain", f.lastPathComponent) }
            // The served copies keep the spec §4 shapes.
            let o = doc as! [String: Any]
            XCTAssertEqual(Set((o["clarityBrain"] as! [String: Any]).keys),
                           ["lakeId", "status", "centralFt", "lowFt", "highFt", "confidence", "observedAt", "freshUntil", "runner", "publishId"])
            XCTAssertEqual(Set((o["waterTempBrain"] as! [String: Any]).keys),
                           ["lakeId", "status", "valueF", "kind", "observedAt", "freshUntil", "runner", "publishId"])
        }
    }

    func testPhoneContractHoldsWithEveryFlagOff() async throws {
        let fields = try PhoneContractTests.loadContract()
        let decoder = JSONDecoder(); decoder.dateDecodingStrategy = .iso8601
        for f in try PhoneContractTests.goldenFiles() {
            let golden = try Data(contentsOf: f)
            var r = try decoder.decode(ConditionsResponse.self, from: golden)
            _ = await wire(&r, flags: .allOff, context: Self.ctx(r.resolvedLake?.id),
                           providers: providers(reader: WReader(nodes: Self.copies()), nws: Self.nws()))
            let bytes = try SectorEngineAPI.makeEncoder().encode(r)
            XCTAssertNoThrow(try decoder.decode(Build28.Response.self, from: bytes), f.lastPathComponent)
            let doc = try JSONSerialization.jsonObject(with: bytes)
            XCTAssertTrue(PhoneContractTests.validate(doc, fields).isEmpty, f.lastPathComponent)
            let diff = PhoneContractTests.difference(PhoneContractTests.project(try JSONSerialization.jsonObject(with: golden), fields),
                                                     PhoneContractTests.project(doc, fields))
            XCTAssertNil(diff, "\(f.lastPathComponent): \(diff ?? "-")")
            let o = doc as! [String: Any]
            for k in ["lakeLevel", "clarityBrain", "waterTempBrain"] { XCTAssertNil(o[k], "\(k) must be absent with every flag off") }
            XCTAssertNil((o["generation"] as? [String: Any])?["bindingSource"])
        }
    }

    // MARK: - Reader config

    func testReaderConfigDefaultsToNone() {
        XCTAssertNil(BrainOutputReaderConfig.reader(from: [:]))
        XCTAssertNil(BrainOutputReaderConfig.reader(from: ["SECTOR_BRAIN_OUTPUT_READER": "1"]))
        XCTAssertNotNil(BrainOutputReaderConfig.reader(from: ["SECTOR_BRAIN_OUTPUT_READER": "rtdb"]))
        XCTAssertNil(ConditionsTileProviders.live.reader, "the test process sets no reader")
    }

    func testRTDBReaderReadsOnlyTheCustomerLane() async throws {
        let urls = WURLs()
        let reader = RTDBCustomerCopyReader(fetch: { url, headers in
            urls.append(url.absoluteString + " " + (headers["Authorization"] ?? ""))
            if url.path.hasSuffix("/missing.json") { return (200, Data("null".utf8)) }
            if url.path.hasSuffix("/denied.json") { return (401, Data()) }
            return (200, Data(#"{"schema":"x"}"#.utf8))
        }, token: { "tok" })
        let data = try await reader.get("customer/lakes/guntersville_al/clarity")
        XCTAssertEqual(data.map { String(decoding: $0, as: UTF8.self) }, #"{"schema":"x"}"#)
        XCTAssertEqual(urls.all, ["https://sector-brain.firebaseio.com/customer/lakes/guntersville_al/clarity.json Bearer tok"])
        let missing = try await reader.get("customer/missing")
        XCTAssertNil(missing)
        do { _ = try await reader.get("customer/denied"); XCTFail("non-200 must throw") } catch {}
        for bad in ["brains/lake-brain/status", "customer/", "customer/../brains", "customer/a.json?x=1", "lakes/x/states", "customer//x"] {
            do { _ = try await reader.get(bad); XCTFail("must refuse \(bad)") } catch {}
        }
        XCTAssertEqual(urls.all.count, 3, "refused paths make no request")
        let noToken = RTDBCustomerCopyReader(fetch: { _, _ in XCTFail("no request without a token"); return nil }, token: { nil })
        do { _ = try await noToken.get("customer/x"); XCTFail("no token must throw") } catch {}
        let wrongDB = RTDBCustomerCopyReader(databaseURL: "https://sector-9393c.firebaseio.com", fetch: { _, _ in nil }, token: { "t" })
        do { _ = try await wrongDB.get("customer/x"); XCTFail("only the sector-brain database") } catch {}
    }
}

// MARK: - Helpers

private final class WCalls: @unchecked Sendable {
    private let lock = NSLock()
    private var counts: [String: Int] = [:]
    func inc(_ k: String) { lock.lock(); counts[k, default: 0] += 1; lock.unlock() }
    var all: [String: Int] { lock.lock(); defer { lock.unlock() }; return counts }
}

private final class WLines: @unchecked Sendable {
    private let lock = NSLock()
    private var lines: [String] = []
    func append(_ s: String) { lock.lock(); lines.append(s); lock.unlock() }
    var all: [String] { lock.lock(); defer { lock.unlock() }; return lines }
}

private final class WURLs: @unchecked Sendable {
    private let lock = NSLock()
    private var items: [String] = []
    func append(_ s: String) { lock.lock(); items.append(s); lock.unlock() }
    var all: [String] { lock.lock(); defer { lock.unlock() }; return items }
}

private final class WReader: BrainOutputReader, @unchecked Sendable {
    private let lock = NSLock()
    private let nodes: [String: String]
    private var count = 0
    init(nodes: [String: String]) { self.nodes = nodes }
    var reads: Int { lock.lock(); defer { lock.unlock() }; return count }
    func get(_ path: String) async throws -> Data? {
        lock.withLock { count += 1 }
        return nodes[path].map { Data($0.utf8) }
    }
}
