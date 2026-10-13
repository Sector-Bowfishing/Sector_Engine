//
//  BrainRTDBStore.swift
//  Sector — Brain RTDB writers (REST) for jobs. Never used by the service.
//
//  RTDBRestStore talks to https://sector-brain.firebaseio.com with an OAuth
//  token (Cloud Run metadata server, or SECTOR_BRAIN_ACCESS_TOKEN locally) under
//  the contract's transport policy (§8): 4 attempts, backoff 1.5·2^n s, retry
//  only on transport errors / 5xx / 429, app-database refusal, illegal-key and
//  ownership checks before every write. The service account needs
//  roles/firebasedatabase.admin on sector-9393c.
//
//  LocalDirectoryStore writes each path as a JSON file; InMemoryBrainStore keeps
//  a tree — dry runs that never touch the database, with the same checks.
//

import Foundation
import AsyncHTTPClient
import NIOCore
import NIOHTTP1

public struct BrainStoreError: Error, CustomStringConvertible {
    public let description: String
    public let status: Int?
    public init(_ description: String, status: Int? = nil) { self.description = description; self.status = status }
}

public enum BrainTransportPolicy {
    public static let attempts = 4
    public static func backoffSeconds(_ attempt: Int) -> Double { 1.5 * pow(2.0, Double(attempt)) }
    /// Transport errors (nil), 5xx and 429 only.
    public static func shouldRetry(status: Int?) -> Bool { status == nil || status! >= 500 || status == 429 }
    public static let connectTimeout: Int64 = 10, readTimeout: Int64 = 30, requestTimeout: Int64 = 60
    public static let maxLakesPerPatch = 50
}

/// Shared pre-write validation (§1, §5).
enum BrainWriteGuard {
    static func validate(_ paths: [String: Data], brainId: String?) throws {
        try BrainPlatform.checkUpdate(paths)
        if let brainId { try BrainOwnership.check(paths, brainId: brainId) }
    }
}

public final class RTDBRestStore: BrainStore, @unchecked Sendable {
    let base: String
    let client: HTTPClient
    let staticToken: String?
    /// When set, every update is ownership-checked for this brain.
    public let brainId: String?
    private var cached: (token: String, until: Date)?
    private let lock = NSLock()
    public private(set) var writes = 0

    /// `databaseURL` e.g. https://sector-brain.firebaseio.com — anything else is refused.
    public init(databaseURL: String = BrainPlatform.databaseURL, brainId: String? = nil,
                accessToken: String? = ProcessInfo.processInfo.environment["SECTOR_BRAIN_ACCESS_TOKEN"]) throws {
        guard BrainPlatform.acceptedDatabaseURL(databaseURL) else {
            throw BrainStoreError("refusing to write Brain data to \(databaseURL): not the dedicated sector-brain database")
        }
        base = databaseURL.hasSuffix("/") ? String(databaseURL.dropLast()) : databaseURL
        var config = HTTPClient.Configuration()
        config.timeout = .init(connect: .seconds(BrainTransportPolicy.connectTimeout), read: .seconds(BrainTransportPolicy.readTimeout))
        client = HTTPClient(eventLoopGroupProvider: .singleton, configuration: config)
        staticToken = accessToken
        self.brainId = brainId
    }

    public func shutdown() async { try? await client.shutdown() }

    func token() async throws -> String {
        if let t = staticToken, !t.isEmpty { return t }
        if let c = lock.withLock({ cached }), c.until > Date() { return c.token }
        let scopes = "https://www.googleapis.com/auth/firebase.database,https://www.googleapis.com/auth/userinfo.email"
        var r = HTTPClientRequest(url: "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token?scopes=\(scopes)")
        r.headers.add(name: "Metadata-Flavor", value: "Google")
        let resp = try await client.execute(r, timeout: .seconds(BrainTransportPolicy.connectTimeout))
        let body = try await resp.body.collect(upTo: 1 << 16)
        struct T: Decodable { let access_token: String; let expires_in: Double }
        let t = try JSONDecoder().decode(T.self, from: Data(body.readableBytesView))
        // Refreshed when < 120 s to expiry (§8).
        lock.withLock { cached = (t.access_token, Date().addingTimeInterval(t.expires_in - 120)) }
        return t.access_token
    }

    private func send(_ method: HTTPMethod, _ path: String, query: String = "", body: Data? = nil) async throws -> Data {
        let trimmed = path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let url = "\(base)/\(trimmed).json" + (query.isEmpty ? "" : "?\(query)")
        var lastError: Error = BrainStoreError("no attempt")
        for attempt in 0..<BrainTransportPolicy.attempts {
            var status: Int? = nil
            do {
                var r = HTTPClientRequest(url: url)
                r.method = method
                r.headers.add(name: "Authorization", value: "Bearer \(try await token())")
                if let body {
                    r.headers.add(name: "Content-Type", value: "application/json")
                    r.body = .bytes(ByteBuffer(bytes: body))
                }
                let resp = try await client.execute(r, timeout: .seconds(BrainTransportPolicy.requestTimeout))
                let out = try await resp.body.collect(upTo: 32 << 20)
                let data = Data(out.readableBytesView)
                status = Int(resp.status.code)
                guard (200..<300).contains(status!) else {
                    throw BrainStoreError("RTDB \(method) /\(trimmed) → \(status!): \(String(decoding: data.prefix(300), as: UTF8.self))", status: status)
                }
                return data
            } catch {
                lastError = error
                guard BrainTransportPolicy.shouldRetry(status: status) else { break }
                if attempt < BrainTransportPolicy.attempts - 1 {
                    try? await Task.sleep(nanoseconds: UInt64(BrainTransportPolicy.backoffSeconds(attempt) * 1_000_000_000))
                }
            }
        }
        throw lastError
    }

    public func update(_ paths: [String: Data]) async throws {
        guard !paths.isEmpty else { return }
        try BrainWriteGuard.validate(paths, brainId: brainId)
        _ = try await send(.PATCH, "", query: "print=silent", body: try BrainJSON.multiPathBody(paths))
        lock.withLock { writes += 1 }
    }

    public func get(_ path: String) async throws -> Data? {
        let d = try await send(.GET, path)
        return String(decoding: d, as: UTF8.self) == "null" ? nil : d
    }

    public func delete(_ path: String) async throws { try await update([path: Data("null".utf8)]) }

    public func shallowKeys(_ path: String) async throws -> [String] {
        let d = try await send(.GET, path, query: "shallow=true")
        guard String(decoding: d, as: UTF8.self) != "null" else { return [] }
        return try JSONDecoder().decode([String: Bool].self, from: d).keys.sorted()
    }

    /// Abort before any write if /schemaVersion is present and not the one this platform speaks (§1).
    public func checkSchema() async throws -> Int? {
        guard let d = try await get("schemaVersion"), let v = try JSONSerialization.jsonObject(with: d, options: [.fragmentsAllowed]) as? Int else { return nil }
        guard v == BrainPlatform.schemaVersion else {
            throw BrainStoreError("Brain RTDB schemaVersion is \(v); this platform writes schema \(BrainPlatform.schemaVersion)")
        }
        return v
    }
}

/// Dry run: every path becomes <dir>/<path>.json. Nothing leaves the machine.
public final class LocalDirectoryStore: BrainStore, @unchecked Sendable {
    let dir: URL
    public let brainId: String?
    public private(set) var updates: [[String: Data]] = []
    private let lock = NSLock()
    public init(directory: String, brainId: String? = nil) { dir = URL(fileURLWithPath: directory); self.brainId = brainId }

    public func update(_ paths: [String: Data]) async throws {
        try BrainWriteGuard.validate(paths, brainId: brainId)
        lock.withLock { updates.append(paths) }
        for (p, d) in paths {
            let f = dir.appendingPathComponent(p + ".json")
            try FileManager.default.createDirectory(at: f.deletingLastPathComponent(), withIntermediateDirectories: true)
            if String(decoding: d, as: UTF8.self) == "null" { try? FileManager.default.removeItem(at: f) } else { try d.write(to: f) }
        }
    }
    public func get(_ path: String) async throws -> Data? { try? Data(contentsOf: dir.appendingPathComponent(path + ".json")) }
    public func delete(_ path: String) async throws { try await update([path: Data("null".utf8)]) }
    public func shallowKeys(_ path: String) async throws -> [String] {
        ((try? FileManager.default.contentsOfDirectory(atPath: dir.appendingPathComponent(path).path)) ?? [])
            .map { $0.hasSuffix(".json") ? String($0.dropLast(5)) : $0 }.sorted()
    }
}

/// Dry run / tests: an in-memory tree with the live store's checks and multi-path semantics.
public final class InMemoryBrainStore: BrainStore, @unchecked Sendable {
    public private(set) var tree: [String: Any]
    public let brainId: String?
    public private(set) var patches: [[String: Data]] = []
    private let lock = NSLock()
    public init(tree: [String: Any] = [:], brainId: String? = nil) { self.tree = tree; self.brainId = brainId }

    public func update(_ paths: [String: Data]) async throws {
        try BrainWriteGuard.validate(paths, brainId: brainId)
        try lock.withLock {
            patches.append(paths)
            for (p, d) in paths {
                let parts = p.split(separator: "/", omittingEmptySubsequences: true).map(String.init)
                let value: Any? = String(decoding: d, as: UTF8.self) == "null" ? nil
                    : try JSONSerialization.jsonObject(with: d, options: [.fragmentsAllowed])
                tree = Self.set(tree, parts[...], value)
            }
        }
    }
    private static func set(_ node: [String: Any], _ parts: ArraySlice<String>, _ value: Any?) -> [String: Any] {
        var node = node
        guard let head = parts.first else { return node }
        if parts.count == 1 {
            if let value { node[head] = value } else { node.removeValue(forKey: head) }
        } else {
            let child = (node[head] as? [String: Any]) ?? [:]
            node[head] = set(child, parts.dropFirst(), value)
        }
        return node
    }
    private func node(_ path: String) -> Any? {
        var cur: Any = lock.withLock { tree }
        for p in path.split(separator: "/", omittingEmptySubsequences: true) {
            guard let d = cur as? [String: Any], let next = d[String(p)] else { return nil }
            cur = next
        }
        return cur
    }
    public func get(_ path: String) async throws -> Data? {
        guard let v = node(path) else { return nil }
        return try JSONSerialization.data(withJSONObject: v, options: [.fragmentsAllowed, .sortedKeys])
    }
    public func delete(_ path: String) async throws { try await update([path: Data("null".utf8)]) }
    public func shallowKeys(_ path: String) async throws -> [String] { ((node(path) as? [String: Any])?.keys.sorted()) ?? [] }
}
