//
//  LakeLocalDate.swift
//  Sector — the lake's own calendar date
//
//  "Today" for a lake is the LAKE's calendar date, never the server's. Cloud Run
//  runs in UTC, so in a US evening the server is already on tomorrow; anything
//  that picks a daily value by `Calendar.current` silently shows tomorrow's
//  forecast as today's water (Stage 2E). Every daily water-temperature choice
//  goes through here.
//
//  Zone source, in order (national, not Central-only):
//    1. the IANA zone the weather provider resolved for the coordinate
//       (Open-Meteo `timezone` with `timezone=auto`) — DST-aware;
//    2. the provider's fixed `utc_offset_seconds` — correct for the request
//       instant, not across a DST change;
//    3. nil → callers report the local date as UNKNOWN rather than guess.
//

import Foundation

public enum LakeLocalDate {

    /// The lake's zone from what the provider returned, or nil when it gave nothing.
    public static func timeZone(identifier: String?, utcOffsetSeconds: Int?) -> TimeZone? {
        if let id = identifier, !id.isEmpty, let tz = TimeZone(identifier: id) { return tz }
        if let off = utcOffsetSeconds { return TimeZone(secondsFromGMT: off) }
        return nil
    }

    /// The lake-local calendar date ("yyyy-MM-dd") of an absolute instant.
    /// Independent of the process time zone.
    public static func string(for instant: Date, in zone: TimeZone) -> String {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = zone
        let c = cal.dateComponents([.year, .month, .day], from: instant)
        return String(format: "%04d-%02d-%02d", c.year ?? 0, c.month ?? 0, c.day ?? 0)
    }
}
