//
//  TileSources.swift
//  SectorEngine
//
//  `tileSources` (spec §4): for every customer tile, which flag mode applied, which path and source the served value
//  came from, its status, and its own observation time when it has one. All ten flag keys plus `moon` are always present,
//  so the apps can rely on `tileSources[key]` existing.
//
//  This foundation has no new tile source yet: every entry states TODAY's path truthfully.
//    humidity, pressure, temperature, sky, wind  engine / open-meteo (current conditions). No observedAt: the reading's
//                                                `time` is Open-Meteo's location-local string parsed in the process zone,
//                                                so it is not a trustworthy instant.
//    windOutlookModel                            engine / open-meteo-best-match, or open-meteo-ncep-nbm-conus when
//                                                SECTOR_WIND_FORECAST_MODEL selects NBM for the future nights (#125).
//    waterLevel                                  engine / usgs-nearest-gauge (`water`), observedAt = the gauge reading.
//    clarity                                     engine / visibility-model: AVAILABLE from an in-situ turbidity gauge
//                                                (observedAt = that reading), ESTIMATE from the rain-decay model.
//    waterTemp                                   engine / the resolved state's source: a lake sensor (AVAILABLE,
//                                                observedAt = the measurement) or the energy-balance model (ESTIMATE).
//    generation                                  engine / engine-generation-service, observedAt = the dam observation.
//    moon                                        app / moon-v1 (the apps compute it).
//

import Foundation

/// Today's facts behind each tile, taken from the snapshot when the response is built. Plain values so the mapping is
/// a pure, testable function.
public struct LegacyTileFacts: Equatable, Sendable {
    public var weatherPresent: Bool
    public var outlookNights: Int
    /// `WindForecastModel.current` (nil = best_match everywhere).
    public var windForecastModel: String?
    public var waterPresent: Bool
    public var waterObservedAt: Date?
    /// `ClarityVisibilityDTO.source`: inSituGauge | rainDecayModel | noRainData; nil when no clarity statement.
    public var claritySource: String?
    public var turbidityObservedAt: Date?
    /// `ResolvedWaterTemperatureState.Kind` raw value: measured | modeled | unavailable.
    public var waterTempKind: String
    /// `ResolvedWaterTemperatureState.SourceKind` raw value.
    public var waterTempSourceKind: String
    public var waterTempObservedAt: Date?
    public var generationPresent: Bool
    /// The dam block carries at least one reading or window (not just the dam's identity).
    public var generationHasReading: Bool
    public var generationObservedAt: Date?

    public init(weatherPresent: Bool = false, outlookNights: Int = 0, windForecastModel: String? = nil,
                waterPresent: Bool = false, waterObservedAt: Date? = nil,
                claritySource: String? = nil, turbidityObservedAt: Date? = nil,
                waterTempKind: String = "unavailable", waterTempSourceKind: String = "none", waterTempObservedAt: Date? = nil,
                generationPresent: Bool = false, generationHasReading: Bool = false, generationObservedAt: Date? = nil) {
        self.weatherPresent = weatherPresent; self.outlookNights = outlookNights; self.windForecastModel = windForecastModel
        self.waterPresent = waterPresent; self.waterObservedAt = waterObservedAt
        self.claritySource = claritySource; self.turbidityObservedAt = turbidityObservedAt
        self.waterTempKind = waterTempKind; self.waterTempSourceKind = waterTempSourceKind
        self.waterTempObservedAt = waterTempObservedAt
        self.generationPresent = generationPresent; self.generationHasReading = generationHasReading
        self.generationObservedAt = generationObservedAt
    }
}

public enum TileSources {

    /// The app-computed tile with no flag (spec §1, last row).
    public static let moonKey = "moon"

    /// Today's entry for every flag tile, flag `off`.
    public static func legacy(_ f: LegacyTileFacts) -> [TileKey: TileSourceDTO] {
        func engine(_ source: String, _ status: TileStatus, _ observedAt: Date? = nil) -> TileSourceDTO {
            TileSourceDTO(flag: TileMode.off.rawValue, path: TilePath.engine.rawValue, source: source,
                          status: status.rawValue, observedAt: observedAt)
        }
        let weather = engine("open-meteo", f.weatherPresent ? .available : .unknown)

        let outlookSource = f.windForecastModel == "ncep_nbm_conus" ? "open-meteo-ncep-nbm-conus" : "open-meteo-best-match"

        let clarity: TileSourceDTO
        switch f.claritySource {
        case "inSituGauge": clarity = engine("visibility-model", .available, f.turbidityObservedAt)
        case "rainDecayModel", "noRainData": clarity = engine("visibility-model", .estimate)
        default: clarity = engine("visibility-model", .unknown)
        }

        let waterTemp: TileSourceDTO
        switch (f.waterTempKind, f.waterTempSourceKind) {
        case ("measured", "usgsLakeSensor"): waterTemp = engine("usgs-lake-sensor", .available, f.waterTempObservedAt)
        case ("measured", "cwmsLakeSensor"): waterTemp = engine("cwms-lake-sensor", .available, f.waterTempObservedAt)
        case ("measured", _): waterTemp = engine("lake-sensor", .available, f.waterTempObservedAt)
        case ("modeled", _): waterTemp = engine("energy-balance-model", .estimate)
        default: waterTemp = engine("water-temp-resolver", .unknown)
        }

        let generationOK = f.generationPresent && f.generationHasReading
        return [
            .humidity: weather,
            .pressure: weather,
            .temperature: weather,
            .sky: weather,
            .wind: weather,
            .windOutlookModel: engine(outlookSource, f.outlookNights > 0 ? .available : .unknown),
            .waterLevel: engine("usgs-nearest-gauge", f.waterPresent ? .available : .unknown,
                                f.waterPresent ? f.waterObservedAt : nil),
            .clarity: clarity,
            .waterTemp: waterTemp,
            .generation: engine("engine-generation-service", generationOK ? .available : .unknown,
                                generationOK ? f.generationObservedAt : nil),
        ]
    }

    public static let moonEntry = TileSourceDTO(flag: TileMode.off.rawValue, path: TilePath.app.rawValue,
                                                source: "moon-v1", status: TileStatus.available.rawValue)

    /// The response's `tileSources`: today's entries passed through the shadow/serve step under the current flags. No tile
    /// has a new source in this foundation, so every value is today's; a tile in `serve` reports FALLBACK.
    public static func build(_ f: LegacyTileFacts, flags: TileFlags, context: TileRequestContext) async -> [String: TileSourceDTO] {
        let legacy = Self.legacy(f)
        var out: [String: TileSourceDTO] = [moonKey: moonEntry]
        for tile in TileKey.allCases {
            let entry = legacy[tile]!
            let present: Bool? = entry.status == TileStatus.unknown.rawValue ? nil : true
            let r = await TileShadow.resolve(tile: tile, mode: flags.mode(for: tile, lakeId: context.lakeId),
                                             old: present, oldEntry: entry, context: context,
                                             new: nil, compare: { _, _ in TileComparison(old: .null, new: .null) })
            out[tile.rawValue] = r.entry
        }
        return out
    }
}
