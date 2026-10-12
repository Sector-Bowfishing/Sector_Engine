//
//  BrainRTDBStore.swift
//  Sector — Brain RTDB writers (REST) for jobs. Never used by the service.
//
//  RTDBRestStore talks to https://sector-brain.firebaseio.com with an OAuth
//  token (Cloud Run metadata server, or SECTOR_BRAIN_ACCESS_TOKEN locally).
//  The service account needs roles/firebasedatabase.admin on sector-9393c;
//  Admin access bypasses the read-only rules Sector Ops is held to.
//
//  LocalDirectoryStore writes each path as a JSON file — a dry run that never
//  touches the database.
//

import Foundation
import AsyncHTTPClient
import NIOCore
import NIOHTTP1

public struct BrainStoreError: Error, CustomStringConvertible {
    public let description: String
}

public final class RTDBRestStore: BrainStore, @unchecked Sendable {
    let base: String
    let client: HTTPClient
    let staticToken: String?
    private var cached: (token: String, until: Date)?
    private let lock = NSLock()

    /// `databaseURL` e.g. https://sector-brain.firebaseio.com
    public init(databaseURL: String, accessToken: String? = ProcessInfo.processInfo.environment["SECTOR_BRAIN_ACCESS_TOKEN"]) {
        base = databaseURL.hasSuffix("/") ? String(databaseURL.dropLast()) : databaseURL
        var config = HTTPClient.Configuration()
        config.timeout = .init(connect: .seconds(10), read: .seconds(30))
        client = HTTPClient(eventLoopGroupProvider: .singleton, configuration: config)
        staticToken = accessToken
    }

    public func shutdown() async { try? await client.shutdown() }

    func token() async throws -> String {
        if let t = staticToken, !t.isEmpty { return t }
        if let c = lock.withLock({ cached }), c.until > Date() { return c.token }
        let scopes = "https://www.googleapis.com/auth/firebase.database,https://www.googleapis.com/auth/userinfo.email"
        var r = HTTPClientRequest(url: "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token?scopes=\(scopes)")
        r.headers.add(name: "Metadata-Flavor", value: "Google")
        let resp = try await client.execute(r, timeout: .seconds(10))
        let body = try await resp.body.collect(upTo: 1 << 16)
        struct T: Decodable { let access_token: String; let expires_in: Double }
        let t = try JSONDecoder().decode(T.self, from: Data(body.readableBytesView))
        lock.withLock { cached = (t.access_token, Date().addingTimeInterval(t.expires_in - 120)) }
        return t.access_token
    }

    private func send(_ method: HTTPMethod, _ path: String, query: String = "", body: Data? = nil) async throws -> Data {
        let trimmed = path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let url = "\(base)/\(trimmed).json" + (query.isEmpty ? "" : "?\(query)")
        var lastError: Error = BrainStoreError(description: "no attempt")
        for attempt in 0..<3 {
            do {
                var r = HTTPClientRequest(url: url)
                r.method = method
                r.headers.add(name: "Authorization", value: "Bearer \(try await token())")
                if let body {
                    r.headers.add(name: "Content-Type", value: "application/json")
                    r.body = .bytes(ByteBuffer(bytes: body))
                }
                let resp = try await client.execute(r, timeout: .seconds(60))
                let out = try await resp.body.collect(upTo: 32 << 20)
                let data = Data(out.readableBytesView)
                guard (200..<300).contains(Int(resp.status.code)) else {
                    throw BrainStoreError(description: "RTDB \(method) /\(trimmed) → \(resp.status.code): \(String(decoding: data.prefix(300), as: UTF8.self))")
                }
                return data
            } catch {
                lastError = error
                if attempt < 2 { try? await Task.sleep(nanoseconds: UInt64(1_000_000_000 * (attempt + 1))) }
            }
        }
        throw lastError
    }

    public func update(_ paths: [String: Data]) async throws {
        guard !paths.isEmpty else { return }
        _ = try await send(.PATCH, "", query: "print=silent", body: try BrainJSON.multiPathBody(paths))
    }

    public func get(_ path: String) async throws -> Data? {
        let d = try await send(.GET, path)
        return String(decoding: d, as: UTF8.self) == "null" ? nil : d
    }

    public func delete(_ path: String) async throws { _ = try await send(.DELETE, path, query: "print=silent") }

    public func shallowKeys(_ path: String) async throws -> [String] {
        let d = try await send(.GET, path, query: "shallow=true")
        guard String(decoding: d, as: UTF8.self) != "null" else { return [] }
        return try JSONDecoder().decode([String: Bool].self, from: d).keys.sorted()
    }
}

/// Dry run: every path becomes <dir>/<path>.json. Nothing leaves the machine.
public final class LocalDirectoryStore: BrainStore, @unchecked Sendable {
    let dir: URL
    public private(set) var updates: [[String: Data]] = []
    private let lock = NSLock()
    public init(directory: String) { dir = URL(fileURLWithPath: directory) }

    public func update(_ paths: [String: Data]) async throws {
        lock.withLock { updates.append(paths) }
        for (p, d) in paths {
            let f = dir.appendingPathComponent(p + ".json")
            try FileManager.default.createDirectory(at: f.deletingLastPathComponent(), withIntermediateDirectories: true)
            if String(decoding: d, as: UTF8.self) == "null" { try? FileManager.default.removeItem(at: f) } else { try d.write(to: f) }
        }
    }
    public func get(_ path: String) async throws -> Data? { try? Data(contentsOf: dir.appendingPathComponent(path + ".json")) }
    public func delete(_ path: String) async throws { try? FileManager.default.removeItem(at: dir.appendingPathComponent(path + ".json")) }
    public func shallowKeys(_ path: String) async throws -> [String] {
        ((try? FileManager.default.contentsOfDirectory(atPath: dir.appendingPathComponent(path).path)) ?? [])
            .map { $0.hasSuffix(".json") ? String($0.dropLast(5)) : $0 }.sorted()
    }
}
