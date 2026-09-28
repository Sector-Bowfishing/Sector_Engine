//
//  CurrentClarity.swift
//  Sector — the one answer to "how clear is the water here, now, and why?"
//  (Clarity Fusion Stage 4)
//
//  ONE TYPE. The Water Clarity map, its tap card and the API all read
//  `CurrentClarityEstimate`; there is no separate "map clarity" and
//  "conditions clarity". The map is the same estimate for every cell, drawn
//  from the lake's composite (CurrentClarityLake + ClarityCells); a tap is
//  the same estimate for one cell.
//
//  RANKED, NEVER AVERAGED. Sources are placed on one ladder and the best one
//  that holds answers; the rest are kept in `composition` as context:
//
//    A  inSitu             a turbidity sensor in this zone of this water, read in the last 6 h
//    B  directSatellite    this cell was read on its region's chosen scene
//    C  nearbySatellite    this cell was filled through the water from readings (confidence falls with distance)
//    D  stableHistorical   B or C more than 72 h old, kept because the drainage has not changed since
//    E  changedHistorical  the scene's number, kept as context: the drainage has changed since
//    F  none               no defensible number: Sector says so rather than inventing one
//
//  HYDROLOGY MOVES AUTHORITY, NEVER FEET. Rain on the drainage and the
//  creek's rise since the scene decide whether the scene still speaks for the
//  water (ClarityStateEngine's runoff state, validated out of sample in Stage
//  3B). They never adjust the number: Stage 3B found no calibrated size for a
//  storm's effect. Where the drainage has changed, the answer is E — the
//  scene's own number, labelled as history.
//
//  THE LEGACY ESTIMATE IS NOT EVIDENCE. The engine's 4.0 ft × rain-decay
//  estimate (ClarityFactor, `rain-decay-v0`) is never an answer here. Where a
//  caller asks for it, it is carried as `legacyEnvironmentalEstimate`, labelled.
//
//  NOT SCORED. Nothing in /conditions or Fish Intelligence reads this yet.
//

import Foundation

// MARK: - Ladders

public enum ClarityEvidenceLevel: String, Codable, Equatable, Comparable {
    case inSitu, directSatellite, nearbySatellite, stableHistorical, changedHistorical, none
    /// A (best) … F.
    public var letter: String {
        ["inSitu": "A", "directSatellite": "B", "nearbySatellite": "C",
         "stableHistorical": "D", "changedHistorical": "E", "none": "F"][rawValue]!
    }
    var rank: Int { ["inSitu": 0, "directSatellite": 1, "nearbySatellite": 2,
                     "stableHistorical": 3, "changedHistorical": 4, "none": 5][rawValue]! }
    /// Lower rank is better evidence, so `<` reads "better than".
    public static func < (a: Self, b: Self) -> Bool { a.rank < b.rank }
}

/// Ordinal, not a probability. How well Sector's evidence supports the number
/// being this water's clarity NOW. The range carries the conversion's error.
public enum ClarityConfidence: String, Codable, Equatable, Comparable {
    case none, low, moderate, high
    var rank: Int { ["none": 0, "low": 1, "moderate": 2, "high": 3][rawValue]! }
    public static func < (a: Self, b: Self) -> Bool { a.rank < b.rank }
    init(_ a: AuthorityLevel) {
        self = [.none: .none, .low: .low, .moderate: .moderate, .high: .high][a]!
    }
    public var label: String { ["none": "None", "low": "Low", "moderate": "Moderate", "high": "High"][rawValue]! }
    /// The words a person sees. Stage 5's preregistered replay did not
    /// separate High from Moderate, so both read "Moderate"; `high` stays
    /// internal (docs/clarity/stage5/CONFIDENCE_TIERS_PREREGISTRATION.md).
    public var presentedLabel: String { self == .high ? ClarityConfidence.moderate.label : label }
}

extension AuthorityLevel {
    init(_ c: ClarityConfidence) { self = [.none: .none, .low: .low, .moderate: .moderate, .high: .high][c]! }
}

/// How a visibility was obtained. Kept apart: a night-time look under
/// bowfishing lights is not a daytime Secchi depth, and nothing here converts
/// one into the other until paired observations establish how they relate.
public enum VisibilityMethod: String, Codable, Equatable {
    /// Sentinel-2 turbidity → Secchi depth (secchi-power-v1).
    case satelliteDerivedSecchi
    /// An in-situ turbidity sensor → Secchi depth (secchi-power-v1).
    case instrumentMeasured
    /// A bowfisher's look into the water under their lights.
    case userReportedNightVisibility
    /// A bowfisher's look into the water by daylight (not a Secchi disk).
    case userReportedDayVisibility
}

public enum ClaritySourceKind: String, Codable, Equatable {
    case inSituGauge, satelliteObserved, satelliteFilled, satelliteGrassBed, userReported, none
}

/// The bins a bowfisher answers in, and the bins the map's key uses.
public enum ClarityCategory: String, Codable, Equatable, CaseIterable {
    case under1ft, ft1to2, ft2to4, ft4to6, ft6plus
    public var lowFt: Double { [0, 1, 2, 4, 6][Self.allCases.firstIndex(of: self)!] }
    /// nil = open-ended.
    public var highFt: Double? { [1, 2, 4, 6, nil][Self.allCases.firstIndex(of: self)!] }
    public var label: String { ["< 1 ft", "1–2 ft", "2–4 ft", "4–6 ft", "6+ ft"][Self.allCases.firstIndex(of: self)!] }
    public init(ft: Double) {
        self = ft < 1 ? .under1ft : ft < 2 ? .ft1to2 : ft < 4 ? .ft2to4 : ft < 6 ? .ft4to6 : .ft6plus
    }
}

/// A reported visibility is an interval and stays one: never a midpoint.
public struct VisibilityInterval: Codable, Equatable {
    public let lowFt: Double
    /// nil = open-ended ("6+ ft").
    public let highFt: Double?
    public init(lowFt: Double, highFt: Double?) { self.lowFt = lowFt; self.highFt = highFt }
    public init(_ c: ClarityCategory) { self.init(lowFt: c.lowFt, highFt: c.highFt) }
    public var label: String {
        if let h = highFt { return lowFt == 0 ? "< \(Self.ft(h)) ft" : "\(Self.ft(lowFt))–\(Self.ft(h)) ft" }
        return "\(Self.ft(lowFt))+ ft"
    }
    static func ft(_ v: Double) -> String { v == v.rounded() ? String(Int(v)) : String(format: "%.1f", v) }
}

// MARK: - Inputs

public struct ClaritySceneRef: Codable, Equatable {
    public let date: String
    public let time: Date
    public let platform: String?
    /// Where the scene's cells came from (the published product, or a rebuild).
    public let source: String
    public init(date: String, time: Date, platform: String?, source: String) {
        self.date = date; self.time = time; self.platform = platform; self.source = source
    }
}

/// One cell's satellite evidence on its region's chosen scene.
public struct ClarityCellEvidence: Equatable {
    public enum Kind: String, Codable, Equatable {
        /// Read on the pass.
        case direct
        /// Estimated through the water from readings (cloud hid it, or the satellite cannot read there).
        case filled
        /// A grass bed: the satellite sees the plants; the value is carried in from the water round it.
        case grassBed
        /// No value.
        case none
    }
    public let kind: Kind
    public let fnu: Double?
    /// Through-water distance to the nearest reading. 0 for a read cell;
    /// .infinity where no path reaches one.
    public let distanceToObservedM: Double?
    /// cloud | unreadable, for a filled cell.
    public let fillReason: String?
    public init(kind: Kind, fnu: Double?, distanceToObservedM: Double?, fillReason: String? = nil) {
        self.kind = kind; self.fnu = fnu; self.distanceToObservedM = distanceToObservedM; self.fillReason = fillReason
    }
}

/// A hydrologic region's state: its chosen scene and what its drainage has done since.
public struct ClarityRegionContext: Codable, Equatable {
    public enum Kind: String, Codable, Equatable { case arm, mainStem }
    public let kind: Kind
    /// The arm id, or "_mainStem".
    public let id: String
    public let name: String
    public let scene: ClaritySceneRef?
    public let anchorStrength: AnchorStrength
    public let anchorNote: String?
    public let runoff: RunoffState
    /// nil = unknown, never zero.
    public let rainSinceSceneIn: Double?
    public let rainRecordThrough: Date?
    /// measuredUSGS | modeledNWM | measuredTVARelease | unavailable
    public let flowProvenance: String
    public let flowSource: String?
    /// The flow's peak since the scene over its value at the scene, same series.
    public let flowChangeRatio: Double?
    public let catchmentCompleteness: CatchmentCompleteness
    public let limitations: [String]

    public init(kind: Kind, id: String, name: String, scene: ClaritySceneRef?, anchorStrength: AnchorStrength,
                anchorNote: String?, runoff: RunoffState, rainSinceSceneIn: Double?, rainRecordThrough: Date?,
                flowProvenance: String, flowSource: String?, flowChangeRatio: Double?,
                catchmentCompleteness: CatchmentCompleteness, limitations: [String]) {
        self.kind = kind; self.id = id; self.name = name; self.scene = scene; self.anchorStrength = anchorStrength
        self.anchorNote = anchorNote; self.runoff = runoff; self.rainSinceSceneIn = rainSinceSceneIn
        self.rainRecordThrough = rainRecordThrough; self.flowProvenance = flowProvenance; self.flowSource = flowSource
        self.flowChangeRatio = flowChangeRatio; self.catchmentCompleteness = catchmentCompleteness
        self.limitations = limitations
    }
}

/// A turbidity sensor in the water, read recently.
public struct InSituTurbidity: Codable, Equatable {
    public let site: String
    public let name: String?
    public let fnu: Double
    public let at: Date
    /// The Stage 3A zone it sits in; it speaks for that zone only.
    public let zone: Int?
    public init(site: String, name: String?, fnu: Double, at: Date, zone: Int?) {
        self.site = site; self.name = name; self.fnu = fnu; self.at = at; self.zone = zone
    }
}

/// The engine's older estimate, labelled for the A/B. Never an answer.
public struct LegacyClarityEstimate: Codable, Equatable {
    /// rain-decay-v0 (or secchi-power-v1 where /conditions had a gauge).
    public let model: String
    public let centralFt: Double
    public let source: String
    public let label: String
    public init(model: String, centralFt: Double, source: String) {
        self.model = model; self.centralFt = centralFt; self.source = source
        self.label = model == "rain-decay-v0"
            ? "Legacy environmental estimate (4.0 ft decayed by recent rain), not an observation"
            : "The conditions engine's clarity (\(model))"
    }
}

// MARK: - The answer

public struct ClarityRegionRef: Codable, Equatable {
    public let kind: ClarityRegionContext.Kind
    public let id: String
    public let name: String
    /// The Stage 3A zone (nil on the main stem): the de-identified unit shared reports use.
    public let zone: Int?
    public let zoneName: String?
}

public struct ClarityObservation: Codable, Equatable {
    public let observedAt: Date
    public let sceneDate: String
    public let platform: String?
    public let sceneSource: String
    public let cellEvidence: ClarityCellEvidence.Kind
    public let fillReason: String?
    /// Through-water distance to the observed evidence (0 for a read cell).
    public let distanceToObservedM: Double?
    public let ageHours: Double
    public let fnu: Double?
}

/// What the scene said, when it no longer speaks for the water now.
public struct LastSupportedClarity: Codable, Equatable {
    public let centralFt: Double
    public let lowFt: Double
    public let highFt: Double
    public let observedAt: Date
    public let whyNotCurrent: String
}

public struct HydrologicChange: Codable, Equatable {
    public let state: RunoffClass
    /// murkierThanPass | sameAsPass | clearerThanPass | unknown — a hydrologic
    /// statement, not a validated clarity change.
    public let expectedDirection: String
    /// Always "uncalibrated": no size is attached.
    public let magnitude: String
    /// nil = unknown, never zero.
    public let rainSinceObservationIn: Double?
    public let rainRecordThrough: Date?
    public let flowChangeRatio: Double?
    public let flowProvenance: String
    public let flowSource: String?
    /// The most this change leaves the observation's authority.
    public let authorityCap: AuthorityLevel
    public let evidence: [String]
}

public struct ClarityEvidenceItem: Codable, Equatable {
    /// answer | context | notCurrent | rejected
    public let role: String
    public let level: ClarityEvidenceLevel
    public let source: ClaritySourceKind
    public let method: VisibilityMethod?
    public let detail: String
    public let centralFt: Double?
    public let lowFt: Double?
    public let highFt: Double?
    public let observedAt: Date?
}

/// The tap card's words, written once here so every platform says the same.
public struct ClarityDisplay: Codable, Equatable {
    public let title: String
    /// "~5.1 ft" | "Last supported estimate ~5.1 ft" | "No supported estimate"
    public let valueText: String
    /// "Likely 2.2–6.8 ft"
    public let rangeText: String?
    public let confidenceText: String
    /// "Sentinel-2 · Sep 20"
    public let sourceText: String?
    /// "Direct satellite observation"
    public let evidenceText: String
    public let notes: [String]
}

public struct CurrentClarityEstimate: Codable, Equatable {
    public static let schemaId = "current-clarity-v1"
    public let schema: String
    public let lakeId: String
    public let lat: Double
    public let lon: Double
    /// false off the water, outside a lake with a hydrologic graph, or where no scene exists.
    public let supported: Bool
    public let region: ClarityRegionRef?
    public let evidenceLevel: ClarityEvidenceLevel
    /// true only for A–D. E and F carry no current number.
    public let magnitudeSupported: Bool
    public let centralFt: Double?
    public let lowFt: Double?
    public let highFt: Double?
    public let category: ClarityCategory?
    public let confidence: ClarityConfidence
    /// This cell's: its region's hydrologic cap and its own evidence, the lower.
    public let authority: AuthorityLevel
    public let primarySource: ClaritySourceKind
    public let method: VisibilityMethod?
    public let model: String?
    public let composition: [ClarityEvidenceItem]
    public let observation: ClarityObservation?
    public let lastSupported: LastSupportedClarity?
    public let hydrologicChange: HydrologicChange?
    public let catchmentCompleteness: CatchmentCompleteness?
    /// measuredUSGS | modeledNWM | measuredTVARelease | unavailable
    public let flowProvenance: String
    public let legacyEnvironmentalEstimate: LegacyClarityEstimate?
    public let display: ClarityDisplay
    public let limitations: [String]
    public let generatedAt: Date
}
