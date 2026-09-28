//
//  VisibilityModel.swift
//  Sector — the one turbidity → visibility conversion, with its error
//
//  TWO FORMULAS SHIPPED. The engine's gauge path used Secchi = 11.123·T^−0.637
//  ft; the Water Clarity map used 4.84·T^−0.672 m (an ADEM fit on
//  Guntersville). At one Sentinel cell they differed by 1.2–1.9 ft.
//
//  VALIDATED, NOT PICKED (scripts/hydrology/visibility_validation.py; lake-
//  grouped, WQP same-site same-day turbidity + Secchi that did not hit bottom):
//
//                                 engine            ADEM map         national refit (CV)
//    in situ, national 81,661    1.22 ft, 42%      2.34 ft, 22%     0.88 ft, 50%
//    in situ, Alabama 3,311      0.81 ft, 60%      0.91 ft, 57%     0.81 ft, 56%
//    in situ, TN River res. 130  0.94 ft, 64%      2.51 ft, 27%     1.17 ft, 63%
//    Sentinel-2 FNU, 905         2.18 ft, 31%      2.91 ft, 30%     2.45 ft, 30%
//    (median absolute error; share within ±30%)
//
//  The ADEM map formula reads 1.5–1.7× too clear nationally and on Tennessee
//  River reservoirs (median bias +0.17 to +0.24 log10). The engine's formula is
//  the most accurate on this region's water and on satellite turbidity, so it
//  is canonical; the national refit is recorded as the candidate to revisit
//  when the engine serves more of the country. On satellite turbidity every
//  power law is ±~2.5× at 80%: the reflectance band model (interim 1.67 ft,
//  48%) is the upgrade path there, through this same interface.
//
//  A RANGE, NOT A NUMBER. The 80% range is the formula's own residual spread
//  on the matching validation set; filled (not observed) satellite cells widen
//  by the fill's held-out error at their distance from a reading.
//

import Foundation

public enum TurbiditySource: String, Codable, Equatable {
    /// A USGS turbidity sensor in the water.
    case inSituGauge
    /// A Sentinel-2 cell the satellite read on its pass.
    case satelliteObserved
    /// A Sentinel-2 cell filled from readings nearby.
    case satelliteEstimated
}

public struct VisibilityEstimate: Codable, Equatable {
    public let centralFt: Double
    /// The 80% range: 1 time in 10 below, 1 in 10 above.
    public let lowFt: Double
    public let highFt: Double
    /// medium | low — nothing converted from turbidity is high
    public let confidence: String
    public let model: String
    public let source: TurbiditySource
}

public enum VisibilityModel {

    public static let modelId = "secchi-power-v1"

    /// log10(observed/predicted) at the 10th and 90th percentile, per source.
    /// (Validation reports predicted − observed; these are its negation.)
    static let rangeLog10: [TurbiditySource: (low: Double, high: Double)] = [
        .inSituGauge: (-0.381, 0.142),          // in situ, national, n = 81,661
        .satelliteObserved: (-0.356, 0.520),    // Sentinel-2 FNU match-ups, n = 905
        .satelliteEstimated: (-0.356, 0.520),
    ]

    /// The fill's held-out error of an estimate, in ft, by through-water
    /// distance to a reading (fill_lake.CLARITY_ERROR_BY_DISTANCE_FT).
    static let fillErrorFtByDistance: [(maxM: Double, ft: Double)] = [
        (250, 0.32), (500, 0.45), (1_000, 0.60), (2_000, 0.78), (5_000, 0.94), (.infinity, 1.11),
    ]

    /// Central visibility, ft — the engine's own gauge formula, so a gauge
    /// reads exactly what the conditions score already uses.
    public static func centralFt(fnu: Double, config: ConditionsConfig = .default) -> Double {
        let c = config.clarity
        return c.secchiCoefA * pow(Swift.max(fnu, 0.1), c.secchiExpB)
    }

    public static func estimate(fnu: Double, source: TurbiditySource,
                                distanceToObservedM: Double? = nil,
                                config: ConditionsConfig = .default) -> VisibilityEstimate {
        let central = centralFt(fnu: fnu, config: config)
        var (lo, hi) = rangeLog10[source] ?? (-0.5, 0.5)
        if source == .satelliteEstimated {
            let d = distanceToObservedM ?? .infinity
            let errFt = fillErrorFtByDistance.first { d <= $0.maxM }?.ft ?? 1.11
            let w = log10(1 + errFt / Swift.max(central, 0.1))
            lo = -((lo * lo + w * w).squareRoot()); hi = (hi * hi + w * w).squareRoot()
        }
        return VisibilityEstimate(centralFt: central,
                                  lowFt: central * pow(10, lo), highFt: central * pow(10, hi),
                                  confidence: source == .inSituGauge ? "medium" : "low",
                                  model: modelId, source: source)
    }
}
