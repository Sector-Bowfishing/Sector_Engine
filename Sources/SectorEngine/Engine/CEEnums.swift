//
//  CEEnums.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Pure, framework-agnostic value types shared across the engine. Foundation
//  only — no SwiftUI / CoreLocation / network. The engine is self-contained so
//  it can be read, tested, and (later) transcribed to another platform without
//  pulling in the rest of the app. See docs/claude-code-handoff.md.
//

import Foundation

/// Coarse latitude band that selects each species' spawn-calendar window.
/// Temperature gates stay the same nationwide; only the calendar shifts. §9.
public enum Region: String, Equatable, CaseIterable, Sendable {
    case south      // < 34°N
    case lowerMid   // 34–39°N
    case north      // > 39°N
    case west       // arid/mountain timing — overridden by state/longitude
}

/// Which weight set the aggregator blends with. §7.1.
public enum ConditionsRegime: String, Equatable, Sendable {
    case normal
    case spawn
    case tailwater

    public var badgeLabel: String {
        switch self {
        case .normal:    return "Normal"
        case .spawn:     return "Spawn run"
        case .tailwater: return "Tailwater"
        }
    }
}

/// Final banding of a 0–100 score. Thresholds match the legacy engine. §7.3.
public enum ConditionsBand: String, Equatable, Sendable {
    case poor  = "Poor"
    case fair  = "Fair"
    case good  = "Good"
    case prime = "Prime"

    public init(score: Int) {
        switch score {
        case 80...:   self = .prime
        case 65..<80: self = .good
        case 50..<65: self = .fair
        default:      self = .poor
        }
    }
}

/// Sediment (brown mud) vs algal (green bloom) turbidity. Algal kills the
/// sightline ~2× sooner than the same FNU of sediment. §5.1. When the data
/// source can't tell, `.unknown` uses the sediment curve + a confidence hit.
public enum TurbidityType: String, Equatable, Sendable {
    case sediment
    case algal
    case unknown
}

/// Spawn-targeting tier. Tier-3 never contributes to the spawn score. §5.2 / §9.
public enum SpeciesTier: Int, Equatable, Sendable {
    case tier1 = 1   // classic shallow spawn-run targets — reward strongly
    case tier2 = 2   // river/flood spawners — score staging, not the spawn act
    case tier3 = 3   // never a warm-water spawn run
}

/// Confidence banding for the displayed Low/Med/High chip. §8.
public enum ConfidenceBand: String, Equatable, Sendable {
    case low    = "Low"
    case medium = "Med"
    case high   = "High"

    public init(score: Int) {
        switch score {
        case 75...:   self = .high
        case 45..<75: self = .medium
        default:      self = .low
        }
    }
}

/// Tailwater dam-generation intensity during the fishing window. §5.7.
public enum GenerationLevel: String, Equatable, Sendable {
    case low        // low/steady — settled, clear, fish roam shallow
    case moderate   // fish pin to seams/breaks
    case high       // muddy, fast — gate candidate
}

/// Direction of a 12-hour barometric move. §5.8.
public enum PressureMovement: String, Equatable, Sendable {
    case rising
    case steady
    case falling
}
