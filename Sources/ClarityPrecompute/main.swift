//
//  ClarityPrecompute — the hourly job that prepares each lake's Current
//  Clarity world (Clarity Fusion Stage 5; see PreparedClarityWorld.swift)
//
//  usage: ClarityPrecompute [--lake ID] [--out DIR] [--bucket NAME]
//    --lake ID      one lake (default: every lake with a regions index)
//    --out DIR      write clarity/current/<slug>/… under DIR (a local mirror)
//    --bucket NAME  upload to gs://NAME as the job's service account
//                   (default: $SECTOR_CLARITY_BUCKET)
//
//  The build is the routes' own live build, run where no one waits for it.
//  Files go up composite first (named by its ETag, so a reader never pairs a
//  new world with an old composite), then changes.json, then world.json.
//  Exits non-zero if any lake failed.
//

import Foundation
import SectorEngine
import AsyncHTTPClient
import NIOCore

let argv = CommandLine.arguments
func flag(_ name: String) -> String? { argv.firstIndex(of: name).flatMap { $0 + 1 < argv.count ? argv[$0 + 1] : nil } }
let lakes = flag("--lake").map { [$0] } ?? ClarityRegionsIndex.lakeIds
let outDir = flag("--out")
let bucket = flag("--bucket") ?? ProcessInfo.processInfo.environment["SECTOR_CLARITY_BUCKET"]
guard outDir != nil || bucket != nil else {
    FileHandle.standardError.write(Data("ClarityPrecompute: give --out DIR or --bucket NAME (or SECTOR_CLARITY_BUCKET)\n".utf8))
    exit(2)
}

let encoder: JSONEncoder = {
    let e = JSONEncoder(); e.dateEncodingStrategy = .iso8601; e.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
    return e
}()

/// gzip -n (no name or time in the header, so the same bytes give the same file).
func gzip(_ bytes: [UInt8]) throws -> [UInt8] {
    let input = FileManager.default.temporaryDirectory.appendingPathComponent("sccc-\(UUID().uuidString).bin")
    try Data(bytes).write(to: input)
    defer { try? FileManager.default.removeItem(at: input) }
    let p = Process()
    p.executableURL = URL(fileURLWithPath: "/usr/bin/env")
    p.arguments = ["gzip", "-n", "-9", "-c", input.path]
    let out = Pipe()
    p.standardOutput = out
    try p.run()
    let data = out.fileHandleForReading.readDataToEndOfFile()
    p.waitUntilExit()
    guard p.terminationStatus == 0, !data.isEmpty else { throw NSError(domain: "gzip", code: Int(p.terminationStatus)) }
    return [UInt8](data)
}

struct Uploader {
    let client = HTTPClient(eventLoopGroupProvider: .singleton)
    let bucket: String

    func token() async throws -> String {
        var r = HTTPClientRequest(url: "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token")
        r.headers.add(name: "Metadata-Flavor", value: "Google")
        let resp = try await client.execute(r, timeout: .seconds(10))
        let body = try await resp.body.collect(upTo: 1 << 20)
        struct T: Decodable { let access_token: String }
        return try JSONDecoder().decode(T.self, from: Data(body.readableBytesView)).access_token
    }

    func put(_ name: String, _ bytes: [UInt8], type: String, cache: String, token: String) async throws {
        let boundary = "sector-\(UUID().uuidString)"
        let meta = try JSONSerialization.data(withJSONObject: ["name": name, "contentType": type, "cacheControl": cache])
        var body = Data("--\(boundary)\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".utf8)
        body.append(meta)
        body.append(Data("\r\n--\(boundary)\r\nContent-Type: \(type)\r\n\r\n".utf8))
        body.append(contentsOf: bytes)
        body.append(Data("\r\n--\(boundary)--\r\n".utf8))
        var r = HTTPClientRequest(url: "https://storage.googleapis.com/upload/storage/v1/b/\(bucket)/o?uploadType=multipart")
        r.method = .POST
        r.headers.add(name: "Authorization", value: "Bearer \(token)")
        r.headers.add(name: "Content-Type", value: "multipart/related; boundary=\(boundary)")
        r.body = .bytes(ByteBuffer(bytes: [UInt8](body)))
        let resp = try await client.execute(r, timeout: .seconds(60))
        let got = try await resp.body.collect(upTo: 1 << 20)
        guard (200..<300).contains(Int(resp.status.code)) else {
            throw NSError(domain: "gcs", code: Int(resp.status.code),
                          userInfo: [NSLocalizedDescriptionKey: "\(name): \(resp.status) \(String(buffer: got))"])
        }
    }
}

let uploader = bucket.map { Uploader(bucket: $0) }
var failed = 0
for lake in lakes {
    let t0 = Date()
    guard let built = await SectorEngineAPI.prepareCurrentClarity(lakeId: lake, now: Date()) else {
        print("✗ \(lake): no world (no hydrologic graph or regions index, or the build failed)")
        failed += 1
        continue
    }
    let (world, changes) = built
    do {
        let slug = lake.replacingOccurrences(of: "|", with: "_")
        let prefix = "clarity/current/\(slug)"
        let bin = world.composite.encoded()
        let gz = try gzip(bin)
        let files = PreparedClarityWorld.Files(composite: "composite-\(world.etag).bin", compositeGzip: "composite-\(world.etag).bin.gz",
                                               compositeBytes: bin.count, compositeGzipBytes: gz.count, changes: "changes.json")
        let dates = world.composite.refs.map(\.date)
        let prepared = PreparedClarityWorld(
            world: world,
            provenance: .init(hydrologyThrough: world.regions.compactMap { $0?.rainRecordThrough }.max(),
                              newestScene: dates.max(), oldestScene: dates.min(),
                              engineCommit: ProcessInfo.processInfo.environment["SECTOR_ENGINE_COMMIT"],
                              buildSeconds: (Date().timeIntervalSince(t0) * 10).rounded() / 10),
            files: files)
        let worldJSON = [UInt8](try encoder.encode(prepared))
        let changesJSON = [UInt8](try encoder.encode(changes))
        let writes: [(String, [UInt8], String, String)] = [
            (files.composite, bin, "application/octet-stream", "public, max-age=31536000"),
            (files.compositeGzip, gz, "application/gzip", "public, max-age=31536000"),
            ("changes.json", changesJSON, "application/json", "public, max-age=60"),
            ("world.json", worldJSON, "application/json", "public, max-age=60"),
        ]
        if let outDir {
            let dir = URL(fileURLWithPath: outDir).appendingPathComponent(prefix)
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            for (name, bytes, _, _) in writes { try Data(bytes).write(to: dir.appendingPathComponent(name)) }
        }
        if let uploader {
            let token = try await uploader.token()
            for (name, bytes, type, cache) in writes {
                try await uploader.put("\(prefix)/\(name)", bytes, type: type, cache: cache, token: token)
            }
        }
        let o = world.overview(table: world.outcomeTable())
        print("✓ \(lake) built \(ISO8601DateFormatter().string(from: world.now)) in \(prepared.provenance.buildSeconds ?? 0)s"
              + " · etag \(world.etag) · \(dates.count) scenes \(dates.min() ?? "-")…\(dates.max() ?? "-")"
              + " · composite \(bin.count) B, gzip \(gz.count) B"
              + " · supported \(o.supportedPct) changed \(o.changedPct) unsupported \(o.unsupportedPct) grass \(o.grassPct)"
              + " · hydrology through \(prepared.provenance.hydrologyThrough.map { ISO8601DateFormatter().string(from: $0) } ?? "unknown")")
        for n in world.notes { print("  note: \(n)") }
    } catch {
        print("✗ \(lake): \(error)")
        failed += 1
    }
}
if let uploader { try? await uploader.client.shutdown() }
exit(failed == 0 ? 0 : 1)
