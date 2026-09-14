//
//  HTTPTests.swift
//  SectorEngineTests
//
//  HTTP.get's budget must cover the whole response, not just the headers.
//  AsyncHTTPClient's own deadline stops at the response head, so an upstream
//  that answers promptly and then stalls its body would otherwise hold a render
//  open indefinitely. A local NIO server reproduces exactly that.
//

import XCTest
import NIOCore
import NIOPosix
@testable import SectorEngine

/// Writes a valid HTTP/1.1 response head promising a body, sends part of it,
/// and then never finishes.
private final class StallingBodyHandler: ChannelInboundHandler, Sendable {
    typealias InboundIn = ByteBuffer
    typealias OutboundOut = ByteBuffer

    func channelRead(context: ChannelHandlerContext, data: NIOAny) {
        let head = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 1000\r\n\r\n{\"partial\":"
        context.writeAndFlush(NIOAny(context.channel.allocator.buffer(string: head)), promise: nil)
        // …and the remaining bytes never arrive.
    }
}

/// Answers every request with a small complete JSON body.
private final class CompleteBodyHandler: ChannelInboundHandler, Sendable {
    typealias InboundIn = ByteBuffer
    typealias OutboundOut = ByteBuffer

    func channelRead(context: ChannelHandlerContext, data: NIOAny) {
        let body = "{\"ok\":true}"
        let response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: \(body.utf8.count)\r\nConnection: close\r\n\r\n\(body)"
        let channel = context.channel
        context.writeAndFlush(NIOAny(channel.allocator.buffer(string: response))).whenComplete { _ in
            channel.close(promise: nil)
        }
    }
}

final class HTTPTests: XCTestCase {

    private func startServer(_ makeHandler: @escaping @Sendable () -> ChannelHandler) async throws -> (Channel, Int) {
        let channel = try await ServerBootstrap(group: MultiThreadedEventLoopGroup.singleton)
            .serverChannelOption(.socketOption(.so_reuseaddr), value: 1)
            .childChannelInitializer { channel in
                channel.eventLoop.makeCompletedFuture {
                    try channel.pipeline.syncOperations.addHandler(makeHandler())
                }
            }
            .bind(host: "127.0.0.1", port: 0)
            .get()
        let port = try XCTUnwrap(channel.localAddress?.port)
        return (channel, port)
    }

    func testBudgetCoversAStalledBody() async throws {
        let (server, port) = try await startServer { StallingBodyHandler() }
        defer { _ = server.close() }

        let url = try XCTUnwrap(URL(string: "http://127.0.0.1:\(port)/stall"))
        let started = Date()
        do {
            _ = try await HTTP.get(url, timeout: 1.0)
            XCTFail("a stalled body must not be returned as a result")
        } catch {
            // Expected: the budget fired (or the client gave up on the body).
        }
        let elapsed = Date().timeIntervalSince(started)
        XCTAssertLessThan(elapsed, 3.0, "fetch must end near its 1s budget, not hang on the body (took \(elapsed)s)")
    }

    func testCompleteResponseIsReturned() async throws {
        let (server, port) = try await startServer { CompleteBodyHandler() }
        defer { _ = server.close() }

        let url = try XCTUnwrap(URL(string: "http://127.0.0.1:\(port)/ok"))
        let result = try await HTTP.get(url, timeout: 3.0)
        XCTAssertEqual(result.status, 200)
        XCTAssertTrue(result.isSuccess)
        XCTAssertEqual(String(decoding: result.body, as: UTF8.self), "{\"ok\":true}")
    }
}
