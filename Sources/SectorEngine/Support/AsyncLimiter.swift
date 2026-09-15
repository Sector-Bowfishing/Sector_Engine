//
//  AsyncLimiter.swift
//  SectorEngine
//
//  A cancellable async semaphore: at most `limit` operations run at once; the
//  rest wait in FIFO order without blocking a thread.
//
//  Used in front of slow upstream hosts. USGS waterservices holds each
//  connection 4–19s, speaks HTTP/1.1 (no multiplexing), and a cold render asks it
//  four times. With several renders — or a /conditions/batch request scoring six
//  points at once — per instance, requests past the HTTP client's per-host pool
//  failed at its 5s pool-wait deadline and quietly became "no gage". A limiter
//  keeps the queue in our process, where waiting counts against the caller's own
//  budget and a cancelled caller leaves the queue cleanly.
//

import Foundation

actor AsyncLimiter {
    private let limit: Int
    private var active = 0
    private var waiters: [(id: UInt64, continuation: CheckedContinuation<Bool, Never>)] = []
    private var nextID: UInt64 = 0

    init(limit: Int) {
        self.limit = max(1, limit)
    }

    /// Waits for a slot. Returns false if the calling task was cancelled first
    /// (a withDeadline that gave up) — the caller must then not run, and must
    /// not call `release()`.
    func acquire() async -> Bool {
        if Task.isCancelled { return false }
        if active < limit {
            active += 1
            return true
        }
        let id = nextID
        nextID += 1
        return await withTaskCancellationHandler {
            await withCheckedContinuation { continuation in
                waiters.append((id, continuation))
            }
        } onCancel: {
            Task { await self.cancelWaiter(id) }
        }
    }

    /// Frees a slot, handing it straight to the longest waiter if there is one.
    func release() {
        if waiters.isEmpty {
            active = max(0, active - 1)
        } else {
            waiters.removeFirst().continuation.resume(returning: true)   // slot passes over
        }
    }

    private func cancelWaiter(_ id: UInt64) {
        guard let index = waiters.firstIndex(where: { $0.id == id }) else { return }
        waiters.remove(at: index).continuation.resume(returning: false)
    }
}

/// Run `operation` inside one of `limiter`'s slots.
func withLimit<T: Sendable>(_ limiter: AsyncLimiter,
                            _ operation: () async throws -> T) async throws -> T {
    guard await limiter.acquire() else { throw CancellationError() }
    do {
        let value = try await operation()
        await limiter.release()
        return value
    } catch {
        await limiter.release()
        throw error
    }
}
