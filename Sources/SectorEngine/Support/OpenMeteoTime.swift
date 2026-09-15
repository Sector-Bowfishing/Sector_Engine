//
//  OpenMeteoTime.swift
//  SectorEngine
//
//  Turning Open-Meteo's local wall-clock times into real instants.
//
//  Requests use `timezone=auto`, so Open-Meteo answers with LOCAL wall-clock
//  strings that carry no offset ("2026-09-14T21:00" = 9 PM at the lake) plus a
//  top-level `utc_offset_seconds`. The engine used to parse those strings in
//  `TimeZone.current`. On a phone that is usually the lake's zone, so it looked
//  right; on Cloud Run it is UTC, so every hourly sample was off by the lake's
//  offset — 5 hours for a Central lake in summer. That shifted the Tonight
//  window to 1 PM–1 AM CDT, scored fog risk and gusts on the wrong hours of the
//  night, and skewed every hourly chart the apps draw.
//
//  Everything that reads an Open-Meteo time goes through here, with the offset
//  from the same response, and gets a true `Date`.
//

import Foundation

enum OpenMeteoTime {
    private static let utc = TimeZone(secondsFromGMT: 0)!

    /// The real instant for a local wall-clock string ("yyyy-MM-dd'T'HH:mm", or a
    /// bare "yyyy-MM-dd" meaning local midnight) at a location `utcOffsetSeconds`
    /// from UTC. Hand-parsed: the format is fixed, and this avoids sharing a
    /// mutable DateFormatter across concurrent renders.
    static func instant(_ string: String, utcOffsetSeconds: Int) -> Date? {
        guard let comps = components(string) else { return nil }
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = utc
        guard let wall = cal.date(from: comps) else { return nil }
        return wall.addingTimeInterval(-Double(utcOffsetSeconds))
    }

    /// The location's zone, as the fixed offset Open-Meteo reported.
    static func zone(utcOffsetSeconds: Int?) -> TimeZone {
        TimeZone(secondsFromGMT: utcOffsetSeconds ?? 0) ?? utc
    }

    /// A gregorian calendar in the location's zone — for "6 PM tonight",
    /// "today", "tomorrow at the lake", independent of the server's zone.
    static func calendar(utcOffsetSeconds: Int?) -> Calendar {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = zone(utcOffsetSeconds: utcOffsetSeconds)
        return cal
    }

    /// The location's local date ("yyyy-MM-dd") for an instant.
    static func localDay(_ date: Date, utcOffsetSeconds: Int?) -> String {
        let c = calendar(utcOffsetSeconds: utcOffsetSeconds).dateComponents([.year, .month, .day], from: date)
        return String(format: "%04d-%02d-%02d", c.year ?? 0, c.month ?? 0, c.day ?? 0)
    }

    /// Hours after local midnight that still belong to the previous evening's
    /// night. Matches the Tonight window (6 PM → 6 AM).
    static let nightRolloverHour = 6

    /// The local date of the fishing night in progress (or coming up) at `date`:
    /// from 6 AM onward that's today's evening; between midnight and 6 AM it's
    /// still last night.
    static func fishingNightDay(_ date: Date, utcOffsetSeconds: Int?) -> String {
        localDay(date.addingTimeInterval(-Double(nightRolloverHour) * 3600), utcOffsetSeconds: utcOffsetSeconds)
    }

    /// Local noon of the fishing night's date. `Astronomy` picks its day by UTC
    /// date, and local noon falls on the local date for every US zone — whereas
    /// "now" at 7 PM Central is already tomorrow in UTC and returns tomorrow's
    /// sunset, moonrise and window.
    static func fishingNightNoon(_ date: Date, utcOffsetSeconds: Int?) -> Date {
        instant(fishingNightDay(date, utcOffsetSeconds: utcOffsetSeconds) + "T12:00",
                utcOffsetSeconds: utcOffsetSeconds ?? 0) ?? date
    }

    /// Best guess at a location's offset when no Open-Meteo response is at hand:
    /// solar time from longitude, whole hours. Close enough to pick the right day
    /// with a noon anchor; never used for clock times.
    static func solarOffsetSeconds(longitude: Double) -> Int {
        Int((longitude / 15).rounded()) * 3600
    }

    private static func components(_ s: String) -> DateComponents? {
        let parts = s.split(separator: "T", maxSplits: 1)
        let ymd = parts.first?.split(separator: "-").compactMap { Int($0) } ?? []
        guard ymd.count == 3 else { return nil }
        var comps = DateComponents(year: ymd[0], month: ymd[1], day: ymd[2], hour: 0, minute: 0)
        if parts.count == 2 {
            let hm = parts[1].split(separator: ":").compactMap { Int($0) }
            guard hm.count >= 2 else { return nil }
            comps.hour = hm[0]
            comps.minute = hm[1]
        }
        return comps
    }
}
