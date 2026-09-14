//
//  ISODate.swift
//  SectorEngine
//
//  Thread-safe ISO-8601 parsing for upstream timestamps (USGS, NWPS, NWS).
//
//  The adapters used to share `static let` ISO8601DateFormatter instances
//  across concurrent renders; a formatter is a mutable reference type that
//  isn't documented as safe to use from several threads at once.
//  `Date.ISO8601FormatStyle` is a Sendable value, so it can be shared freely.
//

import Foundation

enum ISODate {
    private static let fractional = Date.ISO8601FormatStyle(includingFractionalSeconds: true)
    private static let whole = Date.ISO8601FormatStyle()

    /// Parses "2026-09-14T15:30:00.000-05:00", "2026-09-14T15:30:00-05:00" and
    /// "…Z" forms. Nil when the string isn't a timestamp — callers must treat
    /// that as "unknown time", never as "now": a reading stamped now passes
    /// every freshness check however old it really is.
    static func parse(_ string: String) -> Date? {
        (try? Date(string, strategy: fractional)) ?? (try? Date(string, strategy: whole))
    }
}
