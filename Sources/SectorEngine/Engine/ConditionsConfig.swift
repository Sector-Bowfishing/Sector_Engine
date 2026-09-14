//
//  ConditionsConfig.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Every threshold the engine uses lives here — nothing is inlined in a scorer.
//  These are the research-backed starting defaults (see
//  docs/bowfishing-conditions-research.md); they're meant to be calibrated from
//  real user logs later, so they're data, not code. §14.
//

import Foundation

/// The nine weighted factors. Also the stable key used for breakdown rows and
/// weight renormalization when a factor is missing.
public enum FactorKey: String, CaseIterable, Equatable, Sendable {
    case clarity
    case spawn
    case darkness
    case wind
    case waterTemp
    case level
    case current
    case pressure
    case sky
    /// Humidity, scored as FOG RISK — humidity itself barely moves fish, but
    /// fog on the water ends a bowfishing night because you can't shoot or run
    /// what you can't see. Added so every dashboard tile feeds the score.
    case humidity

    public var displayName: String {
        switch self {
        case .clarity:   return "Water clarity"
        case .spawn:     return "Spawn activity"
        case .darkness:  return "Darkness / moon"
        case .wind:      return "Wind"
        case .waterTemp: return "Water temp"
        case .level:     return "Water level"
        case .current:   return "Current / generation"
        case .pressure:  return "Pressure"
        case .sky:       return "Sky & temp"
        case .humidity:  return "Humidity / fog"
        }
    }
}

/// A complete regime weight set. Must sum to 1.0 across all nine factors
/// (asserted in tests); renormalized at runtime when a factor is absent. §7.2.
public struct WeightSet: Equatable, Sendable {
    public var clarity: Double
    public var spawn: Double
    public var darkness: Double
    public var wind: Double
    public var waterTemp: Double
    public var level: Double
    public var current: Double
    public var pressure: Double
    public var sky: Double
    public var humidity: Double = 0.03

    public func weight(for key: FactorKey) -> Double {
        switch key {
        case .clarity:   return clarity
        case .spawn:     return spawn
        case .darkness:  return darkness
        case .wind:      return wind
        case .waterTemp: return waterTemp
        case .level:     return level
        case .current:   return current
        case .pressure:  return pressure
        case .sky:       return sky
        case .humidity:  return humidity
        }
    }

    /// Sum of the nine PRIMARY weights (must be 1.0). Humidity/fog is a small
    /// add-on (0.03) deliberately NOT included — the true applied total is 1.03,
    /// and the aggregator renormalizes over all present keys (humidity included),
    /// so this name makes clear the 0.03 is intentional, not a rounding error to
    /// "fix". §7.2.
    public var sumExcludingHumidity: Double {
        clarity + spawn + darkness + wind + waterTemp + level + current + pressure + sky
    }
}

public struct ConditionsConfig: Sendable {

    public static let `default` = ConditionsConfig()

    // MARK: - Clarity (§5.1)
    public struct Clarity: Sendable {
        /// USGS default Secchi regression: secchi_ft = a * FNU^b.
        public var secchiCoefA: Double = 11.123
        public var secchiExpB: Double = -0.637
        /// Algal bloom kills the sightline ~2× sooner than sediment.
        public var algalSecchiMultiplier: Double = 0.5
        /// Rain-decay fallback when no turbidity gage: secchi = base * exp(-k * rain48h).
        /// Tailwaters and rivers blow out fast (little dilution volume); a large
        /// reservoir's main pool holds a foot-plus of sightline through ordinary
        /// rain because only the creek arms muddy up. So the decay — and a
        /// visibility floor — depend on the water body (§5.1, audit 2026-08-06).
        public var fallbackBaseClearFt: Double = 4.0
        /// Tailwater / river decay (aggressive — no dilution).
        public var fallbackRainDecayK: Double = 0.9
        /// Reservoir main-pool decay (gentle — big volume dilutes runoff).
        public var reservoirRainDecayK: Double = 0.4
        /// Reservoir clarity never falls below this in the fallback: a big lake
        /// still gives ~a foot of sightline after a normal rain. Kept just ABOVE
        /// the blown-out gate (Gates.blownOutVisibilityFt = 1.0) so a no-gage
        /// reservoir estimate can't floor straight INTO the blown-out cap — only
        /// its muddy creek arms actually blow out. Tailwaters have no floor —
        /// they really do blow out to zero.
        public var reservoirVisibilityFloorFt: Double = 1.1
        /// No-gage clarity is a guess, not a measurement — it must never read
        /// Prime. The fallback's score is capped here; its seeability component
        /// is capped by Seeability.estimatedClarityComponentCap. §5.1/§14.
        public var estimatedScoreCap: Double = 70
        /// Saturating visibility→score breakpoints (ft, score). Linear between.
        public var curve: [(ft: Double, score: Double)] = [
            (0.0, 0), (1.0, 15), (2.0, 45), (3.0, 75), (4.0, 92), (8.0, 100),
        ]
        /// Gin-clear "spooky water" nudge.
        public var ginClearFt: Double = 12.0
        public var ginClearPenalty: Double = 3.0
        public var ginClearMaxWindMph: Double = 3.0
    }

    // MARK: - Seeability ceiling ("can I see fish through the surface?")
    // The build philosophy is *visibility-gated*: clarity + surface calm cap the
    // whole score, they don't just vote. Without this a weighted average lets a
    // pile of "good" factors paper over water you literally can't shoot. The
    // ceiling = 100 · clarityComponent · windComponent.
    public struct Seeability: Sendable {
        public var enabled: Bool = true
        /// (visibility_ft, 0…1) breakpoints — how well you can see down.
        public var clarityCurve: [(ft: Double, factor: Double)] = [
            (0, 0.25), (1, 0.45), (2, 0.65), (3, 0.82), (4, 1.0),
        ]
        /// (windMph, 0…1) breakpoints — chop kills the downward sightline.
        public var windCurve: [(mph: Double, factor: Double)] = [
            (7, 1.0), (12, 0.88), (15, 0.72), (20, 0.45), (30, 0.25),
        ]
        /// WMO weather-code → 0…1 — rain on the surface + incoming runoff wreck
        /// the sightline *right now* (independent of the turbidity gage / 3-day
        /// rain total). Default 1.0 for any code not listed.
        public var weatherComponent: [Int: Double] = [
            0: 1.0, 1: 1.0, 2: 1.0, 3: 0.95,
            45: 0.8, 48: 0.8,                                   // fog
            51: 0.9, 53: 0.85, 55: 0.8, 56: 0.85, 57: 0.8,     // drizzle
            61: 0.8, 66: 0.7, 80: 0.75,                         // light rain / showers
            63: 0.6, 81: 0.55,                                  // moderate rain
            65: 0.45, 82: 0.4,                                  // heavy rain
            71: 0.7, 73: 0.6, 75: 0.5, 77: 0.6, 85: 0.65, 86: 0.5, // snow
            95: 0.3, 96: 0.3, 99: 0.3,                          // thunderstorm
        ]
        public var defaultWeatherComponent: Double = 1.0
        /// When clarity is only estimated (no turbidity gage), the component
        /// can't claim the full "definitely can see" 1.0 — unknown water must
        /// not hold a perfect ceiling over the whole score.
        public var estimatedClarityComponentCap: Double = 0.85
    }

    // MARK: - Spawn (§5.2)
    public struct Spawn: Sendable {
        /// Spawn score at/above this triggers SPAWN regime (also the boost floor).
        public var regimeThreshold: Double = 60
        /// Spawn detection genuinely needs water temperature. When it's only an
        /// estimate (no temp gage) we damp the intensity so a guessed-warm summer
        /// night can't manufacture a full-strength spawn run. §3/§14.
        public var estimatedTempDamp: Double = 0.6
        /// Rising-water amplifier for flood-dependent spawners (capped). §5.2.
        public var floodBonusPerFt: Double = 0.5     // per ft of 12h rise
        public var floodBonusCap: Double = 1.2
        public var floodFallingFloor: Double = 0.7   // falling water dampens flood spawners
        /// Tier-2 staging: warm slow backwater, scored lower than a true spawn act.
        public var stagingTempFloorF: Double = 70
        public var stagingMaxScore: Double = 55
        /// Date-window soft taper (days of fade beyond the hard window edge).
        public var windowTaperDays: Double = 14
    }

    // MARK: - Darkness / moon (§5.3)
    public struct Darkness: Sendable {
        public var astroDarkBonus: Double = 5        // window starts after true dark
        public var solunarTiebreaker: Double = 2     // ±2 pt max, near-zero weight
        /// cloudCancel = clamp((cloud-knee)/span,0,1) * cityGlow term.
        public var cloudKneePct: Double = 50
        public var cloudSpanPct: Double = 50
    }

    // MARK: - Wind (§5.4) — calm is best for sight-shooting
    public struct Wind: Sendable {
        /// (maxMph, score) bands, ascending. Score applies up to maxMph.
        /// Bowfishing is a SIGHT sport — you shoot through the surface, so chop is
        /// the enemy. Under ~4 mph is genuinely prime; by 7 mph a working chop is
        /// up and the score is a real drag (not near-prime); past ~10 mph most of
        /// the lake is unshootable and only protected pockets stay readable.
        public var bands: [(maxMph: Double, score: Double)] = [
            (4, 100), (7, 68), (11, 40), (15, 18), (20, 8),
        ]
        public var aboveTopScore: Double = 5         // > last band (gate candidate)
        public var gustPenaltyMax: Double = 15
        /// Gust counts as "<<" sustained once it exceeds sustained by this much.
        public var gustExcessForFullPenalty: Double = 12
    }

    // MARK: - Water temp (§5.5)
    public struct WaterTemp: Sendable {
        /// (maxF, score) bands, ascending.
        public var bands: [(maxF: Double, score: Double)] = [
            (50, 10), (60, 35), (68, 70), (82, 100), (88, 80),
        ]
        public var aboveTopScore: Double = 60
    }

    // MARK: - Water level / stage trend (§5.6)
    public struct Level: Sendable {
        public var stableBandFt: Double = 0.2        // |Δ12h| ≤ this = stable
        public var gentleRiseMaxFt: Double = 1.0     // rise ≤ this = gently rising
        public var fastFallFt: Double = -1.0         // ≤ this = falling fast
        public var stableScore: Double = 85
        public var gentleRiseScore: Double = 100
        public var strongRiseScore: Double = 60
        // Falling water is a NEGATIVE for bowfishing: you need fish up on the
        // flats in inches of water, and a drawdown pulls them off the shallows
        // out of range. Scored below the 50 baseline so it reads as a real drag,
        // not the mild positive rod-fishing would give it. Rising/stable stay good.
        public var slowFallScore: Double = 40
        public var fastFallScore: Double = 20
    }

    // MARK: - Current / generation (§5.7)
    public struct Current: Sendable {
        public var nonTailwaterScore: Double = 90
        // A CURVE, not a slope. Generation isn't purely a penalty below a dam:
        // moderate flow stacks fish on points and seams and is the best of it.
        // Settled water still scores well (clear, fish roam shallow) and heavy
        // flow still scores badly (muddy, fast, hard to see) — but the peak sits
        // in the middle, where a bowfisher actually wants to be.
        public var lowGenScore: Double = 90
        public var moderateGenScore: Double = 100
        public var highGenScore: Double = 25
        /// When generation isn't classified but a discharge trend exists, map the
        /// 12h cfs trend → level using these relative knees.
        public var risingCfsModerateFrac: Double = 0.10   // +10% over 12h → moderate
        public var risingCfsHighFrac: Double = 0.40       // +40% over 12h → high
    }

    // MARK: - Pressure (§5.8) — inHg
    public struct Pressure: Sendable {
        public var steadyLowInHg: Double = 29.9
        public var steadyHighInHg: Double = 30.4
        public var veryHighInHg: Double = 30.5
        public var veryLowInHg: Double = 29.6
        // Brand stance (matches the pressure infographic + detail sheet):
        // rising/steady = fish active, falling = bite shuts down ahead of weather.
        public var steadyNormalScore: Double = 90
        public var fallingScore: Double = 55
        public var risingFastScore: Double = 85
        // A very HIGH glass is the calm, clear, dry, cloudless air a bowfisher
        // wants — it must not score BELOW an ordinary steady day (it used to, at
        // 60, which read as a penalty on the best weather there is).
        public var veryHighScore: Double = 88
        // A very LOW glass is a deep unsettled low under/ahead of weather: worse
        // than a routine fall, so it stays monotonic (< fallingScore) rather than
        // jumping back UP to 60 as the old shared extremeScore did.
        public var veryLowScore: Double = 50
        // Steady pressure sitting OUT of the comfortable band (e.g. a flat 30.45)
        // — neither the optimum nor an extreme swing.
        public var extremeScore: Double = 60
    }

    // MARK: - Sky & temp (§5.9)
    public struct Sky: Sendable {
        public var comfortLowF: Double = 45
        public var comfortHighF: Double = 90
        public var clearBonus: Double = 8
        /// WMO weather-code → 0…1 sky-clarity factor.
        public var codeScores: [Int: Double] = [
            0: 1.0, 1: 1.0, 2: 0.85, 3: 0.70,
            45: 0.60, 48: 0.60,
            51: 0.40, 53: 0.40, 55: 0.40, 56: 0.40, 57: 0.40,
            61: 0.25, 63: 0.25, 65: 0.25, 66: 0.25, 67: 0.25, 80: 0.25, 81: 0.25, 82: 0.25,
            71: 0.30, 73: 0.30, 75: 0.30, 77: 0.30, 85: 0.30, 86: 0.30,
            95: 0.10, 96: 0.10, 99: 0.10,
        ]
        public var defaultCodeScore: Double = 0.6
    }

    // MARK: - Gates / vetoes (§6)
    public struct Gates: Sendable {
        public var blownOutVisibilityFt: Double = 1.0
        public var blownOutCap: Double = 25
        public var highWindMph: Double = 20
        public var highWindCap: Double = 30
        public var tailwaterHighGenCap: Double = 30
        public var coldWaterF: Double = 48
        public var coldWaterCap: Double = 35
        /// A gage-less lake usually scores off a MODELED/air water-temp estimate,
        /// so the live-only cold gate above never fired and a 40°F clear-calm-dark
        /// winter night could blend to Prime. Give the estimate its own, colder
        /// trigger and a SOFTER cap (it's a guess, not a measurement): clearly
        /// cold estimated water can't read better than Fair, but a marginal
        /// estimate near the live threshold isn't penalized on a guess. §3/§6.
        public var coldWaterEstimatedF: Double = 45
        public var coldWaterEstimatedCap: Double = 50
        /// Thunderstorms — you don't bowfish under lightning, and the water's
        /// blown out anyway. WMO codes 95/96/99. The gate only fires when the
        /// storm code is CORROBORATED (measurable precip OR genuinely heavy cloud)
        /// — a lone categorical code is never allowed to veto the score, since
        /// Open-Meteo's code over-reports storms on clear, dry nights.
        public var stormWeatherCodes: Set<Int> = [95, 96, 99]
        public var stormCap: Double = 30
        public var stormMinCloudPct: Double = 70    // cloud ≥ this corroborates a storm code
        public var stormMinPrecipInch: Double = 0.001  // any measurable precip corroborates
        /// Active NWS safety WARNING (tornado / severe thunderstorm / flash flood /
        /// marine) — you don't launch under one whatever the forecast says. A
        /// meteorologist issued it for something happening NOW that the forecast
        /// model routinely misses, so it's authoritative and hard-caps to Poor.
        public var severeWarningCap: Double = 25
        /// Rain measurably falling NOW, independent of the (often-wrong) categorical
        /// code. The storm gate above needs a 95/96/99 code AND corroboration; this
        /// catches active rain the code mislabels. Deliberately conservative so a
        /// passing drizzle doesn't tank an otherwise-good night.
        public var rainNowInch: Double = 0.10
        public var rainNowCap: Double = 40
        /// Fog on the water ends a bowfishing night — you can't shoot what you can't
        /// see, and you can't run a boat blind. Fog is already scored as a low-weight
        /// factor (HumidityFactor, 0.03), but a thing that ENDS the night is a hard
        /// limiter, not a tie-breaker, so it also gates. Driven by the forecast
        /// air–dewpoint spread (small spread → fog forms). Graduated: a tight spread
        /// caps hard (fog likely); a moderate spread soft-caps (patchy — never Prime).
        /// Fires only when a dewpoint series exists (`fogSpreadF != nil`); raw RH alone
        /// is too noisy to gate on and stays a factor-only nudge.
        public var fogLikelySpreadF: Double = 2.0
        public var fogLikelyCap: Double = 35
        public var fogPatchySpreadF: Double = 4.0
        public var fogPatchyCap: Double = 62
    }

    // MARK: - Spawn boost (§7.3)
    public struct SpawnBoost: Sendable {
        public var perPointAboveThreshold: Double = 0.3
        public var maxBoost: Double = 12
    }

    // MARK: - Confidence (§8)
    public struct Confidence: Sendable {
        public var base: Double = 100
        public var noTurbidityGage: Double = 20
        public var estimatedWaterTemp: Double = 15
        public var tailwaterNoGenForecast: Double = 15
        public var perForecastDay: Double = 10
        public var perForecastDayCap: Double = 50
        public var unknownTurbidityNearGate: Double = 10
        public var strongSpawnBonus: Double = 10
        /// A spawn call built on an estimated (no-gage) water temp can't read
        /// "High" — cap it into the Medium band. §8 plausibility guard.
        public var spawnEstimatedConfidenceCeiling: Int = 74
    }

    // MARK: - Regime weight sets (§7.2)
    public struct Weights: Sendable {
        public var normal = WeightSet(clarity: 0.26, spawn: 0.04, darkness: 0.18, wind: 0.18,
                                      waterTemp: 0.12, level: 0.08, current: 0.04, pressure: 0.06, sky: 0.04)
        public var spawn = WeightSet(clarity: 0.20, spawn: 0.34, darkness: 0.08, wind: 0.12,
                                     waterTemp: 0.10, level: 0.08, current: 0.04, pressure: 0.02, sky: 0.02)
        public var tailwater = WeightSet(clarity: 0.22, spawn: 0.04, darkness: 0.14, wind: 0.14,
                                         waterTemp: 0.10, level: 0.10, current: 0.18, pressure: 0.04, sky: 0.04)

        public func set(for regime: ConditionsRegime) -> WeightSet {
            switch regime {
            case .normal:    return normal
            case .spawn:     return spawn
            case .tailwater: return tailwater
            }
        }
    }

    public var clarity = Clarity()
    public var seeability = Seeability()
    public var spawn = Spawn()
    public var darkness = Darkness()
    public var wind = Wind()
    public var waterTemp = WaterTemp()
    public var level = Level()
    public var current = Current()
    public var pressure = Pressure()
    public var sky = Sky()
    public var gates = Gates()
    public var spawnBoost = SpawnBoost()
    public var confidence = Confidence()
    public var weights = Weights()

    public init() {}
}
