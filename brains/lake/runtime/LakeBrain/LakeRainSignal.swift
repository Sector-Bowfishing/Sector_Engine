//
//  LakeRainSignal.swift
//  Sector — Lake Brain: forecast rain at the lake, from the National Weather Service
//
//  One input to the adaptive freshness window (LakeLevelValidity): a lake that is about to get rain is
//  re-checked on a shorter window, so its published level stops being treated as current sooner.
//
//  Source: api.weather.gov (NWS, a U.S. Government work: public domain, no key; it asks every caller to send a
//  self-identifying User-Agent: LakeFeedHTTP's Sector-LakeBrain contact string). /points/{lat},{lon} gives the grid cell
//  (looked up once, then kept in the archive) and that cell's forecastGridData, whose `quantitativePrecipitation` layer is the forecast
//  liquid precipitation per period (usually 6 h). Outside NWS coverage (Alaska is partly covered, Hawaii, Canada)
//  or on any failure the signal is nil, and the validity rule treats an unknown rain signal conservatively.
//

import Foundation

public enum LakeRainSignal {

    /// Hours of forecast rain that count ("in the next 12 h").
    public static let horizonHours = 12.0

    struct Point: Equatable { var forecastGridData: String }

    /// The grid cell for a coordinate, from a /points response. nil when the response has no forecastGridData.
    static func decodePoint(_ data: Data) -> Point? {
        struct R: Decodable { let properties: P; struct P: Decodable { let forecastGridData: String? } }
        guard let g = (try? JSONDecoder().decode(R.self, from: data))?.properties.forecastGridData, !g.isEmpty else { return nil }
        return Point(forecastGridData: g)
    }

    /// Forecast liquid precipitation, inches, over [now, now + hours] from a forecastGridData response.
    /// A period that only partly overlaps the window counts in proportion to the overlap (an accumulation spread evenly
    /// over its period: the conservative reading of a 6 h total). nil when the layer is missing or covers none of the window.
    public static func forecastInches(gridData data: Data, now: Date, hours: Double = horizonHours) -> Double? {
        struct R: Decodable {
            let properties: P
            struct P: Decodable { let quantitativePrecipitation: Layer? }
            struct Layer: Decodable { let uom: String?; let values: [V]? }
            struct V: Decodable { let validTime: String; let value: Double? }
        }
        guard let layer = (try? JSONDecoder().decode(R.self, from: data))?.properties.quantitativePrecipitation,
              let values = layer.values else { return nil }
        let toInches: Double
        switch (layer.uom ?? "wmoUnit:mm").lowercased() {
        case let u where u.hasSuffix(":mm"): toInches = 1 / 25.4
        case let u where u.hasSuffix(":in"): toInches = 1
        default: return nil
        }
        let end = now.addingTimeInterval(hours * 3600)
        var total = 0.0
        var covered = false
        for v in values {
            guard let amount = v.value, amount >= 0, let (start, h) = parseValidTime(v.validTime), h > 0 else { continue }
            let stop = start.addingTimeInterval(Double(h) * 3600)
            let overlap = min(stop, end).timeIntervalSince(max(start, now))
            guard overlap > 0 else { continue }
            covered = true
            total += amount * toInches * overlap / (Double(h) * 3600)
        }
        return covered ? (total * 100).rounded() / 100 : nil
    }

    /// "2026-11-21T06:00:00+00:00/PT6H" (also P1DT6H) → (start, hours).
    static func parseValidTime(_ s: String) -> (Date, Int)? {
        let parts = s.split(separator: "/", maxSplits: 1).map(String.init)
        guard parts.count == 2, let start = isoDate(parts[0]) else { return nil }
        var d = parts[1]
        guard d.hasPrefix("P") else { return nil }
        d.removeFirst()
        var hours = 0
        if let t = d.firstIndex(of: "T") {
            let datePart = String(d[..<t]), timePart = String(d[d.index(after: t)...])
            if !datePart.isEmpty { guard datePart.hasSuffix("D"), let n = Int(datePart.dropLast()) else { return nil }; hours += 24 * n }
            if !timePart.isEmpty { guard timePart.hasSuffix("H"), let n = Int(timePart.dropLast()) else { return nil }; hours += n }
        } else {
            guard d.hasSuffix("D"), let n = Int(d.dropLast()) else { return nil }
            hours += 24 * n
        }
        return hours > 0 ? (start, hours) : nil
    }

    static func isoDate(_ s: String) -> Date? {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f.date(from: s)
    }

    /// The persisted coordinate → gridpoint map, in the Lake Brain's private archive.
    public static let pointsPath = "signals/nws-points.json"

    static func pointsURL(lat: Double, lon: Double) -> String {
        String(format: "https://api.weather.gov/points/%.4f,%.4f", lat, lon)
    }
}

/// Fetches the signal. The coordinate → grid-cell mapping (NWS `/points`) is stable, so it is persisted across runs in the Lake
/// archive (`LakeRainSignal.pointsPath`; LakeBrainRunner loads and saves it) and a steady hourly run makes ONE request per lake (the
/// gridpoint forecast; lakes in one cell share it). Requests to api.weather.gov are spaced `spacing` apart, whatever the runner's
/// concurrency. A cell whose forecast cannot be read is forgotten, so the next run looks the point up again.
public actor LakeRainSignalClient {
    public typealias Fetch = @Sendable (String) async -> Data?
    let fetch: Fetch
    let spacing: TimeInterval
    private var points: [String: String]
    private var unresolved: Set<String> = []
    private var grids: [String: Data?] = [:]
    private var nextSlot = Date.distantPast
    public private(set) var requests = 0

    /// `fetch` is the HTTP GET (the live one, `LakeRainSignalClient.live()`, is in LakeLevelFeeds.swift beside the other clients).
    public init(fetch: @escaping Fetch, spacing: TimeInterval = 0.25, knownPoints: [String: String] = [:]) {
        self.fetch = fetch; self.spacing = spacing; self.points = knownPoints
    }

    public static func pointKey(lat: Double, lon: Double) -> String { String(format: "%.2f,%.2f", lat, lon) }

    /// The persisted coordinate → gridpoint URL map (what the runner saves).
    public func pointMap() -> [String: String] { points }
    /// Seeds the map from the archive; entries already learned in this run win.
    public func seed(_ known: [String: String]) { points.merge(known) { mine, _ in mine } }

    private func get(_ url: String) async -> Data? {
        let slot = max(Date(), nextSlot)
        nextSlot = slot.addingTimeInterval(spacing)
        let wait = slot.timeIntervalSinceNow
        if wait > 0 { try? await Task.sleep(nanoseconds: UInt64(wait * 1_000_000_000)) }
        requests += 1
        return await fetch(url)
    }

    /// Forecast rain, inches, in the next 12 h at the coordinate. nil = unknown.
    public func nextHours(lat: Double, lon: Double, now: Date) async -> Double? {
        let key = Self.pointKey(lat: lat, lon: lon)
        var gridURL = points[key]
        if gridURL == nil, !unresolved.contains(key) {
            gridURL = await get(LakeRainSignal.pointsURL(lat: lat, lon: lon)).flatMap(LakeRainSignal.decodePoint)?.forecastGridData
            if let g = gridURL { points[key] = g } else { unresolved.insert(key) }
        }
        guard let gridURL else { return nil }
        let data: Data?
        if let cached = grids[gridURL] { data = cached }
        else { data = await get(gridURL); grids[gridURL] = data }
        guard let data, let inches = LakeRainSignal.forecastInches(gridData: data, now: now) else {
            points.removeValue(forKey: key)                                   // look the cell up again next run
            return nil
        }
        return inches
    }
}
