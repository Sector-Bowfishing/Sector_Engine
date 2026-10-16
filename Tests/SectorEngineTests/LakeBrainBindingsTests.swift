//
//  LakeBrainBindingsTests.swift
//  Lake Brain: the generated bindings table and its acceptance gate, the fleet adapters (parsers, traps), operator levels,
//  profile pointers, and the candidate dry run. No network.
//

import XCTest
@testable import SectorEngine

final class LakeBrainBindingsTests: XCTestCase {

    let utc = TimeZone(identifier: "UTC")!
    func iso(_ s: String) -> Date { ISO8601DateFormatter().date(from: s)! }

    static let forbiddenProviders: Set<String> = ["nipsco", "njwsa", "duke", "wps-hydro", "alliant", "srp", "cnppid", "nppd", "utahlake",
                                                   "aep", "eccc", "mncsg", "sjrwmd", "nhdes"]

    /// jobs/lake-brain/data/<name> of the checkout this test file lives in.
    func repoData(_ name: String) -> URL {
        URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("jobs/lake-brain/data/\(name)")
    }

    func proposed() throws -> [String: Any] {
        let d = try Data(contentsOf: repoData("bindings.proposed.v1.json"))
        return try XCTUnwrap(JSONSerialization.jsonObject(with: d) as? [String: Any])
    }

    // MARK: (a) the gate with the real (empty) accepted batch

    func testWithoutAnAcceptedBatchNoGeneratedBindingIsReviewed() {
        XCTAssertTrue(LakeGeneratedBindings.loadErrors.isEmpty, "\(LakeGeneratedBindings.loadErrors)")
        XCTAssertTrue(LakeGeneratedBindings.acceptedLakeIds.isEmpty, "accepted_batch.json is created only after Michael's review")
        XCTAssertFalse(LakeSourceBindings.generated.isEmpty)
        XCTAssertTrue(LakeSourceBindings.generated.allSatisfy { $0.status == .candidate })
        // `reviewed` is the list a run publishes from: the five hand-written pilots and nothing else.
        XCTAssertEqual(Set(LakeSourceBindings.reviewed.map(\.lakeId)),
                       ["Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC"])
        XCTAssertTrue(LakeSourceBindings.reviewed.allSatisfy { $0.status == .reviewed })
        XCTAssertEqual(LakeSourceBindings.version, LakeSourceBindings.baseVersion, "an empty batch adds no version suffix")
        // hand-written first: the pilot row is the hand-written one, not the generated record
        let hartwell = LakeSourceBindings.binding(for: "Lake Hartwell|SC")
        XCTAssertEqual(hartwell?.status, .reviewed)
        XCTAssertEqual(hartwell?.live.first?.provider, .cwms, "the hand-written Hartwell has the CWMS pool first")
        let handIds = Set(LakeSourceBindings.handWritten.map(\.lakeId))
        for g in LakeSourceBindings.generated where !handIds.contains(g.lakeId) {
            XCTAssertNil(LakeSourceBindings.reviewedBinding(for: g.lakeId), g.lakeId)
            XCTAssertEqual(LakeSourceBindings.binding(for: g.lakeId)?.status, .candidate)
        }
    }

    func testPlannerAndRunnerNeverPublishForACandidate() async throws {
        let candidate = try XCTUnwrap(LakeSourceBindings.candidates.first)
        let lake = try XCTUnwrap(LakeDirectory.all.first { $0.id == candidate.lakeId })
        let feeds = CountingFeeds()
        // a normal run: no state, no plan, and not one fetch
        let r = await LakeBrainRunner.evaluateLake(lake, feeds: feeds, archive: nil, presence: nil, published: nil, previousProfile: nil,
                                                   options: LakeBrainRunOptions(), now: feeds.now)
        XCTAssertNil(r.state)
        XCTAssertNil(r.plan)
        XCTAssertFalse(r.dryRunCandidate)
        XCTAssertEqual(r.profile.sourceCapability.bindingStatus, .candidate)
        XCTAssertNil(r.profile.operatingPools, "a candidate's plan evidence is never shown")
        XCTAssertNil(r.profile.characteristics, "a candidate's context features are never shown")
        XCTAssertEqual(feeds.calls, 0)
        // a force run does not change that
        var forced = LakeBrainRunOptions(); forced.force = true
        let f = await LakeBrainRunner.evaluateLake(lake, feeds: feeds, archive: nil, presence: nil, published: nil, previousProfile: nil,
                                                   options: forced, now: feeds.now)
        XCTAssertNil(f.state)
        XCTAssertEqual(feeds.calls, 0)
        // the scope of a normal run is the reviewed lakes only
        let store = LocalDirectoryStore(directory: NSTemporaryDirectory() + "lb-gate-\(UUID().uuidString)", brainId: LakeBrainSpec.brainId)
        let run = await LakeBrainRunner.run(store: store, feeds: feeds, archive: nil, presenceArchive: nil, options: LakeBrainRunOptions(), now: feeds.now)
        XCTAssertEqual(Set(run.lakes.map(\.lakeId)), Set(LakeSourceBindings.reviewed.map(\.lakeId)))
        XCTAssertTrue(run.lakes.allSatisfy { !$0.dryRunCandidate })
    }

    func testCandidateDryRunEvaluatesAsIfReviewedAndMarksIt() async throws {
        let candidate = try XCTUnwrap(LakeSourceBindings.candidates.first { $0.live.first?.provider == .cwms || $0.live.first?.provider == .usgs })
        let lake = try XCTUnwrap(LakeDirectory.all.first { $0.id == candidate.lakeId })
        let feeds = FakeFeeds()
        var o = LakeBrainRunOptions(); o.includeCandidates = true
        let r = await LakeBrainRunner.evaluateLake(lake, feeds: feeds, archive: nil, presence: nil, published: nil, previousProfile: nil, options: o, now: feeds.now)
        XCTAssertTrue(r.dryRunCandidate)
        let s = try XCTUnwrap(r.state)
        XCTAssertEqual(s.kind, .observed)
        XCTAssertTrue(s.provenance.qualityFlags?.contains("dryRunCandidate") ?? false)
        XCTAssertEqual(r.profile.sourceCapability.bindingStatus, .candidate, "the profile still says CANDIDATE")
        XCTAssertTrue(r.profile.sourceCapability.note?.hasPrefix("dryRunCandidate") ?? false)
        // the binding table itself is untouched by a dry run
        XCTAssertEqual(LakeSourceBindings.binding(for: lake.id)?.status, .candidate)
    }

    // MARK: (b) a synthetic accepted batch

    func testSyntheticAcceptedBatchFlipsExactlyThoseIdsToReviewed() {
        let ids = LakeGeneratedBindings.records.map(\.lakeId)
        let pick: Set<String> = [ids[3], ids[17], ids[ids.count - 1]]
        let made = LakeGeneratedBindings.make(records: LakeGeneratedBindings.records, accepted: pick, reviewedAt: "2026-10-20")
        XCTAssertEqual(made.count, ids.count)
        XCTAssertEqual(Set(made.filter { $0.status == .reviewed }.map(\.lakeId)), pick)
        XCTAssertTrue(made.filter { $0.status == .candidate }.allSatisfy { !pick.contains($0.lakeId) && $0.reviewedAt == nil })
        XCTAssertEqual(Set(made.filter { $0.status == .reviewed }.compactMap(\.reviewedAt)), ["2026-10-20"])
        // an id that is not in the table accepts nothing
        let none = LakeGeneratedBindings.make(records: LakeGeneratedBindings.records, accepted: ["Nowhere|ZZ"])
        XCTAssertTrue(none.allSatisfy { $0.status == .candidate })
    }

    func testAnAcceptedBindingPublishesAndItsContextAndPlanAppearInTheProfile() async throws {
        let rec = try XCTUnwrap(LakeGeneratedBindings.records.first { $0.plan?.levels.contains { $0.kind == "static" } == true
                                                                   && $0.context != nil && $0.live.first?.provider == "a2w" })
        let accepted = LakeGeneratedBindings.make(records: [rec], accepted: [rec.lakeId], reviewedAt: "2026-10-20")
        let b = try XCTUnwrap(accepted.first)
        XCTAssertEqual(b.status, .reviewed)
        let lake = try XCTUnwrap(LakeDirectory.all.first { $0.id == rec.lakeId })
        let p = LakeBrainProfiles.build(lake: lake, binding: b, state: nil, baseline: nil, previous: nil, presence: nil, live: [],
                                        now: iso("2026-10-13T12:00:00Z"), archiveURI: nil)
        XCTAssertEqual(p.sourceCapability.bindingStatus, .reviewed)
        XCTAssertNotNil(p.characteristics?.context?.lakeClass?.value)
        XCTAssertNotNil(p.characteristics?.context?.lakeClass?.source)
        XCTAssertEqual(p.operatingPools?.planEvidence?.verifiedMatch, true)
        if case .operatorLevels(let o)? = b.guide, let f = o.floodPoolBottom {
            XCTAssertEqual(p.operatingPools?.floodPoolBottom?.name, f.name)
            XCTAssertEqual(p.operatingPools?.floodPoolBottom?.source, f.source)
        }
        XCTAssertEqual(p.identity.geometry?.registryRef, "https://storage.googleapis.com/sector-lake-registry/registry/lakes.v1.json")
        XCTAssertEqual(p.identity.geometry?.lakeKey, BrainPlatform.lakeKey(rec.lakeId))
    }

    // MARK: (c) the generated table is the Python table

    func testGeneratedTableMatchesThePythonTable() throws {
        let doc = try proposed()
        XCTAssertEqual(doc["bindingStatus"] as? String, "MACHINE_VERIFIED")
        let rows = try XCTUnwrap(doc["bindings"] as? [[String: Any]])
        XCTAssertEqual(LakeGeneratedBindings.tableCount, rows.count, "generated Swift table is stale: run scripts/generate-lake-bindings.py")
        XCTAssertEqual(LakeGeneratedBindings.bindings.count, rows.count)
        XCTAssertEqual(Set(LakeGeneratedBindings.records.map(\.lakeId)), Set(rows.compactMap { $0["lakeId"] as? String }))
        // the counts the build script reported
        let counts = try XCTUnwrap(doc["counts"] as? [String: Any])
        XCTAssertEqual(counts["eligible"] as? Int, rows.count)
    }

    func testGeneratedTableSanity() throws {
        let ids = LakeGeneratedBindings.records.map(\.lakeId)
        XCTAssertEqual(Set(ids).count, ids.count, "lake ids are unique")
        let directory = Set(LakeDirectory.all.map(\.id))
        for id in ids { XCTAssertTrue(directory.contains(id), "\(id) is not a LakeDirectory id") }
        for r in LakeGeneratedBindings.records {
            XCTAssertFalse(r.live.isEmpty, r.lakeId)
            for l in r.live {
                XCTAssertNotNil(LevelSeriesRef.Provider(rawValue: l.provider), "\(r.lakeId): provider \(l.provider) has no adapter")
                XCTAssertFalse(Self.forbiddenProviders.contains(l.provider), "\(r.lakeId): forbidden provider \(l.provider)")
                if l.provider == "usgs" { XCTAssertNotEqual(l.series, "00065", "\(r.lakeId): gage height is not an elevation") }
                if l.provider != "tva" && l.provider != "rise" { XCTAssertNotNil(l.series, "\(r.lakeId) \(l.provider) needs a series") }
            }
            XCTAssertNotNil(TimeZone(identifier: r.timeZone), "\(r.lakeId): \(r.timeZone)")
            XCTAssertEqual(r.verification.criteriaVersion, "binding-review-v1")
            XCTAssertTrue(["w1", "w2-v1"].contains(r.verification.wave), "\(r.lakeId): only pre-registered waves")
            XCTAssertTrue(["VERIFIED", "VERIFIED_CORROBORATED"].contains(r.verification.researchStatus), r.lakeId)
        }
        // every binding mapped, none lost
        XCTAssertEqual(LakeGeneratedBindings.bindings.count, ids.count)
        // excluded lakes (undocumented providers, coordinate flags, post-hoc, history/live mismatch, ...) never appear
        let ex = try Data(contentsOf: repoData("bindings.proposed.v1.excluded.json"))
        let excluded = try XCTUnwrap((try JSONSerialization.jsonObject(with: ex) as? [String: Any])?["excluded"] as? [[String: Any]])
        let excludedIds = Set(excluded.compactMap { $0["lakeId"] as? String })
        XCTAssertTrue(excludedIds.count > 100)
        XCTAssertTrue(excludedIds.isDisjoint(with: Set(ids)))
        for must in ["Clinton Lake|IL", "Bartlett|AZ", "Lake Taneycomo|MO", "Rend Lake|IL", "Red Lake|MN", "Lake Shafer|IN"] {
            XCTAssertTrue(excludedIds.contains(must), "\(must) must be excluded")
            XCTAssertFalse(ids.contains(must))
        }
    }

    func testEveryPilotIsReproducedByTheMachineTable() throws {
        // key fields of the five hand-written bindings equal the machine records (build_bindings_table.py asserts the same)
        for pilot in LakeSourceBindings.handWritten {
            guard let rec = LakeGeneratedBindings.records.first(where: { $0.lakeId == pilot.lakeId }) else { continue }
            XCTAssertEqual(rec.timeZone, pilot.timeZone, pilot.lakeId)
            let machine = rec.live.first
            // the pilot's capability is that of its primary; Hartwell's hand-written primary is the CWMS pool, the machine's is the USGS gauge
            if pilot.lakeId != "Lake Hartwell|SC" { XCTAssertEqual(rec.capability, pilot.capability.rawValue, pilot.lakeId) }
            else { XCTAssertEqual(machine?.capability, LevelSourceCapability.directLakeGauge.rawValue) }
            XCTAssertTrue(pilot.live.contains { $0.provider.rawValue == machine?.provider && $0.station == machine?.station && $0.series == machine?.series },
                          "\(pilot.lakeId): the machine primary is among the hand-written refs")
        }
        XCTAssertEqual(LakeGeneratedBindings.records.filter { r in LakeSourceBindings.handWritten.contains { $0.lakeId == r.lakeId } }.count, 5)
    }

    // MARK: adapters: parsers and traps

    func testNWPSRejectsStageAndSentinels() throws {
        let json = """
        {"pedts":"HPIRZ","primaryUnits":"ft","data":[{"validTime":"2026-10-13T10:00:00Z","primary":507.2},{"validTime":"2026-10-13T11:00:00Z","primary":-999},
        {"validTime":"2026-10-13T12:00:00Z","primary":507.3}]}
        """
        let ok = LakeFleetClients.parseNWPS(Data(json.utf8), lid: "RGLA1", expectedPe: "HP", since: iso("2026-10-01T00:00:00Z"))
        XCTAssertNil(ok.error)
        XCTAssertEqual(ok.observations.map(\.ft), [507.2, 507.3], "-999 sentinel dropped")
        let stage = LakeFleetClients.parseNWPS(Data(json.replacingOccurrences(of: "HPIRZ", with: "HGIRZ").utf8), lid: "X", expectedPe: "HP", since: .distantPast)
        XCTAssertNotNil(stage.error, "an HG stage gauge is not pool elevation")
        let flow = LakeFleetClients.parseNWPS(Data(json.replacingOccurrences(of: "\"ft\"", with: "\"kcfs\"").utf8), lid: "X", expectedPe: "HP", since: .distantPast)
        XCTAssertNotNil(flow.error)
        let old = LakeFleetClients.parseNWPS(Data(json.utf8), lid: "X", expectedPe: "HP", since: iso("2026-10-13T11:30:00Z"))
        XCTAssertEqual(old.observations.map(\.ft), [507.3])
    }

    func testRISEDropsZeroPlaceholdersAndModeledResults() {
        let json = """
        {"links":{"next":"/rise/api/result?page=2"},"data":[
        {"attributes":{"dateTime":"2026-10-10T07:00:00+00:00","result":448.7,"resultAttributes":{"resultType":"observed"}}},
        {"attributes":{"dateTime":"2026-10-11T07:00:00+00:00","result":0.0,"resultAttributes":{"resultType":"observed"}}},
        {"attributes":{"dateTime":"2026-10-12T07:00:00+00:00","result":449.1,"resultAttributes":{"resultType":"modeled"}}},
        {"attributes":{"dateTime":"2026-10-13T07:00:00+00:00","result":null}},
        {"attributes":{"dateTime":"2026-10-14T07:00:00+00:00","result":450}}]}
        """
        let (obs, next) = LakeFleetClients.parseRISE(Data(json.utf8))
        XCTAssertEqual(obs.map(\.ft), [448.7, 450])
        XCTAssertTrue(next)
    }

    func testAccess2WaterReadingBuildsTheDayBeforeFromDelta24() throws {
        let json = """
        {"provider":"SWL","code":"Beaver_Dam","timeseries":[
        {"tsid":"Beaver_Dam-Tailwater.Elev-Downstream.Inst.1Hour.0.Decodes-rev","unit":"ft","latest_time":"2026-10-13T06:00:00Z","latest_value":916.3,"delta24hr":-0.06},
        {"tsid":"Beaver_Dam-Headwater.Elev.Inst.1Hour.0.Decodes-rev","unit":"ft","latest_time":"2026-10-13T06:00:00Z","latest_value":1112.66,"delta24hr":-0.19}],
        "levels":[{"label":"Top of Normal","tsid":"Beaver_Dam.Elev-Pool.Inst.0.Top of Normal","units":"ft","type":"REGULAR","latest_value":1120.43}]}
        """
        let loc = try JSONDecoder().decode(A2WLocation.self, from: Data(json.utf8))
        let ref = LevelSeriesRef(provider: .a2w, capability: .directOperatorPool, station: "SWL:Beaver_Dam",
                                 series: "Beaver_Dam-Headwater.Elev.Inst.1Hour.0.Decodes-rev", cadenceMin: 60, lagMin: 120)
        let r = LakeFleetClients.a2wReading(loc, ref: ref)
        XCTAssertEqual(r.observations.count, 2)
        XCTAssertEqual(r.observations[0].ft, 1112.85, accuracy: 0.0001)
        XCTAssertEqual(r.observations[1].ft, 1112.66, accuracy: 0.0001)
        XCTAssertEqual(r.observations[1].at.timeIntervalSince(r.observations[0].at), 86_400)
        // the tailwater sibling is a different tsid and is never read for this binding
        var tail = ref; tail.series = "nope"
        XCTAssertNotNil(LakeFleetClients.a2wReading(loc, ref: tail).error)
        XCTAssertEqual(ref.sourceId, "a2w:SWL:Beaver_Dam:Beaver_Dam-Headwater.Elev.Inst.1Hour.0.Decodes-rev")
        XCTAssertEqual(LakeFleetClients.a2wStation("SWL:Beaver_Dam")?.district, "swl")
    }

    func testUSGSGageHeightIsNotAnElevation() async {
        let feeds = PublicLakeLevelFeeds()
        let ref = LevelSeriesRef(provider: .usgs, capability: .directLakeGauge, station: "02187010", series: "00065", cadenceMin: 60, lagMin: 60)
        let live = await feeds.recent(ref, hours: 24, now: Date())
        XCTAssertNotNil(live.error)
        XCTAssertTrue(live.observations.isEmpty)
        // history: a bare gage height is refused before any request; with a datum offset it is allowed (would hit the network, so not called)
        let h = await feeds.daily(.usgsDaily(site: "04082500", param: "00065", stat: "dv", offsetFt: 0), since: nil, now: Date(), timeZone: utc)
        XCTAssertNil(h)
    }

    func testUSGSDailyValuesMergeStatisticsAndApplyTheOffset() throws {
        let json = """
        {"value":{"timeSeries":[
         {"variable":{"noDataValue":-999999,"options":{"option":[{"optionCode":"32400"}]}},"values":[{"value":[{"dateTime":"2020-01-01T00:00:00.000","value":"10.0"},{"dateTime":"2020-01-02T00:00:00.000","value":"11.0"}]}]},
         {"variable":{"noDataValue":-999999,"options":{"option":[{"optionCode":"00003"}]}},"values":[{"value":[{"dateTime":"2020-01-01T00:00:00.000","value":"10.5"},{"dateTime":"2020-01-03T00:00:00.000","value":"-999999"}]}]}]}}
        """
        let d = try XCTUnwrap(LakeFleetClients.parseUSGSDV(Data(json.utf8), offsetFt: 100, src: "usgs:X:00065:dv"))
        XCTAssertEqual(d.map(\.date), ["2020-01-01", "2020-01-02"])
        XCTAssertEqual(d.map(\.ft), [110.5, 111.0], "00003 wins over 32400 on a shared date; no-data dropped; +offset")
    }

    func testHADSParsesTheFirstPoolColumnAndRejectsStage() {
        let csv = "station,utc_valid,HPIRZZZ,PPDRWZZ\nRGLA1,2026-10-10 00:00:00,506.97,\nRGLA1,2026-10-10 01:00:00,,0.1\nRGLA1,2026-10-10 02:00:00,506.99,\n"
        let obs = LakeFleetClients.parseHADS(Data(csv.utf8), prefix: "HPIR")
        XCTAssertEqual(obs.map(\.ft), [506.97, 506.99])
        XCTAssertEqual(obs[0].at, iso("2026-10-10T00:00:00Z"))
        XCTAssertTrue(LakeFleetClients.parseHADS(Data(csv.utf8), prefix: "HGIR").isEmpty, "no stage column is read as a pool")
    }

    func testHADSTakesTheFirstNonEmptyPoolColumnPerRow() {
        // A gauge can change its DCP configuration over a multi-year chunk: the pool moves from HPIRZZZ to HPIRGZZ.
        let csv = "station,utc_valid,HPIRGZZ,HPIRZZZ\nX,2021-01-01 00:00:00,,100.5\nX,2023-01-01 00:00:00,101.5,\nX,2023-01-01 01:00:00,,\n"
        let obs = LakeFleetClients.parseHADS(Data(csv.utf8), prefix: "HPIR")
        XCTAssertEqual(obs.map(\.ft), [100.5, 101.5])
    }

    func testDailyMediansAreLakeLocalAndShifted() {
        let chicago = TimeZone(identifier: "America/Chicago")!
        // 04:00Z on Oct 14 is 23:00 CDT Oct 13
        let obs = [LevelObservation(at: iso("2026-10-14T04:00:00Z"), ft: 1), LevelObservation(at: iso("2026-10-13T20:00:00Z"), ft: 3),
                   LevelObservation(at: iso("2026-10-13T18:00:00Z"), ft: 100), LevelObservation(at: iso("2026-10-14T06:00:00Z"), ft: 7)]
        let d = LakeFleetClients.dailyMedians(obs, timeZone: chicago, offsetFt: 10, src: "s")
        XCTAssertEqual(d.map(\.date), ["2026-10-13", "2026-10-14"])
        XCTAssertEqual(d[0].ft, 13, accuracy: 0.001, "median of {1, 3, 100} + 10")
        XCTAssertEqual(d[1].ft, 17, accuracy: 0.001)
    }

    func testCWMSWindowShrinksForDenseSeries() {
        let daily = PublicLakeLevelFeeds.cwmsWindowSeconds("Hartwell.Elev-Pool.Inst.1Day.0.Raw-SHEF_SAS")
        let hourly = PublicLakeLevelFeeds.cwmsWindowSeconds("Martin.Elev.Inst.1Hour.0.Raw-APCO")
        let quarter = PublicLakeLevelFeeds.cwmsWindowSeconds("Bankhead.Elev.Inst.15Minutes.0.Raw-USGS")
        XCTAssertEqual(daily, 5 * 365.25 * 86_400, accuracy: 1)
        XCTAssertEqual(hourly, 5 * 365.25 * 86_400, accuracy: 1)
        XCTAssertLessThan(quarter, 2 * 365.25 * 86_400)
        XCTAssertGreaterThan(quarter, 86_400 * 100)
    }

    // MARK: operator levels

    func staticLevel(_ name: String, _ ft: Double) -> OperatorLevelRef {
        OperatorLevelRef(kind: .staticFt, name: name, ft: ft, source: "test:\(name)", seasonal: false)
    }

    func testOperatorLevelsBuildZoneFloodPoolAndGuide() async throws {
        let feeds = PublicLakeLevelFeeds()
        let o = OperatorLevels(guide: nil, zoneTop: staticLevel("Top of Normal", 1120.43), zoneBottom: staticLevel("Bottom of Normal", 1077),
                               floodPoolBottom: staticLevel("Top of Conservation", 1120.43), matchedProject: "SWL:Beaver_Dam", matchBasis: "nid", verifiedMatch: true)
        let gOpt = await feeds.guide(.operatorLevels(o), day: "2026-10-13", timeZone: utc)
        let g = try XCTUnwrap(gOpt)
        XCTAssertEqual(g.zone?.bottomFt, 1077)
        XCTAssertEqual(g.zone?.topFt, 1120.43)
        XCTAssertEqual(g.floodPoolBottomFt, 1120.43)
        XCTAssertNil(g.guideFt)
        XCTAssertEqual(g.levels.count, 3, "top of normal, top of conservation and bottom of normal are three named operator levels")
        XCTAssertEqual(LakeLevelClassifier.levelState(current: 1112, guide: g), .inZone)
        XCTAssertEqual(LakeLevelClassifier.levelState(current: 1125, guide: g), .floodPool)
        XCTAssertEqual(LakeLevelClassifier.floodPoolState(current: 1112, guide: g), .normal)
        // an inverted zone is not a zone
        let bad = OperatorLevels(zoneTop: staticLevel("Top", 10), zoneBottom: staticLevel("Bottom", 20))
        let badG = await feeds.guide(.operatorLevels(bad), day: "2026-10-13", timeZone: utc)
        XCTAssertNil(try XCTUnwrap(badG).zone)
        // a zone needs both edges: the generated mapping drops a lone edge
        var half = OperatorLevels(zoneTop: staticLevel("Top", 10)); half.floodPoolBottom = staticLevel("Top of Conservation", 10)
        XCTAssertFalse(half.hasZone)
        // nothing resolvable = no guide
        let none = OperatorLevels(zoneTop: OperatorLevelRef(kind: .staticFt, name: "x", ft: nil, source: "s", seasonal: false))
        let ng = await feeds.guide(.operatorLevels(none), day: "2026-10-13", timeZone: utc)
        XCTAssertNil(ng)
    }

    func testHistoryLiveMismatchFlag() {
        let now = iso("2026-10-13T12:00:00Z")
        func days(_ ft: Double, _ n: Int) -> [DailyLevel] {
            (1...n).map { DailyLevel(date: LakeLevelCalendar.dayString(now.addingTimeInterval(-Double($0) * 86_400), timeZone: utc), ft: ft, sourceId: "t") }
        }
        XCTAssertNil(LakeBrainRunner.historyLiveMismatch(history: days(100, 200), current: 100.4, now: now, timeZone: utc))
        XCTAssertNil(LakeBrainRunner.historyLiveMismatch(history: days(100, 200), current: 114, now: now, timeZone: utc), "within 15 ft")
        XCTAssertEqual(LakeBrainRunner.historyLiveMismatch(history: days(100, 200), current: 130, now: now, timeZone: utc) ?? 0, -30, accuracy: 0.001)
        XCTAssertNil(LakeBrainRunner.historyLiveMismatch(history: days(100, 10), current: 500, now: now, timeZone: utc), "too little recent history to judge")
    }

    func testProfileCarriesGeometryPointerForEveryLake() throws {
        let lake = try XCTUnwrap(LakeDirectory.all.first)
        let p = LakeBrainProfiles.build(lake: lake, binding: nil, state: nil, baseline: nil, previous: nil, presence: nil, live: [],
                                        now: iso("2026-10-13T12:00:00Z"), archiveURI: nil)
        XCTAssertEqual(p.identity.geometry?.lakeKey, BrainPlatform.lakeKey(lake.id))
        XCTAssertNil(p.operatingPools)
        // a pointer only: nothing but the URL and the key
        let json = String(decoding: try BrainJSON.encode(p.identity), as: UTF8.self)
        XCTAssertTrue(json.contains("registryRef"))
        XCTAssertFalse(json.contains("coordinates"))
    }
}

/// Feeds that count every call (a candidate must trigger none).
final class CountingFeeds: LakeLevelFeeds, @unchecked Sendable {
    let now = ISO8601DateFormatter().date(from: "2026-06-01T12:30:00Z")!
    private let lock = NSLock()
    private var n = 0
    var calls: Int { lock.withLock { n } }
    private func bump() { lock.withLock { n += 1 } }
    func recent(_ ref: LevelSeriesRef, hours: Int, now: Date) async -> FeedResult { bump(); return .failed("counting feeds") }
    func guide(_ source: LakeGuideSource, day: String, timeZone: TimeZone) async -> LakeGuideForDay? { bump(); return nil }
    func daily(_ source: LakeHistorySource, since: String?, now: Date, timeZone: TimeZone) async -> [DailyLevel]? { bump(); return [] }
    func archivedHourly(_ source: LakeHistorySource, days: Int, now: Date, timeZone: TimeZone) async -> [LevelObservation] { bump(); return [] }
}
