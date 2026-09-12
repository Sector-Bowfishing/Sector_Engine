//
//  Net.swift
//  SectorEngine
//
//  One shared URLSession for every outbound engine fetch, with a HARD resource
//  timeout.
//
//  `URLSession.shared` has no resource cap. On Linux swift-corelibs-foundation a
//  stuck connection (a TLS handshake that connects but never completes, a server
//  that accepts then goes silent) ignores task cancellation, so a fetch the
//  engine abandoned at its deadline kept its socket alive until the OS TCP
//  timeout — minutes. On a 1-CPU Cloud Run instance those zombies accumulated
//  until the container was exhausted and restarted: observed in prod as the
//  FIRST request after a cold start succeeding and every request after it
//  504-ing, with the instance repeatedly restarting.
//
//  `timeoutIntervalForResource` is a wall-clock cap on the entire load, enforced
//  by a timer regardless of connection state (verified on swift:6.1-jammy: a
//  hung connect throws on schedule, not minutes later). With it, a stuck fetch
//  is actually torn down a beat after `withDeadline` stops waiting on it — so
//  there are no lingering sockets to pile up. Kept just under the smallest
//  `withDeadline` budget (9s) so the HTTP layer is what ends a stalled fetch,
//  and the deadline is only a backstop.
//

import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

enum Net {
    static let session: URLSession = {
        let cfg = URLSessionConfiguration.ephemeral
        cfg.timeoutIntervalForRequest = 7
        cfg.timeoutIntervalForResource = 8
        cfg.httpMaximumConnectionsPerHost = 6
        return URLSession(configuration: cfg)
    }()
}
