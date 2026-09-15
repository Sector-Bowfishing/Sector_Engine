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
//   - 8s wall-clock budget per fetch by default (the old
//     timeoutIntervalForResource), just under the smallest withDeadline budget
//     (9s). It covers the WHOLE response — headers AND body — so an upstream
//     that answers promptly and then trickles its body can't hold a fetch
//     open. Cached, once-a-day catalog downloads may pass a longer budget.
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
struct HTTPResult: Sendable {
    let status: Int
    let body: Data
    /// The server's Retry-After, in seconds, when it sent one (429 / 503).
    var retryAfterSeconds: Double? = nil
    var isSuccess: Bool { (200..<300).contains(status) }
}

/// Thrown when a response doesn't finish (headers + body) inside its budget.
struct HTTPDeadlineExceeded: Error {}

enum HTTP {
    /// Default budget for one fetch, request start to last body byte.
    static let defaultTimeout: TimeInterval = 8

    /// Largest body buffered. Far above any real payload (the NOAA tide-station
    /// list is ~1–2 MB); a runaway response fails that fetch, not the process.
    static let maxBodyBytes = 32 * 1024 * 1024

    static let defaultUserAgent = "Sector/1.0 (io.sector.co)"

    /// Process-lifetime client on NIO's shared event loop group. Never shut
    /// down — it lives exactly as long as the server process.
    static let client: HTTPClient = {
        var config = HTTPClient.Configuration()
        // No client-wide READ timeout. AHC starts that idle timer when the request
        // is sent, so a fixed 8s value silently capped every longer per-call budget
        // (USGS 11s, CWMS catalogs 25s): a server that took 9s to send its headers
        // failed at 8s whatever `timeout:` was passed. Each call's whole-response
        // deadline (below) is what bounds a fetch. Connect stays 5s — AHC also uses
        // it as the wait for a pooled connection, which the per-host limiters keep
        // short.
        config.timeout = HTTPClient.Configuration.Timeout(connect: .seconds(5), read: nil)
        config.redirectConfiguration = .follow(max: 5, allowCycles: false)
        config.decompression = .enabled(limit: .size(64 * 1024 * 1024))
        // Several renders run at once on one instance, each fanning out to the
        // same few hosts (Open-Meteo, USGS, CWMS). With a small pool, fetches
        // queued for a connection and failed at the 5s connect timeout, turning
        // healthy factors dormant. HTTP/2 hosts multiplex regardless.
        config.connectionPool = HTTPClient.Configuration.ConnectionPool(
            idleTimeout: .seconds(60), concurrentHTTP1ConnectionsPerHostSoftLimit: 64)
        return HTTPClient(eventLoopGroupProvider: .singleton, configuration: config)
    }()

    /// GET `url`. Throws on transport failure, a blown budget, cancellation, or
    /// an oversized body. Any HTTP status is returned — callers check `isSuccess`.
    static func get(_ url: URL,
                    headers: [String: String] = [:],
                    timeout: TimeInterval = defaultTimeout) async throws -> HTTPResult {
        var request = HTTPClientRequest(url: url.absoluteString)
        request.method = .GET
        request.headers.add(name: "User-Agent", value: defaultUserAgent)
        request.headers.add(name: "Accept-Encoding", value: "gzip, deflate")
        for (name, value) in headers {
            request.headers.replaceOrAdd(name: name, value: value)
        }

        let prepared = request   // immutable copy for the concurrent child task
        let budget = TimeAmount.milliseconds(Int64(max(timeout, 0.1) * 1000))
        let deadline = NIODeadline.now() + budget
        let started = Date()

        do {
            // `execute`'s deadline only covers the response head. Race the body
            // against the same deadline; whichever loses is cancelled, and
            // cancelling the body stream tears the request down.
            let result = try await withThrowingTaskGroup(of: HTTPResult.self) { group in
                group.addTask {
                    let response = try await client.execute(prepared, deadline: deadline)
                    let buffer = try await response.body.collect(upTo: maxBodyBytes)
                    return HTTPResult(status: Int(response.status.code), body: Data(buffer.readableBytesView),
                                      retryAfterSeconds: response.headers.first(name: "Retry-After").flatMap(Double.init))
                }
                group.addTask {
                    try await Task.sleep(nanoseconds: UInt64(budget.nanoseconds))
                    throw HTTPDeadlineExceeded()
                }
                defer { group.cancelAll() }
                guard let first = try await group.next() else { throw HTTPDeadlineExceeded() }
                return first
            }
            // Statuses that mean the upstream is refusing or failing us. Plain 4xx
            // stay quiet: USGS answers "no gages in this box" with a 404, and that's
            // an everyday, correct answer.
            if result.status >= 500 || result.status == 429 || result.status == 403 {
                Log.warning("upstream error status",
                            ["host": .string(url.host ?? "?"), "status": .int(result.status),
                             "ms": .int(Int(Date().timeIntervalSince(started) * 1000))])
            }
            return result
        } catch {
            // A fetch the engine deliberately abandoned (withDeadline, a won hedge)
            // is cancelled on purpose — not an upstream problem.
            if !Task.isCancelled, !(error is CancellationError) {
                Log.warning("upstream request failed",
                            ["host": .string(url.host ?? "?"),
                             "error": .string(error is HTTPDeadlineExceeded ? "deadline" : String(describing: error)),
                             "ms": .int(Int(Date().timeIntervalSince(started) * 1000))])
            }
            throw error
        }
    }
}
