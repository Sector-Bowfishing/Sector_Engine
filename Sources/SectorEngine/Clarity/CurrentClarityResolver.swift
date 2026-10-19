//
//  CurrentClarityResolver.swift
//  Sector — one cell's evidence and its region's hydrology in, one answer out
//  (Clarity Fusion Stage 4). Pure: no I/O, no clock of its own.
//
//  PER-CELL AUTHORITY. Stage 2 gave each arm an authority. Two cells of one
//  arm share its hydrology but not its evidence: a cell the satellite read and
//  a creek back 3 km from the nearest reading are not equally known. So
//
//      authority(cell)  = min(hydrologic cap of its region, evidence cap of the cell)
//      confidence(cell) = min(authority, what the drainage record lets Sector check)
//
//  The caps are RULES, fixed before the Stage 4 replay was run and tested by
//  it (CLARITY_FUSION_STAGE_4_HANDOFF.md): the hydrologic cap is Stage 2's
//  (validated out of sample in Stage 3B); the evidence cap follows the fill's
//  own held-out error by through-water distance (fill_lake), and refuses a
//  number beyond 5 km, where the fill also leans ~0.8 ft too clear.
//

import Foundation

public enum CurrentClarityResolver {

    public enum Rules {
        /// A scene older than this is "historical" (D) even while it still holds.
        public static let currentSceneMaxAgeHours = 72.0
        /// An in-situ sensor reading older than this does not answer.
        public static let inSituMaxAgeHours = 6.0
        /// Filled cells: up to this through-water distance, moderate.
        public static let filledModerateMaxM = 500.0
        /// Beyond this, no number: the fill's held-out error is at its largest
        /// and its estimates lean too clear (fill_lake.CLARITY_ERROR_BY_DISTANCE_LOG10).
        public static let filledMaxM = 5_000.0

        /// What a change in the drainage leaves the scene. Stage 2's caps.
        public static func hydrologicCap(_ s: RunoffClass) -> AuthorityLevel {
            switch s {
            case .stable: return .high
            case .minorChange, .unknown: return .moderate
            case .moderateRunoff, .recovering: return .low
            case .majorRunoff: return .none
            }
        }

        /// What the cell's own evidence can carry.
        public static func evidenceCap(_ c: ClarityCellEvidence) -> AuthorityLevel {
            switch c.kind {
            case .none: return .none
            case .direct: return c.fnu == nil ? .none : .high
            // The satellite sees the plants in a bed, never the water, and the
            // values carried into beds erred 0.39 log10 (5 ft) on 2020–24 but
            // 0.12 on 2025–26 (Stage 4 replay): no supported magnitude (Stage 5).
            case .grassBed: return .none
            case .filled:
                guard c.fnu != nil, let d = c.distanceToObservedM, d.isFinite, d <= filledMaxM else { return .none }
                return d <= filledModerateMaxM ? .moderate : .low
            }
        }

        /// High means read, current and checkable (Stage 5): a directly read
        /// cell of a scene no older than `currentSceneMaxAgeHours`, under a
        /// stable, fully recorded drainage. Anything else caps at moderate.
        /// Preregistered in docs/clarity/stage5/CONFIDENCE_TIERS_PREREGISTRATION.md.
        public static func confidence(authority: AuthorityLevel, record: ClarityConfidence,
                                      level: ClarityEvidenceLevel) -> ClarityConfidence {
            let c = min(ClarityConfidence(authority), record)
            return c == .high && level != .directSatellite ? .moderate : c
        }

        /// What the drainage record lets Sector check.
        public static func recordCap(_ completeness: CatchmentCompleteness, flowProvenance: String) -> ClarityConfidence {
            var cap: ClarityConfidence = [.complete: .high, .partial: .moderate, .unavailable: .low][completeness]!
            if flowProvenance == "unavailable" { cap = min(cap, .moderate) }
            return cap
        }
    }

    // MARK: Resolve

    public static func estimate(lakeId: String, lat: Double, lon: Double,
                                region: ClarityRegionContext?, zone: (id: Int, name: String)?,
                                cell: ClarityCellEvidence?, inSitu: InSituTurbidity? = nil,
                                legacy: LegacyClarityEstimate? = nil, now: Date) -> CurrentClarityEstimate {
        guard let region, let cell else {
            return unsupported(lakeId: lakeId, lat: lat, lon: lon, region: nil, zone: nil, legacy: legacy,
                               why: region == nil ? "Not on a lake Sector has a hydrologic model for, or not on its water."
                                                  : "No clarity evidence for this cell.", now: now)
        }
        let ref = ClarityRegionRef(kind: region.kind, id: region.id, name: region.name, zone: zone?.id, zoneName: zone?.name)
        guard let scene = region.scene else {
            return unsupported(lakeId: lakeId, lat: lat, lon: lon, region: region, zone: ref, legacy: legacy,
                               why: "No satellite scene of this water in the last 45 days.", now: now)
        }

        let hydroCap = Rules.hydrologicCap(region.runoff.state)
        let evidenceCap = Rules.evidenceCap(cell)
        let authority = min(hydroCap, evidenceCap)
        let recordCap = Rules.recordCap(region.catchmentCompleteness, flowProvenance: region.flowProvenance)
        let ageH = now.timeIntervalSince(scene.time) / 3600
        let change = HydrologicChange(
            state: region.runoff.state, expectedDirection: region.runoff.expectedDirection, magnitude: "uncalibrated",
            rainSinceObservationIn: region.rainSinceSceneIn, rainRecordThrough: region.rainRecordThrough,
            flowChangeRatio: region.flowChangeRatio, flowProvenance: region.flowProvenance,
            flowSource: region.flowSource, authorityCap: hydroCap, evidence: region.runoff.evidence)

        // The scene's number at this cell, whatever happens to it below.
        let sat: VisibilityEstimate? = cell.fnu.map { fnu in
            cell.kind == .direct
                ? VisibilityModel.estimate(fnu: fnu, source: .satelliteObserved)
                : VisibilityModel.estimate(fnu: fnu, source: .satelliteEstimated, distanceToObservedM: cell.distanceToObservedM)
        }
        let satSource: ClaritySourceKind = cell.kind == .direct ? .satelliteObserved
            : cell.kind == .grassBed ? .satelliteGrassBed : cell.kind == .filled ? .satelliteFilled : .none
        let observation = ClarityObservation(
            observedAt: scene.time, sceneDate: scene.date, platform: scene.platform, sceneSource: scene.source,
            cellEvidence: cell.kind, fillReason: cell.fillReason,
            distanceToObservedM: cell.kind == .direct ? 0 : cell.distanceToObservedM, ageHours: ageH, fnu: cell.fnu)
        var composition: [ClarityEvidenceItem] = []
        var limitations = region.limitations
        if let n = region.anchorNote { limitations.append(n) }

        // A — a sensor in this zone, read recently, outranks the satellite.
        if let g = inSitu, now.timeIntervalSince(g.at) <= Rules.inSituMaxAgeHours * 3600, g.at <= now,
           let z = zone?.id, g.zone == z {
            let v = VisibilityModel.estimate(fnu: g.fnu, source: .inSituGauge)
            composition.append(item("answer", .inSitu, .inSituGauge, .instrumentMeasured,
                                    "\(g.site)\(g.name.map { " \($0)" } ?? ""): \(fmt1(g.fnu)) FNU", v, g.at))
            if let s = sat {
                composition.append(item("context", level(for: cell, ageH: ageH), satSource, .satelliteDerivedSecchi,
                                        "Sentinel-2 \(scene.date), superseded by the sensor", s, scene.time))
            }
            let conf = min(ClarityConfidence.moderate, recordCap)
            return CurrentClarityEstimate(
                schema: CurrentClarityEstimate.schemaId, lakeId: lakeId, lat: lat, lon: lon, supported: true, region: ref,
                evidenceLevel: .inSitu, magnitudeSupported: true, centralFt: v.centralFt, lowFt: v.lowFt, highFt: v.highFt,
                category: ClarityCategory(ft: v.centralFt), confidence: conf, authority: .moderate,
                primarySource: .inSituGauge, method: .instrumentMeasured, model: v.model, composition: composition,
                observation: observation, lastSupported: nil, hydrologicChange: change,
                catchmentCompleteness: region.catchmentCompleteness, flowProvenance: region.flowProvenance,
                legacyEnvironmentalEstimate: legacy,
                display: ClarityDisplay(title: "Water Clarity", valueText: "~\(fmt1(v.centralFt)) ft",
                                        rangeText: "Likely \(fmt1(v.lowFt))–\(fmt1(v.highFt)) ft",
                                        confidenceText: conf.presentedLabel,
                                        sourceText: "\(g.name ?? "USGS \(g.site)") · \(ago(now.timeIntervalSince(g.at)))",
                                        evidenceText: "Turbidity sensor in this water", notes: []),
                limitations: limitations, generatedAt: now)
        }

        // F — the cell's evidence carries no number.
        guard evidenceCap > .none, let s = sat else {
            let why: String = {
                switch cell.kind {
                case .none: return "The scene gives this cell no value."
                case .direct: return "The scene's reading here has no value."
                case .grassBed: return "Grass bed: the satellite reads the plants, not the water, so no visibility is supported here."
                case .filled:
                    guard let d = cell.distanceToObservedM, d.isFinite else { return "No satellite reading connects to this water." }
                    return "The nearest satellite reading is \(km(d)) away through the water: too far to carry a number."
                }
            }()
            if let s = sat {
                composition.append(item("rejected", .none, satSource, .satelliteDerivedSecchi,
                                        "Sentinel-2 \(scene.date) fill: \(why)", s, scene.time))
            }
            return CurrentClarityEstimate(
                schema: CurrentClarityEstimate.schemaId, lakeId: lakeId, lat: lat, lon: lon, supported: true, region: ref,
                evidenceLevel: .none, magnitudeSupported: false, centralFt: nil, lowFt: nil, highFt: nil, category: nil,
                confidence: .none, authority: .none, primarySource: .none, method: nil, model: nil,
                composition: composition, observation: observation, lastSupported: nil, hydrologicChange: change,
                catchmentCompleteness: region.catchmentCompleteness, flowProvenance: region.flowProvenance,
                legacyEnvironmentalEstimate: legacy,
                display: ClarityDisplay(title: "Water Clarity", valueText: "No supported estimate", rangeText: nil,
                                        confidenceText: ClarityConfidence.none.presentedLabel,
                                        sourceText: "Sentinel-2 · \(shortDate(scene.time))",
                                        evidenceText: cell.kind == .grassBed ? "Grass bed" : "Satellite estimate unavailable here",
                                        notes: [why]),
                limitations: limitations + [why], generatedAt: now)
        }

        // E — the drainage has changed since the scene: its number is history.
        if hydroCap <= .low {
            let conf = min(ClarityConfidence(authority), recordCap)
            let why = headline(region.runoff.state)
            composition.append(item("notCurrent", .changedHistorical, satSource, .satelliteDerivedSecchi,
                                    "Sentinel-2 \(scene.date) (\(evidenceWords(cell))): \(why.lowercased())", s, scene.time))
            let notes = [why] + changeLines(region) + ["Current visibility change is not yet calibrated."]
            return CurrentClarityEstimate(
                schema: CurrentClarityEstimate.schemaId, lakeId: lakeId, lat: lat, lon: lon, supported: true, region: ref,
                evidenceLevel: .changedHistorical, magnitudeSupported: false, centralFt: nil, lowFt: nil, highFt: nil,
                category: nil, confidence: conf, authority: authority, primarySource: satSource,
                method: .satelliteDerivedSecchi, model: s.model, composition: composition, observation: observation,
                lastSupported: LastSupportedClarity(centralFt: s.centralFt, lowFt: s.lowFt, highFt: s.highFt,
                                                    observedAt: scene.time, whyNotCurrent: why),
                hydrologicChange: change, catchmentCompleteness: region.catchmentCompleteness,
                flowProvenance: region.flowProvenance, legacyEnvironmentalEstimate: legacy,
                display: ClarityDisplay(title: "Water Clarity", valueText: "Last supported estimate ~\(fmt1(s.centralFt)) ft",
                                        rangeText: nil, confidenceText: conf.presentedLabel,
                                        sourceText: "Sentinel-2 · \(shortDate(scene.time))",
                                        evidenceText: evidenceWords(cell), notes: notes),
                limitations: limitations, generatedAt: now)
        }

        // B, C, D — the scene still speaks for this water.
        let lvl = level(for: cell, ageH: ageH)
        let conf = Rules.confidence(authority: authority, record: recordCap, level: lvl)
        composition.append(item("answer", lvl, satSource, .satelliteDerivedSecchi,
                                "Sentinel-2 \(scene.date): \(evidenceWords(cell))", s, scene.time))
        var notes: [String] = []
        if lvl == .stableHistorical {
            notes.append(region.runoff.state == .stable
                         ? "Observed \(ago(ageH * 3600)); the drainage has stayed as it was since."
                         : "Observed \(ago(ageH * 3600)); only minor rain or flow change since.")
        } else if region.runoff.state == .minorChange {
            notes.append("Some rain or flow change since the observation; not enough to set it aside.")
        } else if region.runoff.state == .unknown {
            notes.append("No record shows whether the drainage has changed since the observation.")
        }
        if region.catchmentCompleteness == .partial {
            notes.append("Rain is known only for the drainage above the creek's head.")
        }
        return CurrentClarityEstimate(
            schema: CurrentClarityEstimate.schemaId, lakeId: lakeId, lat: lat, lon: lon, supported: true, region: ref,
            evidenceLevel: lvl, magnitudeSupported: true, centralFt: s.centralFt, lowFt: s.lowFt, highFt: s.highFt,
            category: ClarityCategory(ft: s.centralFt), confidence: conf, authority: authority, primarySource: satSource,
            method: .satelliteDerivedSecchi, model: s.model, composition: composition, observation: observation,
            lastSupported: nil, hydrologicChange: change, catchmentCompleteness: region.catchmentCompleteness,
            flowProvenance: region.flowProvenance, legacyEnvironmentalEstimate: legacy,
            display: ClarityDisplay(title: "Water Clarity", valueText: "~\(fmt1(s.centralFt)) ft",
                                    rangeText: "Likely \(fmt1(s.lowFt))–\(fmt1(s.highFt)) ft",
                                    confidenceText: conf.presentedLabel, sourceText: "Sentinel-2 · \(shortDate(scene.time))",
                                    evidenceText: evidenceWords(cell), notes: notes),
            limitations: limitations, generatedAt: now)
    }

    /// The outcome for a kind of cell in a region, without its value: what
    /// the map needs per cell (confidence, level, whether a number shows).
    public struct Outcome: Codable, Equatable {
        public let level: ClarityEvidenceLevel
        public let confidence: ClarityConfidence
        public let authority: AuthorityLevel
        public let magnitudeSupported: Bool
    }

    /// The same decision `estimate` makes, for a cell of this kind in this
    /// region. The lake summary's table is built from it, so the map and the
    /// API cannot disagree.
    public static func outcome(region: ClarityRegionContext, cell: ClarityCellEvidence, now: Date) -> Outcome {
        let e = estimate(lakeId: "", lat: 0, lon: 0, region: region, zone: nil, cell: cell, now: now)
        return Outcome(level: e.evidenceLevel, confidence: e.confidence, authority: e.authority,
                       magnitudeSupported: e.magnitudeSupported)
    }

    // MARK: Pieces

    static func level(for cell: ClarityCellEvidence, ageH: Double) -> ClarityEvidenceLevel {
        if ageH > Rules.currentSceneMaxAgeHours { return .stableHistorical }
        return cell.kind == .direct ? .directSatellite : .nearbySatellite
    }

    static func unsupported(lakeId: String, lat: Double, lon: Double, region: ClarityRegionContext?,
                            zone: ClarityRegionRef?, legacy: LegacyClarityEstimate?, why: String, now: Date) -> CurrentClarityEstimate {
        CurrentClarityEstimate(
            schema: CurrentClarityEstimate.schemaId, lakeId: lakeId, lat: lat, lon: lon, supported: region != nil,
            region: zone, evidenceLevel: .none, magnitudeSupported: false, centralFt: nil, lowFt: nil, highFt: nil,
            category: nil, confidence: .none, authority: .none, primarySource: .none, method: nil, model: nil,
            composition: [], observation: nil, lastSupported: nil, hydrologicChange: nil,
            catchmentCompleteness: region?.catchmentCompleteness, flowProvenance: region?.flowProvenance ?? "unavailable",
            legacyEnvironmentalEstimate: legacy,
            display: ClarityDisplay(title: "Water Clarity", valueText: "No supported estimate", rangeText: nil,
                                    confidenceText: ClarityConfidence.none.presentedLabel, sourceText: nil,
                                    evidenceText: "No satellite evidence", notes: [why]),
            limitations: (region?.limitations ?? []) + [why], generatedAt: now)
    }

    static func item(_ role: String, _ level: ClarityEvidenceLevel, _ source: ClaritySourceKind, _ method: VisibilityMethod,
                     _ detail: String, _ v: VisibilityEstimate, _ at: Date) -> ClarityEvidenceItem {
        ClarityEvidenceItem(role: role, level: level, source: source, method: method, detail: detail,
                            centralFt: v.centralFt, lowFt: v.lowFt, highFt: v.highFt, observedAt: at)
    }

    static func evidenceWords(_ c: ClarityCellEvidence) -> String {
        switch c.kind {
        case .direct: return "Direct satellite observation"
        case .grassBed: return "Grass bed: estimated from the water around it"
                + (c.distanceToObservedM.map { $0.isFinite ? ", \(km($0)) from a reading" : "" } ?? "")
        case .filled:
            let why = c.fillReason == "cloud" ? "cloud hid this water" : "the satellite cannot read this water"
            guard let d = c.distanceToObservedM, d.isFinite else { return "Estimated; \(why)" }
            return "Estimated from satellite readings \(km(d)) away through the water (\(why))"
        case .none: return "No satellite value"
        }
    }

    static func headline(_ s: RunoffClass) -> String {
        switch s {
        case .majorRunoff: return "Major hydrologic change since observation"
        case .moderateRunoff: return "Runoff since observation"
        case .recovering: return "Runoff since observation, now receding"
        default: return "Hydrologic change since observation"
        }
    }

    /// The change in plain words, with how each number was obtained.
    static func changeLines(_ r: ClarityRegionContext) -> [String] {
        var out: [String] = []
        if let x = r.flowChangeRatio, x >= 1.5 {
            let how: String
            switch r.flowProvenance {
            // "USGS 03572900", not the gauge's full upper-case name.
            case "measuredUSGS": how = "measured" + (r.flowSource.map { ", " + $0.split(separator: " ").prefix(2).joined(separator: " ") } ?? "")
            case "modeledNWM": how = "modeled by the National Water Model, not measured"
            case "measuredTVARelease": how = "measured TVA release"
            default: how = r.flowProvenance
            }
            let what = r.kind == .mainStem ? "Upstream dam release" : "\(r.name) flow"
            let size = x >= 3 ? "substantially above" : "above"
            out.append("\(what) \(size) its level at the observation (×\(fmt1(x)), \(how))")
        }
        if let rain = r.rainSinceSceneIn, rain >= 0.1 {
            out.append("\(String(format: "%.2f", rain)) in of rain on \(r.kind == .mainStem ? "the reservoir" : "its drainage") since the observation")
        }
        return out
    }

    static func fmt1(_ v: Double) -> String { String(format: "%.1f", v) }
    /// Fill distances come in 100 m steps (the cells file): under one step is "under 100 m", not "0 m".
    static func km(_ m: Double) -> String {
        if m < 100 { return "under 100 m" }
        return m < 1_000 ? "\(Int((m / 100).rounded() * 100)) m" : String(format: "%.1f km", m / 1000)
    }
    static func ago(_ s: TimeInterval) -> String {
        let h = s / 3600
        if h < 1 { return "under an hour ago" }
        if h < 36 { return "\(Int(h.rounded())) hours ago" }
        return "\(Int((h / 24).rounded())) days ago"
    }
    static let dayFormat: DateFormatter = {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "America/Chicago"); f.dateFormat = "MMM d"
        return f
    }()
    static func shortDate(_ d: Date) -> String { dayFormat.string(from: d) }
    static let dayTimeFormat: DateFormatter = {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "America/Chicago"); f.dateFormat = "MMM d, h a"
        return f
    }()
    static func shortDateTime(_ d: Date) -> String { dayTimeFormat.string(from: d) }
}
