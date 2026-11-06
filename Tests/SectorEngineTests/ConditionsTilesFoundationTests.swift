//
//  ConditionsTilesFoundationTests.swift
//  SectorEngineTests
//
//  Conditions consolidation foundation (Sector_Ops #53, docs/architecture/conditions/CONDITIONS_CONSOLIDATION_SPEC_V1.md):
//  tile flags, the per-tile circuit breaker, the shadow/serve step, User-Agent parsing, `tileSources` and the
//  `[conditions-request]` line. Nothing here touches the network or a real clock.
//

import XCTest
#if canImport(CoreLocation)
import CoreLocation
#endif
@testable import SectorEngine

final class ConditionsTilesFoundationTests: XCTestCase {

    // MARK: - TileFlags parsing

    func testTileKeysAreExactlyTheSpecKeys() {
        XCTAssertEqual(TileKey.allCases.map(\.rawValue),
                       ["humidity", "pressure", "temperature", "sky", "wind", "windOutlookModel",
                        "waterLevel", "clarity", "waterTemp", "generation"])
    }

    func testSpecExampleParses() {
        let f = TileFlags.parse(#"{"version":1,"tiles":{"humidity":{"mode":"off"},"waterLevel":{"mode":"shadow","lakes":["Guntersville|AL"]}}}"#)
        XCTAssertEqual(f.version, 1)
        XCTAssertEqual(f.mode(for: .humidity, lakeId: "Guntersville|AL"), .off)
        XCTAssertEqual(f.mode(for: .waterLevel, lakeId: "Guntersville|AL"), .shadow)
        XCTAssertEqual(f.mode(for: .waterLevel, lakeId: "Hartwell|SC"), .off, "lakes list limits the tile")
        XCTAssertEqual(f.mode(for: .waterLevel, lakeId: nil), .off, "no resolved lake is outside the list")
        XCTAssertEqual(f.mode(for: .pressure, lakeId: "Guntersville|AL"), .off, "missing key is off")
    }

    func testServeWithoutLakesAppliesEverywhere() {
        let f = TileFlags.parse(#"{"version":1,"tiles":{"wind":{"mode":"serve"}}}"#)
        XCTAssertEqual(f.mode(for: .wind, lakeId: nil), .serve)
        XCTAssertEqual(f.mode(for: .wind, lakeId: "Any|XX"), .serve)
    }

    func testMissingInvalidAndUnknownAreOff() {
        for raw in [nil, "", "not json", "[]", #"{"version":1}"#, #"{"tiles":"x"}"#] as [String?] {
            let f = TileFlags.parse(raw)
            XCTAssertEqual(f, .allOff, "\(raw ?? "nil")")
            for t in TileKey.allCases { XCTAssertEqual(f.mode(for: t, lakeId: "Guntersville|AL"), .off) }
        }
        let f = TileFlags.parse(#"{"version":1,"tiles":{"humidty":{"mode":"serve"},"sky":{"mode":"on"},"wind":{"mode":"SERVE"},"temperature":"serve","pressure":{"mode":"serve","lakes":"Guntersville|AL"},"clarity":{}}}"#)
        for t in TileKey.allCases { XCTAssertEqual(f.mode(for: t, lakeId: "Guntersville|AL"), .off, t.rawValue) }
    }

    func testEnvOverrideWinsAndNeverFetches() async {
        let store = TileFlagsStore(environment: [TileFlags.envKey: #"{"version":1,"tiles":{"sky":{"mode":"shadow"}}}"#],
                                   fetch: { XCTFail("must not fetch with env override"); return .value("{}") })
        let flags = await store.current()
        XCTAssertEqual(flags.mode(for: .sky, lakeId: nil), .shadow)
        let bad = TileFlagsStore(environment: [TileFlags.envKey: "garbage"], fetch: { .value(#"{"tiles":{"sky":{"mode":"serve"}}}"#) })
        let badFlags = await bad.current()
        XCTAssertEqual(badFlags, .allOff, "an invalid override is off, not Remote Config")
    }

    func testRemoteConfigTTLAndLastGoodFallback() async {
        let clock = TestClock(Date(timeIntervalSince1970: 1_000_000))
        let answers = Answers([.value(#"{"version":1,"tiles":{"humidity":{"mode":"shadow"}}}"#), .unreadable, .absent])
        let store = TileFlagsStore(environment: [:], fetch: { await answers.next() }, now: { clock.now })

        var f = await store.current()
        XCTAssertEqual(f.mode(for: .humidity, lakeId: nil), .shadow)
        let v1 = await answers.calls
        XCTAssertEqual(v1, 1)

        clock.advance(9 * 60)
        f = await store.current()
        let v2 = await answers.calls
        XCTAssertEqual(v2, 1, "within 10-minute TTL: cached")

        clock.advance(2 * 60)   // stale: answers last good now, refreshes in background (unreadable → keep)
        f = await store.current()
        XCTAssertEqual(f.mode(for: .humidity, lakeId: nil), .shadow)
        await waitFor { await answers.calls == 2 }
        f = await store.current()
        XCTAssertEqual(f.mode(for: .humidity, lakeId: nil), .shadow, "unreadable keeps last good")

        clock.advance(11 * 60)  // stale again: absent parameter → every tile off
        _ = await store.current()
        await waitFor { await answers.calls == 3 }
        try? await Task.sleep(nanoseconds: 20_000_000)
        f = await store.current()
        XCTAssertEqual(f, .allOff, "parameter absent from the template means off")
    }

    func testRemoteConfigTemplateParameterExtraction() {
        let template: [String: Any] = ["parameters": ["conditions_tiles_v1": ["defaultValue": ["value": "{\"tiles\":{}}"]]]]
        XCTAssertEqual(RemoteConfigREST.parameter("conditions_tiles_v1", inTemplate: template), .value("{\"tiles\":{}}"))
        XCTAssertEqual(RemoteConfigREST.parameter("conditions_config", inTemplate: template), .absent)
        XCTAssertEqual(RemoteConfigREST.parameter("x", inTemplate: [:]), .absent)
    }

    // MARK: - TileBreaker

    private let t0 = Date(timeIntervalSince1970: 2_000_000)

    private func fill(_ b: inout TileBreaker, newOK: Int, newBad: Int, oldOK: Int = 20, oldBad: Int = 0,
                      newLatency: TimeInterval = 0.2, oldLatency: TimeInterval = 0.2, from start: Date) -> [TileBreaker.Transition] {
        var out: [TileBreaker.Transition] = []
        var i = 0.0
        func at() -> Date { i += 1; return start.addingTimeInterval(i) }
        for _ in 0..<oldOK { b.record(path: .old, ok: true, latency: oldLatency, at: at()) }
        for _ in 0..<oldBad { b.record(path: .old, ok: false, latency: oldLatency, at: at()) }
        for _ in 0..<newOK { if let t = b.record(path: .new, ok: true, latency: newLatency, at: at()) { out.append(t) } }
        for _ in 0..<newBad { if let t = b.record(path: .new, ok: false, latency: newLatency, at: at()) { out.append(t) } }
        return out
    }

    func testBreakerConstantsMatchSpec() {
        XCTAssertEqual(TileBreakerConstants.windowSeconds, 900)
        XCTAssertEqual(TileBreakerConstants.minNewSamples, 20)
        XCTAssertEqual(TileBreakerConstants.failureRateMargin, 0.10)
        XCTAssertEqual(TileBreakerConstants.p95LatencyMarginSeconds, 3)
        XCTAssertEqual(TileBreakerConstants.openSeconds, 1800)
        XCTAssertEqual(TileBreakerConstants.halfOpenTrialFraction, 0.10)
        XCTAssertEqual(TileBreakerConstants.halfOpenGoodSamples, 20)
    }

    func testBreakerNeedsTwentyNewSamples() {
        var b = TileBreaker(tile: .humidity)
        let ts = fill(&b, newOK: 0, newBad: 19, from: t0)
        XCTAssertTrue(ts.isEmpty)
        XCTAssertEqual(b.state, .closed)
    }

    func testBreakerTripsOnFailureRateMargin() {
        // 3/20 = 15% new vs 0% old: +15 points > 10 → trips at the 20th sample.
        var b = TileBreaker(tile: .humidity)
        let ts = fill(&b, newOK: 17, newBad: 3, from: t0)
        XCTAssertEqual(ts.map(\.state), [.open])
        XCTAssertEqual(b.state, .open)
        XCTAssertTrue(ts[0].logLine.hasPrefix(#"[tile-breaker] {"reason":"#))
        XCTAssertTrue(ts[0].logLine.contains(#""state":"open""#))
        XCTAssertTrue(ts[0].logLine.contains(#""tile":"humidity""#))
        XCTAssertTrue(ts[0].logLine.contains(#""window":{"#))
    }

    func testBreakerDoesNotTripWithinMargin() {
        // 2/20 = 10% new vs 0% old: exactly 10 points is not "more than" 10.
        var b = TileBreaker(tile: .humidity)
        XCTAssertTrue(fill(&b, newOK: 18, newBad: 2, from: t0).isEmpty)
        // Old path equally bad: relative rate is what matters.
        var c = TileBreaker(tile: .humidity)
        XCTAssertTrue(fill(&c, newOK: 10, newBad: 10, oldOK: 10, oldBad: 10, from: t0).isEmpty)
    }

    func testBreakerTripsOnP95Latency() {
        var b = TileBreaker(tile: .wind)
        let ts = fill(&b, newOK: 20, newBad: 0, newLatency: 3.6, oldLatency: 0.5, from: t0)
        XCTAssertEqual(ts.first?.reason, "new p95 latency more than 3 s above old")
        var c = TileBreaker(tile: .wind)
        XCTAssertTrue(fill(&c, newOK: 20, newBad: 0, newLatency: 3.4, oldLatency: 0.5, from: t0).isEmpty)
    }

    func testBreakerWindowForgetsOldSamples() {
        var b = TileBreaker(tile: .sky)
        _ = fill(&b, newOK: 0, newBad: 10, from: t0)
        // 16 minutes later: the bad samples are out of the window.
        let ts = fill(&b, newOK: 20, newBad: 0, from: t0.addingTimeInterval(16 * 60))
        XCTAssertTrue(ts.isEmpty)
        XCTAssertEqual(b.stats(at: t0.addingTimeInterval(16 * 60 + 60)).newFailRate, 0)
    }

    func testBreakerOpenHalfOpenClose() {
        var b = TileBreaker(tile: .humidity)
        _ = fill(&b, newOK: 0, newBad: 20, from: t0)
        XCTAssertEqual(b.state, .open)
        let opened = b.openedAt!

        // Open: serve old for 30 minutes regardless of the roll.
        XCTAssertFalse(b.shouldTryNew(at: opened.addingTimeInterval(29 * 60), roll: 0).tryNew)
        // After 30 minutes: half-open, 10% of requests.
        let r = b.shouldTryNew(at: opened.addingTimeInterval(30 * 60), roll: 0.05)
        XCTAssertTrue(r.tryNew)
        XCTAssertEqual(r.transition?.state, .halfOpen)
        XCTAssertFalse(b.shouldTryNew(at: opened.addingTimeInterval(30 * 60 + 1), roll: 0.10).tryNew)
        XCTAssertTrue(b.shouldTryNew(at: opened.addingTimeInterval(30 * 60 + 1), roll: 0.0999).tryNew)

        // 19 good samples: still half-open; the 20th closes it.
        var at = opened.addingTimeInterval(31 * 60)
        for _ in 0..<19 { at += 1; XCTAssertNil(b.record(path: .new, ok: true, latency: 0.1, at: at)) }
        XCTAssertEqual(b.state, .halfOpen)
        at += 1
        XCTAssertEqual(b.record(path: .new, ok: true, latency: 0.1, at: at)?.state, .closed)
        XCTAssertEqual(b.state, .closed)
        XCTAssertTrue(b.samples.isEmpty, "fresh window after recovery")
    }

    func testBreakerHalfOpenFailureReopens() {
        var b = TileBreaker(tile: .humidity)
        _ = fill(&b, newOK: 0, newBad: 20, from: t0)
        let opened = b.openedAt!
        _ = b.shouldTryNew(at: opened.addingTimeInterval(1800), roll: 0)
        XCTAssertEqual(b.state, .halfOpen)
        let t = b.record(path: .new, ok: false, latency: 0.1, at: opened.addingTimeInterval(1801))
        XCTAssertEqual(t?.state, .open)
        XCTAssertEqual(b.openedAt, opened.addingTimeInterval(1801))
        XCTAssertFalse(b.shouldTryNew(at: opened.addingTimeInterval(1802), roll: 0).tryNew)
    }

    func testP95NearestRank() {
        XCTAssertEqual(TileBreaker.p95([]), 0)
        XCTAssertEqual(TileBreaker.p95([1]), 1)
        XCTAssertEqual(TileBreaker.p95((1...20).map(Double.init)), 19)
        XCTAssertEqual(TileBreaker.p95((1...100).map(Double.init)), 95)
    }

    func testRegistryLogsTransitionsWithInjectedClock() async {
        let clock = TestClock(t0)
        let lines = Lines()
        let reg = TileBreakerRegistry(now: { clock.now }, roll: { 0.5 }, log: { lines.append($0) })
        for _ in 0..<20 {
            clock.advance(1)
            await reg.record(.pressure, path: .new, ok: false, latency: 0.1)
        }
        let state = await reg.state(.pressure)
        XCTAssertEqual(state, .open)
        let tryNow = await reg.shouldTryNew(.pressure)
        XCTAssertFalse(tryNow)
        let other = await reg.shouldTryNew(.humidity)
        XCTAssertTrue(other, "breakers are per tile")
        XCTAssertEqual(lines.all.count, 1)
        XCTAssertTrue(lines.all[0].hasPrefix("[tile-breaker] "))
    }

    // MARK: - Shadow / serve helper

    private let ctx = TileRequestContext(lakeId: "Guntersville|AL", lat: 34.4321, lon: -86.2549)
    private let oldEntry = TileSourceDTO(flag: "off", path: "engine", source: "open-meteo", status: "AVAILABLE")

    private func newValue(_ v: Int?, _ s: TileStatus = .available) -> TileNewValue<Int> {
        TileNewValue(value: v, status: s, path: .engine, source: "nws-nbm", observedAt: Date(timeIntervalSince1970: 1_700_000_000))
    }

    func testOffNeverCallsNew() async {
        let lines = Lines()
        let r = await TileShadow.resolve(tile: .humidity, mode: .off, old: 61, oldEntry: oldEntry, context: ctx,
                                         new: { XCTFail("off must not compute new"); return self.newValue(58) },
                                         compare: TileComparison.numeric, breaker: TileBreakerRegistry(log: { _ in }),
                                         log: { lines.append($0) })
        XCTAssertEqual(r.value, 61)
        XCTAssertFalse(r.servedNew)
        XCTAssertEqual(r.entry, oldEntry)
        XCTAssertTrue(lines.all.isEmpty)
    }

    func testShadowServesOldAndLogsDifference() async {
        let lines = Lines()
        let r = await TileShadow.resolve(tile: .humidity, mode: .shadow, old: 61, oldEntry: oldEntry, context: ctx,
                                         new: { self.newValue(58) }, compare: TileComparison.numeric,
                                         breaker: TileBreakerRegistry(log: { _ in }), log: { lines.append($0) })
        XCTAssertEqual(r.value, 61)
        XCTAssertFalse(r.servedNew)
        XCTAssertEqual(r.entry.flag, "shadow")
        XCTAssertEqual(r.entry.source, "open-meteo")
        XCTAssertEqual(lines.all, [#"[tile-shadow] {"delta":-3,"lakeId":"Guntersville|AL","latR":34.4,"lonR":-86.3,"new":58,"newSource":"nws-nbm","old":61,"oldSource":"open-meteo","tile":"humidity"}"#])
    }

    func testShadowLogsBlankNewAsNull() async {
        let lines = Lines()
        _ = await TileShadow.resolve(tile: .humidity, mode: .shadow, old: 61, oldEntry: oldEntry, context: ctx,
                                     new: { self.newValue(nil, .unknown) }, compare: TileComparison.numeric,
                                     breaker: TileBreakerRegistry(log: { _ in }), log: { lines.append($0) })
        XCTAssertTrue(lines.all[0].contains(#""new":null"#))
        XCTAssertFalse(lines.all[0].contains("delta"))
    }

    func testServeUsesNewWhenAvailable() async {
        let r = await TileShadow.resolve(tile: .humidity, mode: .serve, old: 61, oldEntry: oldEntry, context: ctx,
                                         new: { self.newValue(58) }, compare: TileComparison.numeric,
                                         breaker: TileBreakerRegistry(log: { _ in }), log: { _ in })
        XCTAssertEqual(r.value, 58)
        XCTAssertTrue(r.servedNew)
        XCTAssertEqual(r.entry, TileSourceDTO(flag: "serve", path: "engine", source: "nws-nbm", status: "AVAILABLE",
                                              observedAt: Date(timeIntervalSince1970: 1_700_000_000)))
    }

    func testServeFallsBackWhenNewIsNotAvailable() async {
        for status in [TileStatus.unknown, .estimate, .fallback] {
            let r = await TileShadow.resolve(tile: .humidity, mode: .serve, old: 61, oldEntry: oldEntry, context: ctx,
                                             new: { self.newValue(status == .unknown ? nil : 58, status) },
                                             compare: TileComparison.numeric,
                                             breaker: TileBreakerRegistry(log: { _ in }), log: { _ in })
            XCTAssertEqual(r.value, 61, status.rawValue)
            XCTAssertFalse(r.servedNew)
            XCTAssertEqual(r.entry.status, "FALLBACK")
            XCTAssertEqual(r.entry.flag, "serve")
            XCTAssertEqual(r.entry.source, "open-meteo")
        }
        // Old blank too: UNKNOWN, never blank-as-available.
        let blank = await TileShadow.resolve(tile: .humidity, mode: .serve, old: nil as Int?,
                                             oldEntry: TileSourceDTO(flag: "off", path: "engine", source: "open-meteo", status: "UNKNOWN"),
                                             context: ctx, new: { self.newValue(nil, .unknown) },
                                             compare: TileComparison.numeric,
                                             breaker: TileBreakerRegistry(log: { _ in }), log: { _ in })
        XCTAssertEqual(blank.entry.status, "UNKNOWN")
    }

    func testServeWithoutNewSourceReportsTodayAsFallback() async {
        let r = await TileShadow.resolve(tile: .humidity, mode: .serve, old: 61, oldEntry: oldEntry, context: ctx,
                                         new: nil, compare: TileComparison.numeric,
                                         breaker: TileBreakerRegistry(log: { _ in }), log: { _ in })
        XCTAssertEqual(r.value, 61)
        XCTAssertEqual(r.entry.status, "FALLBACK")
    }

    func testServeTripsBreakerThenServesOldWithoutCallingNew() async {
        let clock = TestClock(t0)
        let breakerLines = Lines()
        let reg = TileBreakerRegistry(now: { clock.now }, roll: { 0.99 }, log: { breakerLines.append($0) })
        let calls = Counter()
        for _ in 0..<20 {
            clock.advance(1)
            let r = await TileShadow.resolve(tile: .wind, mode: .serve, old: 7, oldEntry: oldEntry, context: ctx,
                                             new: { await calls.inc(); return self.newValue(nil, .unknown) },
                                             compare: TileComparison.numeric, breaker: reg, log: { _ in })
            XCTAssertEqual(r.value, 7)
        }
        let v3 = await calls.value
        XCTAssertEqual(v3, 20)
        XCTAssertEqual(breakerLines.all.count, 1)
        clock.advance(60)
        let r = await TileShadow.resolve(tile: .wind, mode: .serve, old: 7, oldEntry: oldEntry, context: ctx,
                                         new: { await calls.inc(); return self.newValue(9) },
                                         compare: TileComparison.numeric, breaker: reg, log: { _ in })
        XCTAssertEqual(r.value, 7)
        XCTAssertEqual(r.entry.status, "FALLBACK")
        let v4 = await calls.value
        XCTAssertEqual(v4, 20, "open breaker: new is not called")
    }

    // MARK: - User-Agent parsing

    func testUserAgentTable() {
        let cases: [(String?, String?, String, String?)] = [
            ("Sector/28 CFNetwork/1568.300.101 Darwin/24.2.0", nil, "ios", "28"),
            ("Sector-Android/4.2.0 (412)", nil, "android", "412"),
            ("Sector-Android/4.2.0", nil, "android", "unknown"),
            ("okhttp/4.12.0", nil, "android", "unknown"),
            ("Sector-Web/1.3.0", nil, "web", "1.3.0"),
            ("Mozilla/5.0 (Macintosh)", nil, "other", nil),
            (nil, nil, "other", nil),
            ("", nil, "other", nil),
            ("Mozilla/5.0 (Macintosh)", "web/1.4.2", "web", "1.4.2"),
            ("Sector/30 CFNetwork/1", "web/1.4.2", "ios", "30"),
            ("curl/8.0", "desktop/1", "other", nil),
            ("Sector/28\"},\"x\":{ CFNetwork", nil, "ios", "28x"),
        ]
        for (ua, client, app, build) in cases {
            let id = ClientIdentity.parse(userAgent: ua, sectorClient: client)
            XCTAssertEqual(id, ClientIdentity(app: app, appBuild: build), "\(ua ?? "nil") / \(client ?? "nil")")
        }
    }

    // MARK: - tileSources

    func testLegacyTileSourcesAllPresentAndTruthful() {
        let obs = Date(timeIntervalSince1970: 1_762_000_000)
        let f = LegacyTileFacts(weatherPresent: true, outlookNights: 7, windForecastModel: nil,
                                waterPresent: true, waterObservedAt: obs,
                                claritySource: "inSituGauge", turbidityObservedAt: obs,
                                waterTempKind: "measured", waterTempSourceKind: "usgsLakeSensor", waterTempObservedAt: obs,
                                generationPresent: true, generationHasReading: true, generationObservedAt: obs)
        let m = TileSources.legacy(f)
        XCTAssertEqual(Set(m.keys), Set(TileKey.allCases))
        for t in [TileKey.humidity, .pressure, .temperature, .sky, .wind] {
            XCTAssertEqual(m[t], TileSourceDTO(flag: "off", path: "engine", source: "open-meteo", status: "AVAILABLE"))
        }
        XCTAssertEqual(m[.windOutlookModel]?.source, "open-meteo-best-match")
        XCTAssertEqual(m[.waterLevel], TileSourceDTO(flag: "off", path: "engine", source: "usgs-nearest-gauge", status: "AVAILABLE", observedAt: obs))
        XCTAssertEqual(m[.clarity], TileSourceDTO(flag: "off", path: "engine", source: "visibility-model", status: "AVAILABLE", observedAt: obs))
        XCTAssertEqual(m[.waterTemp], TileSourceDTO(flag: "off", path: "engine", source: "usgs-lake-sensor", status: "AVAILABLE", observedAt: obs))
        XCTAssertEqual(m[.generation], TileSourceDTO(flag: "off", path: "engine", source: "engine-generation-service", status: "AVAILABLE", observedAt: obs))
    }

    func testLegacyTileSourcesUnknownAndEstimate() {
        let m = TileSources.legacy(LegacyTileFacts(windForecastModel: "ncep_nbm_conus", claritySource: "rainDecayModel",
                                                   waterTempKind: "modeled", waterTempSourceKind: "energyBalanceModel",
                                                   generationPresent: true, generationHasReading: false,
                                                   generationObservedAt: Date()))
        for t in [TileKey.humidity, .pressure, .temperature, .sky, .wind, .windOutlookModel, .waterLevel, .generation] {
            XCTAssertEqual(m[t]?.status, "UNKNOWN", t.rawValue)
            XCTAssertNil(m[t]?.observedAt, t.rawValue)
        }
        XCTAssertEqual(m[.windOutlookModel]?.source, "open-meteo-ncep-nbm-conus")
        XCTAssertEqual(m[.clarity], TileSourceDTO(flag: "off", path: "engine", source: "visibility-model", status: "ESTIMATE"))
        XCTAssertEqual(m[.waterTemp], TileSourceDTO(flag: "off", path: "engine", source: "energy-balance-model", status: "ESTIMATE"))
        let u = TileSources.legacy(LegacyTileFacts())
        XCTAssertEqual(u[.waterTemp]?.status, "UNKNOWN")
        XCTAssertEqual(u[.clarity]?.status, "UNKNOWN")
    }

    func testBuildAppliesFlagsAndAddsMoon() async {
        let f = LegacyTileFacts(weatherPresent: true, outlookNights: 7)
        let off = await TileSources.build(f, flags: .allOff, context: ctx)
        XCTAssertEqual(Set(off.keys), Set(TileKey.allCases.map(\.rawValue) + ["moon"]))
        XCTAssertEqual(off["moon"], TileSourceDTO(flag: "off", path: "app", source: "moon-v1", status: "AVAILABLE"))
        XCTAssertTrue(off.values.allSatisfy { $0.flag == "off" })
        XCTAssertEqual(off["humidity"]?.status, "AVAILABLE")

        let flags = TileFlags.parse(#"{"version":1,"tiles":{"humidity":{"mode":"shadow"},"wind":{"mode":"serve"},"waterLevel":{"mode":"serve","lakes":["Hartwell|SC"]}}}"#)
        let on = await TileSources.build(f, flags: flags, context: ctx)
        XCTAssertEqual(on["humidity"], TileSourceDTO(flag: "shadow", path: "engine", source: "open-meteo", status: "AVAILABLE"))
        XCTAssertEqual(on["wind"], TileSourceDTO(flag: "serve", path: "engine", source: "open-meteo", status: "FALLBACK"))
        XCTAssertEqual(on["waterLevel"]?.flag, "off", "lake not in the list")
        XCTAssertEqual(on["waterLevel"]?.status, "UNKNOWN")
    }

    func testTileSourceEncodingOmitsNils() throws {
        let data = try SectorEngineAPI.makeEncoder().encode(
            ["moon": TileSources.moonEntry,
             "waterLevel": TileSourceDTO(flag: "off", path: "engine", source: "usgs-nearest-gauge", status: "AVAILABLE",
                                         observedAt: Date(timeIntervalSince1970: 1_762_786_800))])
        XCTAssertEqual(String(data: data, encoding: .utf8),
                       #"{"moon":{"flag":"off","path":"app","source":"moon-v1","status":"AVAILABLE"},"waterLevel":{"flag":"off","observedAt":"2025-11-10T15:00:00Z","path":"engine","source":"usgs-nearest-gauge","status":"AVAILABLE"}}"#)
    }

    // MARK: - water / discharge gauge keys (Amendment 2)

    func testWaterDTOCarriesGaugeIdentity() throws {
        let at = Date(timeIntervalSince1970: 1_762_786_800)
        var r = WaterLevelReading(siteCode: "03573500", siteName: "TENNESSEE RIVER AT GUNTERSVILLE DAM", parameterCode: "00062",
                                  parameterName: "Reservoir elevation", value: 594.8, unit: "ft", dateTime: at,
                                  latitude: 34.42, longitude: -86.39, trend: .steady, change: 0.1)
        r.history = [594.7, 594.8]
        let origin = CLLocationCoordinate2D(latitude: 34.42, longitude: -86.29)
        let computed = SectorEngineAPI.waterDTO(r, from: origin)
        XCTAssertEqual(computed.siteCode, "03573500")
        XCTAssertEqual(computed.siteName, "TENNESSEE RIVER AT GUNTERSVILLE DAM")
        XCTAssertEqual(computed.observedAt, at)
        XCTAssertEqual(try XCTUnwrap(computed.distanceMiles), 5.7, accuracy: 0.2, "computed from the request coordinate")
        r.distanceMiles = 3.25
        XCTAssertEqual(SectorEngineAPI.waterDTO(r, from: origin).distanceMiles, 3.25, "the fetcher's own distance wins")
        // The frozen keys keep their values.
        XCTAssertEqual([computed.value, computed.change], [594.8, 0.1])
        XCTAssertEqual(computed.unit, "ft"); XCTAssertEqual(computed.trend, "steady"); XCTAssertEqual(computed.history, [594.7, 594.8])
    }

    // MARK: - [conditions-request]

    func testRequestLogLine() async throws {
        let raw = try Data(contentsOf: URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().appendingPathComponent("verification/fixtures/conditions/response_contract.golden.json"))
        let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
        var response = try dec.decode(ConditionsResponse.self, from: raw)
        response.tileSources = ["humidity": TileSourceDTO(flag: "off", path: "engine", source: "open-meteo", status: "AVAILABLE"),
                                "waterLevel": TileSourceDTO(flag: "off", path: "engine", source: "usgs-nearest-gauge", status: "UNKNOWN")]
        let line = ConditionsRequestLog.line(client: ClientIdentity(app: "ios", appBuild: "28"), cache: .hit, ms: 42,
                                             lat: 34.4321, lon: -86.2549, response: response)
        let lakeId = try XCTUnwrap(response.resolvedLake?.id)
        XCTAssertEqual(line, #"[conditions-request] {"app":"ios","appBuild":"28","cache":"hit","lakeId":""# + lakeId
                       + #"","latR":34.4,"lonR":-86.3,"ms":42,"tiles":{"humidity":{"blank":false,"flag":"off","status":"AVAILABLE"},"waterLevel":{"blank":true,"flag":"off","status":"UNKNOWN"}}}"#)

        let none = ConditionsRequestLog.line(client: ClientIdentity(app: "other", appBuild: nil), cache: .miss, ms: 7,
                                             lat: -0.04, lon: 0.05, response: nil)
        XCTAssertEqual(none, #"[conditions-request] {"app":"other","cache":"miss","latR":0,"lonR":0.1,"ms":7,"tiles":{}}"#)
    }

    func testCacheReportsHitAndMiss() async {
        let cache = ConditionsResponseCache()
        let raw = try! Data(contentsOf: URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().appendingPathComponent("verification/fixtures/conditions/response_contract.golden.json"))
        let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
        let response = try! dec.decode(ConditionsResponse.self, from: raw)
        let first = await cache.conditionsWithOutcome(lat: 34.4, lon: -86.3, compute: { response })
        XCTAssertEqual(first.cache, .miss)
        let second = await cache.conditionsWithOutcome(lat: 34.4, lon: -86.3, compute: { nil })
        XCTAssertEqual(second.cache, .hit)
        XCTAssertEqual(second.response, response)
        let fresh = await cache.conditionsWithOutcome(lat: 34.4, lon: -86.3, fresh: true, compute: { response })
        XCTAssertEqual(fresh.cache, .miss)
    }
}

// MARK: - Test doubles

private final class TestClock: @unchecked Sendable {
    private let lock = NSLock()
    private var t: Date
    init(_ t: Date) { self.t = t }
    var now: Date { lock.lock(); defer { lock.unlock() }; return t }
    func advance(_ s: TimeInterval) { lock.lock(); t += s; lock.unlock() }
}

private final class Lines: @unchecked Sendable {
    private let lock = NSLock()
    private var lines: [String] = []
    func append(_ s: String) { lock.lock(); lines.append(s); lock.unlock() }
    var all: [String] { lock.lock(); defer { lock.unlock() }; return lines }
}

private actor Counter {
    var value = 0
    func inc() { value += 1 }
}

private actor Answers {
    private var queue: [RemoteConfigParameter]
    private(set) var calls = 0
    init(_ q: [RemoteConfigParameter]) { queue = q }
    func next() -> RemoteConfigParameter {
        calls += 1
        return queue.isEmpty ? .unreadable : queue.removeFirst()
    }
}

private func waitFor(_ cond: @escaping () async -> Bool) async {
    for _ in 0..<200 {
        if await cond() { return }
        try? await Task.sleep(nanoseconds: 5_000_000)
    }
}
