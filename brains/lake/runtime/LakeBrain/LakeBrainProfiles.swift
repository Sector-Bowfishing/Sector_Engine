//
//  LakeBrainProfiles.swift
//  Sector — Lake Brain: directory + binding → LakeProfile (`/lakes/{k}/brain`)
//
//  REFERENCES the directory, never copies it: name, state, coordinates,
//  operator, full pool, pool basis/confidence stay in GET /lakes. A profile
//  value is written only when a reviewed source states it; everything else is
//  absent (unknown), never inferred.
//

import Foundation
import SectorEngine

public enum LakeBrainProfiles {

    struct HashBasis: Codable {
        var identity: LakeBrainProfileRecord.Identity
        var hydrology: LakeBrainProfileRecord.Hydrology?
        var characteristics: LakeBrainProfileRecord.Characteristics?
        var operatingPools: LakeBrainProfileRecord.OperatingPools?
        var sourceCapability: LakeBrainProfileRecord.SourceCapability
        var baselineStatus: String?
        var historicalTier: String?
        var basisYears: Int?
        var presenceVersion: String?
        var readiness: [String: String]
    }

    static func trusted(_ ref: LevelSeriesRef, live: [(ref: LevelSeriesRef, readings: [LevelObservation], error: String?)],
                        now: Date) -> LakeBrainProfileRecord.TrustedSource {
        let hit = live.first { $0.ref == ref }
        let last = hit?.readings.last
        let status: String
        if hit == nil { status = "UNKNOWN" }
        else if last == nil { status = "FAILED" }
        else if LakeLevelClassifier.isStale(last!.at, ref: ref, now: now) { status = "WARNING" }
        else { status = "HEALTHY" }
        let authority: String
        switch ref.capability {
        case .directOperatorPool: authority = "operator"
        case .directLakeGauge: authority = "agency-gauge"
        case .nearbyGaugeProxy: authority = "proxy"
        default: authority = "none"
        }
        return .init(sourceId: ref.sourceId, provider: ref.providerName, sourceType: ref.capability.rawValue,
                     station: ref.series.map { "\(ref.station) \($0)" } ?? ref.station, status: status,
                     lastObservationAt: last.map { BrainPlatform.iso($0.at) }, authority: authority, brains: [LakeBrainSpec.brainId])
    }

    static func build(lake: DirectoryLake, binding: LakeSourceBinding?, state: LakeLevelStateRecord?,
                             baseline: LakeLevelBaseline?, previous: LakeBrainProfileRecord?, presence: LakePresenceIndex?,
                             live: [(ref: LevelSeriesRef, readings: [LevelObservation], error: String?)], now: Date,
                             archiveURI: String?, dryRunCandidate: Bool = false) -> LakeBrainProfileRecord {
        let gen = BrainPlatform.iso(now)
        let reviewed = binding?.status == .reviewed ? binding : nil

        // A pointer to the shoreline registry (another service owns the polygons); never the polygon itself.
        let identity = LakeBrainProfileRecord.Identity(
            riverSystem: reviewed?.riverSystem, basin: nil, lakeType: nil,
            geometry: LakeGeometryRef(registryRef: LakeGeometryRef.registryURL, lakeKey: BrainPlatform.lakeKey(lake.id)))
        var hydrology: LakeBrainProfileRecord.Hydrology?
        var characteristics: LakeBrainProfileRecord.Characteristics?
        var pools: LakeBrainProfileRecord.OperatingPools?
        var capability: LakeBrainProfileRecord.SourceCapability

        if let b = reviewed {
            let op = b.live.first.map { "\($0.providerName) \($0.station)" } ?? "reviewed binding"
            if let dam = b.damName { hydrology = .init(dam: KnownValue(dam, source: op, quality: "operator"), operation: nil) }
            characteristics = .init(
                floodControl: b.floodControl.map { KnownValue($0, source: b.factsSource ?? "cwms levels (Bottom of Flood Control)", quality: b.factsSource == nil ? "operator" : "NID purposes") },
                hydropower: b.hydropower.map { KnownValue($0, source: b.factsSource ?? "tva:locations DamType", quality: b.factsSource == nil ? "operator" : "NID purposes") },
                navigation: nil, runOfRiver: nil,
                controlled: b.capability == .directOperatorPool ? KnownValue(true, source: op, quality: "operator pool published") : nil,
                naturalLake: nil, context: b.context)
            let guideRef: LakeBrainProfileRecord.GuideCurveRef
            switch b.guide {
            case .tvaOperatingGuide(let loc)?:
                guideRef = .init(available: true, source: "TVA operating guide", ref: "https://www.tva.com/RestApi/operating-guide/\(loc)")
            case .cwms(let office, let g, _, _, _)?:
                guideRef = .init(available: true, source: "USACE CWMS guide curve", ref: "cwms:\(office):\(g)")
            case .operatorLevels(let o)?:
                if let g = o.guide { guideRef = .init(available: true, source: "Operator guide curve (\(g.name))", ref: g.source) }
                else { guideRef = .init(available: false, source: nil, ref: nil) }
            case nil:
                guideRef = .init(available: false, source: nil, ref: nil)
            }
            let zoneSource: String? = {
                switch b.guide {
                case .tvaOperatingGuide?: return "TVA BtmOpZone–TopOpZone (daily)"
                case .cwms(_, _, _, let label, _)?: return "CWMS \(label) to top of conservation (daily)"
                case .operatorLevels(let o)?:
                    guard o.hasZone, let t = o.zoneTop, let bt = o.zoneBottom else { return nil }
                    return "Operator \(bt.name) to \(t.name) (\(t.seasonal || bt.seasonal ? "daily" : "constant"))"
                case nil: return nil
                }
            }()
            pools = .init(normalFullPoolRef: "engine-directory:fullPoolFt (GET /lakes)",
                          topOfGatesFt: b.topOfGatesFt.map { KnownValue($0, source: "tva:locations TopOfGatesFt", quality: "operator") },
                          guideCurve: guideRef, operatingZoneSource: zoneSource,
                          datum: b.datum.map { KnownValue($0, source: op, quality: "operator") })
            if case .operatorLevels(let o)? = b.guide {
                if let f = o.floodPoolBottom {
                    pools?.floodPoolBottom = FloodPoolBottomRef(available: true, name: f.name, source: f.source, seasonal: f.seasonal, valueFt: f.ft)
                }
                pools?.planEvidence = PlanEvidenceRef(matchedProject: o.matchedProject, matchBasis: o.matchBasis, verifiedMatch: o.verifiedMatch,
                                                      criteria: "binding-review-v1 operator plan / flood-pool join, strict columns")
            }
            let refs = b.live.map { LakeBrainProfileRecord.SourceRef(sourceId: $0.sourceId, provider: $0.providerName, capability: $0.capability,
                                                                     cadenceMin: $0.cadenceMin, lagMin: $0.lagMin, note: $0.note) }
            let hist: [String] = b.history.map(\.profileDescription)
            capability = .init(level: b.capability, bindingStatus: dryRunCandidate ? .candidate : .reviewed, bindingVersion: LakeSourceBindings.version,
                               primary: refs.first, fallbacks: refs.count > 1 ? Array(refs.dropFirst()) : nil, history: hist,
                               proxyOnly: b.live.allSatisfy { $0.capability == .nearbyGaugeProxy }, reviewedAt: b.reviewedAt,
                               note: dryRunCandidate ? "dryRunCandidate: CANDIDATE binding evaluated as if reviewed (local dry run, never published). " + (b.note ?? "") : b.note)
        } else {
            capability = .init(level: LakeSourceBindings.candidateCapability(for: lake), bindingStatus: .candidate,
                               bindingVersion: LakeSourceBindings.version, primary: nil, fallbacks: nil, history: nil,
                               proxyOnly: false, reviewedAt: nil,
                               note: "Candidate class from directory hints (operator, cwmsOffice, apiLevel). Not probed; no state is published.")
        }

        var coverage: LakeBrainProfileRecord.HistoricalCoverage?
        if let b = baseline {
            coverage = .init(historyStart: b.historyStart, historyEnd: b.historyEnd, observationCount: b.observationCount,
                             coveragePct: b.coveragePct, yearsCovered: b.basisYears.count, baselineStatus: b.status,
                             historicalTier: b.historicalTier, baselineMethod: b.method, baselineVersion: b.baselineVersion,
                             historyRef: archiveURI.map { "\($0)/\(LakeDailyHistory.path(lake.id))" })
        } else {
            coverage = previous?.historicalCoverage
        }

        let readiness = state?.provenance.readiness ?? (reviewed == nil ? LakeBrainReadiness.discovered.rawValue
                                                        : reviewed!.capability == .noSource ? LakeBrainReadiness.profiled.rawValue
                                                        : LakeBrainReadiness.degraded.rawValue)

        var issues: [LakeBrainProfileRecord.Issue] = []
        func issue(_ id: String, _ severity: String, _ kind: String, _ title: String) {
            issues.append(.init(id: id, severity: severity, kind: kind, title: title, lakeId: lake.id,
                                brainId: LakeBrainSpec.brainId, since: state?.freshness.generatedAt ?? gen))
        }
        for f in state?.provenance.qualityFlags ?? [] {
            if f.hasPrefix("primarySourceStale:") {
                issue("primary-source-stale", "warning", "source-stale", "Primary level source is stale; the reviewed fallback is in use (\(f.dropFirst("primarySourceStale:".count)))")
            } else if f.hasPrefix("sourceStale:") {
                issue("source-stale", "warning", "source-stale", "Level source stale: \(f.dropFirst("sourceStale:".count)); last known value kept")
            } else if f.hasPrefix("sourceError:") {
                issue("source-error-\(BrainPlatform.lakeKey(String(f.dropFirst("sourceError:".count))))", "info", "source-error", "Fetch failed: \(f.dropFirst("sourceError:".count))")
            } else if f.hasPrefix("fallbackDatumDisagreement") {
                issue("fallback-datum", "warning", "datum", "Fallback gauge disagrees with the operator pool (\(f))")
            }
        }
        if state?.kind == .unavailable, reviewed != nil { issue("no-reading", "warning", "source-unavailable", "No reading from any reviewed source") }

        var sources: [String: LakeBrainProfileRecord.TrustedSource]?
        if let b = reviewed {
            var m: [String: LakeBrainProfileRecord.TrustedSource] = [:]
            for ref in b.live { m[BrainPlatform.lakeKey(ref.sourceId)] = trusted(ref, live: live, now: now) }
            // On a SKIP run nothing was fetched: keep what the last full run observed.
            if live.isEmpty, let prev = previous?.trustedSources { m = prev }
            sources = m
        }

        let summary = presence?.summary(lake.id)
        let basis = HashBasis(identity: identity, hydrology: hydrology, characteristics: characteristics, operatingPools: pools,
                              sourceCapability: capability, baselineStatus: coverage?.baselineStatus.rawValue,
                              historicalTier: coverage?.historicalTier?.rawValue, basisYears: coverage?.yearsCovered, presenceVersion: summary?.researchVersion,
                              readiness: [LakeBrainSpec.slot: readiness])
        let hash = LakeBaselineBuilder.fingerprint(String(decoding: (try? BrainJSON.encode(basis)) ?? Data(), as: UTF8.self))
        let version = previous.map { $0.profileHash == hash ? $0.profileVersion : $0.profileVersion + 1 } ?? 1

        return LakeBrainProfileRecord(
            lakeId: lake.id, schemaVersion: LakeBrainSpec.profileSchemaVersion, profileVersion: version, profileHash: hash,
            updatedAt: (previous?.profileHash == hash ? previous?.updatedAt : nil) ?? gen,
            identity: identity, hydrology: hydrology, characteristics: characteristics, operatingPools: pools,
            sourceCapability: capability, historicalCoverage: coverage, speciesPresenceSummary: summary,
            trustedSources: sources, readiness: [LakeBrainSpec.slot: readiness], activeIssues: issues.isEmpty ? nil : issues)
    }
}
