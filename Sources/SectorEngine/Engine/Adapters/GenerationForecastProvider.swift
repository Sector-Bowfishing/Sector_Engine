//
//  GenerationForecastProvider.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Seam for tailwater generation forecasts (TVA recreation release schedules /
//  USACE Nashville preschedule). Those HTML/CSV feeds are DEFERRED for v2 (per
//  project decision), so the shipped provider returns nil and the current factor
//  falls back to the live USGS discharge trend (confidence drops when no forecast
//  exists, per §8). A real TVA/USACE adapter can be dropped in later behind this
//  protocol without touching the engine. §3 / §5.7.
//

import Foundation

/// One forecast point: expected discharge (cfs) at a local hour tonight.
public struct GenerationSample: Equatable, Sendable {
    public let hourLocal: Date
    public let cfs: Double
    public init(hourLocal: Date, cfs: Double) {
        self.hourLocal = hourLocal; self.cfs = cfs
    }
}

public protocol GenerationForecastProvider {
    /// Tonight's generation forecast for a tailwater, or nil if unavailable.
    func generationForecast(latitude: Double, longitude: Double, date: Date) async -> [GenerationSample]?
}

/// The shipped v2 provider: no live feed yet — always nil.
public struct NullGenerationForecastProvider: GenerationForecastProvider, Sendable {
    public init() {}
    public func generationForecast(latitude: Double, longitude: Double, date: Date) async -> [GenerationSample]? {
        nil
    }
}
