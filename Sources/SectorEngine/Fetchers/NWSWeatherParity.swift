//
//  NWSWeatherParity.swift
//  SectorEngine
//
//  Pure per-tile comparison of today's Open-Meteo `WeatherReading` with the
//  NWS/NBM reading (conditions consolidation spec V1 §1, §6). Produces one
//  `NWSTileParity` per weather tile, shaped for the `[tile-shadow]` log line:
//
//    [tile-shadow] {"tile":"humidity","old":61,"new":58,"delta":-3,
//                   "oldSource":"open-meteo","newSource":"nws-nbm",…}
//
//  `old`/`new`/`delta` carry each tile's primary number in build 28 units;
//  `detail` carries the rest (trend, code, symbol, direction) as extra keys.
//  `delta` is new − old (nil when either side is missing). Not wired anywhere.
//

import Foundation

struct NWSTileParity: Equatable, Encodable, Sendable {
    /// Spec §1 flag key: humidity | pressure | temperature | sky | wind.
    let tile: String
    let old: Double?
    let new: Double?
    let delta: Double?
    let oldSource: String
    let newSource: String
    /// When the NWS value was observed (or the NBM hour it is valid for).
    let newObservedAt: Date?
    /// `observation` | `nbmGrid`.
    let newOrigin: String?
    let newStation: String?
    /// Secondary fields, all strings or numbers, e.g. pressure trend or sky code.
    let detail: [String: ParityScalar]

    enum CodingKeys: String, CodingKey {
        case tile, old, new, delta, oldSource, newSource, newObservedAt, newOrigin, newStation, detail
    }

    /// `old`, `new` and `delta` are always present, as explicit null when
    /// missing, so a shadow line always has the same shape.
    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(tile, forKey: .tile)
        try c.encode(old, forKey: .old)
        try c.encode(new, forKey: .new)
        try c.encode(delta, forKey: .delta)
        try c.encode(oldSource, forKey: .oldSource)
        try c.encode(newSource, forKey: .newSource)
        try c.encodeIfPresent(newObservedAt, forKey: .newObservedAt)
        try c.encodeIfPresent(newOrigin, forKey: .newOrigin)
        try c.encodeIfPresent(newStation, forKey: .newStation)
        try c.encode(detail, forKey: .detail)
    }

    /// A JSON scalar for `detail`.
    enum ParityScalar: Equatable, Encodable, Sendable {
        case number(Double)
        case string(String)
        case bool(Bool)
        case null

        func encode(to encoder: Encoder) throws {
            var c = encoder.singleValueContainer()
            switch self {
            case .number(let v): try c.encode(v)
            case .string(let v): try c.encode(v)
            case .bool(let v): try c.encode(v)
            case .null: try c.encodeNil()
            }
        }
    }
}

enum NWSWeatherParity {
    static let oldSource = "open-meteo"
    static let newSource = "nws-nbm"
    static let tiles = ["humidity", "pressure", "temperature", "sky", "wind"]

    /// One entry per tile, in `tiles` order.
    static func compare(old: WeatherReading, new: NWSWeatherReading?) -> [NWSTileParity] {
        typealias S = NWSTileParity.ParityScalar
        func num(_ v: Double?) -> S { v.map { .number(round2($0)) } ?? .null }
        func str(_ v: String?) -> S { v.map { .string($0) } ?? .null }
        func entry<T>(_ tile: String, _ o: Double?, _ n: NWSValue<T>?, _ nValue: Double?,
                      detail: [String: S] = [:]) -> NWSTileParity {
            NWSTileParity(tile: tile, old: o.map(round2), new: nValue.map(round2),
                          delta: delta(o, nValue), oldSource: oldSource, newSource: newSource,
                          newObservedAt: n?.observedAt, newOrigin: n?.origin.rawValue,
                          newStation: n?.stationId, detail: detail)
        }

        let humidity = entry("humidity", Double(old.humidity), new?.humidity,
                             new?.humidity.map { Double($0.value) })

        let pressure = entry("pressure", old.pressure, new?.pressure, new?.pressure?.value, detail: [
            "trendOld": .string(trendString(old.pressureTrend)),
            "trendNew": str(new?.pressureTrend.map(trendString)),
            "changeOld": num(old.pressureChange),
            "changeNew": num(new?.pressureChange),
            "trend3hOld": .string(trendString(old.displayPressureTrend)),
            "trend3hNew": str(new?.pressureTrend3h.map(trendString)),
            "pressureKindNew": str(new?.pressureKind?.rawValue),
        ])

        let temperature = entry("temperature", old.temperature, new?.temperature, new?.temperature?.value)

        let codeNew = new?.weatherCode?.value
        let sky = entry("sky", old.cloudCover, new?.cloudCover, new?.cloudCover?.value, detail: [
            "codeOld": .number(Double(old.weatherCode)),
            "codeNew": codeNew.map { .number(Double($0)) } ?? .null,
            "codeMatch": codeNew.map { .bool($0 == old.weatherCode) } ?? .null,
            "symbolOld": .string(old.conditionSymbol),
            "symbolNew": str(new?.conditionSymbol),
            "symbolMatch": new?.conditionSymbol.map { .bool($0 == old.conditionSymbol) } ?? .null,
            "codeObservedAtNew": str(new?.weatherCode.map { isoSeconds($0.observedAt) }),
        ])

        let dirNew = new?.windDirection?.value
        let wind = entry("wind", old.windSpeed, new?.windSpeed, new?.windSpeed?.value, detail: [
            "dirOld": .number(Double(old.windDirection)),
            "dirNew": dirNew.map { .number(Double($0)) } ?? .null,
            "dirDelta": dirNew.map { .number(Double(angleDelta(from: old.windDirection, to: $0))) } ?? .null,
        ])

        return [humidity, pressure, temperature, sky, wind]
    }

    /// new − old, rounded to 0.01. nil when either side is missing.
    static func delta(_ old: Double?, _ new: Double?) -> Double? {
        guard let old, let new else { return nil }
        return round2(new - old)
    }

    /// Signed shortest turn from `from` to `to`, in −179…180 degrees.
    static func angleDelta(from: Int, to: Int) -> Int {
        var d = (to - from) % 360
        if d > 180 { d -= 360 }
        if d <= -180 { d += 360 }
        return d
    }

    static func round2(_ v: Double) -> Double { (v * 100).rounded() / 100 }

    static func trendString(_ t: PressureTrend) -> String {
        switch t {
        case .rising: "rising"
        case .falling: "falling"
        case .steady: "steady"
        }
    }

    /// `[tile-shadow] {…}` with the spec §6 keys plus the caller's context
    /// (lakeId, latR, lonR — coordinates already rounded to 0.1°). Sorted keys,
    /// ISO 8601 seconds.
    static func logLine(_ p: NWSTileParity, lakeId: String?, latR: Double?, lonR: Double?) -> String {
        struct Line: Encodable {
            let parity: NWSTileParity
            let lakeId: String?
            let latR: Double?
            let lonR: Double?
            enum K: String, CodingKey { case lakeId, latR, lonR }
            func encode(to encoder: Encoder) throws {
                try parity.encode(to: encoder)
                var c = encoder.container(keyedBy: K.self)
                try c.encodeIfPresent(lakeId, forKey: .lakeId)
                try c.encodeIfPresent(latR, forKey: .latR)
                try c.encodeIfPresent(lonR, forKey: .lonR)
            }
        }
        let e = JSONEncoder()
        e.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        e.dateEncodingStrategy = .iso8601
        let body = (try? e.encode(Line(parity: p, lakeId: lakeId, latR: latR, lonR: lonR)))
            .flatMap { String(data: $0, encoding: .utf8) } ?? "{}"
        return "[tile-shadow] " + body
    }

    private static func isoSeconds(_ d: Date) -> String { NWSWeatherService.isoSeconds(d) }
}
