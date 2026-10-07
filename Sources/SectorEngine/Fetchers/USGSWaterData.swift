//
//  USGSWaterData.swift
//  SectorEngine
//
//  Client for the USGS Water Data OGC APIs (api.waterdata.usgs.gov/ogcapi/v1),
//  the replacement for the legacy WaterServices `/nwis/iv/` endpoint, which USGS
//  decommissions in Q1 2027 with intentional blackouts from November 2026.
//
//  It answers the same question the legacy call did — "every active series of
//  these parameters in this box, with its last 12 hours" — in the legacy shape,
//  so `WaterLevelService` keeps its trend math untouched:
//
//    1. `continuous` (bbox + parameter_code + time=PT12H) — every observation
//       in the window, one feature per value, paged via `rel=next`. A series
//       with nothing in the window never appears, which is exactly what the
//       legacy `period=PT12H` + `siteStatus=active` did.
//    2. `monitoring-locations` (id list) — site names, which `continuous`
//       does not carry.
//    3. `time-series-metadata` (id list) — only when a site reports one
//       parameter from more than one sensor, to pick the primary one.
//
//  Strings are mapped back to the legacy spellings (`ft^3/s` → `ft3/s`, the
//  WaterML variable names) because the gauge DTO hands them to the apps.
//
//  Set `USGS_API_KEY` to send a key (api.data.gov); without one the API rate
//  limits by IP and answers 429.
//

import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// One sensor's recent values at one site — the OGC equivalent of a legacy
/// WaterML `timeSeries` with its first `values` block.
struct USGSSeries: Equatable {
    let siteCode: String           // "03574500" — no "USGS-" prefix, as legacy
    let siteName: String
    let parameterCode: String
    let parameterName: String      // legacy WaterML variableName
    let unit: String               // legacy unitCode
    let latitude: Double
    let longitude: Double
    /// Oldest → newest, sentinel-free.
    let points: [(value: Double, at: Date)]

    static func == (a: USGSSeries, b: USGSSeries) -> Bool {
        a.siteCode == b.siteCode && a.siteName == b.siteName
            && a.parameterCode == b.parameterCode && a.parameterName == b.parameterName
            && a.unit == b.unit && a.latitude == b.latitude && a.longitude == b.longitude
            && a.points.map(\.value) == b.points.map(\.value)
            && a.points.map(\.at) == b.points.map(\.at)
    }
}

enum USGSWaterData {
    static let base = "https://api.waterdata.usgs.gov/ogcapi/v1/collections"

    /// USGS reports missing data with this sentinel.
    static let noDataValue = -999_999.0
    /// Features per `continuous` page. A 2.5° box of gage height runs ~5k.
    static let pageLimit = 10_000
    /// Safety stop on `rel=next` — a runaway query, not a real answer.
    static let maxPages = 5
    /// Ids per `monitoring-locations` / `time-series-metadata` request, to keep
    /// URLs short.
    static let idChunk = 100

    static let apiKey: String? = {
        let k = ProcessInfo.processInfo.environment["USGS_API_KEY"] ?? ""
        return k.isEmpty ? nil : k
    }()

    // MARK: Fetch

    /// Every series of `parameterCodes` inside the box with at least one valid
    /// value in the trailing `lookback` (an ISO-8601 duration, e.g. "PT12H").
    static func recentSeries(west: Double, south: Double, east: Double, north: Double,
                             parameterCodes: String, lookback: String,
                             timeout: TimeInterval) async throws -> [USGSSeries] {
        var url: URL? = continuousURL(west: west, south: south, east: east, north: north,
                                      parameterCodes: parameterCodes, lookback: lookback)
        var observations: [Observation] = []
        var pages = 0
        while let next = url, pages < maxPages {
            let page = try decodePage(try await get(next, timeout: timeout))
            observations += page.observations
            url = page.next
            pages += 1
        }

        let grouped = group(observations)

        // Names and sensor metadata are decoration on data we already hold —
        // a failure degrades the label or the sensor pick, never the reading.
        // Both are static, so they are cached for the process: after warm-up a
        // lookup is one request, which matters under the API's rate limit.
        let knownNames = await cache.names
        let knownMeta = await cache.meta
        let missingSites = Array(Set(grouped.map(\.siteCode)).subtracting(knownNames.keys))
            .sorted().map { "USGS-" + $0 }
        let missingMeta = duplicatedSeriesIds(grouped).filter { knownMeta[$0] == nil }
        async let newNames = siteNames(missingSites, timeout: timeout)
        async let newMeta = seriesMetadata(missingMeta, timeout: timeout)
        let names = await cache.addNames(await newNames)
        let meta = await cache.addMeta(await newMeta)
        return assemble(grouped, names: names, metadata: meta)
    }

    private actor Cache {
        var names: [String: String] = [:]
        var meta: [String: SeriesMeta] = [:]
        func addNames(_ n: [String: String]) -> [String: String] {
            names.merge(n) { a, _ in a }
            return names
        }
        func addMeta(_ m: [String: SeriesMeta]) -> [String: SeriesMeta] {
            meta.merge(m) { a, _ in a }
            return meta
        }
    }
    private static let cache = Cache()

    static func get(_ url: URL, timeout: TimeInterval) async throws -> Data {
        var request = URLRequest(url: url, timeoutInterval: timeout)
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let apiKey { request.setValue(apiKey, forHTTPHeaderField: "X-Api-Key") }
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await Net.session.data(for: request)
        } catch {
            throw WaterLevelError.requestFailed
        }
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw WaterLevelError.requestFailed
        }
        return data
    }

    private static func siteNames(_ ids: [String], timeout: TimeInterval) async -> [String: String] {
        guard !ids.isEmpty else { return [:] }
        return await withTaskGroup(of: [String: String].self) { group in
            for chunk in stride(from: 0, to: ids.count, by: idChunk).map({ Array(ids[$0..<min($0 + idChunk, ids.count)]) }) {
                group.addTask {
                    guard let url = idQueryURL("monitoring-locations", ids: chunk,
                                               properties: "monitoring_location_name"),
                          let data = try? await get(url, timeout: timeout)
                    else { return [:] }
                    return decodeNames(data)
                }
            }
            var all: [String: String] = [:]
            for await part in group { all.merge(part) { a, _ in a } }
            return all
        }
    }

    private static func seriesMetadata(_ ids: [String], timeout: TimeInterval) async -> [String: SeriesMeta] {
        guard !ids.isEmpty else { return [:] }
        return await withTaskGroup(of: [String: SeriesMeta].self) { group in
            for chunk in stride(from: 0, to: ids.count, by: idChunk).map({ Array(ids[$0..<min($0 + idChunk, ids.count)]) }) {
                group.addTask {
                    guard let url = idQueryURL("time-series-metadata", ids: chunk,
                                               properties: "primary,sublocation_identifier,begin"),
                          let data = try? await get(url, timeout: timeout)
                    else { return [:] }
                    return decodeMetadata(data)
                }
            }
            var all: [String: SeriesMeta] = [:]
            for await part in group { all.merge(part) { a, _ in a } }
            return all
        }
    }

    // MARK: URLs

    static func continuousURL(west: Double, south: Double, east: Double, north: Double,
                              parameterCodes: String, lookback: String) -> URL? {
        var c = URLComponents(string: "\(base)/continuous/items")
        c?.queryItems = [
            URLQueryItem(name: "f", value: "json"),
            URLQueryItem(name: "bbox", value: String(format: "%.5f,%.5f,%.5f,%.5f", west, south, east, north)),
            URLQueryItem(name: "parameter_code", value: parameterCodes),
            URLQueryItem(name: "time", value: lookback),
            URLQueryItem(name: "limit", value: String(pageLimit)),
            URLQueryItem(name: "properties",
                         value: "time_series_id,monitoring_location_id,parameter_code,time,value,unit_of_measure"),
        ]
        return c?.url
    }

    private static func idQueryURL(_ collection: String, ids: [String], properties: String) -> URL? {
        var c = URLComponents(string: "\(base)/\(collection)/items")
        c?.queryItems = [
            URLQueryItem(name: "f", value: "json"),
            URLQueryItem(name: "id", value: ids.joined(separator: ",")),
            URLQueryItem(name: "properties", value: properties),
            URLQueryItem(name: "limit", value: String(ids.count)),
        ]
        return c?.url
    }

    // MARK: Pure assembly (unit-tested against recorded responses)

    struct Observation {
        let seriesId: String
        let siteCode: String
        let parameterCode: String
        let unit: String
        let at: Date
        let value: Double
        let latitude: Double
        let longitude: Double
    }

    /// One sensor's observations, before the duplicate-sensor pick and naming.
    struct RawSeries {
        let seriesId: String
        let siteCode: String
        let parameterCode: String
        let unit: String
        let latitude: Double
        let longitude: Double
        let points: [(value: Double, at: Date)]
    }

    struct SeriesMeta: Decodable, Sendable {
        let primary: String?
        let sublocation_identifier: String?
        let begin: String?
    }

    static func decodePage(_ data: Data) throws -> (observations: [Observation], next: URL?) {
        let fc: FeatureCollection<ContinuousProps>
        do {
            fc = try JSONDecoder().decode(FeatureCollection<ContinuousProps>.self, from: data)
        } catch {
            throw WaterLevelError.decodingFailed
        }
        let observations = fc.features.compactMap { f -> Observation? in
            let p = f.properties
            guard let raw = p.value, let v = Double(raw), v != noDataValue,
                  let t = p.time, let at = parseTime(t),
                  let coords = f.geometry?.coordinates, coords.count >= 2
            else { return nil }
            return Observation(seriesId: p.time_series_id, siteCode: stripAgency(p.monitoring_location_id),
                               parameterCode: p.parameter_code, unit: p.unit_of_measure ?? "",
                               at: at, value: v, latitude: coords[1], longitude: coords[0])
        }
        let next = fc.links?.first { $0.rel == "next" }.flatMap { URL(string: $0.href) }
        return (observations, next)
    }

    /// `monitoring-locations` → site code (no agency prefix) → name.
    static func decodeNames(_ data: Data) -> [String: String] {
        guard let fc = try? JSONDecoder().decode(FeatureCollection<LocationProps>.self, from: data) else { return [:] }
        var out: [String: String] = [:]
        for f in fc.features {
            if let id = f.id, let name = f.properties.monitoring_location_name { out[stripAgency(id)] = name }
        }
        return out
    }

    /// `time-series-metadata` → series id → the fields the sensor pick reads.
    static func decodeMetadata(_ data: Data) -> [String: SeriesMeta] {
        guard let fc = try? JSONDecoder().decode(FeatureCollection<SeriesMeta>.self, from: data) else { return [:] }
        var out: [String: SeriesMeta] = [:]
        for f in fc.features { if let id = f.id { out[id] = f.properties } }
        return out
    }

    static func group(_ observations: [Observation]) -> [RawSeries] {
        Dictionary(grouping: observations, by: \.seriesId).values.compactMap { obs in
            guard let first = obs.first else { return nil }
            let points = obs.sorted { $0.at < $1.at }.map { (value: $0.value, at: $0.at) }
            return RawSeries(seriesId: first.seriesId, siteCode: first.siteCode,
                             parameterCode: first.parameterCode, unit: first.unit,
                             latitude: first.latitude, longitude: first.longitude, points: points)
        }
    }

    /// Series ids at a (site, parameter) that more than one sensor reports.
    static func duplicatedSeriesIds(_ series: [RawSeries]) -> [String] {
        Dictionary(grouping: series) { "\($0.siteCode)|\($0.parameterCode)" }
            .values.filter { $0.count > 1 }.flatMap { $0.map(\.seriesId) }.sorted()
    }

    /// One series per (site, parameter), named and in legacy spellings.
    ///
    /// Where a site reports a parameter from several sensors (levee flood vs
    /// protected side, lock chamber inside vs outside, a primary and a backup
    /// sensor), legacy WaterServices returned them all under one timeSeries and
    /// the engine took the first block — an order USGS never documented, which
    /// on 2026-10-07 put a "Secondary Sensor" ahead of the primary at several
    /// Texas sites. Here the pick is explicit: the series USGS marks Primary,
    /// then the one at the site itself (no sublocation), then the longest-running
    /// sensor, then the id so it is stable.
    static func assemble(_ series: [RawSeries], names: [String: String],
                         metadata: [String: SeriesMeta]) -> [USGSSeries] {
        func rank(_ s: RawSeries) -> (Int, Int, String, String) {
            let m = metadata[s.seriesId]
            return (m?.primary == "Primary" ? 0 : 1,
                    m?.sublocation_identifier == nil ? 0 : 1,
                    m?.begin ?? "9999",
                    s.seriesId)
        }
        let picked = Dictionary(grouping: series) { "\($0.siteCode)|\($0.parameterCode)" }
            .values.compactMap { candidates in candidates.min { rank($0) < rank($1) } }

        return picked
            .sorted { ($0.siteCode, $0.parameterCode) < ($1.siteCode, $1.parameterCode) }
            .map { s in
                let unit = legacyUnit(s.unit)
                return USGSSeries(siteCode: s.siteCode,
                                  siteName: names[s.siteCode] ?? "USGS \(s.siteCode)",
                                  parameterCode: s.parameterCode,
                                  parameterName: legacyParameterName(s.parameterCode, unit: unit),
                                  unit: unit, latitude: s.latitude, longitude: s.longitude,
                                  points: s.points)
            }
    }

    /// OGC `unit_of_measure` → the legacy WaterML `unitCode`.
    static func legacyUnit(_ unit: String) -> String {
        switch unit {
        case "ft^3/s": return "ft3/s"
        case "degC":   return "deg C"
        case "_FNU":   return "FNU"
        default:       return unit
        }
    }

    /// The legacy WaterML `variableName`, verbatim — HTML entities included,
    /// because that is what the gauge DTO has always sent.
    static func legacyParameterName(_ code: String, unit: String) -> String {
        switch code {
        case "00065": return "Gage height, ft"
        case "62614": return "Lake or reservoir water surface elevation above NGVD 1929, ft"
        case "00060": return "Streamflow, ft&#179;/s"
        case "00010": return "Temperature, water, &#176;C"
        case "63680": return "Turbidity, water, unfiltered, monochrome near infra-red LED light, 780-900 nm, detection angle 90 &#177;2.5&#176;, formazin nephelometric units (FNU)"
        default:      return "\(code), \(unit)"
        }
    }

    static func stripAgency(_ id: String) -> String {
        id.hasPrefix("USGS-") ? String(id.dropFirst(5)) : id
    }

    private static let isoFractional: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()
    private static let iso: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    static func parseTime(_ s: String) -> Date? {
        iso.date(from: s) ?? isoFractional.date(from: s)
    }

    // MARK: Wire format

    private struct FeatureCollection<P: Decodable>: Decodable {
        let features: [Feature<P>]
        let links: [Link]?
    }
    private struct Feature<P: Decodable>: Decodable {
        let id: String?
        let properties: P
        let geometry: Geometry?
    }
    private struct Geometry: Decodable { let coordinates: [Double] }
    private struct Link: Decodable {
        let rel: String?
        let href: String
    }
    private struct ContinuousProps: Decodable {
        let time_series_id: String
        let monitoring_location_id: String
        let parameter_code: String
        let time: String?
        let value: String?
        let unit_of_measure: String?
    }
    private struct LocationProps: Decodable { let monitoring_location_name: String? }
}
