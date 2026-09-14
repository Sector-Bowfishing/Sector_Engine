//
//  WeatherAlertsService.swift
//  Sector
//
//  Active National Weather Service alerts (watches / warnings / advisories) for a
//  location, shown as a pill under the shooting-conditions score, and never posts a
//  push notification. Most alerts are a display-only safety heads-up, but a
//  severe-wind WARNING also floors the Conditions Score via `impliedWindFloorMph`
//  (see below): a live NWS Warning outranks the smoothed Open-Meteo wind, so the
//  night can't read "Prime" while dangerous gusts are happening now. That floor is
//  applied in the shared ConditionsInputBuilder — so every surface (gauge, 7-night,
//  Lake Alerts) and the Android port must apply it identically to avoid score drift.
//
//  Source: https://api.weather.gov/alerts/active?point=<lat>,<lng>  (US-only, free,
//  no API key). The fetch is best-effort: any failure yields an empty list so the
//  score card always renders.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

// MARK: - Model

/// NWS severity, ordered most→least urgent. Drives the pill color and whether the
/// event reads as a "warning" (act now) vs a "watch/advisory" (be aware).
enum AlertSeverity: Int, Comparable {
    case extreme = 4, severe = 3, moderate = 2, minor = 1, unknown = 0

    init(_ raw: String?) {
        switch raw?.lowercased() {
        case "extreme":  self = .extreme
        case "severe":   self = .severe
        case "moderate": self = .moderate
        case "minor":    self = .minor
        default:         self = .unknown
        }
    }

    static func < (a: AlertSeverity, b: AlertSeverity) -> Bool { a.rawValue < b.rawValue }
}

struct WeatherAlert: Identifiable, Equatable {
    let id: String
    let event: String          // e.g. "Flood Watch", "Tornado Warning"
    let severity: AlertSeverity
    let headline: String
    let details: String
    let ends: Date?

    /// If this is an active *warning* implying dangerous wind, the wind speed (mph)
    /// the shooting-conditions score should assume — for wind, a live NWS warning
    /// outranks the smoothed forecast (a Severe Thunderstorm Warning means 58+ mph
    /// gusts happening now, which Open-Meteo's hourly model often misses).
    ///
    /// Only *warnings* qualify — a Watch means "possible," not "occurring," so it
    /// stays display-only. Flood/marine-fog/other non-wind events return nil.
    var impliedWindFloorMph: Double? {
        let e = event.lowercased()
        guard e.contains("warning") else { return nil }
        if e.contains("tornado") || e.contains("extreme wind") { return 70 }
        if e.contains("severe thunderstorm") || e.contains("high wind") { return 58 }
        if e.contains("special marine") { return 39 }   // ~34 kt
        return nil
    }

    /// True when this active WARNING makes being out on the water dangerous — the
    /// score must be capped no matter how good the forecast reads. This is the
    /// authoritative real-time signal: a meteorologist has issued a warning for
    /// something happening NOW that the forecast model routinely misses (a
    /// fast-developing squall line is why a night can score Prime with a storm
    /// overhead). WATCHES don't count — "possible", not "occurring"; only issued
    /// warnings. Non-convective advisories (heat, dense fog, etc.) don't qualify.
    var impliesUnsafeToFish: Bool {
        let e = event.lowercased()
        guard e.contains("warning") else { return false }
        return e.contains("tornado") || e.contains("severe thunderstorm")
            || e.contains("flash flood") || e.contains("special marine")
            || e.contains("extreme wind") || e.contains("hurricane")
            || e.contains("tropical storm")
    }
}

// MARK: - Service

actor WeatherAlertsService {
    static let shared = WeatherAlertsService()
    private init() {}

    /// Active alerts for the point, most-severe first. Returns `[]` on any error or
    /// for locations NWS doesn't cover (outside the US) — never throws to the caller.
    func activeAlerts(near coordinate: CLLocationCoordinate2D) async -> [WeatherAlert] {
        var components = URLComponents(string: "https://api.weather.gov/alerts/active")
        components?.queryItems = [
            URLQueryItem(name: "point", value: String(format: "%.4f,%.4f",
                                                      coordinate.latitude, coordinate.longitude)),
            URLQueryItem(name: "status", value: "actual"),
        ]
        guard let url = components?.url else { return [] }

        do {
            // NWS requires a self-identifying User-Agent or it returns 403.
            let result = try await HTTP.get(url, headers: [
                "User-Agent": "Sector/1.0 (io.sector.co)",
                "Accept": "application/geo+json",
            ])
            guard result.status == 200 else { return [] }
            let decoded = try JSONDecoder().decode(NWSAlertsResponse.self, from: result.body)
            let alerts = decoded.features.compactMap { $0.properties.toAlert() }
            // NWS routinely issues OVERLAPPING records for the same event — e.g.
            // a Heat Advisory ending tonight plus a follow-on for the next two
            // days, both active now — which rendered as duplicate pills saying
            // the same thing. Keep one per event name: highest severity, then
            // the one ending soonest (the period in effect right now, whose
            // details are the actionable ones).
            let sorted = alerts.sorted {
                if $0.severity != $1.severity { return $0.severity > $1.severity }
                return ($0.ends ?? .distantFuture) < ($1.ends ?? .distantFuture)
            }
            var seenEvents = Set<String>()
            return sorted.filter { seenEvents.insert($0.event).inserted }
        } catch {
            return []
        }
    }
}

// MARK: - NWS GeoJSON

private struct NWSAlertsResponse: Decodable {
    let features: [Feature]
    struct Feature: Decodable { let properties: Properties }

    struct Properties: Decodable {
        let id: String?
        let event: String?
        let severity: String?
        let headline: String?
        let description: String?
        let messageType: String?
        let ends: String?
        let expires: String?

        func toAlert() -> WeatherAlert? {
            // Skip cancellations — the point query can still surface them briefly.
            guard messageType?.lowercased() != "cancel" else { return nil }
            guard let event, !event.isEmpty else { return nil }
            let end = Self.parse(ends) ?? Self.parse(expires)
            return WeatherAlert(
                id: id ?? "\(event)-\(headline ?? "")",
                event: event,
                severity: AlertSeverity(severity),
                headline: headline ?? event,
                details: description ?? "",
                ends: end)
        }

        static func parse(_ s: String?) -> Date? {
            guard let s, !s.isEmpty else { return nil }
            return ISODate.parse(s)
        }
    }
}
