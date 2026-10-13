//
//  ConditionsScoreVersion.swift
//  Sector — the Conditions Score's explicit version (Phase 8 of the 2026-10-12 consolidation).
//
//  The customer-facing score had no version of its own: only the water-temperature model and the
//  clarity model were stamped. `ConditionsResponse.scoreVersion` now names the scoring semantics a
//  response was produced with, so a number on a phone can be traced to the code and rubric that
//  made it. Bump `current` whenever factor math, gates, bands, regime rules or the default
//  `ConditionsConfig` change customer-visible results (not for additive fields or fixes that
//  preserve numbers). Remote Config overrides are reported separately (`configSource`).
//

import Foundation

public enum ConditionsScoreVersion {
    /// v1 = the semantics served since the 2026-10-07 production baseline (`bc9e09fb`) plus the
    /// rain-gate and severe-warning-parity fixes restored on 2026-10-12.
    public static let current = "conditions-score-v1"

    /// The serving revision, when the platform tells us (Cloud Run sets `K_REVISION`).
    public static var engineRevision: String? {
        let env = ProcessInfo.processInfo.environment
        return env["SECTOR_ENGINE_REVISION"] ?? env["K_REVISION"] ?? env["SECTOR_ENGINE_COMMIT"]
    }
}
