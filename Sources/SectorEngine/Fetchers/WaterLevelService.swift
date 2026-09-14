//
//  WaterLevelService.swift
//  Sector
//
//  Fetches current water levels (gage height / reservoir elevation) from the
//  USGS Instantaneous Values web service. Free, no API key.
//  https://waterservices.usgs.gov/
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

enum WaterTrend: Equatable {
    case rising
    case falling
    case steady
}

struct WaterLevelReading: Identifiable, Equatable {
    var id: String { siteCode + "-" + parameterCode }
    let siteCode: String
    let siteName: String
    let parameterCode: String      // e.g. "00065"
    let parameterName: String      // e.g. "Gage height, ft"
    let value: Double
    let unit: String               // e.g. "ft"
    let dateTime: Date
    let latitude: Double
    let longitude: Double
    let trend: WaterTrend
    let change: Double             // signed change over the lookback window, in `unit`
    /// The lookback-window values (oldest → newest) for a sparkline. May be empty.
    var history: [Double] = []
    /// Straight-line distance (miles) from the requested coordinate to this gage.
    /// Set by `latestReading(near:)`; nil when not computed against an origin.
    var distanceMiles: Double? = nil

    /// The lake's normal ("full") pool elevation, when known (reservoir readings
    /// only). Lets us say how far above/below full pool the water is sitting.
    var fullPoolFt: Double? = nil

    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
    }

    /// "0.2 ft above full pool" / "1.4 ft below full pool" / "at full pool" —
    /// nil when there's no known full-pool reference (rivers, unmapped lakes).
    var poolDeltaText: String? {
        guard let ref = fullPoolFt else { return nil }
        let delta = value - ref
        if abs(delta) < 0.1 { return "at full pool" }
        return String(format: "%.1f ft %@ full pool", abs(delta), delta > 0 ? "above" : "below")
    }
}

enum WaterLevelError: Error {
    case invalidURL
    case requestFailed
    case decodingFailed
}

final class WaterLevelService: Sendable {
    static let shared = WaterLevelService()
    private init() {}

    private let endpoint = "https://waterservices.usgs.gov/nwis/iv/"
    // 00065 = gage height (ft); 62614 = reservoir/lake water-surface elevation (ft).
    private let parameterCodes = "00065,62614"
    // USGS reports missing data with this sentinel.
    private let noDataValue = -999_999.0
    // How far back to look when deciding whether the level is rising/falling.
    private let lookbackPeriod = "PT12H"
    // Changes smaller than this (in the reading's native unit, ft) read as "steady".
    private let steadyThreshold = 0.1

    /// All active readings inside a box `halfWidthMiles` each way from the
    /// coordinate, each with its most recent value.
    func nearbyReadings(near coordinate: CLLocationCoordinate2D,
                        halfWidthMiles: Double,
                        parameterCd: String? = nil,
                        absThreshold: Double = 0.1,
                        pctThreshold: Double = 0) async throws -> [WaterLevelReading] {
        // Miles → degrees. A degree of longitude shrinks with latitude, so the box
        // is square on the ground, not on the map (floored so it can't blow up
        // near the poles).
        let latHalf = halfWidthMiles / 69.0
        let lonHalf = halfWidthMiles / (69.0 * Swift.max(cos(coordinate.latitude * .pi / 180), 0.2))
        let west = coordinate.longitude - lonHalf
        let east = coordinate.longitude + lonHalf
        let south = coordinate.latitude - latHalf
        let north = coordinate.latitude + latHalf

        var components = URLComponents(string: endpoint)
        components?.queryItems = [
            URLQueryItem(name: "format", value: "json"),
            URLQueryItem(name: "bBox", value: String(format: "%.5f,%.5f,%.5f,%.5f", west, south, east, north)),
            URLQueryItem(name: "parameterCd", value: parameterCd ?? parameterCodes),
            URLQueryItem(name: "siteStatus", value: "active"),
            URLQueryItem(name: "period", value: lookbackPeriod),
        ]

        guard let url = components?.url else { throw WaterLevelError.invalidURL }

        // Bounded — one slow gage query must not tentpole the whole parallel
        // snapshot. A dropped reading degrades the render (and is reported as
        // such); a long hang would block the response.
        let result: HTTPResult
        do {
            result = try await HTTP.get(url, timeout: Self.usgsTimeoutSeconds)
        } catch {
            throw WaterLevelError.requestFailed
        }

        guard result.isSuccess else {
            throw WaterLevelError.requestFailed
        }
        let data = result.body

        let decoded: USGSResponse
        do {
            decoded = try JSONDecoder().decode(USGSResponse.self, from: data)
        } catch {
            throw WaterLevelError.decodingFailed
        }

        return decoded.value.timeSeries.compactMap { series -> WaterLevelReading? in
            let datapoints = series.values.first?.value ?? []
            // Keep only real measurements, in chronological order (USGS returns oldest-first).
            let valid = datapoints.compactMap { point -> (Double, String)? in
                guard let v = Double(point.value), v != noDataValue else { return nil }
                return (v, point.dateTime)
            }
            guard let latest = valid.last,
                  let siteCode = series.sourceInfo.siteCode.first?.value,
                  let parameterCode = series.variable.variableCode.first?.value
            else { return nil }

            let measurement = latest.0
            // An unparseable timestamp drops the reading. It used to fall back to
            // `Date()`, which let a gage of unknown age pass every freshness check.
            guard let date = ISODate.parse(latest.1) else { return nil }

            // Compare the latest value to the oldest in the lookback window.
            // Threshold is the larger of an absolute floor and a percentage of
            // the value, so it works for both gage height (ft) and discharge
            // (cfs, which ranges from ~10 to 10,000+).
            let change = measurement - (valid.first?.0 ?? measurement)
            let thr = Swift.max(absThreshold, pctThreshold * abs(measurement))
            let trend: WaterTrend
            if change > thr {
                trend = .rising
            } else if change < -thr {
                trend = .falling
            } else {
                trend = .steady
            }

            return WaterLevelReading(
                siteCode: siteCode,
                siteName: series.sourceInfo.siteName,
                parameterCode: parameterCode,
                parameterName: series.variable.variableName,
                value: measurement,
                unit: series.variable.unit.unitCode,
                dateTime: date,
                latitude: series.sourceInfo.geoLocation.geogLocation.latitude,
                longitude: series.sourceInfo.geoLocation.geogLocation.longitude,
                trend: trend,
                change: change,
                history: valid.map { $0.0 }
            )
        }
    }

    /// The closest monitoring site to the coordinate. Expands the search box
    /// outward until it finds the nearest gage (so we almost always return one),
    /// and stamps how far that gage is — in miles — from the requested point.
    /// Beyond this, a "nearest gage" is a different water body, not yours — we'd
    /// rather show nothing than a river 50+ miles away (the reservoir bug).
    static let maxUsefulMiles = 40.0

    /// USGS waterservices is slow in a way that doesn't depend on the query: a
    /// request that finds ZERO gages still takes ~4–5s, and a 40-mile box ~5–8s
    /// (measured 2026-09-14). So one query per input, with room to finish.
    static let usgsTimeoutSeconds: TimeInterval = 11

    /// - Parameter maxMiles: the farthest gage this input will actually USE — the
    ///   search box is exactly that big, in ONE query. It used to try progressively
    ///   larger boxes (0.25°, 1.0°, then 2.5° ≈ 340×280 mi) for every input, even
    ///   temp and turbidity whose readings the builder discards beyond 15 and
    ///   10 miles. Because every USGS call carries a fixed multi-second cost, those
    ///   sequential queries added up and routinely blew the budget, dropping
    ///   level and discharge from the render.
    func latestReading(near coordinate: CLLocationCoordinate2D,
                       maxMiles: Double = maxUsefulMiles,
                       parameterCd: String? = nil,
                       absThreshold: Double = 0.1,
                       pctThreshold: Double = 0) async throws -> WaterLevelReading? {
        let origin = CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude)

        // Managed reservoirs (Kentucky Lake, Lake Barkley, …) have NO nearby USGS
        // pool gauge, so the fallback below grabs an unrelated river's gage height
        // and shows it as "the water level." For those lakes, read the real pool
        // elevation + forecast from NWPS instead. Only for the main water-level
        // lookup — never for discharge/temp/turbidity (those pass a parameterCd).
        if parameterCd == nil, let pool = await reservoirReading(for: coordinate) {
            return pool
        }

        // One box exactly `maxMiles` each way; the nearest gage inside the radius wins.
        let readings = try await nearbyReadings(near: coordinate, halfWidthMiles: maxMiles,
                                                parameterCd: parameterCd,
                                                absThreshold: absThreshold, pctThreshold: pctThreshold)
        let ranked = readings
            .map { r -> (WaterLevelReading, Double) in
                (r, origin.distance(from: CLLocation(latitude: r.latitude, longitude: r.longitude)) / 1609.34)
            }
            // The box's corners reach past maxMiles; beyond it isn't your water.
            .filter { $0.1 <= maxMiles }
        guard let nearest = ranked.min(by: { $0.1 < $1.1 }) else { return nil }
        var result = nearest.0
        result.distanceMiles = nearest.1
        return result
    }

    /// Nearest USGS **discharge** (streamflow) gage — cfs released/flowing, the
    /// observed "generator output / current" signal. Nationwide, no auth, no
    /// backend. Trend uses a relative threshold (discharge varies hugely by river).
    func nearestDischarge(near coordinate: CLLocationCoordinate2D) async throws -> WaterLevelReading? {
        try await latestReading(near: coordinate,
                                parameterCd: "00060",
                                absThreshold: 20,      // ignore <20 cfs noise
                                pctThreshold: 0.08)    // …or <8% of the flow
    }

    /// Nearest USGS **water temperature** gage (param 00010, °C). Drives fish
    /// activity — rough fish hold shallow & feed hard in warm water. Sparse
    /// coverage; returns nil where no temp gage is near.
    func nearestWaterTemp(near coordinate: CLLocationCoordinate2D) async throws -> WaterLevelReading? {
        try await latestReading(near: coordinate,
                                // No farther than the builder will use a temp gage.
                                maxMiles: ConditionsInputBuilder.maxWaterTempDistanceMiles,
                                parameterCd: "00010",
                                absThreshold: 0.5,     // °C; temp moves slowly
                                pctThreshold: 0)
    }

    /// Nearest USGS **turbidity** gage (param 63680, FNU). The master clarity
    /// signal for sight-shooting — drives the clarity factor + blown-out gate via
    /// the USGS Secchi regression. Sparse coverage; returns nil where none is
    /// near (the engine then falls back to the rain-decay model + lowers
    /// confidence). USGS reports raw FNU only — it can't distinguish algal from
    /// sediment, so callers treat the type as `.unknown`.
    func nearestTurbidity(near coordinate: CLLocationCoordinate2D) async throws -> WaterLevelReading? {
        try await latestReading(near: coordinate,
                                // No farther than the builder will use a turbidity gage.
                                maxMiles: ConditionsInputBuilder.maxTurbidityDistanceMiles,
                                parameterCd: "63680",
                                absThreshold: 1.0,     // FNU; ignore sub-1 noise
                                pctThreshold: 0.10)    // …or <10% of the reading
    }
}

// MARK: - USGS JSON (WaterML in JSON)

private struct USGSResponse: Decodable {
    let value: Value
    struct Value: Decodable {
        let timeSeries: [TimeSeries]
    }
}

private struct TimeSeries: Decodable {
    let sourceInfo: SourceInfo
    let variable: Variable
    let values: [ValueBlock]
}

private struct SourceInfo: Decodable {
    let siteName: String
    let siteCode: [CodeValue]
    let geoLocation: GeoLocation
}

private struct GeoLocation: Decodable {
    let geogLocation: GeogLocation
    struct GeogLocation: Decodable {
        let latitude: Double
        let longitude: Double
    }
}

private struct Variable: Decodable {
    let variableName: String
    let variableCode: [CodeValue]
    let unit: Unit
    struct Unit: Decodable {
        let unitCode: String
    }
}

private struct CodeValue: Decodable {
    let value: String
}

private struct ValueBlock: Decodable {
    let value: [Datapoint]
}

private struct Datapoint: Decodable {
    let value: String
    let dateTime: String
}

// MARK: - NOAA Tides (CO-OPS)
//
// Coastal tide predictions from NOAA's Tides & Currents service. Free, no API
// key. Two endpoints: a one-time station list (metadata) to find the nearest
// tidal station, then hi/lo predictions for that station.
// https://api.tidesandcurrents.gov/

enum TideKind: Equatable {
    case high
    case low
}

/// One upcoming tide extreme (a high or a low).
struct TideEvent: Equatable {
    let time: Date          // absolute instant
    let heightFt: Double    // feet, MLLW datum
    let kind: TideKind
}

/// A point on the continuous tide curve (for plotting the height over time).
struct TidePoint: Equatable {
    let time: Date
    let heightFt: Double
}

struct TideReading: Equatable {
    let stationId: String
    let stationName: String
    let latitude: Double
    let longitude: Double
    /// Straight-line distance (miles) from the requested point to the station.
    let distanceMiles: Double
    /// Upcoming hi/lo events (all after "now"), soonest first.
    let upcoming: [TideEvent]
    /// Interpolated water height (ft) right now, between the surrounding extremes.
    let currentLevelFt: Double?

    var nextHigh: TideEvent? { upcoming.first { $0.kind == .high } }
    var nextLow: TideEvent? { upcoming.first { $0.kind == .low } }
    /// The tide is coming in when the very next extreme is a high.
    var isRising: Bool { upcoming.first?.kind == .high }
}

struct TideStation {
    let id: String
    let name: String
    let latitude: Double
    let longitude: Double
}

final class NoaaTideService: Sendable {
    static let shared = NoaaTideService()
    private init() {}

    // NOAA tide stations exist only on tidal water, so "is there a station within
    // range?" doubles as the coastal test: an inland freshwater point has no
    // station within this radius → no tides (caller falls back to USGS stage).
    private let maxStationMiles = 35.0

    private let stationsURL = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=tidepredictions"
    private let dataGetter = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

    // The station list is effectively static — one fetch a day, shared by
    // concurrent callers.
    private let stationsCache = SingleFlightCache<String, [TideStation]>(
        ttl: 24 * 3600, failureTTL: 120, maxEntries: 1)

    /// The nearest tidal station's upcoming highs/lows — or nil when the point
    /// isn't coastal (no station within `maxStationMiles`) or the fetch fails.
    func nextTides(near coordinate: CLLocationCoordinate2D) async -> TideReading? {
        guard let stations = await loadStations(), !stations.isEmpty else { return nil }

        let origin = CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude)
        guard let nearest = stations.min(by: {
            origin.distance(from: CLLocation(latitude: $0.latitude, longitude: $0.longitude))
                < origin.distance(from: CLLocation(latitude: $1.latitude, longitude: $1.longitude))
        }) else { return nil }

        let miles = origin.distance(from: CLLocation(latitude: nearest.latitude, longitude: nearest.longitude)) / 1609.34
        guard miles <= maxStationMiles else { return nil }   // inland → not a tidal spot

        guard let events = await fetchPredictions(stationId: nearest.id) else { return nil }
        let now = Date()
        let upcoming = events.filter { $0.time > now }.sorted { $0.time < $1.time }
        guard !upcoming.isEmpty else { return nil }

        // Current level = half-cosine interpolation between the extremes bracketing now.
        let sortedAll = events.sorted { $0.time < $1.time }
        var currentLevel: Double? = nil
        if sortedAll.count >= 2 {
            for i in 0..<(sortedAll.count - 1) {
                let a = sortedAll[i], b = sortedAll[i + 1]
                let span = b.time.timeIntervalSince(a.time)
                if a.time <= now, now <= b.time, span > 0 {
                    let mid: Double = (a.heightFt + b.heightFt) / 2.0
                    let amp: Double = (a.heightFt - b.heightFt) / 2.0
                    let phase: Double = Double.pi * now.timeIntervalSince(a.time) / span
                    currentLevel = mid + amp * cos(phase)
                    break
                }
            }
        }

        return TideReading(stationId: nearest.id, stationName: nearest.name,
                           latitude: nearest.latitude, longitude: nearest.longitude,
                           distanceMiles: miles, upcoming: upcoming, currentLevelFt: currentLevel)
    }

    // MARK: Station list

    private func loadStations() async -> [TideStation]? {
        await stationsCache.value(for: "stations") { [self] in await self.fetchStations() }
    }

    private func fetchStations() async -> [TideStation]? {
        guard let url = URL(string: stationsURL) else { return nil }
        do {
            let result = try await HTTP.get(url)
            guard result.isSuccess else { return nil }
            let decoded = try JSONDecoder().decode(StationsResponse.self, from: result.body)
            // Skip any station missing coordinates rather than failing the whole list.
            let stations = decoded.stations.compactMap { s -> TideStation? in
                guard let id = s.id, let lat = s.lat, let lng = s.lng else { return nil }
                return TideStation(id: id, name: s.name ?? "Tide station", latitude: lat, longitude: lng)
            }
            return stations.isEmpty ? nil : stations
        } catch {
            return nil
        }
    }

    // MARK: Predictions

    // We request times in GMT and parse them as absolute instants, so "next"
    // is computed correctly regardless of the station's local zone.
    private static let noaaTimeFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd HH:mm"
        f.timeZone = TimeZone(identifier: "UTC")
        f.locale = Locale(identifier: "en_US_POSIX")
        return f
    }()

    private static let beginDateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "yyyyMMdd"
        f.timeZone = TimeZone(identifier: "UTC")
        f.locale = Locale(identifier: "en_US_POSIX")
        return f
    }()

    /// Highs & lows (`interval=hilo`) — powers "next tide" and the multi-day table.
    private func fetchPredictions(stationId: String) async -> [TideEvent]? {
        guard let preds = await rawPredictions(stationId: stationId, interval: "hilo", rangeHours: 96) else { return nil }
        return preds.compactMap { p -> TideEvent? in
            guard let date = Self.noaaTimeFormatter.date(from: p.t), let ft = Double(p.v) else { return nil }
            return TideEvent(time: date, heightFt: ft,
                             kind: p.type?.uppercased() == "H" ? .high : .low)
        }
    }

    /// The tide curve, built by interpolating a smooth half-cosine between the
    /// hi/lo extremes. Derived from `interval=hilo` (which every station supports,
    /// including subordinate stations that have no continuous prediction series),
    /// so the curve always renders and always matches the hi/lo table.
    func tideCurve(stationId: String) async -> [TidePoint]? {
        guard let preds = await rawPredictions(stationId: stationId, interval: "hilo", rangeHours: 96) else { return nil }
        let extremes: [(t: Date, h: Double)] = preds.compactMap { p in
            guard let d = Self.noaaTimeFormatter.date(from: p.t), let v = Double(p.v) else { return nil }
            return (d, v)
        }.sorted { $0.t < $1.t }
        guard extremes.count >= 2 else { return nil }

        var points: [TidePoint] = []
        let step: TimeInterval = 20 * 60   // 20-min samples
        for i in 0..<(extremes.count - 1) {
            let a = extremes[i], b = extremes[i + 1]
            let span = b.t.timeIntervalSince(a.t)
            guard span > 0 else { continue }
            let mid: Double = (a.h + b.h) / 2.0
            let amp: Double = (a.h - b.h) / 2.0
            var t = a.t
            while t < b.t {
                let phase: Double = Double.pi * t.timeIntervalSince(a.t) / span
                points.append(TidePoint(time: t, heightFt: mid + amp * cos(phase)))
                t = t.addingTimeInterval(step)
            }
        }
        if let last = extremes.last { points.append(TidePoint(time: last.t, heightFt: last.h)) }

        // Keep a readable ~2-day window around now.
        let now = Date()
        let start = now.addingTimeInterval(-6 * 3600)
        let end = now.addingTimeInterval(42 * 3600)
        let windowed = points.filter { $0.time >= start && $0.time <= end }
        return windowed.isEmpty ? points : windowed
    }

    /// Shared datagetter request. `interval` is "hilo" (extremes) or a minute
    /// count like "30"/"60" (continuous curve). Times come back in GMT.
    private func rawPredictions(stationId: String, interval: String, rangeHours: Int) async -> [PredictionsResponse.Prediction]? {
        var comps = URLComponents(string: dataGetter)
        comps?.queryItems = [
            URLQueryItem(name: "product", value: "predictions"),
            URLQueryItem(name: "interval", value: interval),
            URLQueryItem(name: "datum", value: "MLLW"),
            URLQueryItem(name: "units", value: "english"),          // feet
            URLQueryItem(name: "time_zone", value: "gmt"),
            URLQueryItem(name: "format", value: "json"),
            URLQueryItem(name: "application", value: "SectorBowfishing"),
            URLQueryItem(name: "station", value: stationId),
            URLQueryItem(name: "begin_date", value: Self.beginDateFormatter.string(from: Date())),
            URLQueryItem(name: "range", value: String(rangeHours)),
        ]
        guard let url = comps?.url else { return nil }
        do {
            let result = try await HTTP.get(url)
            guard result.isSuccess else { return nil }
            return try JSONDecoder().decode(PredictionsResponse.self, from: result.body).predictions
        } catch {
            return nil
        }
    }

    // MARK: Decoding

    private struct StationsResponse: Decodable {
        let stations: [Station]
        struct Station: Decodable {
            let id: String?
            let name: String?
            let lat: Double?
            let lng: Double?
        }
    }

    private struct PredictionsResponse: Decodable {
        let predictions: [Prediction]?
        struct Prediction: Decodable {
            let t: String       // "2026-07-14 03:03"
            let v: String       // "-0.700"
            let type: String?   // "H" / "L" (present only for interval=hilo)
        }
    }
}

// MARK: - Reservoir pool elevation (NWPS)

/// A managed reservoir mapped to its NWPS pool gauge, with a bounding box for
/// "is the user on this lake." USGS has no pool gauge on these lakes, so the
/// USGS nearest-gage fallback grabs an unrelated river; NWPS gives the real pool
/// elevation + a multi-day forecast instead.
private struct ReservoirGauge {
    let name: String
    let lid: String            // NWPS location id, e.g. "KYDK2"
    let fullPoolFt: Double?     // normal/summer full pool elevation (msl), if known
    let minLat, maxLat, minLon, maxLon: Double
    func contains(_ c: CLLocationCoordinate2D) -> Bool {
        c.latitude >= minLat && c.latitude <= maxLat && c.longitude >= minLon && c.longitude <= maxLon
    }
}

extension WaterLevelService {
    /// Known managed reservoirs → NWPS pool gauge. **Kentucky Lake and Lake
    /// Barkley are joined by the Barkley Canal and held at the SAME pool, rising
    /// and falling together**, so both use `KYDK2` (Kentucky Lake pool). To wire
    /// another lake that shows a wrong (far-river) level, drop in a row with its
    /// verified NWPS lid + a bounding box.
    fileprivate static let reservoirs: [ReservoirGauge] = [
        // Tennessee/Cumberland River lakes that HAVE an NWPS pool-elevation gauge.
        // Full pools = TVA/USACE normal summer pool (each verified against the
        // gauge's live reading). Boxes are per-lake so a coordinate maps to the
        // right pool. NOTE: Pickwick, Guntersville, Wheeler + Wilson are NOT here —
        // NWPS only carries river STAGE for those, not pool elevation.
        //
        // Kentucky Lake + Lake Barkley share a 359 ft pool (Barkley Canal); Eddyville
        // sits on Barkley, so list it first for the right label there.
        ReservoirGauge(name: "Lake Barkley",   lid: "KYDK2", fullPoolFt: 359.0,
                       minLat: 36.20, maxLat: 37.10, minLon: -88.25, maxLon: -87.55),
        ReservoirGauge(name: "Kentucky Lake",  lid: "KYDK2", fullPoolFt: 359.0,
                       minLat: 35.40, maxLat: 37.10, minLon: -88.60, maxLon: -88.15),
        ReservoirGauge(name: "Nickajack Lake", lid: "NKJT1", fullPoolFt: 634.5,
                       minLat: 34.90, maxLat: 35.12, minLon: -85.65, maxLon: -85.18),
        ReservoirGauge(name: "Chickamauga Lake", lid: "CKDT1", fullPoolFt: 682.5,
                       minLat: 35.10, maxLat: 35.58, minLon: -85.30, maxLon: -84.75),
        ReservoirGauge(name: "Watts Bar Lake", lid: "WBOT1", fullPoolFt: 741.0,
                       minLat: 35.55, maxLat: 35.79, minLon: -85.00, maxLon: -84.25),
        ReservoirGauge(name: "Fort Loudoun Lake", lid: "FLDT1", fullPoolFt: 813.0,
                       minLat: 35.79, maxLat: 36.05, minLon: -84.45, maxLon: -83.80),
    ]

    /// If `coordinate` sits on a mapped reservoir, fetch its NWPS pool elevation
    /// (+ forecast trend). Returns nil off-reservoir or on any fetch/parse
    /// failure, so the caller falls back to USGS.
    func reservoirReading(for coordinate: CLLocationCoordinate2D) async -> WaterLevelReading? {
        guard let lake = Self.reservoirs.first(where: { $0.contains(coordinate) }),
              let url = URL(string: "https://api.water.noaa.gov/nwps/v1/gauges/\(lake.lid)/stageflow"),
              let result = try? await HTTP.get(url), result.isSuccess,
              let decoded = try? JSONDecoder().decode(NWPSStageFlow.self, from: result.body)
        else { return nil }

        // Ordered pool values (observed then forecast), dropping NWPS's -9999
        // missing sentinel.
        func valid(_ s: NWPSStageFlow.Series?) -> [(value: Double, at: Date)] {
            guard let s, s.primaryName == "Pool" else { return [] }
            // Pool elevations are large positives (hundreds of ft msl); drop the
            // -9999 sentinel AND any 0/missing point so they don't tank the chart.
            return s.data.compactMap { p in
                guard let v = p.primary, v > 1, let at = ISODate.parse(p.validTime) else { return nil }
                return (value: v, at: at)
            }
        }
        let observed = valid(decoded.observed)
        let forecast = valid(decoded.forecast)
        // "Now" = most recent valid observed, else the first forecast point.
        guard let now = observed.last ?? forecast.first else { return nil }
        // Trend = where the forecast is headed across its horizon (the whole point
        // — for clarity/fish, whether it's rising or falling matters most).
        let horizon = forecast.last ?? now
        let change = horizon.value - now.value
        let trend: WaterTrend = change > 0.1 ? .rising : (change < -0.1 ? .falling : .steady)
        let units = decoded.forecast?.primaryUnits ?? decoded.observed?.primaryUnits ?? "ft"

        return WaterLevelReading(
            siteCode: lake.lid,
            siteName: lake.name,
            parameterCode: "62614",                    // reservoir water-surface elevation
            parameterName: "Reservoir pool, \(units)",
            value: now.value,
            unit: units,
            dateTime: now.at,
            latitude: coordinate.latitude,
            longitude: coordinate.longitude,
            trend: trend,
            change: change,
            history: observed.map { $0.value } + forecast.map { $0.value },
            fullPoolFt: lake.fullPoolFt
        )
    }
}

/// NWPS `/gauges/{lid}/stageflow` decoding (observed + forecast pool series).
private struct NWPSStageFlow: Decodable {
    let observed: Series?
    let forecast: Series?

    struct Series: Decodable {
        let primaryName: String?
        let primaryUnits: String?
        let data: [Point]
    }
    struct Point: Decodable {
        let validTime: String
        let primary: Double?
    }
}
