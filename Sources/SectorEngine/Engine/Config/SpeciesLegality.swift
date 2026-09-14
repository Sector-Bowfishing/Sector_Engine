//
//  SpeciesLegality.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Per the project decision, legality is a global denylist + disclaimer rather
//  than a per-state table. Protected/closed-by-default species (paddlefish,
//  American shad, sturgeon) are NEVER auto-recommended as a target; species with
//  known seasonal/state closures ("check") may be surfaced but always with a
//  "verify your local regs" disclaimer. §9.
//

import Foundation

public enum SpeciesLegality: Sendable {

    /// May this species be surfaced as a recommended target at all?
    /// `.no` (protected by default) → never.
    public static func canAutoRecommend(_ species: SpawnSpecies) -> Bool {
        species.legalByDefault != .no
    }

    /// Does surfacing this species require the legality disclaimer?
    public static func needsDisclaimer(_ species: SpawnSpecies) -> Bool {
        species.legalByDefault == .check
    }

    public static let disclaimer = "Verify your state's bowfishing regulations before targeting this species — seasonal or local closures may apply."
}
