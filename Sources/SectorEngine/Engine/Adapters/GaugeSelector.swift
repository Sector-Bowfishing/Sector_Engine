//
//  GaugeSelector.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  "Which of these USGS series may drive this input at this point?" The
//  snapshot fetches every series and method block in the input's box; this
//  picks at most one, and says why about every candidate.
//
//  WHY NOT THE NEAREST: the nearest series is often the wrong water. Lake Lanier
//  took 52 °F release water and a +4,184 cfs generation pulse from the gauge AT
//  Buford Dam; Lake Catherine took 153 °F from Quapaw Spring; a pond in Suwanee
//  borrowed the Buford reach's cold flow from six miles off; Calico Rock took
//  North Fork water from 10.6 mi instead of its own gauge. A series now drives
//  an input only when three things hold (gauge_final.json, rule step C):
//    1. its ROLE (GaugeClassifier) is allowed for
//    2. the point's WATER CONTEXT (WaterContext: lake / belowDam / open), and
//    3. it passes freshness, plausibility and distance checks — applied BEFORE
//       ranking, so a stale or implausible nearest gauge can't hide a good one.
//  Nothing accepted → nil, and the builder's existing fallbacks run (modeled
//  temp, pool label or dormant level, no discharge, rain-decay clarity). The box
//  is never widened after a rejection.
//
//  Pure and synchronous: no I/O, evaluated once per input after the snapshot's
//  fetches. `legacyNearest` is the pre-selection pick, kept for the
//  ConditionsConfig.gaugeSelection.enabled kill switch.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

/// One candidate series' verdict, for diagnostics (gaugeDecisions in the API).
/// `accepted` means the series passed rule step C; the pick is the first accepted
/// decision. A second accepted series at the picked site (a 00065 beside its
/// 62614) stays accepted, with a reason saying which series the site used.
struct GaugeDecision: Equatable, Sendable {
    let kind: GaugeKind
    let siteCode: String
    let siteName: String
    let parameterCode: String
    let blockIndex: Int
    /// The block's method text ("HEADWATER", "Tailwater"), for the DTO's `method`.
    let methodDescription: String?
    let role: GaugeRole
    let distanceMiles: Double?
    let value: Double
    let accepted: Bool
    let reason: String
}

/// Everything besides the candidates that a verdict depends on.
struct GaugeInputs: Sendable {
    let context: WaterContext
    /// Freshness is measured against this, not the wall clock, so tests and the
    /// forecast see the same verdicts.
    let now: Date
    /// The builder's modeled water temp (°F): the yardstick for the warm-gap and
    /// cold-release checks. nil when the model couldn't run.
    let modeledWaterTempF: Double?
    /// P, the context lake's pool elevation (ft): live generation pool when that
    /// generation is this lake, else the roster's normal pool, else NWPS full pool.
    let poolFt: Double?
    /// The level box (NWPS pool reading included). Pool-site identity is read
    /// from it for every input: a lake's thermometer is trusted because its site
    /// publishes this lake's pool elevation.
    let levelCandidates: [WaterLevelReading]

    init(context: WaterContext, now: Date, modeledWaterTempF: Double? = nil, poolFt: Double? = nil,
         levelCandidates: [WaterLevelReading] = []) {
        self.context = context
        self.now = now
        self.modeledWaterTempF = modeledWaterTempF
        self.poolFt = poolFt
        self.levelCandidates = levelCandidates
    }
}

enum GaugeSelector: Sendable {

    // MARK: Tunables (each justified in gauge_final.json "thresholds")

    /// Level and discharge cap — the service-wide "not your water" distance.
    static let serviceMaxMiles: Double = WaterLevelService.maxUsefulMiles
    /// Temp cap for a thermometer at a site name-matched to the context lake. Very
    /// large natural lakes (Red Lake MN) keep their named thermometer beyond 15 mi;
    /// river gauges keep the builder's 15 mi.
    static let matchedPoolTempMaxMiles: Double = 25
    /// An unnamed pool gauge this close is the lake the point is on.
    static let unnamedPoolMiles: Double = 3
    /// An elevation-code series this close to P identifies the lake's pool site.
    /// 5 ft matched Lake Monona 844.79 to Mendota (P 849.76) and Lake Marion to
    /// Moultrie; 3 ft still rescues Eufaula's Coast Guard dock (188.73 vs 188.6)
    /// and absorbs datum offsets (Lake Murray 00062 vs 62615 = 1.3 ft).
    static let poolMatchFt: Double = 3
    /// A name-matched 62614/62615 this far from P is a different datum or a wrong
    /// P. Never applied to 00065/00062, which can be local datum (Taylorsville's
    /// "[Lake]" 00065 reads 47.24 on a ~547 ft pool).
    static let poolVetoFt: Double = 10
    /// The pool-value match must not accept a gauge named for another directory
    /// lake this close to it.
    static let otherLakeMiles: Double = 25
    /// Temp, turbidity and stage on a dam's reach must be measured near the point:
    /// Forsyth sits 25 mi down Table Rock's reach, where it enters Bull Shoals
    /// Lake, and must not take 07053450's 55 °F from 13 mi. Flow is conserved
    /// along the reach, so discharge is exempt.
    static let belowDamLocalGaugeMiles: Double = 8
    /// NLDI's site lists are incomplete (Keystone omits 07164480, Holter omits
    /// 06066500); a river-class gauge this close to the flowline is on the reach.
    static let gaugeOnReachMiles: Double = 0.30
    /// Below a dam, an off-reach river-class gauge this close is still accepted.
    static let unmatchedBelowDamMiles: Double = 5
    /// Ranking bonus for on-reach or matched-pool evidence. Only a mile: priority
    /// over distance picked North Fork (10.6 mi) over Calico Rock's own gauge.
    static let matchBonusMiles: Double = 1
    /// A tributary gauge describes the point only when it is this close.
    static let tributaryMiles: Double = 1.5
    /// A tributary ranks after any accepted river-class or pool gauge this close:
    /// Yellow River (3.0 mi) over "WATSON CREEK TRIB 2" (0.57 mi).
    static let riverPreferenceMiles: Double = 5
    /// Open water: a dam-release gauge farther than this is another dam's river.
    static let openReleaseMiles: Double = 5
    /// Open water: stage beyond 10 mi and flow beyond 15 mi are a different reach.
    static let openLevelMiles: Double = 10
    static let openDischargeMiles: Double = 15
    /// Open water: a gauge on a roster reach farther than this describes that
    /// dam's river, not the point (Suwanee pond vs McGinnis Ferry at 6.2 mi).
    static let openReachGaugeMiles: Double = 1.5
    /// Open water: a release-influenced thermometer this far below the model is
    /// cold release water (39 of 40 gauges at −8 °F or colder were tailwater,
    /// spring or well).
    static let coldReleaseGapF: Double = 8
    /// A thermometer this far above the model is broken or a hot spring; honest
    /// warm gaps topped out at +14 °F.
    static let warmRejectGapF: Double = 25
    /// Surface water a bowfisher stands over. 95 °F would clip cooling reservoirs.
    static let plausibleTempF: ClosedRange<Double> = 32...100
    /// A 60 km reach can't end farther than ~37 mi from its dam, so a gauge's
    /// release-influence check only looks at dams this close.
    static let reachDamSearchMiles: Double = 40
    /// WaterLevelService stamps NWPS pool readings with this method text.
    static let nwpsMethodDescription = "NWPS pool"
    /// Elevation codes a level pick prefers over 00065 gage height.
    static let elevationCodes: Set<String> = ["62614", "62615", "00062"]

    // MARK: Selection

    /// Rule step C for one input. Returns the pick (with `acceptance` stamped) and
    /// one decision per candidate: accepted first, in rank order, then rejected by
    /// distance.
    static func select(_ candidates: [WaterLevelReading], kind: GaugeKind, inputs: GaugeInputs,
                       roster: [RosterDam] = DamRoster.all,
                       directory: [DirectoryLake] = LakeDirectory.all) -> (pick: WaterLevelReading?, decisions: [GaugeDecision]) {
        var run = Run(kind: kind, inputs: inputs, roster: roster, directory: directory, candidates: candidates)

        var accepted: [(candidate: Candidate, verdict: Verdict)] = []
        var rejected: [(candidate: Candidate, verdict: Verdict)] = []
        for candidate in run.candidates {
            let verdict = run.judge(candidate)
            if verdict.acceptance != nil {
                accepted.append((candidate, verdict))
            } else {
                rejected.append((candidate, verdict))
            }
        }

        // One reading per site. Every method block is a candidate, so a site can
        // offer primary/secondary sensors, left/right banks, or a 62614 beside a
        // local-datum 00065.
        var bestBySite: [String: Int] = [:]
        for (i, entry) in accepted.enumerated() {
            let site = entry.candidate.reading.siteCode
            if let j = bestBySite[site] {
                if sitePreference(entry.candidate.reading, kind: kind) < sitePreference(accepted[j].candidate.reading, kind: kind) {
                    bestBySite[site] = i
                }
            } else {
                bestBySite[site] = i
            }
        }
        let winners = Set(bestBySite.values)
        var used = accepted.enumerated().filter { winners.contains($0.offset) }.map(\.element)
        let shadowed = accepted.enumerated().filter { !winners.contains($0.offset) }.map(\.element)

        let riverClassNear = used.contains {
            $0.candidate.role != .tributary && $0.candidate.miles <= riverPreferenceMiles
        }
        func rankKey(_ entry: (candidate: Candidate, verdict: Verdict)) -> (Int, Double, String, Int) {
            let c = entry.candidate
            let bonus = entry.verdict.acceptance == .nearby ? 0 : matchBonusMiles
            let demoted = c.role == .tributary && riverClassNear ? 1 : 0
            return (demoted, c.miles - bonus, c.reading.siteCode, c.reading.blockIndex)
        }
        used.sort { rankKey($0) < rankKey($1) }

        var pick = used.first?.candidate.reading
        pick?.acceptance = used.first?.verdict.acceptance

        var decisions = used.map { decision($0.candidate, $0.verdict, kind: kind, accepted: true) }
        decisions += shadowed.sorted { rankKey($0) < rankKey($1) }.map { entry in
            let siteWinner = accepted[bestBySite[entry.candidate.reading.siteCode] ?? 0].candidate.reading
            return decision(entry.candidate, entry.verdict, kind: kind, accepted: true,
                            note: "; not used: this site's \(siteWinner.parameterCode) block \(siteWinner.blockIndex) is preferred")
        }
        decisions += rejected
            .sorted { ($0.candidate.miles, $0.candidate.reading.siteCode) < ($1.candidate.miles, $1.candidate.reading.siteCode) }
            .map { decision($0.candidate, $0.verdict, kind: kind, accepted: false) }
        return (pick, decisions)
    }

    /// The pre-selection pick, for the kill switch: today's nearest first-block
    /// reading within the input's search distance. For level, an NWPS pool reading
    /// the caller included wins outright, as `latestReading` always checked NWPS
    /// before USGS.
    static func legacyNearest(_ candidates: [WaterLevelReading], kind: GaugeKind) -> WaterLevelReading? {
        if kind == .level, let pool = candidates.first(where: isNWPS) { return pool }
        return WaterLevelService.legacyNearest(candidates, maxMiles: kind.searchMiles)
    }

    // MARK: - Internals

    private struct Candidate {
        let reading: WaterLevelReading
        let classification: GaugeClassification
        var role: GaugeRole { classification.role }
        /// Only NWPS pool readings lack a distance; their reservoir-box match IS
        /// their location evidence, so they count as at the point.
        var miles: Double { reading.distanceMiles ?? 0 }
        var isNWPS: Bool { GaugeSelector.isNWPS(reading) }
    }

    /// `acceptance` nil means rejected.
    private struct Verdict {
        let acceptance: GaugeAcceptance?
        let reason: String
        static func accept(_ acceptance: GaugeAcceptance, _ reason: String) -> Verdict { Verdict(acceptance: acceptance, reason: reason) }
        static func reject(_ reason: String) -> Verdict { Verdict(acceptance: nil, reason: reason) }
    }

    /// How a site proved it is the context lake's pool. Order is strength: name
    /// evidence also earns the wider temp cap.
    private enum PoolEvidence: Comparable {
        case name
        case poolValue(value: Double, pool: Double)
        case unnamed

        var text: String {
            switch self {
            case .name: return "name match"
            case .poolValue(let v, let p): return "pool value \(fmt(v)) ft within \(fmt(poolMatchFt, 0)) ft of \(fmt(p)) ft"
            case .unnamed: return "unnamed pool within \(fmt(unnamedPoolMiles, 0)) mi"
            }
        }
    }

    /// Per-call state: classifications, pool identity and the release-influence memo.
    private struct Run {
        let kind: GaugeKind
        let inputs: GaugeInputs
        let roster: [RosterDam]
        let directory: [DirectoryLake]
        let candidates: [Candidate]
        /// Lake context: sites identified as its pool, and name-matched elevation
        /// series vetoed for sitting too far from P (by reading id).
        private var poolSites: [String: PoolEvidence] = [:]
        private var vetoed: Set<String> = []
        private let contextAliases: [[String]]
        private let ownLakeAliases: [[String]]
        /// Every role seen at each site in this call, for the site-level
        /// release-influence test.
        private let rolesBySite: [String: Set<GaugeRole>]
        /// releaseInfluenced, memoized per siteCode: the roster dam whose reach
        /// the site lies on, or nil.
        private var releaseMemo: [String: RosterDam?] = [:]

        init(kind: GaugeKind, inputs: GaugeInputs, roster: [RosterDam], directory: [DirectoryLake],
             candidates: [WaterLevelReading]) {
            self.kind = kind
            self.inputs = inputs
            self.roster = roster
            self.directory = directory
            self.candidates = candidates.map(GaugeSelector.classify)
            switch inputs.context {
            case .lake(let ref):
                contextAliases = GaugeClassifier.lakeAliases(ref.name)
                ownLakeAliases = []
            case .belowDam(_, _, let ownLake):
                contextAliases = []
                ownLakeAliases = ownLake.map { GaugeClassifier.lakeAliases($0.name) } ?? []
            case .open:
                contextAliases = []
                ownLakeAliases = []
            }
            var roles: [String: Set<GaugeRole>] = [:]
            for c in self.candidates { roles[c.reading.siteCode, default: []].insert(c.role) }
            rolesBySite = roles
            if case .lake = inputs.context { identifyPoolSites() }
        }

        // MARK: Pool-site identity (lake context)

        /// A site is this lake's pool when any of its series: is pool-role and
        /// name-matches the lake; is an elevation code within `poolMatchFt` of P
        /// and isn't named for another directory lake nearby; or is an unnamed
        /// pool within `unnamedPoolMiles`. Value evidence comes from the level box
        /// only (elevation codes live there); name evidence also from this input's
        /// own series, so a lake thermometer at a site without a level series
        /// still counts.
        private mutating func identifyPoolSites() {
            var seen = Set<String>()
            let pool = inputs.poolFt
            let levelBox = inputs.levelCandidates.map(GaugeSelector.classify)
            for c in levelBox + candidates where !c.isNWPS {
                guard seen.insert(c.reading.id).inserted else { continue }
                guard ![.damRelease, .nonSurface, .tributary].contains(c.role) else { continue }
                let code = c.reading.parameterCode
                let nameOK = c.role == .pool && GaugeClassifier.keysMatch(c.classification.nameKey, contextAliases)
                if nameOK, let pool, ["62614", "62615"].contains(code), abs(c.reading.value - pool) > poolVetoFt {
                    vetoed.insert(c.reading.id)
                    continue
                }
                var evidence: PoolEvidence?
                if nameOK {
                    evidence = .name
                } else if let pool, elevationCodes.contains(code), abs(c.reading.value - pool) <= poolMatchFt,
                          otherDirectoryLake(named: c) == nil {
                    evidence = .poolValue(value: c.reading.value, pool: pool)
                } else if c.role == .pool, c.classification.nameKey.isEmpty, c.reading.distanceMiles != nil,
                          c.miles <= unnamedPoolMiles {
                    evidence = .unnamed
                }
                if let evidence {
                    let site = c.reading.siteCode
                    poolSites[site] = poolSites[site].map { Swift.min($0, evidence) } ?? evidence
                }
            }
        }

        /// A directory lake, other than the context lake, that the gauge is named
        /// for and lies within `otherLakeMiles` of. A gauge whose name matches the
        /// context lake is never "another" lake (a reservoir listed once per state).
        func otherDirectoryLake(named c: Candidate) -> DirectoryLake? {
            let key = c.classification.nameKey
            guard !key.isEmpty, case .lake(let ref) = inputs.context,
                  !GaugeClassifier.keysMatch(key, contextAliases) else { return nil }
            return directory
                .filter { $0.name != ref.name }
                .map { (lake: $0, miles: TailwaterRegistry.haversineMiles(lat1: c.reading.latitude, lon1: c.reading.longitude,
                                                                          lat2: $0.lat, lon2: $0.lon)) }
                .filter { $0.miles <= otherLakeMiles }
                .sorted { $0.miles < $1.miles }
                .first { GaugeClassifier.keysMatch(key, GaugeClassifier.lakeAliases($0.lake.name)) }?
                .lake
        }

        // MARK: Verdicts

        mutating func judge(_ c: Candidate) -> Verdict {
            if let reject = globalReject(c) { return .reject(reject) }
            switch inputs.context {
            case .lake(let ref): return judgeLake(c, ref)
            case .belowDam(let dam, _, let ownLake): return judgeBelowDam(c, dam, ownLake)
            case .open: return judgeOpen(c)
            }
        }

        /// Rejects that hold in every context. Freshness and plausibility run
        /// before ranking so a stale or broken nearest gauge can't hide a good one.
        private func globalReject(_ c: Candidate) -> String? {
            let r = c.reading
            if c.role == .nonSurface {
                return "nonSurface: site type \(r.siteTypeCode ?? "?") is not surface water"
            }
            let maxAge = kind == .level || kind == .discharge
                ? ConditionsInputBuilder.stageDischargeMaxAgeHours
                : ConditionsInputBuilder.tempTurbidityMaxAgeHours
            let ageHours = inputs.now.timeIntervalSince(r.dateTime) / 3600
            if ageHours > maxAge {
                return "stale: \(fmt(ageHours, 1)) h old (limit \(fmt(maxAge, 0)) h)"
            }
            if kind == .waterTemp {
                let f = fahrenheit(r.value)
                if !plausibleTempF.contains(f) {
                    return "implausible water temp \(fmt(f, 1))F (outside \(fmt(plausibleTempF.lowerBound, 0))-\(fmt(plausibleTempF.upperBound, 0))F)"
                }
                if let model = inputs.modeledWaterTempF, f > model + warmRejectGapF {
                    return "\(fmt(f, 1))F is more than the model's \(fmt(model, 1))F + \(fmt(warmRejectGapF, 0))F"
                }
            }
            if let miles = r.distanceMiles {
                let cap = cap(for: c)
                if miles > cap {
                    return "\(fmt(miles)) mi is beyond the \(fmt(cap, 0)) mi \(kind.rawValue) cap"
                }
            }
            return nil
        }

        private func cap(for c: Candidate) -> Double {
            switch kind {
            case .level, .discharge:
                return serviceMaxMiles
            case .turbidity:
                return ConditionsInputBuilder.maxTurbidityDistanceMiles
            case .waterTemp:
                if case .lake = inputs.context, poolSites[c.reading.siteCode] == .name {
                    return matchedPoolTempMaxMiles
                }
                return ConditionsInputBuilder.maxWaterTempDistanceMiles
            }
        }

        /// lake(L): no discharge; otherwise only series at a site identified as
        /// L's pool, and never its release blocks.
        private func judgeLake(_ c: Candidate, _ ref: LakeRef) -> Verdict {
            if kind == .discharge {
                return .reject("discharge on a lake is outflow, not \(ref.name)'s water")
            }
            if c.isNWPS {
                return .accept(.matchedPool, "NWPS pool reading for the reservoir box around \(ref.name)")
            }
            if c.role == .damRelease {
                return .reject("release water below a dam, not \(ref.name)'s pool")
            }
            if vetoed.contains(c.reading.id), let pool = inputs.poolFt {
                return .reject("\(c.reading.parameterCode) \(fmt(c.reading.value)) ft is more than "
                               + "\(fmt(poolVetoFt, 0)) ft from \(ref.name)'s pool \(fmt(pool)) ft")
            }
            if let evidence = poolSites[c.reading.siteCode], [.pool, .river, .unknownSurface].contains(c.role) {
                return .accept(.matchedPool, "site identified as \(ref.name)'s pool (\(evidence.text))")
            }
            if let other = otherDirectoryLake(named: c) {
                return .reject("names another directory lake (\(other.name)), not \(ref.name)")
            }
            return .reject("\(c.role.rawValue) gauge is not at \(ref.name)'s pool")
        }

        /// belowDam(D): the reach's own gauges (near the point, except discharge),
        /// a tributary at the point, or a river-class gauge close below the dam.
        /// A TAILWATER / LOWER POOL block is classified damRelease before it could
        /// be pool, so it arrives here through the on-reach test.
        private func judgeBelowDam(_ c: Candidate, _ dam: RosterDam, _ ownLake: DirectoryLake?) -> Verdict {
            if c.isNWPS {
                return .reject("NWPS reading is the pool above the dam, not the water below \(dam.name)")
            }
            if c.role == .pool {
                if let ownLake, GaugeClassifier.keysMatch(c.classification.nameKey, ownLakeAliases) {
                    return .accept(.matchedPool, "pool of \(ownLake.name), the lake the point is on")
                }
                return .reject("pool above the dam or another lake, not the water below \(dam.name)")
            }
            if let evidence = onReach(c, dam) {
                if kind != .discharge, c.miles > belowDamLocalGaugeMiles {
                    return .reject("on the \(dam.name) reach but \(fmt(c.miles)) mi away; \(kind.rawValue) "
                                   + "must be measured within \(fmt(belowDamLocalGaugeMiles, 0)) mi of the point")
                }
                return .accept(.onReach, "on the \(dam.name) reach (\(evidence))")
            }
            if c.role == .tributary {
                return c.miles <= tributaryMiles
                    ? .accept(.nearby, "tributary \(fmt(c.miles)) mi from the point")
                    : .reject("tributary \(fmt(c.miles)) mi away (limit \(fmt(tributaryMiles, 1)) mi), "
                              + "not the water below \(dam.name)")
            }
            if c.miles <= unmatchedBelowDamMiles {
                return .accept(.nearby, "\(c.role.rawValue) gauge off the \(dam.name) reach, "
                               + "\(fmt(c.miles)) mi away (limit \(fmt(unmatchedBelowDamMiles, 0)) mi)")
            }
            return .reject("different water: off the \(dam.name) reach and \(fmt(c.miles)) mi away "
                           + "(limit \(fmt(unmatchedBelowDamMiles, 0)) mi)")
        }

        /// open: rivers and unknown surface water by distance; release, tributary
        /// and pool gauges only close by; and a gauge on any roster reach is that
        /// dam's river, not this water, beyond `openReachGaugeMiles`.
        private mutating func judgeOpen(_ c: Candidate) -> Verdict {
            if c.isNWPS {
                return .accept(.nearby, "NWPS pool reading (the point is inside its reservoir box)")
            }
            let miles = c.miles
            switch c.role {
            case .damRelease where miles > openReleaseMiles:
                return .reject("release gauge \(fmt(miles)) mi away (limit \(fmt(openReleaseMiles, 0)) mi) "
                               + "from an open-water point")
            case .tributary where miles > tributaryMiles:
                return .reject("tributary \(fmt(miles)) mi away (limit \(fmt(tributaryMiles, 1)) mi), not this water")
            case .pool where kind == .discharge:
                return .reject("pool site: its flow is a dam's outflow, not this water")
            case .pool where miles > unnamedPoolMiles:
                return .reject("pool gauge \(fmt(miles)) mi away (limit \(fmt(unnamedPoolMiles, 0)) mi) is a different lake")
            default:
                break
            }
            if kind == .level, miles > openLevelMiles {
                return .reject("stage gauge \(fmt(miles)) mi away (limit \(fmt(openLevelMiles, 0)) mi) is a different reach")
            }
            if kind == .discharge, miles > openDischargeMiles {
                return .reject("flow gauge \(fmt(miles)) mi away (limit \(fmt(openDischargeMiles, 0)) mi) is a different reach")
            }
            if let dam = releaseInfluence(c) {
                if miles > openReachGaugeMiles {
                    return .reject("describes the \(dam.name) reach (\(fmt(miles)) mi away, limit "
                                   + "\(fmt(openReachGaugeMiles, 1)) mi); the point is off that reach")
                }
                if kind == .waterTemp {
                    guard let model = inputs.modeledWaterTempF else {
                        return .reject("release-influenced (\(dam.name) reach) and no modeled temp to rule out release water")
                    }
                    let f = fahrenheit(c.reading.value)
                    if f <= model - coldReleaseGapF {
                        return .reject("cold release water: \(fmt(f, 1))F is \(fmt(coldReleaseGapF, 0))F+ below the "
                                       + "model's \(fmt(model, 1))F on the \(dam.name) reach")
                    }
                }
            }
            return .accept(.nearby, "\(c.role.rawValue) gauge \(fmt(miles)) mi from an open-water point")
        }

        // MARK: Reach membership

        /// Evidence that a series measures `dam`'s release reach, or nil: the site
        /// is on NLDI's list; a damRelease name names the dam; or a river-class
        /// gauge lies within `gaugeOnReachMiles` of the flowline (tributaries never
        /// count by geometry — creek mouths sit next to the flowline).
        func onReach(_ c: Candidate, _ dam: RosterDam) -> String? {
            onReach(site: c.reading.siteCode, roles: [c.role], tokens: c.classification.nameTokens,
                    lat: c.reading.latitude, lon: c.reading.longitude, dam: dam)
        }

        private func onReach(site: String, roles: Set<GaugeRole>, tokens: Set<String>,
                             lat: Double, lon: Double, dam: RosterDam) -> String? {
            if dam.reachSiteCodes.contains(site) { return "site listed on the reach" }
            if roles.contains(.damRelease), GaugeSelector.names(dam, tokens) { return "names \(dam.name)" }
            guard !roles.isDisjoint(with: [.river, .damRelease, .unknownSurface, .openWater]) else { return nil }
            let damMiles = TailwaterRegistry.haversineMiles(lat1: dam.latitude, lon1: dam.longitude, lat2: lat, lon2: lon)
            guard let projection = WaterContext.distanceToReach(dam.reach, lat: lat, lon: lon,
                                                                allowBehind: damMiles <= WaterContext.damNoiseMiles),
                  projection.miles <= gaugeOnReachMiles else { return nil }
            return "\(fmt(projection.miles)) mi from the flowline"
        }

        /// releaseInfluenced: the roster dam whose reach the gauge's SITE lies on.
        /// Site-level (every role published there counts), so a lock's HEADWATER
        /// and TAILWATER blocks get one answer. Memoized per siteCode.
        private mutating func releaseInfluence(_ c: Candidate) -> RosterDam? {
            let site = c.reading.siteCode
            if let memo = releaseMemo[site] { return memo }
            let roles = rolesBySite[site] ?? [c.role]
            var hit = roster.first { $0.reachSiteCodes.contains(site) }
            if hit == nil {
                let point = CLLocationCoordinate2D(latitude: c.reading.latitude, longitude: c.reading.longitude)
                hit = DamRoster.dams(within: reachDamSearchMiles, of: point, in: roster)
                    .first { entry in
                        onReach(site: site, roles: roles, tokens: c.classification.nameTokens,
                                lat: c.reading.latitude, lon: c.reading.longitude, dam: entry.0) != nil
                    }?.0
            }
            releaseMemo[site] = .some(hit)
            return hit
        }
    }

    // MARK: Helpers

    private static func classify(_ reading: WaterLevelReading) -> Candidate {
        Candidate(reading: reading,
                  classification: GaugeClassifier.classify(siteName: reading.siteName,
                                                           siteTypeCode: reading.siteTypeCode,
                                                           methodDescription: reading.methodDescription))
    }

    private static func isNWPS(_ reading: WaterLevelReading) -> Bool {
        reading.methodDescription == nwpsMethodDescription
    }

    /// A damRelease gauge "names" D when every distinctive word of D's name is in
    /// the gauge name: "North Fork Riv … bl Norfork Dam" names Norfork Dam.
    private static func names(_ dam: RosterDam, _ gaugeTokens: Set<String>) -> Bool {
        let damTokens = Set(GaugeClassifier.tokens(dam.name))
            .subtracting(GaugeClassifier.genericWords)
            .subtracting(["LOCK", "AND"])
        return !damTokens.isEmpty && damTokens.isSubset(of: gaugeTokens)
    }

    /// Lower sorts first. Level: an elevation code over 00065 gage height, then
    /// the lowest block, then the lower code (USGS's response order, which puts a
    /// lake's 00062 ahead of its 62615). Other inputs: the lowest block.
    private static func sitePreference(_ r: WaterLevelReading, kind: GaugeKind) -> (Int, Int, String) {
        let codeRank = kind == .level && !elevationCodes.contains(r.parameterCode) ? 1 : 0
        return (codeRank, r.blockIndex, r.parameterCode)
    }

    private static func decision(_ c: Candidate, _ v: Verdict, kind: GaugeKind, accepted: Bool,
                                 note: String = "") -> GaugeDecision {
        let r = c.reading
        return GaugeDecision(kind: kind, siteCode: r.siteCode, siteName: r.siteName, parameterCode: r.parameterCode,
                             blockIndex: r.blockIndex, methodDescription: r.methodDescription, role: c.role,
                             distanceMiles: r.distanceMiles, value: r.value, accepted: accepted, reason: v.reason + note)
    }

    private static func fahrenheit(_ celsius: Double) -> Double { celsius * 9 / 5 + 32 }

    private static func fmt(_ value: Double, _ places: Int = 2) -> String {
        String(format: "%.\(places)f", value)
    }
}
