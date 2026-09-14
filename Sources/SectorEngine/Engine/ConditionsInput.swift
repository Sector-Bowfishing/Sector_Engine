//
//  ConditionsInput.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  The normalized, source-agnostic input the factor scorers and aggregator
//  consume — one per night (or per hour for tonight's curve). Adapters fill it
//  in; the engine never touches a network or a framework type. §4.
//
//  Every optional that comes back `nil` (no nearby gage, no temp sensor, no
//  generation forecast) is dropped from the weighted blend with weights
//  renormalized, and lowers *confidence* rather than the score. §3.
//

import Foundation

public struct ConditionsInput: Equatable, Sendable {

    // MARK: Identity / place
    public var date: Date
    public var latitude: Double
    public var longitude: Double
    public var region: Region

    // MARK: Weather
    public var windMph: Double
    public var windGustMph: Double?         // for the gust penalty, if known
    public var windDirDeg: Int
    public var airTempF: Double
    public var cloudPct: Double             // 0…100
    public var humidityPct: Double
    public var pressureInHg: Double
    public var pressureTrend: PressureMovement
    public var pressureChange12hInHg: Double // signed
    public var weatherCode: Int             // WMO code (sky factor) — already sanitized
    public var precipitationInchNow: Double // measured precip right now (storm-gate corroboration)
    /// Active NWS safety WARNING covering the point (tornado / severe thunderstorm /
    /// flash flood / marine) — the event name, for the gate reason; nil when none.
    /// Authoritative real-time signal that hard-caps the score even when the
    /// forecast reads clean (the model routinely misses a fast-developing storm).
    public var severeWarningLabel: String?
    /// City light pollution near the spot (0 = pristine dark, 1 = heavy skyglow).
    /// Drives whether cloud cancels the moon or reflects city glow. §5.3.
    public var cityGlowFactor: Double

    // MARK: Water
    public var waterTempF: Double?
    public var waterTempEstimated: Bool     // true if estimated from air/season
    public var stageFt: Double?
    public var stageTrend12hFt: Double?      // signed feet over 12 h
    public var dischargeCfs: Double?
    public var dischargeTrend12hCfs: Double? // signed cfs over 12 h
    public var turbidityFNU: Double?
    public var turbidityType: TurbidityType
    public var rainLast48hIn: Double         // Open-Meteo point 48 h — fallback only
    /// MRMS radar-gauge rain over the last 72 h, aggregated across the surrounding
    /// watershed. Preferred clarity input when present (see ClarityFactor).
    public var rainWatershed72hIn: Double?
    /// False when NEITHER rain source answered — clarity must not then read the
    /// dry-baseline "clear", which would be the most optimistic possible guess.
    public var rainDataAvailable: Bool

    // MARK: Tailwater / current
    public var isTailwater: Bool
    /// Pool elevation behind the nearest dam (ft), when a dam feed covers this
    /// water. On a reservoir this is the level that actually describes where
    /// you're shooting — a USGS river stage gage does not.
    public var reservoirElevationFt: Double?
    /// Signed 12 h change in the reservoir POOL (ft), from the dam's own history.
    /// On a reservoir this is the real level trend of the water you're standing
    /// on — preferred over a distant USGS river-stage gage. §5.6.
    public var reservoirTrend12hFt: Double?
    /// Smallest air–dewpoint spread (°F) forecast during tonight's window. Small
    /// spread → fog forms on the water. nil when no dewpoint series is available,
    /// in which case the humidity factor falls back to raw RH.
    public var fogSpreadF: Double?
    public var generationLevel: GenerationLevel?   // resolved for the window, if known
    public var hasGenerationForecast: Bool

    // MARK: Astronomy (computed locally — no network)
    public var sunset: Date?
    public var sunrise: Date?
    public var civilDusk: Date?
    public var astronomicalDusk: Date?
    public var moonIllumPct: Double          // 0…100
    public var moonrise: Date?
    public var moonset: Date?
    /// 0…1 — how present/high the moon is across the fishing window. §5.3.
    public var moonAltitudeAtWindow: Double

    // MARK: Window (for darkness / per-night scoring)
    public var windowStart: Date?            // when shooting realistically begins
    public var windowEnd: Date?

    // MARK: Confidence inputs
    public var hasTurbidityGage: Bool
    public var forecastDayIndex: Int         // 0 = tonight, …, 7 = far out

    public init(date: Date,
                latitude: Double,
                longitude: Double,
                region: Region,
                windMph: Double,
                windGustMph: Double? = nil,
                windDirDeg: Int,
                airTempF: Double,
                cloudPct: Double,
                humidityPct: Double,
                pressureInHg: Double,
                pressureTrend: PressureMovement,
                pressureChange12hInHg: Double,
                weatherCode: Int,
                precipitationInchNow: Double = 0,
                severeWarningLabel: String? = nil,
                cityGlowFactor: Double,
                waterTempF: Double? = nil,
                waterTempEstimated: Bool = false,
                stageFt: Double? = nil,
                stageTrend12hFt: Double? = nil,
                dischargeCfs: Double? = nil,
                dischargeTrend12hCfs: Double? = nil,
                turbidityFNU: Double? = nil,
                turbidityType: TurbidityType = .unknown,
                rainLast48hIn: Double = 0,
                rainWatershed72hIn: Double? = nil,
                rainDataAvailable: Bool = true,
                isTailwater: Bool = false,
                reservoirElevationFt: Double? = nil,
                reservoirTrend12hFt: Double? = nil,
                fogSpreadF: Double? = nil,
                generationLevel: GenerationLevel? = nil,
                hasGenerationForecast: Bool = false,
                sunset: Date? = nil,
                sunrise: Date? = nil,
                civilDusk: Date? = nil,
                astronomicalDusk: Date? = nil,
                moonIllumPct: Double = 0,
                moonrise: Date? = nil,
                moonset: Date? = nil,
                moonAltitudeAtWindow: Double = 0,
                windowStart: Date? = nil,
                windowEnd: Date? = nil,
                hasTurbidityGage: Bool = false,
                forecastDayIndex: Int = 0) {
        self.date = date
        self.latitude = latitude
        self.longitude = longitude
        self.region = region
        self.windMph = windMph
        self.windGustMph = windGustMph
        self.windDirDeg = windDirDeg
        self.airTempF = airTempF
        self.cloudPct = cloudPct
        self.humidityPct = humidityPct
        self.pressureInHg = pressureInHg
        self.pressureTrend = pressureTrend
        self.pressureChange12hInHg = pressureChange12hInHg
        self.weatherCode = weatherCode
        self.precipitationInchNow = precipitationInchNow
        self.severeWarningLabel = severeWarningLabel
        self.cityGlowFactor = cityGlowFactor
        self.waterTempF = waterTempF
        self.waterTempEstimated = waterTempEstimated
        self.stageFt = stageFt
        self.stageTrend12hFt = stageTrend12hFt
        self.dischargeCfs = dischargeCfs
        self.dischargeTrend12hCfs = dischargeTrend12hCfs
        self.turbidityFNU = turbidityFNU
        self.turbidityType = turbidityType
        self.rainLast48hIn = rainLast48hIn
        self.rainWatershed72hIn = rainWatershed72hIn
        self.rainDataAvailable = rainDataAvailable
        self.isTailwater = isTailwater
        self.reservoirElevationFt = reservoirElevationFt
        self.reservoirTrend12hFt = reservoirTrend12hFt
        self.fogSpreadF = fogSpreadF
        self.generationLevel = generationLevel
        self.hasGenerationForecast = hasGenerationForecast
        self.sunset = sunset
        self.sunrise = sunrise
        self.civilDusk = civilDusk
        self.astronomicalDusk = astronomicalDusk
        self.moonIllumPct = moonIllumPct
        self.moonrise = moonrise
        self.moonset = moonset
        self.moonAltitudeAtWindow = moonAltitudeAtWindow
        self.windowStart = windowStart
        self.windowEnd = windowEnd
        self.hasTurbidityGage = hasTurbidityGage
        self.forecastDayIndex = forecastDayIndex
    }
}
