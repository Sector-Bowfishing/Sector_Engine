//
//  HTTP.swift
//  SectorEngine
//
//  The one outbound HTTP client for every engine fetch: AsyncHTTPClient on
//  SwiftNIO. Replaced Foundation's URLSession (Net.swift) on 2026-09-14.
//
//  Why not URLSession: on Linux, swift-corelibs-foundation runs every task of a
//  session through one internal work queue on top of libcurl, and it ignores
//  cancellation for a connection stuck mid-handshake. With two or more
//  /conditions renders on one Cloud Run instance that tied up Swift's
//  cooperative thread pool — withDeadline's timers couldn't fire, every request
//  rode to the 60s limit, and the instance froze (even /health) until it was
//  replaced. The engine had to run at concurrency=1 to stay up.
//
//  AsyncHTTPClient does its I/O on NIO event loops, never parks a cooperative
//  thread while waiting on the network, enforces its own deadline, and cancels
//  the underlying request when the awaiting task is cancelled — so a fetch that
//  withDeadline gives up on is actually torn down instead of lingering.
//
//  Behaviour is kept at parity with the old session:
//   - 8s wall-clock cap per fetch (the old timeoutIntervalForResource), just
//     under the smallest withDeadline budget (9s). Longer per-call timeouts were
//     never in effect and are clamped.
//   - Redirects followed (max 5).
//   - gzip/deflate advertised and decoded — libcurl did both implicitly.
//   - A self-identifying User-Agent on every request — libcurl sent one
//     implicitly, and NWS returns 403 without it. Call sites can override any
//     header (energy.gov and apcshorelines need a browser-style UA).
//

import Foundation
import AsyncHTTPClient
import NIOCore
import NIOHTTP1

/// A completed response: HTTP status + the whole body.
package struct HTTPResult: Sendable {
    let status: Int
    package let body: Data
    package var isSuccess: Bool { (200..<300).contains(status) }
}

package enum HTTP {
    /// Upper bound on one fetch, request start to last body byte.
    static let maxTimeout: TimeInterval = 8

    /// Largest body buffered. Far above any real payload (the NOAA tide-station
    /// list is ~1–2 MB); a runaway response fails that fetch, not the process.
    static let maxBodyBytes = 32 * 1024 * 1024

    static let defaultUserAgent = "Sector/1.0 (io.sector.co)"

    /// Process-lifetime client on NIO's shared event loop group. Never shut
    /// down — it lives exactly as long as the server process.
    package static let client: HTTPClient = {
        var config = HTTPClient.Configuration()
        config.timeout = HTTPClient.Configuration.Timeout(connect: .seconds(5), read: .seconds(8))
        config.redirectConfiguration = .follow(max: 5, allowCycles: false)
        config.decompression = .enabled(limit: .size(64 * 1024 * 1024))
        // Several renders at once each race two Open-Meteo hosts; don't make
        // them queue behind the default soft limit of 8 connections per host.
        config.connectionPool = HTTPClient.Configuration.ConnectionPool(
            idleTimeout: .seconds(60), concurrentHTTP1ConnectionsPerHostSoftLimit: 16)
        return HTTPClient(eventLoopGroupProvider: .singleton, configuration: config)
    }()

    /// GET `url`. Throws on transport failure, timeout, cancellation, or an
    /// oversized body. Any HTTP status is returned — callers check `isSuccess`.
    package static func get(_ url: URL,
                    headers: [String: String] = [:],
                    timeout: TimeInterval = maxTimeout) async throws -> HTTPResult {
        var request = HTTPClientRequest(url: url.absoluteString)
        request.method = .GET
        request.headers.add(name: "User-Agent", value: defaultUserAgent)
        request.headers.add(name: "Accept-Encoding", value: "gzip, deflate")
        for (name, value) in headers {
            request.headers.replaceOrAdd(name: name, value: value)
        }

        let ms = Int64(min(timeout, maxTimeout) * 1000)
        let started = Date()
        do {
            let response = try await client.execute(request, timeout: .milliseconds(ms))
            let buffer = try await response.body.collect(upTo: maxBodyBytes)
            let result = HTTPResult(status: Int(response.status.code), body: Data(buffer.readableBytesView))
            print(logLine(url: url, outcome: String(result.status), bytes: result.body.count, started: started))
            return result
        } catch {
            print(logLine(url: url, outcome: errorLabel(error), bytes: 0, started: started))
            throw error
        }
    }

    // MARK: Upstream call log (Sector_Ops #51 F1)

    /// One line per upstream call: start time, host, path, status (or why it
    /// failed), body bytes and wall time. Plain stdout, like the `[engine]`
    /// deadline lines, so Cloud Logging picks it up with no extra client.
    ///
    /// Never the query string: some upstreams carry a key there (Firebase
    /// Remote Config `?key=`), and USGS bounding boxes would make every line
    /// unique. Keys sent as headers (`X-Api-Key`) are never touched. The path
    /// is capped so a long one can't bloat the log.
    static func logLine(url: URL, outcome: String, bytes: Int, started: Date,
                        now: Date = Date()) -> String {
        let host = url.host ?? "?"
        var path = url.path.isEmpty ? "/" : url.path
        if path.count > maxLoggedPath { path = String(path.prefix(maxLoggedPath)) + "…" }
        let ms = Int((now.timeIntervalSince(started) * 1000).rounded())
        return "[http] at=\(isoMillis(started)) host=\(host) path=\(path) status=\(outcome) bytes=\(bytes) ms=\(ms)"
    }

    static let maxLoggedPath = 80

    /// A short, stable label for a failed call: a timeout, a cancellation (a
    /// `withDeadline` budget ran out and tore the request down), or the error's
    /// type. Never the error's text, which can echo the URL with its query.
    static func errorLabel(_ error: Error) -> String {
        if error is CancellationError { return "CANCELLED" }
        if let e = error as? HTTPClientError {
            switch e {
            case .deadlineExceeded: return "TIMEOUT"
            case .readTimeout: return "READ_TIMEOUT"
            case .connectTimeout: return "CONNECT_TIMEOUT"
            case .cancelled: return "CANCELLED"
            case .remoteConnectionClosed: return "CONNECTION_CLOSED"
            default: return "HTTP_CLIENT_ERROR"
            }
        }
        return "ERR_" + String(describing: type(of: error))
    }

    /// One formatter for the process (creating one per call opens an ICU formatter on Linux). ISO8601DateFormatter
    /// is thread-safe for formatting.
    private static let isoFormatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    private static func isoMillis(_ d: Date) -> String { isoFormatter.string(from: d) }
}
