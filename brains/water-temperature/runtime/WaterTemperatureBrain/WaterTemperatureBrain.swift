//
//  WaterTemperatureBrain.swift
//  Sector — [CONDITION]Brain for water temperature ("water-temp")
//
//  Answers ONE question: what is the water temperature doing? It does not judge
//  fish activity, species behaviour or fishing quality — those are downstream.
//
//  INTEGRATION, NOT NEW SCIENCE. Every number comes from the production path:
//    · measurement — the lake's own configured sensor (LakeTempSensorService),
//      else a USGS lake gauge ≤ 10 mi (WaterLevelService.nearestWaterTemp):
//      the same selection ConditionsSnapshot makes for /conditions;
//    · model — WaterTemperatureService.model (surface-energy-balance-v2, k = 0.09);
//    · decision — WaterTemperatureResolver.resolve (shown = scored, Stage 2E).
//  The selection is restated here (not shared) because changing
//  ConditionsSnapshot would touch the customer path; WaterTemperatureBrainTests
//  pins the resolver and directory semantics it relies on.
//
//  Three things are kept apart on purpose:
//    · MODEL / SCIENCE VALIDATION  → /validation/water-temp (+ per lake where real)
//    · LAKE READINESS              → evidence class of each lake (static)
//    · RUNTIME HEALTH              → /health/brains/water-temp (this run)
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
import SectorEngine
#endif

public enum WaterTemperatureBrain {

    public static let brainId = "water-temp"
    public static let slot = "waterTemp"
    public static let snapshotField = "waterTemperature"
    /// Brain integration release (not the science model).
    public static let brainVersion = "1.0"
    /// A state older than two former 3-hourly runs is stale (unchanged threshold; the Orchestrator starts the job when this rule says so).
    public static let staleAfterHours = 6.0
    /// Published in /health/jobs/water-temp-brain: there is no scheduler; the Brain Orchestrator starts the job when the state is stale.
    public static let schedule = "orchestrator-started when stale (no scheduler)"
    public static var modelVersion: String { WaterTemperatureResolver.modelVersion }
    public static let baseModel = "surface-energy-balance-v2"

    // MARK: Engine-owned vocabularies (published in the registry)

    /// EVIDENCE CLASS — what evidence stands behind this lake's value. Static; never runtime health
    /// and never readiness (Brain Platform contract §3: readiness is the promotion ladder, not an
    /// evidence class — the pre-contract PRODUCTION/BETA readiness values were this field).
    public enum EvidenceClass: String, CaseIterable {
        /// Lake has its own configured authoritative in-lake surface sensor (directory `tempSensor`).
        /// Production shows that measurement whenever it is fresh (≤ 6 h); the model otherwise.
        case sensor = "sensor"
        /// Production serves the model value. The model is validated only globally
        /// (leave-one-lake-out on 17 OTHER USGS-gauged lakes); no lake-specific held-out evidence.
        case modeled = "modeled"
    }

    public static let evidenceClassDefinitions: [String: String] = [
        EvidenceClass.sensor.rawValue: "Lake has its own configured authoritative in-lake surface sensor; production shows the measurement when ≤ 6 h old, the model otherwise.",
        EvidenceClass.modeled.rawValue: "Production serves the modelled value. Model validated globally only (leave-one-lake-out, 17 USGS lake gauges); no lake-specific held-out validation.",
    ]

    /// LAKE READINESS (contract ladder). Every lake is CALIBRATION: the brain is internal and
    /// unscheduled, its model is validated globally only, and the Level-4 protected gate failed
    /// (score 3/10). Promotion to BETA/VALIDATED is a separate, evidence-backed decision.
    public static let lakeReadiness = "CALIBRATION"
    public static let readinessDefinitions: [String: String] = [
        lakeReadiness: "Published for every lake: production's own number (shown = scored), model validated globally only, Level-4 protected validation not passed, brain unscheduled. Evidence class is in `evidenceClass`.",
    ]

    /// STATE KIND — production vocabulary (`ResolvedWaterTemperatureState.Kind`), verbatim.
    public static let stateKindDefinitions: [String: String] = [
        "measured": "OBSERVED — a lake sensor reading ≤ 6 h old and ≤ 15 mi away (production resolver).",
        "modeled": "MODELED — surface-energy-balance-v2 value for the lake-local today; no observation correction.",
        "unavailable": "UNKNOWN — no fresh measurement and no model value. Never filled in.",
    ]

    public static func observationType(forKind kind: String) -> String {
        switch kind {
        case "measured": return "OBSERVED"
        case "modeled": return "MODELED"
        default: return "UNKNOWN"
        }
    }

    static func evidenceClass(for lake: DirectoryLake) -> EvidenceClass {
        lake.tempSensor == nil ? .modeled : .sensor
    }

    // MARK: Protected development lakes (Stage 3C.3, 2026-10-11): real per-lake validation status

    struct ProtectedLake { let lakeId: String; let holdout: Int; let calibration: Int }
    static let protectedLakes: [ProtectedLake] = [
        .init(lakeId: "Guntersville|AL", holdout: 90, calibration: 106),
        .init(lakeId: "Wheeler|AL", holdout: 18, calibration: 14),
        .init(lakeId: "Wilson|AL", holdout: 2, calibration: 0),
        .init(lakeId: "Pickwick Lake|TN", holdout: 57, calibration: 92),
    ]
    static let protectedTruthRequiredPerLake = 25
    static let protectedTruthRequiredTotal = 150
    static let artifactIOS = "Sector iOS repo docs/intelligence/water-temp/"

    // MARK: - Inputs (what production fetches for /conditions)

    struct LakeInputs {
        let lake: DirectoryLake
        var measurement: WaterLevelReading?
        /// "lakeSensor" | "nearbyUsgsLakeGauge"; nil when no reading came back.
        var measurementOrigin: String?
        var model: WaterTempModel?
        var modelFetchFailed: Bool
    }

    static func fetchInputs(for lake: DirectoryLake) async -> LakeInputs {
        let coordinate = lake.coordinate
        async let measured = withDeadline(9, "brain.waterTemp") { () -> (WaterLevelReading, String)? in
            if lake.tempSensor != nil, let r = await LakeTempSensorService.latest(for: lake) { return (r, "lakeSensor") }
            if let r = try? await WaterLevelService.shared.nearestWaterTemp(near: coordinate) { return (r, "nearbyUsgsLakeGauge") }
            return nil
        }
        async let model = withDeadline(9, "brain.waterTempModel") { await WaterTemperatureService.model(near: coordinate) }
        let m = await measured
        let mo = await model
        return LakeInputs(lake: lake, measurement: m?.0, measurementOrigin: m?.1, model: mo, modelFetchFailed: mo == nil)
    }

    // MARK: - State

    public struct ForecastDay: Codable, Equatable {
        /// Lake-local calendar date (the model is daily).
        public var at: String
        public var tempF: Double
    }

    public struct State: Codable, Equatable {
        public var lakeId: String
        /// Production vocabulary: measured | modeled | unavailable.
        public var kind: String
        /// OBSERVED | MODELED | UNKNOWN (normalised alias of `kind`).
        public var observationType: String
        /// sensor | modeled — the static evidence behind this lake's value (not readiness).
        public var evidenceClass: String
        public var currentTempF: Double?
        public var unit: String = "degF"
        public var lakeLocalDate: String?
        public var lakeTimeZone: String?
        public var spatialSupport: String
        /// Model day-over-day change (lake-local today − yesterday). Basis in `trendBasis`.
        public var trend24hF: Double?
        public var trendBasis: String?
        /// The sensor's own trend label, verbatim, when the shown value is a measurement.
        public var sensorTrend: String?
        public var lastObservationAt: String?
        public var sourceAgeHours: Double?
        public var measurementDistanceMiles: Double?
        /// Production does not state sensor depth; nil = unknown.
        public var depthM: Double?
        /// Production model's value for the same lake-local day (also when a measurement is shown).
        public var modelCurrentF: Double?
        /// measured − modelled, only when a measurement is shown. A live residual, not validation.
        public var measuredMinusModelF: Double?
        public var forecast: [ForecastDay]?
        /// The lake has a configured sensor but no fresh reading was shown.
        public var evidenceStale: Bool
        public var stale: Bool
        public var provenance: BrainProvenance
    }

    static func r1(_ v: Double?) -> Double? { v.map { ($0 * 10).rounded() / 10 } }
    static func r2(_ v: Double?) -> Double? { v.map { ($0 * 100).rounded() / 100 } }

    static func state(from inputs: LakeInputs, resolved: ResolvedWaterTemperatureState, now: Date,
                      processingVersion: String?) -> State {
        let lake = inputs.lake
        let kind = resolved.kind.rawValue
        var flags = resolved.qualityFlags
        let model = inputs.model

        // Model trend (day-over-day, lake-local) and forecast (days after the lake-local today).
        var trend: Double? = nil
        var forecast: [ForecastDay]? = nil
        // Production's forecast-night rule (ConditionsForecast.buildNights `gaugeAnchorF`): when a
        // measurement is shown, later model days are shifted by (measured − modelled today).
        let anchorF: Double = {
            guard resolved.kind == .measured, let v = resolved.valueF, let m = model?.currentF else { return 0 }
            return v - m
        }()
        if let m = model, let today = m.currentLocalDate,
           let i = m.series.lastIndex(where: { $0.localDate == today }) {
            if i > 0 { trend = m.series[i].waterF - m.series[i - 1].waterF }
            let future = m.series[(i + 1)...].compactMap { d -> ForecastDay? in
                guard let ld = d.localDate else { return nil }
                return ForecastDay(at: ld, tempF: r1(d.waterF + anchorF)!)
            }
            forecast = future.isEmpty ? nil : future
            if forecast != nil {
                flags.append("forecastModelOnly:notSeparatelyValidated")
                if resolved.kind == .measured { flags.append("forecastGaugeAnchored") }
            }
        } else if model != nil {
            flags.append("modelLocalDateUnknown:noTrendNoForecast")
        }
        if inputs.modelFetchFailed { flags.append("modelUnavailable") }

        let sensorConfigured = lake.tempSensor != nil
        let evidenceStale = sensorConfigured && kind != "measured"
        if evidenceStale { flags.append("lakeSensorNoFreshReading") }
        if kind == "measured", inputs.measurementOrigin == "nearbyUsgsLakeGauge" { flags.append("measurementFromNearbyGauge") }

        var sources: [BrainSourceRef] = []
        if let r = inputs.measurement {
            sources.append(BrainSourceRef(sourceType: resolved.kind == .measured ? resolved.sourceKind.rawValue
                                                   : (r.provider == "USACE CWMS" ? "cwmsLakeSensor" : "usgsLakeSensor"),
                                          sourceId: (r.provider == "USACE CWMS" ? "CWMS:" : "USGS:") + r.siteCode,
                                          lastObservationAt: BrainPlatform.iso(r.dateTime)))
        }
        if model != nil {
            sources.append(BrainSourceRef(sourceType: "energyBalanceModel", sourceId: "open-meteo-forecast",
                                          lastObservationAt: nil))
        }
        let evidence = evidenceClass(for: lake)
        let measuredShown = resolved.kind == .measured
        let ageHours = r2(resolved.ageHours)
        let isProtected = protectedLakes.contains { $0.lakeId == lake.id }

        return State(
            lakeId: lake.id, kind: kind, observationType: observationType(forKind: kind), evidenceClass: evidence.rawValue,
            currentTempF: r1(resolved.valueF), lakeLocalDate: resolved.lakeLocalDate,
            lakeTimeZone: model?.timeZoneIdentifier, spatialSupport: resolved.spatialSupport,
            trend24hF: r1(trend), trendBasis: trend == nil ? nil : "model:dailyChange(lakeLocal)",
            sensorTrend: measuredShown ? inputs.measurement.map { "\($0.trend)" } : nil,
            lastObservationAt: resolved.observedAt.map(BrainPlatform.iso), sourceAgeHours: ageHours,
            measurementDistanceMiles: measuredShown ? r2(resolved.distanceMiles) : nil, depthM: resolved.depthM,
            modelCurrentF: r1(model?.currentF),
            measuredMinusModelF: measuredShown ? r1(model.flatMap { m in resolved.valueF.map { $0 - m.currentF } }) : nil,
            forecast: forecast, evidenceStale: evidenceStale,
            stale: evidenceStale,
            provenance: BrainProvenance(
                brainId: brainId, brainVersion: brainVersion,
                modelVersion: resolved.kind == .measured ? nil : resolved.modelVersion ?? (model == nil ? nil : modelVersion),
                processingVersion: processingVersion, generatedAt: BrainPlatform.iso(now),
                sources: sources.isEmpty ? nil : sources,
                inputAgeHours: measuredShown ? ageHours : nil,
                readiness: lakeReadiness, qualityFlags: flags.isEmpty ? nil : flags,
                validationRef: isProtected ? "/lakes/\(BrainPlatform.lakeKey(lake.id))/validation/\(brainId)" : "/validation/\(brainId)"))
    }

    // MARK: - Profile

    public struct ObservationSource: Codable, Equatable { public var sourceKind: String; public var sourceId: String }

    public struct MeasurementRule: Codable, Equatable {
        public var maxAgeHours: Double
        public var maxDistanceMiles: Double
        public var lakeSensorFetchToleranceHours: Double
        public var nearbyGaugeMaxMiles: Double
    }

    public struct Profile: Codable, Equatable {
        public var lakeId: String
        public var schemaVersion: Int
        public var baseModel: String
        public var modelVersion: String
        /// Configured in-lake sensor (directory `tempSensor`); nearby USGS lake gauges are looked up live.
        public var observationSources: [ObservationSource]?
        public var nearbyGaugeLookup: Bool
        /// Production assimilation: none (a fresh measurement replaces the model; it does not correct it).
        public var assimilation: String
        /// Directory classification, verbatim (buoy | inSitu | satellite | limited) — not a readiness claim.
        public var directoryTempSource: String
        public var thermalClass: String?
        public var lakeType: String?
        public var measurementRule: MeasurementRule
        public var validation: [String: String]
        public var readiness: String
        /// sensor | modeled (static evidence; readiness is the ladder value above).
        public var evidenceClass: String
        public var knownLimitations: [String]
    }

    static func profile(for lake: DirectoryLake) -> Profile {
        var sources: [ObservationSource]? = nil
        if let s = lake.tempSensor {
            let parts = s.split(separator: ":", maxSplits: 2).map(String.init)
            if parts.first == "usgs", parts.count == 2 { sources = [.init(sourceKind: "usgsLakeSensor", sourceId: "USGS:\(parts[1])")] }
            else if parts.first == "cwms", parts.count == 3 { sources = [.init(sourceKind: "cwmsLakeSensor", sourceId: "CWMS:\(parts[1]):\(parts[2])")] }
        }
        var limits = [
            "Model validated globally only: leave-one-lake-out on 17 USGS lake gauges, held-out RMSE 3.40 °F, bias −0.06 °F (2026-09-23).",
            "Daily upper-surface value; no depth or thermal profile.",
            "Forecast days run the same model on forecast weather and are not separately validated.",
            "No observation assimilation in production: a fresh measurement replaces the model, it does not correct it.",
        ]
        var validation = ["ref": "/validation/\(brainId)"]
        if let p = protectedLakes.first(where: { $0.lakeId == lake.id }) {
            validation["lakeRef"] = "/lakes/\(BrainPlatform.lakeKey(lake.id))/validation/\(brainId)"
            limits.append("Protected development lake: Level-4 held-out validation not yet possible (holdout \(p.holdout) of \(protectedTruthRequiredPerLake) required).")
        }
        return Profile(lakeId: lake.id, schemaVersion: BrainPlatform.schemaVersion, baseModel: baseModel, modelVersion: modelVersion,
                       observationSources: sources, nearbyGaugeLookup: true, assimilation: "none",
                       directoryTempSource: lake.tempSource.rawValue, thermalClass: nil, lakeType: nil,
                       measurementRule: .init(maxAgeHours: WaterTemperatureResolver.measurementMaxAgeHours,
                                              maxDistanceMiles: WaterTemperatureResolver.measurementMaxDistanceMiles,
                                              lakeSensorFetchToleranceHours: LakeTempSensorService.maxAgeHours,
                                              nearbyGaugeMaxMiles: WaterLevelService.maxLakeTempGaugeMiles),
                       validation: validation, readiness: lakeReadiness, evidenceClass: evidenceClass(for: lake).rawValue, knownLimitations: limits)
    }

    // MARK: - Validation (documented evidence only; numbers are not recomputed here)

    public struct ValidationSummary: Codable, Equatable {
        public var brainId: String
        public var modelVersion: String
        public var validationVersion: String
        public var status: String
        public var lastRunAt: String?
        public var holdoutType: String?
        public var sampleCount: Int
        public var lakeCount: Int
        public var failedGates: [String]
        public var metrics: [String: Double?]
        public var metricUnits: [String: String]?
        public var modelHistory: [ModelHistory]?
        public var artifactRef: String?
        public var notes: [String]?
        public var researchCandidate: CandidateValidation?
    }

    public struct ModelHistory: Codable, Equatable { public var version: String; public var date: String; public var status: String }

    public struct CandidateValidation: Codable, Equatable {
        public var candidate: String
        public var status: String
        public var evidence: [String]
        public var protectedValidation: String
        public var artifactRef: String
    }

    static func fleetValidation() -> ValidationSummary {
        ValidationSummary(
            brainId: brainId, modelVersion: modelVersion, validationVersion: "calibration-2026-09-23",
            status: "GLOBAL_HOLDOUT_ONLY", lastRunAt: "2026-09-23",
            holdoutType: "leave-one-lake-out across 17 USGS lake gauges (one global parameter set)",
            sampleCount: 8110, lakeCount: 17,
            failedGates: ["LEVEL4_PROTECTED_TRUTH_INSUFFICIENT"],
            metrics: ["rmseF": 3.40, "maeF": nil, "biasF": -0.06, "pctDaysOffMoreThan5F": 14,
                      "worstMonthBiasF": -1.63, "seasonalBiasSpreadF": 2.69],
            metricUnits: ["rmseF": "°F", "maeF": "°F", "biasF": "°F", "pctDaysOffMoreThan5F": "%",
                          "worstMonthBiasF": "°F", "seasonalBiasSpreadF": "°F"],
            modelHistory: [.init(version: "air-lag k=0.20", date: "2026-09-23", status: "RETIRED"),
                           .init(version: modelVersion, date: "2026-09-23", status: "CURRENT")],
            artifactRef: "Sector iOS repo docs/decisions/2026-09-23-water-temperature-calibration.md",
            notes: ["Per-lake held-out errors were not preserved; the calibration script is in neither repo. MAE unknown.",
                    "Better on 15 of 17 lakes; slightly worse on Osoyoos (−1.2 °F) and Detroit Lake (−0.2 °F) than the retired model.",
                    "Level-4 protected validation (Guntersville, Wheeler, Wilson, Pickwick) not run: holdout 167 total but Wheeler 18 and Wilson 2 of 25 required (Stage 3C.3, 2026-10-11)."],
            researchCandidate: CandidateValidation(
                candidate: "Water Temp V2 = production M0 + Stage 3C.1 Arm A 2-state Kalman filter [x, b] + operational state engine",
                status: "RESEARCH — frozen 2026-10-11, NOT promoted, not running",
                evidence: ["Non-protected cross-station replay (8 lakes, 60 directions): weekly median RMSE improvement +1.18 °C vs the free model (Stage 3C.1).",
                           "Single-station replay (12 gauges): weekly +0.80 °C (Stage 3C/3C.2)."],
                protectedValidation: "NOT RUN — protected truth insufficient (Stage 3C.3)",
                artifactRef: artifactIOS + "WATER_TEMP_STAGE_3C3_PROTECTED_VALIDATION.md"))
    }

    static func protectedLakeValidation(_ p: ProtectedLake) -> ValidationSummary {
        ValidationSummary(
            brainId: brainId, modelVersion: modelVersion, validationVersion: "stage-3c3-2026-10-11",
            status: p.holdout >= protectedTruthRequiredPerLake ? "TRUTH_SUFFICIENT_FOR_LAKE_NOT_SCORED" : "INSUFFICIENT_TRUTH",
            lastRunAt: "2026-10-11", holdoutType: "protected historical holdout 2021-01 → 2026-06 (rule v3, main-body casts)",
            sampleCount: p.holdout, lakeCount: 1,
            failedGates: p.holdout >= protectedTruthRequiredPerLake ? ["LEVEL4_FOUR_LAKE_SUFFICIENCY"] : ["LAKE_HOLDOUT_BELOW_25", "LEVEL4_FOUR_LAKE_SUFFICIENCY"],
            metrics: ["rmseF": nil, "maeF": nil, "biasF": nil, "holdoutObservations": Double(p.holdout),
                      "calibrationObservations": Double(p.calibration), "holdoutRequired": Double(protectedTruthRequiredPerLake)],
            metricUnits: ["rmseF": "°F", "maeF": "°F", "biasF": "°F", "holdoutObservations": "casts",
                          "calibrationObservations": "casts", "holdoutRequired": "casts"],
            modelHistory: nil, artifactRef: artifactIOS + "WATER_TEMP_PROTECTED_TRUTH_STATUS.md",
            notes: ["Not scored: the four-lake protected gate (≥ 150 total and ≥ 25 per lake) fails, so no model is compared with this lake's truth."],
            researchCandidate: nil)
    }
}
