//
//  Build28Response.swift
//  SectorEngineTests
//
//  VENDORED VERBATIM, DO NOT EDIT: `EngineAPIClient.Response` from iOS_Sector tag v4.1.0-28 (App Store 4.1.0 build 28),
//  Sector/SwiftData/Models/EngineAPIClient.swift. It is the decoder released iPhones run against GET /conditions.
//  PhoneContractTests decodes the Engine's own output with it (dates `.iso8601`, as the app does), so a server change
//  that would fail on those phones fails CI (Sector_Ops #53, rule 1). Replace it only when build 28 is no longer in
//  use according to request logs by app version.
//

import Foundation

enum Build28 {
    struct Response: Decodable {
        let score: Int
        let band: String                 // Poor | Fair | Good | Prime
        let regime: String               // normal | spawn | tailwater
        let confidence: Int
        let confidenceBand: String       // Low | Med | High
        let topReasons: [String]
        let closingLine: String
        let spawnSpeciesName: String?
        let spawnNeedsDisclaimer: Bool
        let baseline: Double?
        let dormantFactors: [DormantFactor]?
        let factors: [Factor]
        let gates: [Gate]
        let whereToLook: [WhereToLook]

        let weather: Weather?
        let water: Water?
        let discharge: Water?
        let generation: Generation?
        let waterTempModel: TempModel?
        let moonIllumination: Double
        let alerts: [Alert]

        let tonight: Tonight?
        let nights: [Night]

        /// MRMS radar-gauge rainfall behind the clarity estimate (watershed 72h +
        /// daily series). Optional so a pre-update server still decodes.
        let clarityRain: ClarityRain?
        struct ClarityRain: Decodable {
            let watershed72hIn: Double
            let point72hIn: Double
            let source: String
            let daily: [RainDay]
        }
        struct RainDay: Decodable { let date: Date; let inches: Double }

        /// USGS gauges behind the clarity estimate (turbidity + discharge). Optional
        /// so a pre-update server still decodes.
        let clarityGauges: [Gauge]?
        struct Gauge: Decodable {
            let siteCode: String; let siteName: String
            let parameterCode: String; let parameterName: String
            let role: String; let value: Double; let unit: String
            let trend: String; let change: Double
            let distanceMiles: Double?; let latitude: Double; let longitude: Double
            let driving: Bool
        }

        struct Factor: Decodable {
            let key: String; let score: Int; let weightPct: Int; let label: String; let why: String
            // Optional so a pre-update server still decodes; nil → derived in mapping.
            let contribution: Double?
        }
        struct DormantFactor: Decodable { let key: String; let label: String; let reason: String }
        struct Gate: Decodable { let reason: String; let cap: Int }
        struct WhereToLook: Decodable { let kind: String; let title: String; let body: String }

        struct Weather: Decodable {
            let temperature: Double; let conditionDescription: String; let conditionSymbol: String
            let windSpeed: Double; let windDirection: Int; let precipitation: Double
            let recentRainfall: Double; let humidity: Int; let pressure: Double
            let pressureTrend: String; let pressureChange: Double; let cloudCover: Double; let weatherCode: Int
            // Hourly barometric series (past + near future). Optional so a pre-update
            // server still decodes; when present it drives the pressure trend chart.
            let pressureHourly: [PressureHour]?
            // Hourly conditions series — drives the wind / temp / humidity / sky / rain
            // detail charts. Optional for the same back-compat reason.
            let hourlyConditions: [ConditionsHour]?
        }
        struct PressureHour: Decodable { let time: Date; let hPa: Double }
        struct ConditionsHour: Decodable {
            let time: Date
            let tempF: Double?; let humidity: Double?; let windMph: Double?; let gustMph: Double?
            let windDir: Double?; let dewPointF: Double?; let cloudPct: Double?; let precipIn: Double?
        }
        struct Water: Decodable {
            let value: Double; let unit: String; let trend: String; let change: Double; let history: [Double]
        }
        struct Generation: Decodable {
            let damName: String; let river: String
            // Optional so a not-yet-redeployed server (pre-operator/coords) still decodes.
            let operatorId: String?; let latitude: Double?; let longitude: Double?
            let distanceMiles: Double
            let dischargeCfs: Double?; let dischargeTrend12hCfs: Double?
            let reservoirElevationFt: Double?; let tailwaterElevationFt: Double?
            let observedAt: Date?; let windows: [Window]
            struct Window: Decodable {
                let start: Date; let end: Date; let generators: Int
                let isMinimum: Bool; let unitsAreDerived: Bool; let timeZoneIdentifier: String
            }
        }
        struct TempModel: Decodable {
            let currentF: Double; let series: [Day]
            struct Day: Decodable { let date: Date; let waterF: Double; let airF: Double }
        }
        struct Alert: Decodable {
            let id: String; let event: String; let severity: String
            let headline: String; let details: String; let ends: Date?
        }
        struct Tonight: Decodable {
            let headline: String; let windowStart: Date?; let windowEnd: Date?; let peak: Date?
            let sunset: Date?; let sunrise: Date?; let displayStart: Date?; let displayEnd: Date?
            let hours: [Hour]
            struct Hour: Decodable { let date: Date; let score: Int }
        }
        struct Night: Decodable {
            let date: Date; let score: Int; let rating: String; let moonIllumination: Double
            let windMax: Double; let weatherCode: Int; let precip: Double
            let precipProbability: Int?   // 0…100 % chance of rain; nil when unknown
            let confidence: Int; let regime: String; let topReasons: [String]; let factors: [NightFactor]
            let hourly: [HourPoint]?      // night-detail ribbon; nil on a pre-update server
            let moonset: Date?
            struct NightFactor: Decodable { let key: String; let detail: String; let sub: Int; let weight: Int }
            struct HourPoint: Decodable {
                let hour: Date; let score: Int; let windMph: Double; let moonUp: Bool; let fogRisk: Int
            }
        }
    }

}
