//
//  LakeTempSensorService.swift
//  Sector — the lake's own water-temperature sensor
//
//  29 directory lakes have a surface temperature sensor inside their outline
//  that reported within the last 30 days (docs/data/temp_sensors.csv, built
//  2026-09-27 from USGS lake sites and USACE CWMS pool/forebay series, with
//  dam-release and deep sensors thrown out). When the spot is on one of them,
//  the reading is the lake's measured temperature and the model steps aside.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

enum LakeTempSensorService {

    /// A reading older than this is not "now".
    static let maxAgeHours = 72.0

    /// The latest reading from `lake`'s sensor as a WaterLevelReading (value in
    /// °C, the unit the snapshot carries water temperature in), or nil.
    static func latest(for lake: DirectoryLake) async -> WaterLevelReading? {
        guard let sensor = lake.tempSensor else { return nil }
        let parts = sensor.split(separator: ":", maxSplits: 2).map(String.init)
        let reading: WaterLevelReading?
        switch parts.first {
        case "usgs" where parts.count == 2:
            reading = try? await WaterLevelService.shared.nearbyReadings(
                near: lake.coordinate, parameterCd: "00010", sites: parts[1], absThreshold: 0.5)
                .max { $0.dateTime < $1.dateTime }
        case "cwms" where parts.count == 3:
            reading = await cwms(office: parts[1], tsid: parts[2], lake: lake)
        default:
            reading = nil
        }
        guard let r = reading, Date().timeIntervalSince(r.dateTime) <= maxAgeHours * 3600 else { return nil }
        return r
    }

    private struct CWMSValues: Decodable {
        let values: [[Double?]]?
        let units: String?
    }

    private static func cwms(office: String, tsid: String, lake: DirectoryLake) async -> WaterLevelReading? {
        var c = URLComponents(string: "https://cwms-data.usace.army.mil/cwms-data/timeseries")
        let begin = ISO8601DateFormatter().string(from: Date().addingTimeInterval(-3 * 86_400))
        c?.queryItems = [URLQueryItem(name: "name", value: tsid), URLQueryItem(name: "office", value: office),
                         URLQueryItem(name: "begin", value: begin), URLQueryItem(name: "unit", value: "EN"),
                         URLQueryItem(name: "page-size", value: "500")]
        guard let url = c?.url,
              let result = try? await HTTP.get(url, headers: ["Accept": "application/json;version=2"]),
              result.isSuccess else { return nil }
        let body = String(decoding: result.body, as: UTF8.self)
        guard let decoded = try? JSONDecoder().decode(CWMSValues.self, from: Data(body.utf8)),
              let rows = decoded.values else { return nil }
        let points = rows.compactMap { row -> (Date, Double)? in
            guard row.count >= 2, let ms = row[0], let v = row[1], v > -50, v < 130 else { return nil }
            return (Date(timeIntervalSince1970: ms / 1000), v)
        }.sorted { $0.0 < $1.0 }
        guard let last = points.last, let first = points.first else { return nil }
        let celsius = (decoded.units ?? "F").uppercased().contains("C")
        func toF(_ v: Double) -> Double { celsius ? v * 9 / 5 + 32 : v }
        let latestF = toF(last.1)
        let changeF = latestF - toF(first.1)
        var reading = WaterLevelReading(
            siteCode: tsid, siteName: "\(lake.name) (USACE \(office))",
            parameterCode: "00010", parameterName: "Temperature, water",
            value: (latestF - 32) * 5 / 9, unit: "deg C", dateTime: last.0,
            latitude: lake.lat, longitude: lake.lon,
            trend: changeF > 0.9 ? .rising : (changeF < -0.9 ? .falling : .steady),
            change: changeF * 5 / 9)
        reading.provider = "USACE CWMS"
        return reading
    }
}
