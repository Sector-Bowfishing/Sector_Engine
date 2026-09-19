//
//  USGSWaterData.swift
//  SectorEngine
//
//  The current USGS Water Data OGC API, replacing the legacy WaterServices
//  instantaneous-values endpoint.
//
//  Two reasons, one mandated and one measured.
//
//  Mandated: new work is not to be built against `waterservices.usgs.gov/nwis/iv`.
//  It is the retiring interface, and it returned 503 during the architecture
//  audit while the OGC host answered in 0.36 s.
//
//  Measured: the legacy path fails intermittently from inside the engine while
//  succeeding from curl against the identical URL, headers included. A
//  `/conditions` render fires four concurrent USGS requests — level, discharge,
//  temperature, turbidity — and in that burst the first one throws often enough
//  that Guntersville was rendering with no water level and no discharge at all.
//  That is a silent degradation: the factors drop, the score still prints.
//
//  The shape is different too, and better for us. Legacy returned a whole
//  12-hour series for every gage in the box just to find the nearest one; here
//  `latest-continuous` answers "what is the newest value at each gage" directly,
//  and only the winning gage pays for its history.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

enum USGSWaterData {

    private static let base = "https://api.waterdata.usgs.gov/ogcapi/v0/collections"

    /// USGS returns bare parameter codes; the legacy API sent a human name
    /// alongside and the UI shows it. Only the codes the engine asks for.
    static func parameterName(_ code: String, unit: String) -> String {
        switch code {
        case "00065": return "Gage height, \(unit)"
        case "62614": return "Reservoir elevation, \(unit)"
        case "00060": return "Discharge, \(unit)"
        case "00010": return "Temperature, water, \(unit)"
        case "63680": return "Turbidity, \(unit)"
        default:      return "Parameter \(code), \(unit)"
        }
    }

    /// One gage's most recent value for one parameter.
    struct Latest {
        let siteId: String          // bare USGS site number, "USGS-" stripped
        let parameterCode: String
        let value: Double
        let unit: String
        let time: Date
        let latitude: Double
        let longitude: Double
    }

    /// Newest reading per gage inside `bbox`, for any of `parameterCodes`.
    ///
    /// One request regardless of how many gages are in the box, and no history —
    /// which is the whole point: the caller is choosing a gage, not charting one.
    static func latest(bbox: (west: Double, south: Double, east: Double, north: Double),
                       parameterCodes: [String],
                       limit: Int = 200) async throws -> [Latest] {
        var comp = URLComponents(string: "\(base)/latest-continuous/items")
        comp?.queryItems = [
            URLQueryItem(name: "bbox", value: String(format: "%.5f,%.5f,%.5f,%.5f",
                                                     bbox.west, bbox.south, bbox.east, bbox.north)),
            URLQueryItem(name: "parameter_code", value: parameterCodes.joined(separator: ",")),
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "f", value: "json"),
        ]
        guard let url = comp?.url else { throw WaterLevelError.invalidURL }

        let result: HTTPResult
        do { result = try await HTTP.get(url) } catch { throw WaterLevelError.requestFailed }
        guard result.isSuccess else { throw WaterLevelError.requestFailed }

        let decoded: FeatureCollection
        do { decoded = try JSONDecoder().decode(FeatureCollection.self, from: result.body) }
        catch { throw WaterLevelError.decodingFailed }

        return decoded.features.compactMap { f -> Latest? in
            let p = f.properties
            // `value` arrives as a string, and a gage with nothing to report
            // sends null rather than a sentinel — no -999999 to filter here.
            guard let raw = p.value, let v = Double(raw),
                  let code = p.parameter_code,
                  let time = parse(p.time),
                  let coords = f.geometry?.coordinates, coords.count >= 2
            else { return nil }
            return Latest(siteId: strippedSiteId(p.monitoring_location_id),
                          parameterCode: code, value: v,
                          unit: p.unit_of_measure ?? "",
                          time: time, latitude: coords[1], longitude: coords[0])
        }
    }

    /// One gage's values back to `since`, oldest first — for the trend and the
    /// sparkline. Fetched only for the gage that actually won.
    static func history(siteId: String, parameterCode: String,
                        since: Date, now: Date = Date()) async throws -> [Double] {
        var comp = URLComponents(string: "\(base)/continuous/items")
        comp?.queryItems = [
            URLQueryItem(name: "monitoring_location_id", value: "USGS-\(siteId)"),
            URLQueryItem(name: "parameter_code", value: parameterCode),
            URLQueryItem(name: "datetime", value: "\(iso(since))/\(iso(now))"),
            URLQueryItem(name: "limit", value: "500"),
            URLQueryItem(name: "f", value: "json"),
        ]
        guard let url = comp?.url else { throw WaterLevelError.invalidURL }
        guard let result = try? await HTTP.get(url), result.isSuccess,
              let decoded = try? JSONDecoder().decode(FeatureCollection.self, from: result.body)
        else { return [] }        // no history is a worse chart, not a failed read

        return decoded.features
            .compactMap { f -> (Date, Double)? in
                guard let raw = f.properties.value, let v = Double(raw),
                      let t = parse(f.properties.time) else { return nil }
                return (t, v)
            }
            .sorted { $0.0 < $1.0 }
            .map(\.1)
    }

    /// Site names for everything in the box, in one request. `latest-continuous`
    /// carries only ids, and the app shows the gage's name.
    static func siteNames(bbox: (west: Double, south: Double, east: Double, north: Double),
                          limit: Int = 200) async -> [String: String] {
        var comp = URLComponents(string: "\(base)/monitoring-locations/items")
        comp?.queryItems = [
            URLQueryItem(name: "bbox", value: String(format: "%.5f,%.5f,%.5f,%.5f",
                                                     bbox.west, bbox.south, bbox.east, bbox.north)),
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "f", value: "json"),
        ]
        guard let url = comp?.url,
              let result = try? await HTTP.get(url), result.isSuccess,
              let decoded = try? JSONDecoder().decode(SiteCollection.self, from: result.body)
        else { return [:] }
        var out: [String: String] = [:]
        for f in decoded.features {
            guard let id = f.properties.monitoring_location_number,
                  let name = f.properties.monitoring_location_name else { continue }
            out[id] = name
        }
        return out
    }

    // MARK: Decoding

    private struct FeatureCollection: Decodable {
        let features: [Feature]
        struct Feature: Decodable {
            let properties: Properties
            let geometry: Geometry?
        }
        struct Properties: Decodable {
            let monitoring_location_id: String?
            let parameter_code: String?
            let value: String?
            let unit_of_measure: String?
            let time: String?
        }
        struct Geometry: Decodable { let coordinates: [Double]? }
    }

    private struct SiteCollection: Decodable {
        let features: [Feature]
        struct Feature: Decodable { let properties: Properties }
        struct Properties: Decodable {
            let monitoring_location_number: String?
            let monitoring_location_name: String?
        }
    }

    // MARK: Time

    /// The OGC API stamps `+00:00`, never fractional seconds — but a formatter
    /// configured for one shape silently fails on the other, and a failed parse
    /// used to become `Date()`, i.e. "this reading is current". Try both.
    private static let withFraction: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()
    private static let plain: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    static func parse(_ s: String?) -> Date? {
        guard let s else { return nil }
        return plain.date(from: s) ?? withFraction.date(from: s)
    }

    private static func iso(_ d: Date) -> String { plain.string(from: d) }

    private static func strippedSiteId(_ raw: String?) -> String {
        guard let raw else { return "" }
        return raw.hasPrefix("USGS-") ? String(raw.dropFirst(5)) : raw
    }
}
