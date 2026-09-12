//
//  Deadline.swift
//  SectorEngine
//
//  Structured-concurrency deadline + lightweight per-fetch timing for the
//  engine's upstream calls.
//
//  Every live input (weather, USGS gages, dam generation, NWS alerts, MRMS
//  radar rain) is an independent network fetch to a third-party service we
//  don't control. Any one can stall — a TLS handshake that never completes, a
//  datacenter peering hiccup, an operator feed that hangs open. The conditions
//  fan-out awaited ALL of them with no ceiling, so the single slowest stalled
//  upstream dictated the whole request's latency: it could blow past Cloud
//  Run's 60s request limit (→ 504) or the app's 45s client timeout (→ the
//  "Couldn't read conditions" banner), even though every other input had
//  already arrived.
//
//  `withDeadline` bounds each fetch independently: finish within `seconds` or
//  the result is dropped to nil — which the aggregator already renders as a
//  *dormant* factor. A partial score from eight live inputs beats no score
//  because the ninth hung. It also logs any slow or timed-out fetch BY NAME, so
//  the next stall names itself in the Cloud Run logs instead of needing another
//  round of manual bisection.
//

import Foundation

/// Run `operation`, returning its value if it completes within `seconds`,
/// otherwise nil. The losing task is cancelled (URLSession honours cancellation,
/// so the in-flight request is torn down rather than leaked). A genuine fast nil
/// — e.g. no gage near this coordinate — returns immediately without waiting out
/// the budget. Never throws for the timeout: a stalled upstream becomes a
/// missing input, not a failed request.
///
/// - Parameters:
///   - seconds: the wall-clock budget for this fetch.
///   - name: short label used only in the slow/timeout log line.
///   - slowThreshold: log a successful-but-slow fetch at or above this duration.
func withDeadline<T: Sendable>(
    _ seconds: Double,
    _ name: String,
    slowThreshold: Double = 3,
    _ operation: @escaping @Sendable () async -> T?
) async -> T? {
    let start = Date()
    let value: T? = await withTaskGroup(of: T?.self) { group in
        group.addTask { await operation() }
        group.addTask {
            try? await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
            return nil
        }
        let first = await group.next() ?? nil
        group.cancelAll()
        return first
    }
    let elapsed = Date().timeIntervalSince(start)
    if value == nil && elapsed >= seconds - 0.25 {
        print("[engine] fetch '\(name)' exceeded \(String(format: "%.0f", seconds))s budget — dropped to dormant")
    } else if elapsed >= slowThreshold {
        print("[engine] fetch '\(name)' slow: \(String(format: "%.1f", elapsed))s")
    }
    return value
}
