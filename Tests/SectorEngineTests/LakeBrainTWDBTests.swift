//
//  LakeBrainTWDBTests.swift
//  Lake Brain: the TWDB Water Data for Texas adapter, against recorded responses (Fixtures/TWDB, fetched 2026-10-13).
//  amistad-30day, travis-30day and possum-kingdom-1year are complete real responses (not-found.html is a real 404 body without its
//  telemetry script); the *-glitch / *-zeros / *-spike / *-blank / *-headerless excerpts keep the real header (or its absence) and a
//  real slice of rows. No network.
//

import XCTest
@testable import SectorEngine

final class LakeBrainTWDBTests: XCTestCase {

    func fixture(_ name: String) throws -> Data {
        let url = URL(fileURLWithPath: #filePath).deletingLastPathComponent().appendingPathComponent("Fixtures/TWDB/\(name)")
        return try Data(contentsOf: url)
    }
    func iso(_ s: String) -> Date { ISO8601DateFormatter().date(from: s)! }
    func parsed(_ name: String, datum: String? = nil) throws -> TWDBSeries {
        try TWDB.parse(try fixture(name), expectedDatum: datum).get()
    }

    // Fake transport: scripted responses, recorded URLs and sleeps.
    final class Script: @unchecked Sendable {
        private let lock = NSLock()
        var responses: [TWDBResponse?]
        private(set) var urls: [String] = []
        private(set) var sleeps: [TimeInterval] = []
        init(_ r: [TWDBResponse?]) { responses = r }
        func next(_ url: String) -> TWDBResponse? {
            lock.withLock { urls.append(url); return responses.isEmpty ? nil : (responses.count == 1 ? responses[0] : responses.removeFirst()) }
        }
        func slept(_ s: TimeInterval) { lock.withLock { sleeps.append(s) } }
        var seenUrls: [String] { lock.withLock { urls } }
        var seenSleeps: [TimeInterval] { lock.withLock { sleeps } }
        func transport() -> TWDBTransport {
            TWDBTransport(fetch: { [self] u in next(u) }, sleep: { [self] s in slept(s) }, gate: TWDBGate(), minGapSeconds: 0)
        }
    }
    func ok(_ name: String) throws -> TWDBResponse { TWDBResponse(status: 200, body: try fixture(name), retryAfter: nil) }
    func ref(_ slug: String = "amistad", series: String? = "water_level@NGVD29") -> LevelSeriesRef {
        LevelSeriesRef(provider: .twdb, capability: .directLakeGauge, station: slug, series: series, cadenceMin: 1440, lagMin: 1440, datumOffsetFt: 0, note: nil)
    }

    // MARK: parse, units, datum

    func testParsesARecordedThirtyDayFileWithItsDatumAndUnits() throws {
        let s = try parsed("amistad-30day.csv", datum: "NGVD29")
        XCTAssertEqual(s.reservoir, "Amistad Reservoir")
        XCTAssertEqual(s.datum, "NGVD29")
        XCTAssertEqual(s.days.count, 31)
        XCTAssertEqual(s.days.first?.date, "2026-09-13"); XCTAssertEqual(s.days.first?.ft ?? 0, 1056.48, accuracy: 1e-9)
        XCTAssertEqual(s.days.last?.date, "2026-10-13"); XCTAssertEqual(s.days.last?.ft ?? 0, 1059.79, accuracy: 1e-9)
    }

    func testDatumLabelMustMatchTheBindingExactly() throws {
        // Travis declares NAVD88 +0.6: an NGVD29 binding refuses it, a binding verified against that label accepts it.
        XCTAssertEqual(try parsed("travis-30day.csv").datum, "NAVD88 +0.6")
        guard case .failure(let e) = TWDB.parse(try fixture("travis-30day.csv"), expectedDatum: "NGVD29") else { return XCTFail("accepted a different datum") }
        XCTAssertEqual(e, .datumMismatch(file: "NAVD88 +0.6", binding: "NGVD29"))
        XCTAssertNoThrow(try parsed("travis-30day.csv", datum: "navd88 +0.6"))
        // Elephant Butte's label carries an offset the Brain does not guess: also refused as NGVD29
        guard case .failure(let e2) = TWDB.parse(try fixture("elephant-butte-2026-glitch.csv"), expectedDatum: "NGVD29") else { return XCTFail() }
        XCTAssertEqual(e2, .datumMismatch(file: "NGVD29 -43.3", binding: "NGVD29"))
    }

    func testBindingDatumSyntax() {
        XCTAssertEqual(TWDB.bindingDatum("water_level@NGVD29"), "NGVD29")
        XCTAssertEqual(TWDB.bindingDatum("water_level@NAVD88 +0.6"), "NAVD88 +0.6")
        XCTAssertNil(TWDB.bindingDatum("water_level"))
        XCTAssertNil(TWDB.bindingDatum("stage@NGVD29"))
        XCTAssertNil(TWDB.bindingDatum(nil))
    }

    func testAUnitOtherThanFeetIsRefused() throws {
        let text = String(decoding: try fixture("amistad-30day.csv"), as: UTF8.self)
            .replacingOccurrences(of: "water_level: feet above vertical datum", with: "water_level: meters above vertical datum")
        guard case .failure(let e) = TWDB.parse(Data(text.utf8), expectedDatum: "NGVD29") else { return XCTFail() }
        XCTAssertEqual(e, .unitNotFeet("meters above vertical datum"))
    }

    func testHTMLAndEmptyBodiesAreNotCSV() throws {
        guard case .failure(let e) = TWDB.parse(try fixture("not-found.html"), expectedDatum: nil) else { return XCTFail() }
        XCTAssertEqual(e, .notCSV)
        guard case .failure(let e2) = TWDB.parse(Data(), expectedDatum: nil) else { return XCTFail() }
        XCTAssertEqual(e2, .notCSV)
    }

    // MARK: missing / placeholder values

    func testBlankWaterLevelRowsAreDropped() throws {
        // Canyon Lake 1988: storage is reported for six days before any elevation exists
        let s = try parsed("canyon-blank-rows.csv", datum: "NGVD29")
        XCTAssertEqual(s.days.first?.date, "1988-10-01")
        XCTAssertEqual(s.days.count, 5)
    }

    func testZeroPlaceholdersAreDropped() throws {
        let raw = String(decoding: try fixture("sam-rayburn-1988-zeros.csv"), as: UTF8.self)
        XCTAssertTrue(raw.contains(",0.00,"), "fixture must contain real 0.00 placeholders")
        let s = try parsed("sam-rayburn-1988-zeros.csv", datum: "NGVD29")
        XCTAssertTrue(s.days.allSatisfy { $0.ft > 0 })
        XCTAssertFalse(s.days.isEmpty)
    }

    // MARK: glitch runs

    func testAmistadSingleDayGlitchIsRemoved() throws {
        let raw = String(decoding: try fixture("amistad-2008-glitch.csv"), as: UTF8.self)
        XCTAssertTrue(raw.contains("2008-11-30,790.09"))
        let s = try parsed("amistad-2008-glitch.csv", datum: "NGVD29")
        XCTAssertFalse(s.days.contains { $0.date == "2008-11-30" })
        XCTAssertTrue(s.days.contains { $0.date == "2008-11-29" } && s.days.contains { $0.date == "2008-12-01" })
        XCTAssertTrue(s.days.allSatisfy { $0.ft > 1100 })
    }

    func testElephantButteThreeDayRunIsRemovedAndTheRestKept() throws {
        let s = try parsed("elephant-butte-2026-glitch.csv", datum: "NGVD29 -43.3")
        for d in ["2026-09-08", "2026-09-09", "2026-09-10"] { XCTAssertFalse(s.days.contains { $0.date == d }, d) }
        XCTAssertTrue(s.days.contains { $0.date == "2026-09-07" } && s.days.contains { $0.date == "2026-09-11" })
        XCTAssertTrue(s.days.allSatisfy { $0.ft > 4000 })
        XCTAssertEqual(s.days.last?.date, "2026-10-13")
    }

    func testCaddoSpikeIsRemoved() throws {
        let s = try parsed("caddo-2012-spike.csv", datum: "NGVD29")
        XCTAssertFalse(s.days.contains { $0.date == "2012-10-22" })
        XCTAssertEqual(s.days.count, 13)
    }

    func testRealRampsAreNotGlitches() {
        // a 56 ft flood day that does not come back (Travis 1952) is real; a persistent step is not a glitch either
        let ramp = TWDB.despike([("2026-01-01", 619.27), ("2026-01-02", 675.65), ("2026-01-03", 697.0), ("2026-01-04", 698.0)])
        XCTAssertEqual(ramp.map(\.ft), [619.27, 675.65, 697.0, 698.0])
    }

    func testTrailingUnconfirmedJumpIsHeldBackOneDay() {
        let held = TWDB.despike([("2026-01-01", 100.0), ("2026-01-02", 100.1), ("2026-01-03", 130.0)])
        XCTAssertEqual(held.map(\.date), ["2026-01-01", "2026-01-02"])
        // the next day confirms it: the jump is real
        let confirmed = TWDB.despike([("2026-01-01", 100.0), ("2026-01-02", 100.1), ("2026-01-03", 130.0), ("2026-01-04", 131.0)])
        XCTAssertEqual(confirmed.map(\.date), ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"])
    }

    func testAFourDayRunIsNotDropped() {
        let four = TWDB.despike([("2026-01-01", 100), ("2026-01-02", 140), ("2026-01-03", 141), ("2026-01-04", 140), ("2026-01-05", 139), ("2026-01-06", 101), ("2026-01-07", 101.5)])
        XCTAssertEqual(four.count, 7)
    }

    // MARK: freshness and the live read

    func testStampIsNoonCentral() {
        XCTAssertEqual(TWDB.stamp("2026-10-13"), iso("2026-10-13T17:00:00Z"))   // CDT
        XCTAssertEqual(TWDB.stamp("2026-01-13"), iso("2026-01-13T18:00:00Z"))   // CST
    }

    func testLiveReadAsksForTheThirtyDayFileAndReturnsDailyReadings() async throws {
        let s = Script([try ok("amistad-30day.csv")])
        let r = await TWDBClient(transport: s.transport()).recent(ref(), hours: 72, now: iso("2026-10-13T20:30:00Z"))
        XCTAssertNil(r.error)
        XCTAssertEqual(s.seenUrls, ["https://www.waterdatafortexas.org/reservoirs/individual/amistad-30day.csv"])
        XCTAssertEqual(r.observations.map(\.ft), [1059.77, 1059.78, 1059.79])
        XCTAssertEqual(r.observations.last?.at, iso("2026-10-13T17:00:00Z"))
    }

    func testFreshnessEnvelopeMatchesTheDailyCadence() async throws {
        let s = Script([try ok("amistad-30day.csv")])
        let r = await TWDBClient(transport: s.transport()).recent(ref(), hours: 24 * 7, now: iso("2026-10-13T20:30:00Z"))
        let last = try XCTUnwrap(r.observations.last)
        // cadence 1440 / lag 1440: stale after lag + 3 cadences = 4 days
        XCTAssertFalse(LakeLevelClassifier.isStale(last.at, ref: ref(), now: iso("2026-10-13T20:30:00Z")))
        XCTAssertFalse(LakeLevelClassifier.isStale(last.at, ref: ref(), now: iso("2026-10-17T16:00:00Z")))
        XCTAssertTrue(LakeLevelClassifier.isStale(last.at, ref: ref(), now: iso("2026-10-17T18:00:00Z")))
        // a window that excludes every stamp is an error, not an empty success
        let old = await TWDBClient(transport: Script([try ok("amistad-30day.csv")]).transport()).recent(ref(), hours: 24, now: iso("2026-12-31T00:00:00Z"))
        XCTAssertNotNil(old.error)
        XCTAssertTrue(old.observations.isEmpty)
    }

    func testLiveReadRefusesABindingWithoutADatumAndAMismatchedFile() async throws {
        let noDatum = await TWDBClient(transport: Script([try ok("amistad-30day.csv")]).transport()).recent(ref(series: "water_level"), hours: 72, now: iso("2026-10-13T20:30:00Z"))
        XCTAssertTrue(noDatum.error?.contains("water_level@<datum>") == true, noDatum.error ?? "")
        let wrong = await TWDBClient(transport: Script([try ok("travis-30day.csv")]).transport()).recent(ref("travis"), hours: 72, now: iso("2026-10-13T20:30:00Z"))
        XCTAssertTrue(wrong.error?.contains("NAVD88 +0.6") == true && wrong.error?.contains("NGVD29") == true, wrong.error ?? "")
        XCTAssertTrue(wrong.observations.isEmpty)
    }

    // MARK: HTTP errors and rate limit

    func testHTTPErrorsMapToNamedErrors() async throws {
        func run(_ r: TWDBResponse?) async -> String? {
            await TWDBClient(transport: Script([r]).transport(), maxAttempts: 1).recent(ref(), hours: 72, now: iso("2026-10-13T20:30:00Z")).error
        }
        let e404 = await run(TWDBResponse(status: 404, body: try fixture("not-found.html"), retryAfter: nil))
        XCTAssertTrue(e404?.contains("not found") == true, e404 ?? "")
        let e500 = await run(TWDBResponse(status: 500, body: Data(), retryAfter: nil))
        XCTAssertEqual(e500, "TWDB amistad: HTTP 500")
        let eNil = await run(nil)
        XCTAssertEqual(eNil, "TWDB amistad unreachable")
        let eHTML = await run(TWDBResponse(status: 200, body: try fixture("not-found.html"), retryAfter: nil))
        XCTAssertTrue(eHTML?.contains("not a TWDB CSV") == true, eHTML ?? "")
        let eSlug = await TWDBClient(transport: Script([nil]).transport()).recent(ref("../etc"), hours: 72, now: iso("2026-10-13T20:30:00Z")).error
        XCTAssertTrue(eSlug?.contains("invalid reservoir slug") == true, eSlug ?? "")
    }

    func testRateLimitBacksOffHonoursRetryAfterAndRecovers() async throws {
        let s = Script([TWDBResponse(status: 429, body: Data(), retryAfter: 45), TWDBResponse(status: 503, body: Data(), retryAfter: nil), try ok("amistad-30day.csv")])
        let r = await TWDBClient(transport: s.transport()).recent(ref(), hours: 72, now: iso("2026-10-13T20:30:00Z"))
        XCTAssertNil(r.error)
        XCTAssertEqual(s.seenUrls.count, 3)
        XCTAssertEqual(s.seenSleeps, [45, 60], "Retry-After 45 s is above the 30 s first back-off; then the back-off doubled to 60 s")
    }

    func testRateLimitThatNeverClearsFailsWithoutAHole() async throws {
        let s = Script([TWDBResponse(status: 429, body: Data(), retryAfter: 1000)])
        let r = await TWDBClient(transport: s.transport(), maxAttempts: 3).recent(ref(), hours: 72, now: iso("2026-10-13T20:30:00Z"))
        XCTAssertEqual(r.error, "TWDB amistad: rate limited (HTTP 429) after 3 attempts")
        XCTAssertTrue(r.observations.isEmpty)
        XCTAssertEqual(s.seenUrls.count, 3)
        XCTAssertEqual(s.seenSleeps, [120, 120], "the pause is capped at 120 s")
    }

    // MARK: history

    func testHistoryFileSelectionAndSinceFilter() async throws {
        let now = iso("2026-10-13T20:30:00Z")
        XCTAssertEqual(TWDB.fileName(slug: "travis", since: nil, now: now), "travis")
        XCTAssertEqual(TWDB.fileName(slug: "travis", since: "2026-09-25", now: now), "travis-30day")
        XCTAssertEqual(TWDB.fileName(slug: "travis", since: "2026-03-01", now: now), "travis-1year")
        XCTAssertEqual(TWDB.fileName(slug: "travis", since: "2020-01-01", now: now), "travis")
        let s = Script([try ok("amistad-2008-glitch.csv")])
        let d = await TWDBClient(transport: s.transport()).daily(slug: "amistad", datum: "NGVD29", offsetFt: 0, since: nil, now: now)
        let days = try XCTUnwrap(d)
        XCTAssertEqual(days.first?.date, "2008-11-20")
        XCTAssertFalse(days.contains { $0.date == "2008-11-30" })
        XCTAssertTrue(days.allSatisfy { $0.sourceId == "twdb:amistad" })
        let shifted = await TWDBClient(transport: Script([try ok("amistad-2008-glitch.csv")]).transport()).daily(slug: "amistad", datum: "NGVD29", offsetFt: -0.5, since: "2008-12-01", now: now)
        XCTAssertEqual(shifted?.first?.date, "2008-12-01")
        XCTAssertEqual(shifted?.first?.ft ?? 0, 1118.19 - 0.5, accuracy: 1e-9)
        // a datum mismatch or an HTTP error gives nil: never a silent hole
        let nilWrong = await TWDBClient(transport: Script([try ok("travis-30day.csv")]).transport()).daily(slug: "travis", datum: "NGVD29", offsetFt: 0, since: nil, now: now)
        XCTAssertNil(nilWrong)
        let nil404 = await TWDBClient(transport: Script([TWDBResponse(status: 404, body: Data(), retryAfter: nil)]).transport()).daily(slug: "x", datum: "NGVD29", offsetFt: 0, since: nil, now: now)
        XCTAssertNil(nil404)
    }


    // MARK: a full-record file without its comment block (real: Possum Kingdom, 2026-10-13)

    func testHeaderlessFileIsRefusedUnlessCorroboratedByTheOneYearFile() async throws {
        let headerless = try fixture("possum-kingdom-headerless.csv")
        guard case .failure(let e) = TWDB.parse(headerless, expectedDatum: "NGVD29") else { return XCTFail("accepted a file with no datum") }
        XCTAssertEqual(e, .noDatum)
        let parsedRows = try TWDB.parse(headerless, expectedDatum: "NGVD29", allowHeaderless: true).get()
        XCTAssertTrue(parsedRows.headerless)
        XCTAssertEqual(parsedRows.datum, "")
        XCTAssertEqual(parsedRows.days.last?.date, "2026-10-13")
        let year = try parsed("possum-kingdom-1year.csv", datum: "NGVD29")
        XCTAssertEqual(year.datum, "NGVD29")
        XCTAssertTrue(TWDB.corroborates(parsedRows.days, year.days))
        // history pull: full file (headerless) then the -1year file
        let now = iso("2026-10-13T20:30:00Z")
        let s = Script([TWDBResponse(status: 200, body: headerless, retryAfter: nil), try ok("possum-kingdom-1year.csv")])
        let d = await TWDBClient(transport: s.transport()).daily(slug: "possum-kingdom", datum: "NGVD29", offsetFt: 0, since: nil, now: now)
        XCTAssertEqual(d?.count, parsedRows.days.count)
        XCTAssertEqual(s.seenUrls.map { URL(string: $0)!.lastPathComponent }, ["possum-kingdom.csv", "possum-kingdom-1year.csv"])
        // the -1year file declares another datum: refused
        let travisAsYear = Script([TWDBResponse(status: 200, body: headerless, retryAfter: nil), try ok("travis-30day.csv")])
        let none = await TWDBClient(transport: travisAsYear.transport()).daily(slug: "possum-kingdom", datum: "NGVD29", offsetFt: 0, since: nil, now: now)
        XCTAssertNil(none)
        // the -1year file disagrees with the rows: refused
        let shifted = String(decoding: try fixture("possum-kingdom-1year.csv"), as: UTF8.self)
            .split(whereSeparator: \.isNewline)
            .map { l -> String in
                guard !l.hasPrefix("#"), l.hasPrefix("202"), var c = Optional(l.split(separator: ",", omittingEmptySubsequences: false).map(String.init)), c.count > 2, let v = Double(c[1]) else { return String(l) }
                c[1] = String(format: "%.2f", v + 1.0); return c.joined(separator: ",")
            }.joined(separator: "\n")
        let bad = Script([TWDBResponse(status: 200, body: headerless, retryAfter: nil), TWDBResponse(status: 200, body: Data(shifted.utf8), retryAfter: nil)])
        let nil2 = await TWDBClient(transport: bad.transport()).daily(slug: "possum-kingdom", datum: "NGVD29", offsetFt: 0, since: nil, now: now)
        XCTAssertNil(nil2)
        // a live read never takes a headerless file
        let live = await TWDBClient(transport: Script([TWDBResponse(status: 200, body: headerless, retryAfter: nil)]).transport())
            .recent(ref("possum-kingdom"), hours: 72, now: now)
        XCTAssertTrue(live.error?.contains("no vertical datum") == true, live.error ?? "")
    }

    // MARK: terms gate

    func testLiveTransportIsClosedUntilTheTermsAreCleared() async throws {
        XCTAssertFalse(TWDBTransport.termsCleared(env: [:]))
        XCTAssertFalse(TWDBTransport.termsCleared(env: ["SECTOR_TWDB_TERMS_OK": "true"]), "only the exact value 1 opens it")
        XCTAssertTrue(TWDBTransport.termsCleared(env: ["SECTOR_TWDB_TERMS_OK": "1"]))
        let closed = TWDBTransport.live(env: [:])
        XCTAssertFalse(closed.enabled)
        let r = await TWDBClient(transport: closed).recent(ref(), hours: 72, now: iso("2026-10-13T20:30:00Z"))
        XCTAssertEqual(r.error, TWDBTransport.disabledMessage)
        XCTAssertTrue(r.observations.isEmpty)
        let h = await TWDBClient(transport: closed).daily(slug: "amistad", datum: "NGVD29", offsetFt: 0, since: nil, now: iso("2026-10-13T20:30:00Z"))
        XCTAssertNil(h)
        // the process default (no env var in the test run) is closed too
        XCTAssertFalse(TWDBTransport.live().enabled)
    }

    // MARK: identity, user agent, table gate

    func testUserAgentNamesNoMailboxAndTakesAnOptionalEnvContact() {
        let base = TWDBTransport.userAgent(env: [:])
        XCTAssertEqual(base, "Sector-LakeBrain/1.0 (io.sector.co; Rehtac Labs; read-only public data)")
        XCTAssertFalse(base.contains("@"))
        XCTAssertEqual(TWDBTransport.userAgent(env: ["SECTOR_CONTACT": "  "]), base)
        XCTAssertEqual(TWDBTransport.userAgent(env: ["SECTOR_CONTACT": "ops@example.org"]), base + " contact: ops@example.org")
    }

    func testProviderAndHistoryKindsRoundTripThroughTheGeneratedTableCodec() throws {
        let live = LakeGeneratedBindings.Record.Live(provider: "twdb", capability: "DIRECT_LAKE_GAUGE", station: "cedar-creek",
                                                      series: "water_level@NGVD29", cadenceMin: 1440, lagMin: 1440, datumOffsetFt: nil, note: nil)
        let r = try XCTUnwrap(LakeGeneratedBindings.ref(live))
        XCTAssertEqual(r.provider, .twdb)
        XCTAssertEqual(r.sourceId, "twdb:cedar-creek:water_level@NGVD29")
        XCTAssertEqual(r.providerName, "TWDB Water Data for Texas")
        let h = try JSONDecoder().decode(LakeGeneratedBindings.Record.Hist.self,
                                         from: Data(#"{"kind":"twdbDaily","slug":"cedar-creek","datum":"NGVD29"}"#.utf8))
        let src = try XCTUnwrap(LakeGeneratedBindings.history(h))
        XCTAssertEqual(src, .twdbDaily(slug: "cedar-creek", datum: "NGVD29", offsetFt: 0))
        XCTAssertTrue(src.profileDescription.contains("twdb:cedar-creek"))
        // an incomplete record is unmappable, never a half binding
        let bad = try JSONDecoder().decode(LakeGeneratedBindings.Record.Hist.self, from: Data(#"{"kind":"twdbDaily","slug":"x"}"#.utf8))
        XCTAssertNil(LakeGeneratedBindings.history(bad))
    }

    func testThePublishedTableHasNoTWDBRowAndNothingIsReviewed() {
        XCTAssertTrue(LakeGeneratedBindings.loadErrors.isEmpty, "\(LakeGeneratedBindings.loadErrors)")
        let twdb = LakeSourceBindings.generated.filter { b in
            b.live.contains { $0.provider == .twdb } || b.history.contains { if case .twdbDaily = $0 { return true } else { return false } }
        }
        XCTAssertTrue(twdb.isEmpty, "TWDB rows are produced only by the opt-in overlay, never by the published table: \(twdb.map(\.lakeId))")
        XCTAssertTrue(LakeSourceBindings.generated.allSatisfy { $0.status == .candidate })
    }
}
