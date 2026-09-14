//
//  WeatherCode.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Pure reconciliation of Open-Meteo's categorical WMO weather code against its
//  own measurements. The code is model-derived and over-reports rain/storm on
//  clear, dry steps (observed: code 95 with precipitation 0 and 0% cloud on a
//  calm night). Everything downstream — the storm gate, the seeability weather
//  component, and the sky factor — must key off the reconciled code, never the
//  raw one, so a single bad categorical field can't tank the score. The
//  aggregator applies this at the top of `evaluate`; the weather adapter applies
//  it again for the display label. Belt and suspenders, by design.
//

import Foundation

public enum WeatherCode: Sendable {

    /// Cloud ceiling below which a "precip" code with zero precip is treated as a
    /// false positive. A genuine storm brings heavy overcast, so at/above this we
    /// keep the code. Kept in sync with ConditionsConfig.Gates.stormMinCloudPct.
    public static let falsePrecipCloudCeiling: Double = 70

    /// Codes ≥ 51 mean drizzle/rain/snow/storm. If nothing is actually falling and
    /// the sky isn't heavily overcast, the code is a false positive → return a
    /// clear/cloudy code reflecting the measured cloud cover instead.
    public static func sanitized(_ code: Int, precipitation: Double, cloudCover: Double) -> Int {
        guard code >= 51, precipitation <= 0, cloudCover < falsePrecipCloudCeiling else { return code }
        if cloudCover < 12 { return 0 }        // clear
        if cloudCover < 50 { return 1 }        // mainly clear
        return 2                                // partly cloudy
    }
}
