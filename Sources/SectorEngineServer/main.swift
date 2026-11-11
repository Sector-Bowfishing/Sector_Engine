//
//  SectorEngineServer
//
//  Thin HTTP wrapper around SectorEngineAPI. GET /conditions?lat=&lon= → JSON.
//  This is what Cloud Run will run; for Phase 0 it runs on localhost so iOS can
//  A/B its numbers against the app's local engine.
//

import Foundation
import Hummingbird
import SectorEngine

// Line-buffered stdout (Sector_Ops #51 F1 review): on Cloud Run stdout is a pipe, so it is fully buffered by default —
// the [engine]/[http]/[usgs] lines reached Cloud Logging in 4–8 KB batches stamped with the flush time, and lines
// still buffered were lost when an instance was stopped (more often at min-instances 0). One write per line instead.
setvbuf(stdout, nil, _IOLBF, 0)

let router = Router()

// Browser CORS for the website (CORSPolicy): GET /conditions and GET /health only, from the Web project's own origins.
// Added before every route so it wraps them (and the not-found responder, which answers the OPTIONS preflight). A
// request without an Origin header (the apps) passes straight through, unchanged.
struct SectorCORSMiddleware<Context: RequestContext>: RouterMiddleware {
    let policy: CORSPolicy

    func handle(_ request: Request, context: Context,
                next: (Request, Context) async throws -> Response) async throws -> Response {
        guard CORSPolicy.paths.contains(request.uri.path), let origin = request.headers[.origin] else {
            return try await next(request, context)
        }
        if request.method == .options, let headers = policy.preflightHeaders(origin: origin) {
            var response = Response(status: .noContent)
            Self.apply(headers, to: &response)
            return response
        }
        guard request.method == .get || request.method == .head else { return try await next(request, context) }
        var response = try await next(request, context)
        Self.apply(policy.responseHeaders(origin: origin), to: &response)
        return response
    }

    static func apply(_ headers: [(name: String, value: String)], to response: inout Response) {
        for (name, value) in headers {
            switch name {
            case "Vary": response.headers[.vary] = value
            case "Access-Control-Allow-Origin": response.headers[.accessControlAllowOrigin] = value
            case "Access-Control-Allow-Methods": response.headers[.accessControlAllowMethods] = value
            case "Access-Control-Allow-Headers": response.headers[.accessControlAllowHeaders] = value
            case "Access-Control-Max-Age": response.headers[.accessControlMaxAge] = value
            default: break
            }
        }
    }
}
router.add(middleware: SectorCORSMiddleware(policy: CORSPolicy.fromEnvironment()))

router.get("health") { _, _ in "ok" }

func jsonResponse<T: Encodable>(_ value: T) -> Response {
    let data = (try? SectorEngineAPI.makeEncoder().encode(value)) ?? Data()
    var buffer = ByteBuffer()
    buffer.writeBytes(data)
    return Response(status: .ok, headers: [.contentType: "application/json"], body: .init(byteBuffer: buffer))
}

// Full render payload for one coordinate. Fronted by a short-TTL, single-flight
// response cache (see ConditionsResponseCache): the My Lakes preload hits this
// once per saved lake every launch, so without it a broad burst starves the
// engine's cooperative thread pool (2026-09-14 outage). `?fresh=1` bypasses the
// cache read for pull-to-refresh.
router.get("conditions") { request, _ -> Response in
    guard let lat = request.uri.queryParameters.get("lat").flatMap({ Double(String($0)) }),
          let lon = request.uri.queryParameters.get("lon").flatMap({ Double(String($0)) }),
          CoordinateRange.isValid(lat: lat, lon: lon) else {
        return Response(status: .badRequest)   // missing, unparseable or out-of-range coordinate
    }
    let fresh = request.uri.queryParameters.get("fresh").map { $0 == "1" || $0 == "true" } ?? false
    let started = ContinuousClock.now
    let (payload, cache) = await ConditionsResponseCache.shared.conditionsWithOutcome(
        lat: lat, lon: lon, fresh: fresh,
        compute: { await SectorEngineAPI.conditions(lat: lat, lon: lon) }
    )
    // [conditions-request] (Sector_Ops #53 spec §6): one line per request, cache hits included. Client app and build
    // from the User-Agent / X-Sector-Client headers; coordinates rounded to 0.1; no user ids.
    print(ConditionsRequestLog.line(client: clientIdentity(request), cache: cache, ms: elapsedMs(since: started),
                                    lat: lat, lon: lon, response: payload))
    guard let payload else {
        return Response(status: .serviceUnavailable)   // no live data to score
    }
    return jsonResponse(payload)
}

func clientIdentity(_ request: Request) -> ClientIdentity {
    ClientIdentity.parse(userAgent: request.headers[.userAgent],
                         sectorClient: request.headers.first { $0.name.canonicalName == "x-sector-client" }?.value)
}

func elapsedMs(since started: ContinuousClock.Instant) -> Int {
    let e = ContinuousClock.now - started
    return Int(e.components.seconds * 1000 + e.components.attoseconds / 1_000_000_000_000_000)
}

// Slim score+band for many coordinates in one request — My Lakes list rings.
// Body: {"points":[{"lat":..,"lon":..}, …]}  →  {"results":[{lat,lon,score,band}, …]}
struct BatchRequest: Decodable { struct Point: Decodable { let lat: Double; let lon: Double }; let points: [Point] }
struct BatchResult: Encodable { let results: [BatchScore] }
router.post("conditions/batch") { request, _ -> Response in
    var body = try await request.body.collect(upTo: 64 * 1024)
    let data = body.readData(length: body.readableBytes) ?? Data()
    guard let req = try? JSONDecoder().decode(BatchRequest.self, from: data), !req.points.isEmpty,
          req.points.allSatisfy({ CoordinateRange.isValid(lat: $0.lat, lon: $0.lon) }) else {
        return Response(status: .badRequest)   // any out-of-range point rejects the whole batch
    }
    let points = req.points.prefix(50).map { (lat: $0.lat, lon: $0.lon) }   // cap the list
    let started = ContinuousClock.now
    let scores = await SectorEngineAPI.batch(points: Array(points))
    // [conditions-request] with `batch: n` (spec §6 rule 5): which app builds still use the batch endpoint.
    print(ConditionsRequestLog.batchLine(client: clientIdentity(request), points: points.count, ms: elapsedMs(since: started)))
    return jsonResponse(BatchResult(results: scores))
}

// The lake directory — the one list every app's lake search, My Lakes picker
// and dam routing read (see LakeDirectoryAPI). ETagged: an app that already
// holds this version gets a 304 and keeps its cached copy.
router.get("lakes") { request, _ -> Response in
    let directory = SectorEngineAPI.lakeDirectory
    let etag = "\"\(directory.response.version)\""
    var headers: HTTPFields = [.eTag: etag, .cacheControl: "public, max-age=3600"]
    if request.headers[.ifNoneMatch] == etag {
        return Response(status: .notModified, headers: headers)
    }
    headers[.contentType] = "application/json"
    var buffer = ByteBuffer()
    buffer.writeBytes(directory.body)
    return Response(status: .ok, headers: headers, body: .init(byteBuffer: buffer))
}

// A lake's hydrologic arm graph and its live inputs, with provenance
// (HydrologyAPI). Exposure only: nothing scores from these yet.
router.get("hydrology/graph") { request, _ -> Response in
    guard let lake = request.uri.queryParameters.get("lake").map({ String($0) }),
          let graph = SectorEngineAPI.hydrologyGraph(lakeId: lake) else {
        return Response(status: .notFound)
    }
    return jsonResponse(graph)
}
router.get("hydrology") { request, _ -> Response in
    guard let lake = request.uri.queryParameters.get("lake").map({ String($0) }),
          let inputs = await SectorEngineAPI.hydrology(lakeId: lake) else {
        return Response(status: .notFound)
    }
    return jsonResponse(inputs)
}

// Lake Brain's level and trend for one lake (LakeLevelOutputAPI, Sector_Ops #43, #44).
// Routed only where SECTOR_LAKE_LEVEL_OUTPUT=1, so a deploy with the flag off
// exposes no new endpoint. Even then it fails closed: UNKNOWN unless the lake is
// on the validated list and the Publisher's CUSTOMER-lane copy can be read. This
// server has no reader yet (granting it one is a separate, approved IAM change),
// so every lake answers UNKNOWN.
let lakeLevelEligibility = LakeLevelEligibility.fromEnvironment()
if lakeLevelEligibility.enabled {
    router.get("lake/level") { request, _ -> Response in
        guard let lake = request.uri.queryParameters.get("lake").map({ String($0) }), !lake.isEmpty else {
            return Response(status: .badRequest)
        }
        return jsonResponse(await LakeLevelOutputAPI.output(lakeId: lake, eligibility: lakeLevelEligibility, reader: nil))
    }
}

// The lakes with real Brain data, for the app's lake picker (LakesReadyAPI, Sector_Engine #156, #158).
// Routed only where SECTOR_LAKES_READY_OUTPUT=1, so a deploy with the flag off
// exposes no new endpoint (404, as /lake/level). Even then it fails closed: it
// reads only the Publisher's CUSTOMER-lane copies through the configured reader
// (SECTOR_BRAIN_OUTPUT_READER; none by default), and with no reader or no fresh
// copy it answers 200 with an empty list.
let lakesReadyConfig = LakesReadyConfig.fromEnvironment()
if lakesReadyConfig.enabled {
    // The whole customer/lakes subtree in one read: a longer bound than one small copy's.
    let cache = BrainOutputReaderConfig.reader(timeoutSeconds: 5).map { LakesReadySnapshotCache(reader: $0, ttl: 60) }
    // Each lake's bbox from the public Lake Registry index (#158): lake geometry identity, not a Brain output; no credential.
    let extents = LakeRegistryExtents.indexURL().map { LakeRegistryExtentCache(url: $0) }
    router.get("lakes/ready") { _, _ -> Response in
        guard let body = await LakesReadyAPI.response(config: lakesReadyConfig, cache: cache, extents: extents,
                                                      levelEligibility: lakeLevelEligibility) else {
            return Response(status: .notFound)
        }
        return jsonResponse(body)
    }
}

// Each arm's current clarity state (ClarityStateAPI, Clarity Fusion Stage 2).
// A review build: routed only where SECTOR_STAGE2_ROUTES=1, so a deploy of
// this branch does not publish it before it is reviewed.
if ProcessInfo.processInfo.environment["SECTOR_STAGE2_ROUTES"] == "1" {
    router.get("clarity/state") { request, _ -> Response in
        let q = request.uri.queryParameters
        guard let lake = q.get("lake").map({ String($0) }),
              let lat = q.get("lat").flatMap({ Double(String($0)) }),
              let lon = q.get("lon").flatMap({ Double(String($0)) }),
              let state = await SectorEngineAPI.currentClarityState(lakeId: lake, lat: lat, lon: lon) else {
            return Response(status: .notFound)
        }
        return jsonResponse(state)
    }
    router.get("clarity/states") { request, _ -> Response in
        guard let lake = request.uri.queryParameters.get("lake").map({ String($0) }),
              let states = await SectorEngineAPI.clarityStates(lakeId: lake) else {
            return Response(status: .notFound)
        }
        return jsonResponse(states)
    }
}

// The Current Clarity Engine (CurrentClarityAPI, Clarity Fusion Stage 4): one
// estimate per coordinate, the map's composite and summary, and a region's
// change since a moment. A review build, routed only where
// SECTOR_CURRENT_CLARITY_ROUTES=1; nothing scores from it.
if ProcessInfo.processInfo.environment["SECTOR_CURRENT_CLARITY_ROUTES"] == "1" {
    router.get("clarity/current") { request, _ -> Response in
        let q = request.uri.queryParameters
        guard let lake = q.get("lake").map({ String($0) }),
              let lat = q.get("lat").flatMap({ Double(String($0)) }),
              let lon = q.get("lon").flatMap({ Double(String($0)) }),
              let e = await SectorEngineAPI.currentClarity(lakeId: lake, lat: lat, lon: lon,
                                                           withLegacy: q.get("legacy") == "1") else {
            return Response(status: .notFound)
        }
        return jsonResponse(e)
    }
    router.get("clarity/current/lake") { request, _ -> Response in
        guard let lake = request.uri.queryParameters.get("lake").map({ String($0) }),
              let w = await SectorEngineAPI.currentClarityWorld(lakeId: lake) else {
            return Response(status: .notFound)
        }
        let path = "/clarity/current/cells?lake=\(lake.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? lake)"
        return jsonResponse(w.lakeSummary(path: path))
    }
    router.get("clarity/current/cells") { request, _ -> Response in
        guard let lake = request.uri.queryParameters.get("lake").map({ String($0) }),
              let w = await SectorEngineAPI.currentClarityWorld(lakeId: lake) else {
            return Response(status: .notFound)
        }
        // The job's own gzip where the client takes it (2.9 MB → ~0.26 MB,
        // Stage 5); each form has its own ETag, as HTTP requires.
        let gzip = w.compositeGzip.flatMap { gz in
            (request.headers[.acceptEncoding] ?? "").lowercased().contains("gzip") ? gz : nil
        }
        let etag = gzip == nil ? "\"\(w.etag)\"" : "\"\(w.etag)-gz\""
        var headers: HTTPFields = [.eTag: etag, .cacheControl: "public, max-age=600", .vary: "Accept-Encoding"]
        if request.headers[.ifNoneMatch] == etag { return Response(status: .notModified, headers: headers) }
        headers[.contentType] = "application/octet-stream"
        if gzip != nil { headers[.contentEncoding] = "gzip" }
        var buffer = ByteBuffer()
        buffer.writeBytes(gzip ?? w.compositeBytes ?? w.composite.encoded())
        return Response(status: .ok, headers: headers, body: .init(byteBuffer: buffer))
    }
    router.get("clarity/current/change") { request, _ -> Response in
        let q = request.uri.queryParameters
        let iso = ISO8601DateFormatter()
        guard let lake = q.get("lake").map({ String($0) }), let region = q.get("region").map({ String($0) }),
              let since = q.get("since").flatMap({ iso.date(from: String($0)) }),
              let c = await SectorEngineAPI.clarityChange(lakeId: lake, region: region, since: since) else {
            return Response(status: .notFound)
        }
        return jsonResponse(c)
    }
}

// Cloud Run injects PORT and expects the server to bind 0.0.0.0 (all interfaces).
// Locally, without PORT set, that's still reachable as localhost:8080 for the A/B.
let port = ProcessInfo.processInfo.environment["PORT"].flatMap(Int.init) ?? 8080
let app = Application(
    router: router,
    configuration: .init(address: .hostname("0.0.0.0", port: port)))

try await app.runService()
