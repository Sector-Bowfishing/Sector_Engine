//
//  ConditionsConfigOverrides.swift
//  SectorEngine
//
//  Phase 6 Stage 4: the tuning knobs Firebase Remote Config can drive at runtime.
//  ConditionsConfig itself has tuple fields (curves) that aren't Codable and knobs
//  we never want changed live, so Remote Config carries a small TYPED overrides
//  blob instead. The server starts from the compiled ConditionsConfig.default and
//  applies whatever overrides are present — anything omitted keeps its default.
//
//  This is the JSON you edit in the Firebase console under the `conditions_config`
//  parameter. Add a field here (+ apply it below) to expose another knob.
//

import Foundation

/// A partial weight set — any factor omitted keeps the base weight.
public struct WeightSetOverride: Codable, Equatable, Sendable {
    public var clarity: Double?
    public var spawn: Double?
    public var darkness: Double?
    public var wind: Double?
    public var waterTemp: Double?
    public var level: Double?
    public var current: Double?
    public var pressure: Double?
    public var sky: Double?
    public var humidity: Double?

    func apply(to base: WeightSet) -> WeightSet {
        var w = base
        if let v = clarity { w.clarity = v }
        if let v = spawn { w.spawn = v }
        if let v = darkness { w.darkness = v }
        if let v = wind { w.wind = v }
        if let v = waterTemp { w.waterTemp = v }
        if let v = level { w.level = v }
        if let v = current { w.current = v }
        if let v = pressure { w.pressure = v }
        if let v = sky { w.sky = v }
        if let v = humidity { w.humidity = v }
        return w
    }
}

/// The Remote Config payload. Everything optional — omit to keep the compiled default.
public struct ConditionsConfigOverrides: Codable, Equatable, Sendable {
    // The biggest lever: per-regime factor weights.
    public var weightsNormal: WeightSetOverride?
    public var weightsSpawn: WeightSetOverride?
    public var weightsTailwater: WeightSetOverride?

    // A few high-value scalar thresholds.
    public var spawnRegimeThreshold: Double?
    public var clarityEstimatedScoreCap: Double?
    public var darknessAstroDarkBonus: Double?
    public var seeabilityEnabled: Bool?

    /// Problems that make this payload unsafe to apply; empty means valid.
    ///
    /// Remote Config is edited by hand in the Firebase console, and a typo used
    /// to go live on every instance within ten minutes — zeroed or negative
    /// weights made every lake in that regime score 0 "Poor", with no error
    /// anywhere. A payload with any problem is rejected whole and the last good
    /// config stays in force.
    public func problems(against base: ConditionsConfig = .default) -> [String] {
        var out: [String] = []
        func checkWeights(_ name: String, _ w: WeightSetOverride?) {
            guard let w else { return }
            let provided: [(String, Double?)] = [
                ("clarity", w.clarity), ("spawn", w.spawn), ("darkness", w.darkness), ("wind", w.wind),
                ("waterTemp", w.waterTemp), ("level", w.level), ("current", w.current),
                ("pressure", w.pressure), ("sky", w.sky), ("humidity", w.humidity),
            ]
            for (key, value) in provided {
                guard let value else { continue }
                if !value.isFinite || value < 0 || value > 1 {
                    out.append("\(name).\(key)=\(value) must be within 0...1")
                }
            }
        }
        checkWeights("weightsNormal", weightsNormal)
        checkWeights("weightsSpawn", weightsSpawn)
        checkWeights("weightsTailwater", weightsTailwater)

        // The merged weights for each regime must still add up to a sane total.
        let merged = apply(to: base).weights
        for (name, set) in [("normal", merged.normal), ("spawn", merged.spawn), ("tailwater", merged.tailwater)] {
            let total = FactorKey.allCases.reduce(0.0) { $0 + set.weight(for: $1) }
            if !total.isFinite || total < 0.5 || total > 1.5 {
                out.append("weights.\(name) sum \(total) must be within 0.5...1.5")
            }
        }

        if let v = spawnRegimeThreshold, !(v.isFinite && (0...100).contains(v)) {
            out.append("spawnRegimeThreshold=\(v) must be within 0...100")
        }
        if let v = clarityEstimatedScoreCap, !(v.isFinite && (0...100).contains(v)) {
            out.append("clarityEstimatedScoreCap=\(v) must be within 0...100")
        }
        if let v = darknessAstroDarkBonus, !(v.isFinite && (-50...50).contains(v)) {
            out.append("darknessAstroDarkBonus=\(v) must be within -50...50")
        }
        return out
    }

    /// Merge onto a base config (normally `ConditionsConfig.default`).
    public func apply(to base: ConditionsConfig) -> ConditionsConfig {
        var c = base
        if let w = weightsNormal { c.weights.normal = w.apply(to: c.weights.normal) }
        if let w = weightsSpawn { c.weights.spawn = w.apply(to: c.weights.spawn) }
        if let w = weightsTailwater { c.weights.tailwater = w.apply(to: c.weights.tailwater) }
        if let v = spawnRegimeThreshold { c.spawn.regimeThreshold = v }
        if let v = clarityEstimatedScoreCap { c.clarity.estimatedScoreCap = v }
        if let v = darknessAstroDarkBonus { c.darkness.astroDarkBonus = v }
        if let v = seeabilityEnabled { c.seeability.enabled = v }
        return c
    }
}
