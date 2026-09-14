//
//  FactorScore.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  The uniform output of every factor scorer: a 0–100 sub-score plus the copy
//  the breakdown sheet and "top reasons" render. Each scorer is a pure function
//  — numbers in, `FactorScore` out — so it can be unit-tested in isolation. §2.
//

import Foundation

/// One factor's contribution. `score` is 0–100, higher = better for bowfishing.
public struct FactorScore: Equatable, Sendable {
    /// 0…100, higher is better for sight-shooting.
    public let score: Double
    /// Short human value, e.g. "0.6 ft viz" or "74% lit".
    public let label: String
    /// One-line explanation for the breakdown / reasons list.
    public let why: String

    public init(score: Double, label: String, why: String) {
        self.score = score.clampedToScore
        self.label = label
        self.why = why
    }

    /// Rounded integer score for display.
    public var intScore: Int { Int(score.rounded()) }
}

public extension Double {
    /// Clamp to the 0…100 sub-score range.
    var clampedToScore: Double { Swift.min(100, Swift.max(0, self)) }
    /// Clamp to the 0…1 unit range.
    var clamped01: Double { Swift.min(1, Swift.max(0, self)) }
}
