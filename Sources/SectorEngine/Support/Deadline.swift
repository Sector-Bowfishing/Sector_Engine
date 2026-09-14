//
//  Deadline.swift
//  SectorEngine
//
//  Wall-clock deadline + lightweight per-fetch timing for the engine's upstream
//  calls.
//
//  Every live input (weather, USGS gages, dam generation, NWS alerts, MRMS
//  radar rain) is an independent network fetch to a third-party service we
//  don't control. Any one can stall — most viciously a TLS handshake that
//  connects at the TCP layer but never completes, which on Linux
//  swift-corelibs-foundation honours NEITHER task cancellation NOR
//  URLRequest.timeoutInterval. The conditions fan-out awaited all inputs, so one
//  such stall blew past Cloud Run's 60s request limit (→ 504) and the app's 45s
//  client timeout (→ "Couldn't read conditions").
//
//  `withDeadline` bounds each fetch: finish within `seconds` or the result is
//  dropped to nil — which the aggregator renders as a *dormant* factor. A
//  partial score from the inputs that arrived beats no score because one hung.
//
//  CRITICAL implementation note: this does NOT use `withTaskGroup`. A task group
//  waits for every child task to finish before it returns, and `cancelAll()`
//  only *requests* cancellation — so a child stuck in an uncancellable network
//  call would block the group and defeat the whole point (this was a real bug:
//  the deadline "fired" but the response still hung to 60s). Instead the work
//  runs in a detached task that reports through a one-shot actor; the moment the
//  work OR the timer wins, we return. The loser is cancelled: an in-flight
//  HTTP.get honours that by tearing its request down (AsyncHTTPClient), and it
//  carries its own 8s cap regardless (see HTTP.swift), so no socket is leaked.
//  The HTTP response is ALWAYS freed at the budget, no matter how the upstream
//  misbehaves.
//
//  The timer only works if a cooperative thread is free to run it. Under
//  Foundation's URLSession on Linux it wasn't: two or more concurrent renders
//  tied the pool up, the timers never fired, and the instance froze (2026-09-14).
//  That's why every fetch now goes through HTTP.swift instead.
//

import Foundation

func withDeadline<T: Sendable>(
    _ seconds: Double,
    _ name: String,
    slowThreshold: Double = 3,
    _ operation: @escaping @Sendable () async -> T?
) async -> T? {
    let start = Date()
    let gate = DeadlineGate<T>()

    let work = Task {
        let v = await operation()
        await gate.offer(v)
    }
    let timer = Task {
        try? await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
        await gate.offer(nil)
    }

    let value = await gate.result()
    // Cancel the loser. HTTP.get tears its request down on cancellation, and
    // is capped at 8s regardless — we do not wait for it either way.
    work.cancel()
    timer.cancel()

    let elapsed = Date().timeIntervalSince(start)
    if value == nil && elapsed >= seconds - 0.25 {
        print("[engine] fetch '\(name)' exceeded \(String(format: "%.0f", seconds))s budget — dropped to dormant")
    } else if elapsed >= slowThreshold {
        print("[engine] fetch '\(name)' slow: \(String(format: "%.1f", elapsed))s")
    }
    return value
}

/// One-shot rendezvous between the work task and the timer task: the first
/// `offer` wins and is delivered to the single `result()` awaiter. Being an
/// actor makes the first-wins check atomic, so the result is resolved exactly
/// once even when both tasks fire at nearly the same instant.
private actor DeadlineGate<T: Sendable> {
    private var delivered = false
    private var stored: T?
    private var waiter: CheckedContinuation<T?, Never>?

    func offer(_ value: T?) {
        guard !delivered else { return }
        delivered = true
        if let waiter {
            self.waiter = nil
            waiter.resume(returning: value)
        } else {
            stored = value
        }
    }

    func result() async -> T? {
        if delivered { return stored }
        return await withCheckedContinuation { waiter = $0 }
    }
}
