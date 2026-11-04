//
//  LakeLevelFeedsCWMS.swift
//  Sector — bounded, classified retries for USACE CWMS Data API requests made by the Lake Brain
//
//  Why (2026-10-20 investigation): the daily 12:00Z Lake Brain run lost the Hartwell CWMS pool series on 4 of 6 mornings
//  (Oct 14, 15, 16, 19; `sourceError:cwms:SAS:Hartwell.Elev-Pool…` in the prediction ledger), fell back to USGS 02187010 and
//  reported WARNING. The same request takes ~0.47 s off-peak. Before this file every CWMS request was ONE attempt through the
//  engine-wide `HTTP.get` (8 s cap, tuned for the /conditions render path), and every failure collapsed into "unreachable".
//
//  What this changes (CWMS only; TVA / USGS / TWDB / fleet clients untouched):
//   • transient failures (timeout, connection error, HTTP 408 / 429 / 500 / 502 / 503 / 504) are retried, at most
//     `maxAttempts` (3) per request, with exponential backoff and jitter (2 s, then 4 s, each × 0.5–1.0) and `Retry-After`
//     honoured up to 30 s. A `Retry-After` beyond the cap is not waited for and is not hammered: the request gives up.
//   • permanent failures (any other HTTP status, e.g. 400 / 404) are NOT retried.
//   • each attempt has its own 20 s timeout on the Lake Brain feed client (batch job, 15 min task budget), not the 8 s
//     render-path cap. Worst case per request: 3 × 20 s + ~6 s of backoff.
//   • the failure reason is kept ("timed out after 3 attempts", "HTTP 503 after 3 attempts", "HTTP 404 (permanent)").
//  What it does NOT change: the USGS fallback, the stale rule, the flags, the WARNING rule, scheduling, or idempotency
//  (requests are read-only GETs; a retry never writes anything).
//

import Foundation
import AsyncHTTPClient
import NIOCore

struct CWMSResponse: Sendable {
    var status: Int
    var body: Data
    /// `Retry-After` in seconds, when the server sent one.
    var retryAfter: TimeInterval?
}

enum CWMSTransportFailure: Error, Equatable, Sendable {
    case timeout
    case connection(String)
}

/// Everything a CWMS request needs from the world; tests inject fakes.
struct CWMSTransport: Sendable {
    var fetch: @Sendable (_ url: String, _ accept: String, _ timeout: TimeInterval) async -> Result<CWMSResponse, CWMSTransportFailure>
    var sleep: @Sendable (_ seconds: TimeInterval) async -> Void
    /// Uniform in [0, 1); scales each backoff into 50–100 % of its nominal value.
    var jitter: @Sendable () -> Double
    /// Progress lines ("CWMS retry …") for the job log.
    var log: @Sendable (_ line: String) -> Void

    static func live() -> CWMSTransport {
        CWMSTransport(
            fetch: { url, accept, timeout in
                var request = HTTPClientRequest(url: url)
                request.method = .GET
                request.headers.add(name: "User-Agent", value: LakeFeedHTTP.userAgent)
                request.headers.add(name: "Accept", value: accept)
                request.headers.add(name: "Accept-Encoding", value: "gzip, deflate")
                do {
                    let response = try await LakeFeedHTTP.client.execute(request, timeout: .milliseconds(Int64(timeout * 1000)))
                    let buffer = try await response.body.collect(upTo: 64 * 1024 * 1024)
                    let ra = response.headers.first(name: "Retry-After").flatMap { Double($0.trimmingCharacters(in: .whitespaces)) }
                    return .success(CWMSResponse(status: Int(response.status.code), body: Data(buffer.readableBytesView), retryAfter: ra))
                } catch let e as HTTPClientError where e == .deadlineExceeded || e == .readTimeout || e == .connectTimeout {
                    return .failure(.timeout)
                } catch {
                    return .failure(.connection(String(describing: error).prefix(120).description))
                }
            },
            sleep: { s in try? await Task.sleep(nanoseconds: UInt64(max(0, s) * 1_000_000_000)) },
            jitter: { Double.random(in: 0..<1) },
            log: { print($0) })
    }
}

struct CWMSRetryPolicy: Sendable, Equatable {
    var maxAttempts = 3
    var attemptTimeout: TimeInterval = 20
    var baseDelay: TimeInterval = 2
    var maxDelay: TimeInterval = 10
    var maxRetryAfter: TimeInterval = 30

    static let transientStatus: Set<Int> = [408, 429, 500, 502, 503, 504]

    /// Wait before retry number `retry` (1-based): exponential, capped, jittered into 50–100 %; a server `Retry-After` wins when longer.
    func delay(beforeRetry retry: Int, retryAfter: TimeInterval?, jitter: Double) -> TimeInterval {
        let nominal = min(maxDelay, baseDelay * pow(2, Double(max(0, retry - 1))))
        let jittered = nominal * (0.5 + 0.5 * min(max(jitter, 0), 1))
        guard let ra = retryAfter, ra > 0 else { return jittered }
        return max(jittered, ra)
    }
}

enum CWMSFetch: Equatable, Sendable {
    case ok(Data, attempts: Int)
    /// Not worth repeating (e.g. 400 / 404): one attempt, no retry.
    case permanent(String)
    /// Transient every time, or the server asked us to wait longer than the cap.
    case exhausted(String, attempts: Int)

    var failure: String? {
        switch self {
        case .ok: return nil
        case .permanent(let m), .exhausted(let m, _): return m
        }
    }
}

enum CWMSRequest {
    /// GET with bounded, classified retries. `label` names the series in messages ("SAS Hartwell.Elev-Pool…").
    static func get(_ url: String, accept: String, label: String, transport: CWMSTransport, policy: CWMSRetryPolicy) async -> CWMSFetch {
        var last = "unreachable"
        for attempt in 1...max(1, policy.maxAttempts) {
            var retryAfter: TimeInterval? = nil
            switch await transport.fetch(url, accept, policy.attemptTimeout) {
            case .success(let r) where (200..<300).contains(r.status):
                if attempt > 1 { transport.log("CWMS \(label): ok on attempt \(attempt)/\(policy.maxAttempts)") }
                return .ok(r.body, attempts: attempt)
            case .success(let r) where CWMSRetryPolicy.transientStatus.contains(r.status):
                last = "HTTP \(r.status)"
                retryAfter = r.retryAfter
                if let ra = r.retryAfter, ra > policy.maxRetryAfter {
                    return .exhausted("CWMS \(label): HTTP \(r.status) with Retry-After \(Int(ra)) s (over the \(Int(policy.maxRetryAfter)) s cap; not retried sooner)", attempts: attempt)
                }
            case .success(let r):
                return .permanent("CWMS \(label): HTTP \(r.status) (permanent; not retried)")
            case .failure(.timeout):
                last = "timed out (\(Int(policy.attemptTimeout)) s)"
            case .failure(.connection(let why)):
                last = "connection error (\(why))"
            }
            guard attempt < policy.maxAttempts else { break }
            let wait = policy.delay(beforeRetry: attempt, retryAfter: retryAfter, jitter: transport.jitter())
            transport.log("CWMS \(label): attempt \(attempt)/\(policy.maxAttempts) \(last); retrying in \(String(format: "%.1f", wait)) s")
            await transport.sleep(wait)
        }
        return .exhausted("CWMS \(label): \(last) after \(policy.maxAttempts) attempts", attempts: policy.maxAttempts)
    }
}
