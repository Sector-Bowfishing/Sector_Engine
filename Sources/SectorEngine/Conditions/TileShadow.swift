//
//  TileShadow.swift
//  SectorEngine
//
//  The generic shadow/serve step every consolidation PR plugs a new tile source into (spec §0 rules 2-3, §1 modes):
//
//      let r = await TileShadow.resolve(tile: .humidity, mode: flags.mode(for: .humidity, lakeId: lakeId),
//                                       old: oldValue, oldEntry: legacyEntry, context: ctx,
//                                       new: { await NbmHumidity.fetch(...) },       // -> TileNewValue<Int>
//                                       compare: TileComparison.numeric)
//      // serve r.value, put r.entry into tileSources["humidity"]
//
//  - off:    the new provider is not called. Old is served.
//  - shadow: old is served at once; the new provider runs DETACHED (the response never waits for it), bounded to
//            `TileShadowRunner.maxConcurrent` at a time (the excess is dropped and counted), and one `[tile-shadow]`
//            line logs the difference when it finishes.
//  - serve:  if the tile's breaker allows, the new provider is called with a `newPathDeadlineSeconds` (3 s) deadline;
//            new is served when it is AVAILABLE with a value, otherwise old (status FALLBACK). A timeout counts as a
//            failed/blank sample. Both outcomes feed the breaker.
//  A tile with no new source yet (`new: nil`) always serves old and reports today's path.
//
//  Frozen fields are never overwritten: the caller decides what `T` is, and must put a served new value only into an
//  additive field or a non-frozen field whose units match (spec §1).
//

import Foundation

/// One `tileSources` entry (spec §4). Every optional is omitted from the JSON when nil.
public struct TileSourceDTO: Codable, Equatable, Sendable {
    public var flag: String           // off | shadow | serve
    public var path: String           // engine | brain | app
    public var source: String         // e.g. open-meteo, usgs-nearest-gauge, nws-nbm, lake-brain, moon-v1
    public var status: String         // AVAILABLE | ESTIMATE | FALLBACK | UNKNOWN
    public var observedAt: Date?      // the data's own observation time; never a run or fetch time
    public var freshUntil: Date?
    public var runner: String?        // pulse | cloud | engine
    public var publishId: String?

    public init(flag: String, path: String, source: String, status: String, observedAt: Date? = nil,
                freshUntil: Date? = nil, runner: String? = nil, publishId: String? = nil) {
        self.flag = flag; self.path = path; self.source = source; self.status = status
        self.observedAt = observedAt; self.freshUntil = freshUntil; self.runner = runner; self.publishId = publishId
    }
}

/// `tileSources` vocabulary (spec §4).
public enum TileStatus: String, Codable, Sendable {
    case available = "AVAILABLE"
    case estimate = "ESTIMATE"
    case fallback = "FALLBACK"
    case unknown = "UNKNOWN"
}

public enum TilePath: String, Codable, Sendable { case engine, brain, app }

/// What a new-path provider returns.
public struct TileNewValue<T> {
    public var value: T?
    public var status: TileStatus
    public var path: TilePath
    public var source: String
    public var observedAt: Date?
    public var freshUntil: Date?
    public var runner: String?
    public var publishId: String?

    public init(value: T?, status: TileStatus, path: TilePath, source: String, observedAt: Date? = nil,
                freshUntil: Date? = nil, runner: String? = nil, publishId: String? = nil) {
        self.value = value; self.status = status; self.path = path; self.source = source
        self.observedAt = observedAt; self.freshUntil = freshUntil; self.runner = runner; self.publishId = publishId
    }

    /// Usable for serving: AVAILABLE with a value. (ESTIMATE, FALLBACK and UNKNOWN are not served over old.)
    public var isServable: Bool { status == .available && value != nil }

    func entry(flag: TileMode) -> TileSourceDTO {
        TileSourceDTO(flag: flag.rawValue, path: path.rawValue, source: source, status: status.rawValue,
                      observedAt: observedAt, freshUntil: freshUntil, runner: runner, publishId: publishId)
    }
}

/// A JSON scalar for the `[tile-shadow]` line.
public enum TileLogValue: Encodable, Equatable, Sendable {
    case number(Double)
    case string(String)
    case bool(Bool)
    case null

    public func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .number(let d): if d.isFinite { try c.encode(d) } else { try c.encodeNil() }
        case .string(let s): try c.encode(s)
        case .bool(let b): try c.encode(b)
        case .null: try c.encodeNil()
        }
    }
}

/// The comparator's answer: what to log as old/new and the signed difference when numeric.
public struct TileComparison: Equatable, Sendable {
    public var old: TileLogValue
    public var new: TileLogValue
    public var delta: Double?

    public init(old: TileLogValue, new: TileLogValue, delta: Double? = nil) {
        self.old = old; self.new = new; self.delta = delta
    }

    /// For numeric tiles: logs both values and `new − old`, rounded to 0.01.
    public static func numeric<T: BinaryFloatingPoint>(_ old: T?, _ new: T?) -> TileComparison {
        let o = old.map { Double($0) }, n = new.map { Double($0) }
        let delta = (o != nil && n != nil) ? ((n! - o!) * 100).rounded() / 100 : nil
        return TileComparison(old: o.map(TileLogValue.number) ?? .null, new: n.map(TileLogValue.number) ?? .null, delta: delta)
    }

    public static func numeric<T: BinaryInteger>(_ old: T?, _ new: T?) -> TileComparison {
        numeric(old.map { Double($0) }, new.map { Double($0) })
    }
}

/// Request facts every tile line carries. Coordinates are already rounded to 0.1 degree; no user ids, ever.
public struct TileRequestContext: Equatable, Sendable {
    public let lakeId: String?
    public let latR: Double
    public let lonR: Double

    public init(lakeId: String?, lat: Double, lon: Double) {
        self.lakeId = lakeId
        self.latR = ConditionsRequestLog.round1(lat)
        self.lonR = ConditionsRequestLog.round1(lon)
    }
}

/// The step's answer: the value to serve and its `tileSources` entry.
extension TileNewValue: Sendable where T: Sendable {}

public struct TileServeResult<T> {
    public let value: T?
    public let entry: TileSourceDTO
    /// true only when the new path's value is the one served.
    public let servedNew: Bool
}

public enum TileShadow {

    /// The deadline on every new-path call (serve and shadow). A provider that misses it counts as failed/blank.
    public static let newPathDeadlineSeconds: Double = 3

    /// Apply the tile's flag mode and breaker. See the file header.
    /// - Parameters:
    ///   - old: today's value (nil = blank).
    ///   - oldEntry: today's `tileSources` entry (its `flag` is overwritten with `mode`).
    ///   - oldLatency: how long today's value took, when known; the breaker compares the new path's p95 against it
    ///     (unknown counts as 0 s, the strictest comparison).
    ///   - new: the new-path provider, or nil when the tile has no new source yet.
    ///   - compare: builds the `[tile-shadow]` old/new/delta.
    ///   - shadowRunner: bounds the detached shadow computations.
    public static func resolve<T: Sendable>(
        tile: TileKey,
        mode: TileMode,
        old: T?,
        oldEntry: TileSourceDTO,
        oldLatency: TimeInterval? = nil,
        context: TileRequestContext,
        new: (@Sendable () async -> TileNewValue<T>)?,
        compare: @escaping @Sendable (T?, T?) -> TileComparison,
        breaker: TileBreakerRegistry = .shared,
        shadowRunner: TileShadowRunner = .shared,
        log: @escaping @Sendable (String) -> Void = { print($0) }
    ) async -> TileServeResult<T> {
        var oldOut = oldEntry
        oldOut.flag = mode.rawValue

        switch mode {
        case .off:
            return TileServeResult(value: old, entry: oldOut, servedNew: false)

        case .shadow:
            guard let new else { return TileServeResult(value: old, entry: oldOut, servedNew: false) }
            let oldSource = oldEntry.source
            await shadowRunner.launch {
                let n = await withDeadline(newPathDeadlineSeconds, "tile-shadow-\(tile.rawValue)") { await new() }
                log(shadowLine(tile: tile, comparison: compare(old, n?.value), oldSource: oldSource,
                               newSource: n?.source ?? "timeout", context: context))
            }
            return TileServeResult(value: old, entry: oldOut, servedNew: false)

        case .serve:
            // Serve was on but old is served: FALLBACK (UNKNOWN when old is blank too).
            var fallback = oldOut
            fallback.status = old == nil ? TileStatus.unknown.rawValue : TileStatus.fallback.rawValue
            guard let new, await breaker.shouldTryNew(tile) else {
                return TileServeResult(value: old, entry: fallback, servedNew: false)
            }
            let started = DispatchTime.now().uptimeNanoseconds
            let n = await withDeadline(newPathDeadlineSeconds, "tile-serve-\(tile.rawValue)") { await new() }
            let latency = Double(DispatchTime.now().uptimeNanoseconds - started) / 1e9
            await breaker.record(tile, path: .old, ok: old != nil, latency: oldLatency ?? 0)
            await breaker.record(tile, path: .new, ok: n?.isServable ?? false, latency: latency)
            guard let n, n.isServable else { return TileServeResult(value: old, entry: fallback, servedNew: false) }
            return TileServeResult(value: n.value, entry: n.entry(flag: .serve), servedNew: true)
        }
    }

    /// `[tile-shadow] {"tile":…,"old":…,"new":…,"delta":…,"oldSource":…,"newSource":…,"lakeId":…,"latR":…,"lonR":…}`
    public static func shadowLine(tile: TileKey, comparison: TileComparison, oldSource: String, newSource: String,
                                  context: TileRequestContext) -> String {
        struct Line: Encodable {
            let tile: String; let old: TileLogValue; let new: TileLogValue; let delta: Double?
            let oldSource: String; let newSource: String
            let lakeId: String?; let latR: Double; let lonR: Double
        }
        let line = Line(tile: tile.rawValue, old: comparison.old, new: comparison.new, delta: comparison.delta,
                        oldSource: oldSource, newSource: newSource,
                        lakeId: context.lakeId, latR: context.latR, lonR: context.lonR)
        return "[tile-shadow] " + ConditionsRequestLog.json(line)
    }
}

/// Runs shadow computations detached from the request, at most `maxConcurrent` at a time. A launch beyond that is
/// dropped (never queued) and counted, so a slow new source can neither delay a response nor pile up work.
public actor TileShadowRunner {
    public static let defaultMaxConcurrent = 8
    public static let shared = TileShadowRunner()

    public let maxConcurrent: Int
    public private(set) var running = 0
    /// Shadow computations dropped because `maxConcurrent` were already running.
    public private(set) var dropped = 0
    private var idleWaiters: [CheckedContinuation<Void, Never>] = []

    public init(maxConcurrent: Int = defaultMaxConcurrent) { self.maxConcurrent = maxConcurrent }

    /// Start `work` detached, or drop it when the runner is full. Returns whether it started; never waits for `work`.
    @discardableResult
    public func launch(_ work: @escaping @Sendable () async -> Void) -> Bool {
        guard running < maxConcurrent else {
            dropped += 1
            return false
        }
        running += 1
        Task.detached { [self] in
            await work()
            await self.finished()
        }
        return true
    }

    private func finished() {
        running -= 1
        if running == 0 {
            let waiters = idleWaiters
            idleWaiters = []
            for w in waiters { w.resume() }
        }
    }

    /// Wait until no shadow computation is running (tests and shutdown).
    public func waitUntilIdle() async {
        guard running > 0 else { return }
        await withCheckedContinuation { idleWaiters.append($0) }
    }
}
