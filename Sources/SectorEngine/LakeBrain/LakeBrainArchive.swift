//
//  LakeBrainArchive.swift
//  Sector — Lake Brain: history storage (GCS) and the daily level history
//
//  History never goes in the Brain RTDB. It lives in the private, versioned
//  bucket gs://sector-lake-brain:
//    history/{lakeKey}/daily.csv              date,elevationFt,sourceId (one row per lake-local day)
//    baselines/{lakeKey}/{baselineVersion}.json
//    presence/latest.json → presence/releases/{researchVersion}/presence.json   (private research data)
//
//  The Water Temp lane's TVA archive (gs://sector-water-temp-archive) is read,
//  never written (shared archive, approved 2026-10-12).
//

import Foundation
import AsyncHTTPClient
import NIOCore
import NIOHTTP1

public protocol LakeBrainArchive: Sendable {
    var uri: String { get }
    func read(_ path: String) async throws -> Data?
    func write(_ path: String, _ data: Data, contentType: String) async throws
}

/// Dry run / tests: a directory on disk.
public final class LocalLakeBrainArchive: LakeBrainArchive, @unchecked Sendable {
    let dir: URL
    public var uri: String { dir.path }
    public init(directory: String) { dir = URL(fileURLWithPath: directory) }
    public func read(_ path: String) async throws -> Data? { try? Data(contentsOf: dir.appendingPathComponent(path)) }
    public func write(_ path: String, _ data: Data, contentType: String) async throws {
        let f = dir.appendingPathComponent(path)
        try FileManager.default.createDirectory(at: f.deletingLastPathComponent(), withIntermediateDirectories: true)
        try data.write(to: f)
    }
}

/// Reads from `primary`, falling back to `seed`; writes only to `primary`. Lets a
/// dry run start from the real bucket's history without ever writing to it.
public final class LayeredLakeBrainArchive: LakeBrainArchive, @unchecked Sendable {
    let primary: LakeBrainArchive, seed: LakeBrainArchive
    public var uri: String { "\(primary.uri) (seeded from \(seed.uri))" }
    public init(primary: LakeBrainArchive, seed: LakeBrainArchive) { self.primary = primary; self.seed = seed }
    public func read(_ path: String) async throws -> Data? {
        if let d = try await primary.read(path) { return d }
        return try await seed.read(path)
    }
    public func write(_ path: String, _ data: Data, contentType: String) async throws {
        try await primary.write(path, data, contentType: contentType)
    }
}

/// Google Cloud Storage JSON API. Token: `SECTOR_GCS_ACCESS_TOKEN`, else the Cloud Run metadata server.
public final class GCSLakeBrainArchive: LakeBrainArchive, @unchecked Sendable {
    public let bucket: String
    public let readOnly: Bool
    /// The engine's process-lifetime client (never shut down), so archives need no lifecycle.
    var client: HTTPClient { HTTP.client }
    let staticToken: String?
    private var cached: (token: String, until: Date)?
    private let lock = NSLock()
    public var uri: String { "gs://\(bucket)" }

    public init(bucket: String, readOnly: Bool = false,
                accessToken: String? = ProcessInfo.processInfo.environment["SECTOR_GCS_ACCESS_TOKEN"]) {
        self.bucket = bucket; self.readOnly = readOnly
        staticToken = accessToken
    }

    func token() async throws -> String {
        if let t = staticToken, !t.isEmpty { return t }
        if let c = lock.withLock({ cached }), c.until > Date() { return c.token }
        var r = HTTPClientRequest(url: "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token?scopes=https://www.googleapis.com/auth/devstorage.read_write")
        r.headers.add(name: "Metadata-Flavor", value: "Google")
        let resp = try await client.execute(r, timeout: .seconds(10))
        let body = try await resp.body.collect(upTo: 1 << 16)
        struct T: Decodable { let access_token: String; let expires_in: Double }
        let t = try JSONDecoder().decode(T.self, from: Data(body.readableBytesView))
        lock.withLock { cached = (t.access_token, Date().addingTimeInterval(t.expires_in - 120)) }
        return t.access_token
    }

    static func encodeObject(_ path: String) -> String {
        var allowed = CharacterSet.urlPathAllowed; allowed.remove(charactersIn: "/?#[]@!$&'()*+,;=")
        return path.addingPercentEncoding(withAllowedCharacters: allowed) ?? path
    }

    public func read(_ path: String) async throws -> Data? {
        var r = HTTPClientRequest(url: "https://storage.googleapis.com/storage/v1/b/\(bucket)/o/\(Self.encodeObject(path))?alt=media")
        r.headers.add(name: "Authorization", value: "Bearer \(try await token())")
        let resp = try await client.execute(r, timeout: .seconds(30))
        let body = try await resp.body.collect(upTo: 64 << 20)
        if resp.status.code == 404 { return nil }
        guard (200..<300).contains(Int(resp.status.code)) else {
            throw BrainStoreError(description: "GCS GET gs://\(bucket)/\(path) → \(resp.status.code)")
        }
        return Data(body.readableBytesView)
    }

    public func write(_ path: String, _ data: Data, contentType: String) async throws {
        guard !readOnly else { throw BrainStoreError(description: "gs://\(bucket) is read-only for the Lake Brain") }
        var r = HTTPClientRequest(url: "https://storage.googleapis.com/upload/storage/v1/b/\(bucket)/o?uploadType=media&name=\(Self.encodeObject(path))")
        r.method = .POST
        r.headers.add(name: "Authorization", value: "Bearer \(try await token())")
        r.headers.add(name: "Content-Type", value: contentType)
        r.body = .bytes(ByteBuffer(bytes: data))
        let resp = try await client.execute(r, timeout: .seconds(30))
        let body = try await resp.body.collect(upTo: 1 << 20)
        guard (200..<300).contains(Int(resp.status.code)) else {
            throw BrainStoreError(description: "GCS PUT gs://\(bucket)/\(path) → \(resp.status.code): \(String(decoding: Data(body.readableBytesView).prefix(200), as: UTF8.self))")
        }
    }
}

// MARK: - Daily history (history/{lakeKey}/daily.csv)

public enum LakeDailyHistory {
    public static func path(_ lakeId: String) -> String { "history/\(BrainPlatform.lakeKey(lakeId))/daily.csv" }

    /// One value per date; when two sources give the same date the later entry in `xs` wins.
    public static func dedupe(_ xs: [DailyLevel]) -> [DailyLevel] {
        var byDate: [String: DailyLevel] = [:]
        for x in xs { byDate[x.date] = x }
        return byDate.values.sorted { $0.date < $1.date }
    }

    public static func encode(_ xs: [DailyLevel]) -> Data {
        var s = "date,elevationFt,sourceId\n"
        for x in dedupe(xs) { s += "\(x.date),\(String(format: "%.2f", x.ft)),\(x.sourceId)\n" }
        return Data(s.utf8)
    }

    public static func decode(_ d: Data) -> [DailyLevel] {
        String(decoding: d, as: UTF8.self).split(separator: "\n").dropFirst().compactMap { line in
            let p = line.split(separator: ",", maxSplits: 2).map(String.init)
            guard p.count == 3, let ft = Double(p[1]), LakeLevelCalendar.isDayString(p[0]) else { return nil }
            return DailyLevel(date: p[0], ft: ft, sourceId: p[2])
        }
    }

    /// Existing archive ∪ new rows. New rows win on the same date (operators revise).
    public static func merge(existing: [DailyLevel], new: [DailyLevel]) -> [DailyLevel] { dedupe(existing + new) }
}

extension LakeLevelCalendar {
    static func isDayString(_ day: String) -> Bool { day.count == 10 && doy365(day) != nil }
}
