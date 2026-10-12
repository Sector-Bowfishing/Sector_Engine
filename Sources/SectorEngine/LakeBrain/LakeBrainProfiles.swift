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

public enum LakeBrainProfiles {

    struct HashBasis: Codable {
        var identity: LakeBrainProfileRecord.Identity
        var hydrology: LakeBrainProfileRecord.Hydrology?
        var characteristics: LakeBrainProfileRecord.Characteristics?
        var operatingPools: LakeBrainProfileRecord.OperatingPools?
        var sourceCapability: LakeBrainProfileRecord.SourceCapability
        var baselineStatus: String?
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
                             archiveURI: String?) -> LakeBrainProfileRecord {
        let gen = BrainPlatform.iso(now)
        let reviewed = binding?.status == .reviewed ? binding : nil

        let identity = LakeBrainProfileRecord.Identity(riverSystem: reviewed?.riverSystem, basin: nil, lakeType: nil)
        var hydrology: LakeBrainProfileRecord.Hydrology?
        var characteristics: LakeBrainProfileRecord.Characteristics?
        var pools: LakeBrainProfileRecord.OperatingPools?
        var capability: LakeBrainProfileRecord.SourceCapability

        if let b = reviewed {
            let op = b.live.first.map { "\($0.providerName) \($0.station)" } ?? "reviewed binding"
            if let dam = b.damName { hydrology = .init(dam: KnownValue(dam, source: op, quality: "operator"), operation: nil) }
            characteristics = .init(
                floodControl: b.floodControl.map { KnownValue($0, source: "cwms levels (Bottom of Flood Control)", quality: "operator") },
                hydropower: b.hydropower.map { KnownValue($0, source: "tva:locations DamType", quality: "operator") },
                navigation: nil, runOfRiver: nil,
                controlled: b.capability == .directOperatorPool ? KnownValue(true, source: op, quality: "operator pool published") : nil,
                naturalLake: nil)
            let guideRef: LakeBrainProfileRecord.GuideCurveRef
            switch b.guide {
            case .tvaOperatingGuide(let loc)?:
                guideRef = .init(available: true, source: "TVA operating guide", ref: "https://www.tva.com/RestApi/operating-guide/\(loc)")
            case .cwms(let office, let g, _, _, _)?:
                guideRef = .init(available: true, source: "USACE CWMS guide curve", ref: "cwms:\(office):\(g)")
            case nil:
                guideRef = .init(available: false, source: nil, ref: nil)
            }
            let zoneSource: String? = {
                switch b.guide {
                case .tvaOperatingGuide?: return "TVA BtmOpZone–TopOpZone (daily)"
                case .cwms(_, _, _, let label, _)?: return "CWMS \(label) to top of conservation (daily)"
                case nil: return nil
                }
            }()
            pools = .init(normalFullPoolRef: "engine-directory:fullPoolFt (GET /lakes)",
                          topOfGatesFt: b.topOfGatesFt.map { KnownValue($0, source: "tva:locations TopOfGatesFt", quality: "operator") },
                          guideCurve: guideRef, operatingZoneSource: zoneSource,
                          datum: b.datum.map { KnownValue($0, source: op, quality: "operator") })
            let refs = b.live.map { LakeBrainProfileRecord.SourceRef(sourceId: $0.sourceId, provider: $0.providerName, capability: $0.capability,
                                                                     cadenceMin: $0.cadenceMin, lagMin: $0.lagMin, note: $0.note) }
            let hist: [String] = b.history.map {
                switch $0 {
                case .tvaOperatingGuide(let l): return "tva:operating-guide:\(l) (current + previous year, daily midnight)"
                case .sharedTVAArchive(let bucket, let prefix, let l): return "gs://\(bucket)/\(prefix)/\(l) (hourly, shared archive, read-only)"
                case .cwmsDaily(let o, let s): return "cwms:\(o):\(s) (daily)"
                }
            }
            capability = .init(level: b.capability, bindingStatus: .reviewed, bindingVersion: LakeSourceBindings.version,
                               primary: refs.first, fallbacks: refs.count > 1 ? Array(refs.dropFirst()) : nil, history: hist,
                               proxyOnly: b.live.allSatisfy { $0.capability == .nearbyGaugeProxy }, reviewedAt: b.reviewedAt, note: b.note)
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
                             baselineMethod: b.method, baselineVersion: b.baselineVersion,
                             historyRef: archiveURI.map { "\($0)/\(LakeDailyHistory.path(lake.id))" })
        } else {
            coverage = previous?.historicalCoverage
        }

        let readiness = state?.provenance.readiness ?? (reviewed == nil ? LakeBrainReadiness.discovered.rawValue
                                                        : reviewed!.capability == .noSource ? LakeBrainReadiness.profiled.rawValue
                                                        : LakeBrainReadiness.degraded.rawValue)

        var issues: [LakeBrainProfileRecord.Issue] = []
        for f in state?.provenance.qualityFlags ?? [] {
            if f.hasPrefix("primarySourceStale:") {
                issues.append(.init(id: "primary-source-stale", severity: "WARN", title: "Primary level source is stale; the reviewed fallback is in use (\(f.dropFirst("primarySourceStale:".count)))", since: nil))
            } else if f.hasPrefix("sourceStale:") {
                issues.append(.init(id: "source-stale", severity: "WARN", title: "Level source stale: \(f.dropFirst("sourceStale:".count)); last known value kept", since: nil))
            } else if f.hasPrefix("sourceError:") {
                issues.append(.init(id: "source-error-\(BrainPlatform.lakeKey(String(f.dropFirst("sourceError:".count))))", severity: "INFO", title: "Fetch failed: \(f.dropFirst("sourceError:".count))", since: nil))
            } else if f.hasPrefix("fallbackDatumDisagreement") {
                issues.append(.init(id: "fallback-datum", severity: "WARN", title: "Fallback gauge disagrees with the operator pool (\(f))", since: nil))
            }
        }
        if state?.kind == .unavailable { issues.append(.init(id: "no-reading", severity: "WARN", title: "No reading from any reviewed source", since: nil)) }

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
                              basisYears: coverage?.yearsCovered, presenceVersion: summary?.researchVersion,
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
