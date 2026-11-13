//
//  TileFlags.swift
//  SectorEngine
//
//  Conditions consolidation (Sector_Ops #53, docs/architecture/conditions/CONDITIONS_CONSOLIDATION_SPEC_V1.md §1-§2):
//  one flag per customer tile, each `off` | `shadow` | `serve`.
//
//  Source of truth: the Firebase Remote Config parameter `conditions_tiles_v1` (a JSON string), read through the same
//  REST + metadata-token path as `conditions_config` (RemoteConfigREST), cached for 10 minutes with last-good fallback.
//  The env `SECTOR_CONDITIONS_TILES_V1` (same JSON) wins over Remote Config; it is for local runs and tests only.
//
//  Fail-safe: a missing, unreadable or invalid document, an unknown tile key, or an unknown mode all mean `off`.
//  Every tile is `off` unless the owner turns it on.
//

import Foundation

/// The ten flag keys of spec §1. Raw values are binding (Remote Config, logs, `tileSources`).
public enum TileKey: String, CaseIterable, Codable, Sendable {
    case humidity, pressure, temperature, sky, wind, windOutlookModel, waterLevel, clarity, waterTemp, generation
}

/// A tile's flag mode (spec §1).
public enum TileMode: String, Codable, Sendable {
    /// The new path is not computed.
    case off
    /// Compute both, serve old, log the difference.
    case shadow
    /// Serve new when it is AVAILABLE and the breaker is closed, otherwise old.
    case serve
}

/// The parsed `conditions_tiles_v1` document.
public struct TileFlags: Equatable, Sendable {

    public struct Tile: Equatable, Sendable {
        public let mode: TileMode
        /// When set, `shadow`/`serve` apply only to these lake ids ("Name|ST"); every other lake is `off`.
        public let lakes: Set<String>?

        public init(mode: TileMode, lakes: Set<String>? = nil) {
            self.mode = mode
            self.lakes = lakes
        }
    }

    public let version: Int?
    public let tiles: [TileKey: Tile]

    public init(version: Int? = 1, tiles: [TileKey: Tile] = [:]) {
        self.version = version
        self.tiles = tiles
    }

    /// Every tile `off`: the default and the answer to anything unreadable.
    public static let allOff = TileFlags(version: nil, tiles: [:])

    /// The effective mode of `tile` for a request about `lakeId`. A tile with a `lakes` list is `off` for any other lake,
    /// and for a request that resolved to no lake.
    public func mode(for tile: TileKey, lakeId: String?) -> TileMode {
        guard let t = tiles[tile] else { return .off }
        if t.mode == .off { return .off }
        if let lakes = t.lakes {
            guard let lakeId, lakes.contains(lakeId) else { return .off }
        }
        return t.mode
    }

    /// Parse a `conditions_tiles_v1` JSON string. nil, empty or invalid JSON → `allOff`. Unknown tile keys are ignored;
    /// an unknown or missing mode, or a malformed tile entry, is `off`. A `lakes` value that is not a list of strings
    /// makes that tile `off` (never wider than the owner wrote).
    public static func parse(_ json: String?) -> TileFlags {
        guard let json, let data = json.data(using: .utf8) else { return .allOff }
        return parse(data: data)
    }

    public static func parse(data: Data) -> TileFlags {
        guard let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let rawTiles = root["tiles"] as? [String: Any] else { return .allOff }
        let version = (root["version"] as? NSNumber)?.intValue
        var tiles: [TileKey: Tile] = [:]
        for (key, value) in rawTiles {
            guard let tile = TileKey(rawValue: key),
                  let entry = value as? [String: Any],
                  let modeText = entry["mode"] as? String,
                  let mode = TileMode(rawValue: modeText) else { continue }
            var lakes: Set<String>? = nil
            if let rawLakes = entry["lakes"] {
                guard let list = rawLakes as? [String] else { continue }   // malformed restriction → off
                lakes = Set(list)
            }
            tiles[tile] = Tile(mode: mode, lakes: lakes)
        }
        return TileFlags(version: version, tiles: tiles)
    }

    /// The env override name (spec §2). Production never sets it.
    public static let envKey = "SECTOR_CONDITIONS_TILES_V1"
    /// The Remote Config parameter name (spec §2).
    public static let remoteConfigParameter = "conditions_tiles_v1"
}

/// Serves the current `TileFlags`: env override first, else Remote Config with a 10-minute TTL and last-good fallback.
/// Mirrors `RemoteConfigStore.current()`: within the TTL it answers from cache; when stale with a prior value it answers
/// at once and refreshes in the background; the first read of the process waits for the fetch, capped at 3 s, then
/// falls back to `allOff`. Never throws, never blocks a request on Firebase for long.
public actor TileFlagsStore {
    public static let shared = TileFlagsStore()

    private let envOverride: String?
    private let fetch: @Sendable () async -> RemoteConfigParameter
    private let now: @Sendable () -> Date
    private let ttl: TimeInterval = 10 * 60

    private var cached: TileFlags = .allOff
    private var fetchedAt: Date?
    private var inFlight: Task<TileFlags, Never>?

    /// - Parameters:
    ///   - environment: the process environment (read for `SECTOR_CONDITIONS_TILES_V1`).
    ///   - fetch: reads the `conditions_tiles_v1` parameter. Defaults to the Remote Config REST path; tests inject their
    ///     own so nothing touches the network.
    ///   - now: the clock (tests inject one).
    public init(environment: [String: String] = ProcessInfo.processInfo.environment,
                fetch: (@Sendable () async -> RemoteConfigParameter)? = nil,
                now: @escaping @Sendable () -> Date = { Date() }) {
        self.envOverride = environment[TileFlags.envKey]
        self.fetch = fetch ?? { await RemoteConfigREST.parameter(TileFlags.remoteConfigParameter) }
        self.now = now
    }

    public func current() async -> TileFlags {
        if let envOverride { return TileFlags.parse(envOverride) }
        if let at = fetchedAt, now().timeIntervalSince(at) < ttl { return cached }

        let task = inFlight ?? {
            let t = Task { await refresh() }
            inFlight = t
            return t
        }()
        if fetchedAt != nil { return cached }

        let fetched = await withDeadline(3, "tileFlags", slowThreshold: 2) { () -> TileFlags? in await task.value }
        return fetched ?? cached
    }

    private func refresh() async -> TileFlags {
        defer { fetchedAt = now(); inFlight = nil }
        switch await fetch() {
        case .value(let raw): cached = TileFlags.parse(raw)   // invalid JSON parses to allOff
        case .absent: cached = .allOff                          // the template has no such parameter: every tile off
        case .unreadable: break                                 // no token, HTTP error, bad template: keep the last good flags
        }
        return cached
    }
}
