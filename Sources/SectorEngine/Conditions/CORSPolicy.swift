//
//  CORSPolicy.swift
//  SectorEngine
//
//  Browser access for the website (Sector_Ops #53 spec, "Web CORS"): `GET /conditions` and `GET /health` only, from an
//  allow-list of the Web project's own origins. Never `*`, never credentials. A request without an `Origin` header (the
//  apps) gets no CORS header at all, so its response is byte-for-byte what it was.
//
//  Origins (Web repo Sector-Web: firebase.json hosting targets prod `sector-9393c` and dev `sector-9393c-dev`, and the
//  custom domain sectorbowfishing.com):
//    https://sectorbowfishing.com, https://www.sectorbowfishing.com,
//    https://sector-9393c.web.app, https://sector-9393c.firebaseapp.com,
//    https://sector-9393c-dev.web.app, https://sector-9393c-dev.firebaseapp.com
//  plus http://localhost:3000 only when SECTOR_CORS_DEV=1.
//

import Foundation

public struct CORSPolicy: Equatable, Sendable {

    public static let productionOrigins: [String] = [
        "https://sectorbowfishing.com",
        "https://www.sectorbowfishing.com",
        "https://sector-9393c.web.app",
        "https://sector-9393c.firebaseapp.com",
        "https://sector-9393c-dev.web.app",
        "https://sector-9393c-dev.firebaseapp.com",
    ]
    public static let devOrigin = "http://localhost:3000"

    /// The paths that answer cross-origin requests.
    public static let paths: Set<String> = ["/conditions", "/health"]
    public static let allowMethods = "GET"
    public static let allowHeaders = "X-Sector-Client, Accept"
    public static let maxAgeSeconds = 600

    public let allowedOrigins: Set<String>

    public init(allowedOrigins: Set<String>) { self.allowedOrigins = allowedOrigins }

    public static func fromEnvironment(_ env: [String: String] = ProcessInfo.processInfo.environment) -> CORSPolicy {
        var origins = Set(productionOrigins)
        if env["SECTOR_CORS_DEV"] == "1" { origins.insert(devOrigin) }
        return CORSPolicy(allowedOrigins: origins)
    }

    /// The `Access-Control-Allow-Origin` value: the request's origin echoed back when it is on the list (exact match,
    /// case-sensitive scheme and host as browsers send them), else nil.
    public func allowedOrigin(_ origin: String?) -> String? {
        guard let origin, allowedOrigins.contains(origin) else { return nil }
        return origin
    }

    /// Headers to add to a GET response. Empty when the request has no `Origin` (unchanged response). With an `Origin`
    /// it always carries `Vary: Origin`, and `Access-Control-Allow-Origin` only for an allowed origin.
    public func responseHeaders(origin: String?) -> [(name: String, value: String)] {
        guard origin != nil else { return [] }
        var out: [(name: String, value: String)] = [("Vary", "Origin")]
        if let allowed = allowedOrigin(origin) { out.append(("Access-Control-Allow-Origin", allowed)) }
        return out
    }

    /// The preflight answer: nil when the request has no `Origin` (not a preflight; the route stays 404 as before),
    /// else 204 with `Vary: Origin`, plus the allow headers only for an allowed origin.
    public func preflightHeaders(origin: String?) -> [(name: String, value: String)]? {
        guard origin != nil else { return nil }
        var out = responseHeaders(origin: origin)
        if allowedOrigin(origin) != nil {
            out.append(("Access-Control-Allow-Methods", Self.allowMethods))
            out.append(("Access-Control-Allow-Headers", Self.allowHeaders))
            out.append(("Access-Control-Max-Age", String(Self.maxAgeSeconds)))
        }
        return out
    }
}
