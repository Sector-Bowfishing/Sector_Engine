//
//  BowfishingConditions.swift
//  SectorEngine
//
//  Extracted from the iOS app's DashboardView.swift (where it was co-located with
//  the view). The legacy result shape the app renders, plus the bridge that maps
//  the v2 engine's `ConditionsResult` into it. Pure value-type logic — no UI.
//

import Foundation

/// The legacy result shape the existing dashboard views render.
struct BowfishingConditionsResult {
    let score: Int               // 0...100
    let rating: Rating
    let highlights: [String]     // the factors working in your favor
    let limiter: String?         // the single biggest drag, if any
    let moonDetail: String       // single moon line, e.g. "New moon — dark water"
    let moonFavorable: Bool?     // true = dark/good, false = bright/bad, nil = neutral

    enum Rating: String {
        case prime = "Prime"
        case good  = "Good"
        case fair  = "Fair"
        case poor  = "Poor"
    }
}

extension ConditionsBand {
    /// The legacy presentation enum. Same four words, same order — this exists
    /// only so the cut-points live in exactly one place (`ConditionsBand`).
    var rating: BowfishingConditionsResult.Rating {
        switch self {
        case .prime: return .prime
        case .good:  return .good
        case .fair:  return .fair
        case .poor:  return .poor
        }
    }
}

enum BowfishingConditions {

    /// Bridges the v2 engine's `ConditionsResult` into the legacy result shape the
    /// existing dashboard views render. The real scoring lives in the
    /// ConditionsEngine module (ConditionsAggregator); this is presentation glue.
    static func bridge(from c: ConditionsResult, input: ConditionsInput) -> BowfishingConditionsResult {
        let rating: BowfishingConditionsResult.Rating
        switch c.band {
        case .poor:  rating = .poor
        case .fair:  rating = .fair
        case .good:  rating = .good
        case .prime: rating = .prime
        }
        let highlights = c.factors
            .filter { $0.score >= 70 && $0.key != .darkness }
            .sorted { $0.score > $1.score }
            .prefix(3)
            .map { $0.why }
        let limiter = c.primaryGate?.reason
            ?? c.factors.filter { $0.score < 45 && $0.key != .darkness }
                .min { $0.score < $1.score }?.why

        let moonName = Astronomy.moonPhaseName(on: input.date)
        let darkness = c.factors.first { $0.key == .darkness }
        let favorable: Bool?
        if let d = darkness { favorable = d.score >= 70 ? true : (d.score <= 40 ? false : nil) }
        else { favorable = nil }
        let moonDetail: String
        switch favorable {
        case .some(true):  moonDetail = "\(moonName) — dark water"
        case .some(false): moonDetail = "\(moonName) — bright moon"
        default:           moonDetail = moonName
        }

        return BowfishingConditionsResult(
            score: c.score, rating: rating,
            highlights: Array(highlights), limiter: limiter,
            moonDetail: moonDetail, moonFavorable: favorable)
    }

    // MARK: Helpers still used by the forecast curve

    /// Wind score for bowfishing (0…1). Kept for ConditionsForecast's hourly /
    /// 7-night curve, which scores per-hour rather than through the aggregator.
    static func windScore(_ mph: Double) -> Double {
        switch mph {
        case ..<1:     return 0.80
        case 1..<4:    return 0.90
        case 4..<9:    return 1.00
        case 9..<13:   return 0.80
        case 13..<18:  return 0.55
        default:       return 0.30
        }
    }

    /// Fraction through the synodic cycle (0 = new … 0.5 = full). Delegates to the
    /// engine ephemeris so moon math has a single source.
    static func moonPhaseFraction(on date: Date) -> Double {
        Astronomy.moonPhaseFraction(on: date)
    }
}
