//
//  WaterTemperatureState.swift
//  Sector — the ONE resolved water temperature
//
//  The temperature Sector shows, scores, explains and passes downstream comes
//  from one resolution, made once (Stage 2E). Before this, the DTO showed any
//  sensor reading up to 72 h old while the score builder dropped it after 6 h
//  and scored the model — the user saw "measured" and the score ran on
//  "modeled". Now the snapshot's raw inputs go through `WaterTemperatureResolver`
//  once; the score builder, the response DTO and the forecast anchor all take
//  that same state.
//
//  The hierarchy is the one the engine already applied for scoring — unchanged:
//    1. a lake temperature measurement (the lake's own sensor, else a USGS lake
//       gauge — chosen upstream in ConditionsSnapshot) that is FRESH (≤ 6 h) and
//       NEAR (≤ 15 mi);
//    2. the calibrated surface-energy-balance model's value for the lake-local today;
//    3. unavailable — the value is nil, never a stand-in.
//  (The conditions score keeps its existing, separate air-temperature fallback
//  when this state is unavailable; that is reported explicitly, not shown as
//  water temperature.)
//
//  FRESHNESS POLICY (flagged for scientific review): a measurement is current
//  for 6 h. That is the score builder's existing qualification age
//  (`ConditionsInputBuilder.tempTurbidityMaxAgeHours`, from the July 2026
//  conditions audit). The 72 h window in LakeTempSensorService is a fetch
//  tolerance with no documented scientific basis; the stricter existing rule is
//  used so what is shown is what is scored. Neither age has a written
//  scientific justification yet.
//

import Foundation

public struct ResolvedWaterTemperatureState: Equatable {

    public enum Kind: String { case measured, modeled, unavailable }

    public enum SourceKind: String {
        case usgsLakeSensor        // USGS 00010 surface series (directory sensor or nearby LK gauge)
        case cwmsLakeSensor        // USACE CWMS pool/forebay surface series
        case energyBalanceModel    // Sector's calibrated surface-energy-balance model
        case none
    }

    public let kind: Kind
    public let sourceKind: SourceKind
    /// °F. nil when unavailable — never a fabricated value.
    public let valueF: Double?
    public let unit: String = "degF"
    public let sourceId: String?          // USGS site / CWMS tsid; nil for the model
    public let sourceName: String?
    public let observedAt: Date?          // measurement instant; nil for a model day
    public let ageHours: Double?          // resolvedAt − observedAt (absolute instants)
    /// The lake-local calendar date the value is for; nil when the lake's zone is unknown.
    public let lakeLocalDate: String?
    public let distanceMiles: Double?
    /// Sensor depth in metres when the source states one. USGS/CWMS surface
    /// series are qualified as ≤ 1.5 m upstream but rarely state a number, so
    /// this is usually nil (unknown), not 0.
    public let depthM: Double?
    public let spatialSupport: String     // "point" (a sensor) | "lakeWide" (the model) | "none"
    public let modelVersion: String?
    /// Why a measurement was passed over, or other caveats.
    public let qualityFlags: [String]
    public let resolvedAt: Date
    public let measurementMaxAgeHours: Double

    public var isMeasured: Bool { kind == .measured }
}

public enum WaterTemperatureResolver {

    /// A measurement older than this is not the current water (see policy above).
    public static var measurementMaxAgeHours: Double { ConditionsInputBuilder.tempTurbidityMaxAgeHours }
    /// A measurement from farther than this is another water.
    public static var measurementMaxDistanceMiles: Double { ConditionsInputBuilder.maxWaterTempDistanceMiles }
    public static let modelVersion = "surface-energy-balance-v2 (17-gauge calibration 2026-09-23; k=0.09)"

    /// The single source decision. Every consumer takes its output.
    static func resolve(measurement: WaterLevelReading?, model: WaterTempModel?, at now: Date) -> ResolvedWaterTemperatureState {
        resolve(measurement: measurement, modelValueF: model?.currentF,
                modelLocalDate: model?.currentLocalDate,
                lakeTimeZone: LakeLocalDate.timeZone(identifier: model?.timeZoneIdentifier, utcOffsetSeconds: nil),
                at: now)
    }

    static func resolve(measurement: WaterLevelReading?, modelValueF: Double?, modelLocalDate: String?,
                        lakeTimeZone: TimeZone?, at now: Date) -> ResolvedWaterTemperatureState {
        var flags: [String] = []
        if let m = measurement {
            let age = now.timeIntervalSince(m.dateTime) / 3600
            let tooOld = age > measurementMaxAgeHours
            let tooFar = (m.distanceMiles ?? 0) > measurementMaxDistanceMiles
            if !tooOld && !tooFar {
                return ResolvedWaterTemperatureState(
                    kind: .measured,
                    sourceKind: m.provider == "USACE CWMS" ? .cwmsLakeSensor : .usgsLakeSensor,
                    valueF: m.value * 9 / 5 + 32, sourceId: m.siteCode, sourceName: m.siteName,
                    observedAt: m.dateTime, ageHours: max(0, age),
                    lakeLocalDate: lakeTimeZone.map { LakeLocalDate.string(for: m.dateTime, in: $0) },
                    distanceMiles: m.distanceMiles, depthM: nil, spatialSupport: "point",
                    modelVersion: nil, qualityFlags: age < 0 ? ["observedAtInFuture"] : [],
                    resolvedAt: now, measurementMaxAgeHours: measurementMaxAgeHours)
            }
            if tooOld { flags.append(String(format: "measurementStale:%.1fh>%gh", age, measurementMaxAgeHours)) }
            if tooFar { flags.append(String(format: "measurementTooFar:%.1fmi", m.distanceMiles ?? 0)) }
        }
        if let v = modelValueF {
            if modelLocalDate == nil { flags.append("modelLocalDateUnknown") }
            return ResolvedWaterTemperatureState(
                kind: .modeled, sourceKind: .energyBalanceModel, valueF: v, sourceId: nil, sourceName: nil,
                observedAt: nil, ageHours: nil, lakeLocalDate: modelLocalDate, distanceMiles: nil, depthM: nil,
                spatialSupport: "lakeWide", modelVersion: modelVersion, qualityFlags: flags,
                resolvedAt: now, measurementMaxAgeHours: measurementMaxAgeHours)
        }
        return ResolvedWaterTemperatureState(
            kind: .unavailable, sourceKind: .none, valueF: nil, sourceId: nil, sourceName: nil,
            observedAt: nil, ageHours: nil, lakeLocalDate: lakeTimeZone.map { LakeLocalDate.string(for: now, in: $0) },
            distanceMiles: nil, depthM: nil, spatialSupport: "none", modelVersion: nil,
            qualityFlags: flags + ["noMeasurementNoModel"],
            resolvedAt: now, measurementMaxAgeHours: measurementMaxAgeHours)
    }
}
