//
//  AlgalWaterWarning.swift
//  Sector — the algal-water reliability warning (Clarity Stage 8, master beta)
//
//  WHAT IT IS. The red-band turbidity model reads sediment. Where the water is
//  algal it reads the water clearer than it is (Stage 6: chlorophyll, not
//  turbidity, drove the Oct 2025 failures; Stage 7: national held-out, flagged
//  water was overstated 48% of the time against 8% unflagged, RR 6.1).
//
//  WHAT IT IS NOT. Not a clarity value, never feet, never a colour. It only
//  lowers how much authority the satellite estimate is given — confidence and
//  authority at most Low — and says why. Sentinel-2 only: Landsat has no
//  red-edge band, and the rule was validated on Sentinel-2 alone.
//
//  THE RULE (fixed; Stage 7 secondary rule, chosen on Guntersville by nested
//  leave-one-year-out, held-out on 669 national match-ups): NDCI > 0.03, with
//  NDCI = (B05 - B04) / (B05 + B04) from the pixels the turbidity was read on.
//

import Foundation

public enum AlgalWaterRule {
    public static let id = "ndci-algal-warning-v1"
    public static let description = "NDCI > 0.03 (Sentinel-2 only)"
    public static let threshold = 0.03
    /// The lake-surface product's encoding: 0 none, else lo + (q - 1) * step.
    public static let lo = -0.30, step = 0.0025
    /// 0.03 decodes from exactly this code; the warning fires above it.
    public static let thresholdCode: UInt8 = 133

    public static let headline = "Algal water detected"
    public static let message = "The satellite clarity estimate may read clearer than the water actually is."

    public static func decode(_ q: UInt8) -> Double? {
        q == 0 ? nil : ((lo + Double(Int(q) - 1) * step) * 10_000).rounded() / 10_000
    }
    /// On the code, so the threshold is exact rather than a float comparison.
    public static func fires(code q: UInt8) -> Bool { q > thresholdCode }
    public static func appliesTo(platform: String?) -> Bool {
        (platform ?? "").lowercased().hasPrefix("sentinel-2")
    }
}

/// What the warning did at one place, carried on the estimate for the tap
/// card's diagnostics.
public struct AlgalWaterWarning: Codable, Equatable {
    public let ruleId: String
    public let rule: String
    public let fired: Bool
    public let ndci: Double
    /// "sentinel-2b", and the scene the NDCI came from.
    public let satellite: String?
    public let sceneDate: String
    public let originalConfidence: ClarityConfidence
    public let displayedConfidence: ClarityConfidence
    public let originalAuthority: AuthorityLevel
    public let displayedAuthority: AuthorityLevel
    /// The sediment estimate before the warning (feet, and its report band).
    public let originalCentralFt: Double?
    public let originalCategory: ClarityCategory?
    public let headline: String?
    public let message: String?
}

extension CurrentClarityEstimate {
    /// The estimate with the warning applied. Where it fires on a cell that
    /// shows a value: confidence and authority capped at Low, no report band,
    /// and the warning first among the notes. The number, the range and the
    /// hue are the sediment model's, unchanged.
    func applyingAlgalWarning(fired: Bool, ndci: Double, scene: ClaritySceneRef) -> CurrentClarityEstimate {
        let showsValue = centralFt != nil || lastSupported != nil
        let act = fired && showsValue
        let conf = act ? Swift.min(confidence, .low) : confidence
        let auth = act ? Swift.min(authority, .low) : authority
        let warning = AlgalWaterWarning(
            ruleId: AlgalWaterRule.id, rule: AlgalWaterRule.description, fired: fired, ndci: ndci,
            satellite: scene.platform, sceneDate: scene.date,
            originalConfidence: confidence, displayedConfidence: conf, originalAuthority: authority, displayedAuthority: auth,
            originalCentralFt: centralFt ?? lastSupported?.centralFt, originalCategory: category,
            headline: act ? AlgalWaterRule.headline : nil, message: act ? AlgalWaterRule.message : nil)
        let shown = act
            ? ClarityDisplay(title: display.title, valueText: display.valueText, rangeText: display.rangeText,
                             confidenceText: conf.presentedLabel, sourceText: display.sourceText, evidenceText: display.evidenceText,
                             notes: ["\(AlgalWaterRule.headline). \(AlgalWaterRule.message)"] + display.notes)
            : display
        return CurrentClarityEstimate(
            schema: schema, lakeId: lakeId, lat: lat, lon: lon, supported: supported, region: region,
            evidenceLevel: evidenceLevel, magnitudeSupported: magnitudeSupported, centralFt: centralFt, lowFt: lowFt,
            highFt: highFt, category: act ? nil : category, confidence: conf, authority: auth, primarySource: primarySource,
            method: method, model: model, composition: composition, observation: observation, lastSupported: lastSupported,
            hydrologicChange: hydrologicChange, catchmentCompleteness: catchmentCompleteness, flowProvenance: flowProvenance,
            legacyEnvironmentalEstimate: legacyEnvironmentalEstimate, display: shown,
            limitations: act ? limitations + ["Algal water: the red-band estimate reads sediment and can read algal water clearer than it is."] : limitations,
            generatedAt: generatedAt, algalWarning: warning)
    }
}
