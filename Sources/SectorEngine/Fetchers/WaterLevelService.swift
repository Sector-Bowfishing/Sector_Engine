//
//  WaterLevelService.swift
//  Sector
//
//  Fetches current water levels (gage height / reservoir elevation) from the
//  USGS Water Data OGC API (see USGSWaterData.swift), plus reservoir pool
//  elevation from NOAA NWPS for lakes USGS does not gauge. Free, no API key.
//  https://api.waterdata.usgs.gov/ogcapi/v0/
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
    var siteName: String
    let parameterCode: String      // e.g. "00065"
    let parameterName: String      // e.g. "Gage height, ft"
    let value: Double
    let unit: String               // e.g. "ft"
    let dateTime: Date
    let latitude: Double
    let longitude: Double
    var trend: WaterTrend
    var change: Double             // signed change over the lookback window, in `unit`
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

final class WaterLevelService {
    static let shared = WaterLevelService()
    private init() {}

    // 00065 = gage height (ft); 62614 = reservoir/lake water-surface elevation (ft).
    private let parameterCodes = "00065,62614"
    // How far back to look when deciding whether the level is rising/falling.
    private let lookbackHours: Double = 12

    /// Candidate gages within a box around the coordinate, each with its most
    /// recent value — no history.
    ///
    /// History used to come back for every gage in the box, because the legacy
    /// endpoint had no way to ask for "newest value only". The caller then threw
    /// all but one away. Now only the gage that wins pays for its series.
    func nearbyReadings(near coordinate: CLLocationCoordinate2D,
                        radiusDegrees: Double = 0.25,
                        parameterCd: String? = nil,
                        absThreshold: Double = 0.1,
                        pctThreshold: Double = 0) async throws -> [WaterLevelReading] {
        let codes = (parameterCd ?? parameterCodes).split(separator: ",").map(String.init)
        let box = (west: coordinate.longitude - radiusDegrees,
                   south: coordinate.latitude - radiusDegrees,
                   east: coordinate.longitude + radiusDegrees,
                   north: coordinate.latitude + radiusDegrees)

        let latest = try await USGSWaterData.latest(bbox: box, parameterCodes: codes)
        guard !latest.isEmpty else { return [] }

        return latest.map { l in
            WaterLevelReading(
                siteCode: l.siteId,
                siteName: "",                       // filled in by `latestReading`
                parameterCode: l.parameterCode,
                parameterName: USGSWaterData.parameterName(l.parameterCode, unit: l.unit),
                value: l.value,
                unit: l.unit,
                dateTime: l.time,
                latitude: l.latitude,
                longitude: l.longitude,
                trend: .steady,                     // resolved with the history
                change: 0,
                history: [])
        }
    }

    /// Fill in the trend, change, history and name for the gage that was chosen.
    /// Two small requests for one gage, in parallel, instead of a full series for
    /// every gage in the box.
    private func enrich(_ reading: WaterLevelReading,
                        near coordinate: CLLocationCoordinate2D,
                        radiusDegrees: Double,
                        absThreshold: Double,
                        pctThreshold: Double) async -> WaterLevelReading {
        var out = reading
        let box = (west: coordinate.longitude - radiusDegrees,
                   south: coordinate.latitude - radiusDegrees,
                   east: coordinate.longitude + radiusDegrees,
                   north: coordinate.latitude + radiusDegrees)

        async let historyTask = try? await USGSWaterData.history(
            siteId: reading.siteCode, parameterCode: reading.parameterCode,
            since: Date().addingTimeInterval(-lookbackHours * 3600))
        async let namesTask = USGSWaterData.siteNames(bbox: box)

        let history = (await historyTask) ?? []
        out.history = history
        out.siteName = (await namesTask)[reading.siteCode] ?? reading.siteCode

        // Same rule as before: the latest value against the oldest in the
        // window, with a threshold that is the larger of an absolute floor and a
        // fraction of the reading — gage height moves in tenths of a foot,
        // discharge in thousands of cfs.
        if let oldest = history.first {
            let change = reading.value - oldest
            let thr = Swift.max(absThreshold, pctThreshold * abs(reading.value))
            out.change = change
            out.trend = change > thr ? .rising : (change < -thr ? .falling : .steady)
        }
        return out
    }

    /// Beyond this, a "nearest gage" is a different water body, not yours — we'd
    /// rather show nothing than a river 50+ miles away (the reservoir bug).
    private static let maxUsefulMiles = 40.0

    /// The closest monitoring site to the coordinate. Expands the search box
    /// outward until it finds one, and stamps how far it is in miles.
    func latestReading(near coordinate: CLLocationCoordinate2D,
                       radiusDegrees: Double = 0.25,
                       parameterCd: String? = nil,
                       absThreshold: Double = 0.1,
                       pctThreshold: Double = 0) async throws -> WaterLevelReading? {
        let origin = CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude)

        // Managed reservoirs have NO nearby USGS pool gauge, so the fallback
        // below grabs an unrelated river's gage height and shows it as "the
        // water level." For those lakes read the real pool elevation + forecast
        // from NWPS instead. Only for the main water-level lookup — never for
        // discharge/temp/turbidity (those pass a parameterCd).
        if parameterCd == nil, let pool = await reservoirReading(for: coordinate) {
            return pool
        }

        // Progressively larger boxes. The first (small) box hits for most lakes;
        // the wider ones only run when nothing closer exists.
        for radius in [radiusDegrees, 1.0, 2.5] {
            let readings = try await nearbyReadings(near: coordinate, radiusDegrees: radius,
                                                    parameterCd: parameterCd,
                                                    absThreshold: absThreshold,
                                                    pctThreshold: pctThreshold)
            guard let nearest = readings.min(by: {
                origin.distance(from: CLLocation(latitude: $0.latitude, longitude: $0.longitude))
                    < origin.distance(from: CLLocation(latitude: $1.latitude, longitude: $1.longitude))
            }) else { continue }

            var result = nearest
            let gage = CLLocation(latitude: nearest.latitude, longitude: nearest.longitude)
            result.distanceMiles = origin.distance(from: gage) / 1609.34
            // A gage farther than this isn't your water — don't present it as fact.
            if let d = result.distanceMiles, d > Self.maxUsefulMiles { return nil }
            var enriched = await enrich(result, near: coordinate, radiusDegrees: radius,
                                        absThreshold: absThreshold, pctThreshold: pctThreshold)
            enriched.distanceMiles = result.distanceMiles
            return enriched
        }
        return nil
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
                                parameterCd: "63680",
                                absThreshold: 1.0,     // FNU; ignore sub-1 noise
                                pctThreshold: 0.10)    // …or <10% of the reading
    }
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

final class NoaaTideService {
    static let shared = NoaaTideService()
    private init() {}

    // NOAA tide stations exist only on tidal water, so "is there a station within
    // range?" doubles as the coastal test: an inland freshwater point has no
    // station within this radius → no tides (caller falls back to USGS stage).
    private let maxStationMiles = 35.0

    private let stationsURL = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=tidepredictions"
    private let dataGetter = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

    // The station list is effectively static, so cache it for the session.
    private var cachedStations: [TideStation]?

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
        if let cachedStations { return cachedStations }
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
            cachedStations = stations
            return stations
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
        // Nickajack's box started at 34.90, which reaches ~7 miles BELOW
        // Nickajack Dam (35.00, -85.60) into Guntersville's pool. Raised to the
        // dam so the two reservoirs stop overlapping; Nickajack is listed first
        // so the seam itself resolves upstream.
        ReservoirGauge(name: "Nickajack Lake", lid: "NKJT1", fullPoolFt: 634.5,
                       minLat: 35.00, maxLat: 35.12, minLon: -85.65, maxLon: -85.18),
        // Box from the NHD high-resolution waterbody polygon (permanent id
        // 139326855), not estimated. Summer full pool 595.44 ft; TVA draws down
        // to roughly 593 in winter, so "below full pool" reads low all winter by
        // design — a seasonal guide curve, not a single number, is the real fix.
        ReservoirGauge(name: "Lake Guntersville", lid: "GVHA1", fullPoolFt: 595.44,
                       minLat: 34.28, maxLat: 35.04, minLon: -86.42, maxLon: -85.60),
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
                guard let v = p.primary, v > 1 else { return nil }
                return (value: v, at: NWPSStageFlow.parseTime(p.validTime))
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

    static func parseTime(_ s: String) -> Date {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f.date(from: s) ?? Date()
    }
}
