//
//  ConditionsRequestLog.swift
//  SectorEngine
//
//  The `[conditions-request]` line (spec §6, owner rule 5 "nothing removed while used"): one line per /conditions
//  request, cache hits included, so Ops can see which app builds still read which fields and tiles.
//
//    [conditions-request] {"app":"ios","appBuild":"28","cache":"hit","lakeId":"Guntersville|AL","latR":34.4,"lonR":-86.3,
//                          "ms":42,"tiles":{"humidity":{"blank":false,"flag":"off","status":"AVAILABLE"},…}}
//
//  Coordinates are rounded to 0.1 degree. No user ids, IPs or raw headers, ever. Cheap: built from the response already
//  in hand, no extra work on the request path.
//

import Foundation

/// The client app, from the User-Agent (or `X-Sector-Client`) header (spec §6, §8).
public struct ClientIdentity: Equatable, Sendable {
    /// ios | android | web | other
    public let app: String
    /// The build (iOS), versionCode (Android), version (web) or `unknown`; nil for `other`.
    public let appBuild: String?

    public init(app: String, appBuild: String?) {
        self.app = app
        self.appBuild = appBuild
    }

    /// | User-Agent                                     | app     | appBuild    |
    /// | `Sector/<build> CFNetwork/...`                 | ios     | build       |
    /// | `Sector-Android/<versionName> (<versionCode>)` | android | versionCode |
    /// | `okhttp/...`                                   | android | unknown     |
    /// | `Sector-Web/<v>`                               | web     | v           |
    /// | anything else                                  | other   | –           |
    /// A recognised User-Agent wins; otherwise `X-Sector-Client: <ios|android|web>/<version>` is used (browsers that
    /// cannot set the User-Agent send it).
    public static func parse(userAgent: String?, sectorClient: String? = nil) -> ClientIdentity {
        if let ua = userAgent?.trimmingCharacters(in: .whitespaces), !ua.isEmpty {
            if ua.hasPrefix("Sector/") {
                return ClientIdentity(app: "ios", appBuild: token(after: "Sector/", in: ua) ?? "unknown")
            }
            if ua.hasPrefix("Sector-Android/") {
                // versionCode is the parenthesised part; without it the build is unknown.
                var code: String? = nil
                if let open = ua.firstIndex(of: "("), let close = ua[open...].firstIndex(of: ")") {
                    code = sanitize(String(ua[ua.index(after: open)..<close]))
                }
                return ClientIdentity(app: "android", appBuild: code ?? "unknown")
            }
            if ua.lowercased().hasPrefix("okhttp/") {
                return ClientIdentity(app: "android", appBuild: "unknown")
            }
            if ua.hasPrefix("Sector-Web/") {
                return ClientIdentity(app: "web", appBuild: token(after: "Sector-Web/", in: ua) ?? "unknown")
            }
        }
        if let client = sectorClient?.trimmingCharacters(in: .whitespaces), let slash = client.firstIndex(of: "/") {
            let app = client[..<slash].lowercased()
            if ["ios", "android", "web"].contains(app) {
                return ClientIdentity(app: app, appBuild: sanitize(String(client[client.index(after: slash)...])) ?? "unknown")
            }
        }
        return ClientIdentity(app: "other", appBuild: nil)
    }

    /// The run of characters after `prefix` up to the first space.
    private static func token(after prefix: String, in s: String) -> String? {
        let rest = s.dropFirst(prefix.count)
        return sanitize(String(rest.prefix { $0 != " " }))
    }

    /// Keep only a short build-like token (letters, digits, `.`, `-`, `_`), at most 32 characters; nil when empty.
    static func sanitize(_ s: String) -> String? {
        let allowed = Set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_")
        let kept = String(s.trimmingCharacters(in: .whitespaces).filter { allowed.contains($0) }.prefix(32))
        return kept.isEmpty ? nil : kept
    }
}

public enum ConditionsRequestLog {

    /// hit = served from the response cache; miss = this request computed (or waited on) a render.
    public enum CacheOutcome: String, Sendable { case hit, miss }

    struct TileLine: Encodable, Equatable {
        let flag: String
        let status: String
        let blank: Bool
    }

    struct Line: Encodable {
        let app: String
        let appBuild: String?
        var batch: Int? = nil
        let cache: String?
        let ms: Int
        let lakeId: String?
        let latR: Double?
        let lonR: Double?
        let tiles: [String: TileLine]?
    }

    /// Round to 0.1 degree (spec §6).
    public static func round1(_ v: Double) -> Double { (v * 10).rounded() / 10 + 0 }   // + 0 turns -0 into 0

    /// The full `[conditions-request]` line. `response` nil (no live data, a 503) logs no lake and no tiles.
    public static func line(client: ClientIdentity, cache: CacheOutcome, ms: Int, lat: Double, lon: Double,
                            response: ConditionsResponse?) -> String {
        let tiles = (response?.tileSources ?? [:]).mapValues {
            TileLine(flag: $0.flag, status: $0.status, blank: $0.status == TileStatus.unknown.rawValue)
        }
        let l = Line(app: client.app, appBuild: client.appBuild, cache: cache.rawValue, ms: max(0, ms),
                     lakeId: response?.resolvedLake?.id, latR: round1(lat), lonR: round1(lon), tiles: tiles)
        return "[conditions-request] " + json(l)
    }

    /// `POST /conditions/batch` (the My Lakes rings): one line per batch request, `batch` = number of points scored.
    /// It carries no coordinates (many points, and the slim scores have no tiles) and no cache field (the batch path
    /// reads the snapshot cache, not the /conditions response cache).
    public static func batchLine(client: ClientIdentity, points: Int, ms: Int) -> String {
        let l = Line(app: client.app, appBuild: client.appBuild, batch: points, cache: nil, ms: max(0, ms),
                     lakeId: nil, latR: nil, lonR: nil, tiles: nil)
        return "[conditions-request] " + json(l)
    }

    /// Compact, key-sorted JSON for a log line.
    static func json<T: Encodable>(_ value: T) -> String {
        let enc = JSONEncoder()
        enc.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        enc.dateEncodingStrategy = .iso8601
        return (try? enc.encode(value)).flatMap { String(data: $0, encoding: .utf8) } ?? "{}"
    }
}
