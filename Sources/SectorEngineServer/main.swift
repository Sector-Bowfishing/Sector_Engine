//
//  SectorEngineServer
//
//  Thin HTTP wrapper around SectorEngineAPI. GET /conditions?lat=&lon= → JSON.
//  This is what Cloud Run will run; for Phase 0 it runs on localhost so iOS can
//  A/B its numbers against the app's local engine.
//

import Foundation
#if canImport(Glibc)
import Glibc
#elseif canImport(Darwin)
import Darwin
#endif
import Hummingbird
import SectorEngine

// Line-buffer stdout FIRST. Cloud Run captures stdout as logs, and by default a
// non-terminal stdout is block-buffered: engine log lines arrived minutes late
// and were lost when an instance crashed or froze — the moments they explain.
setvbuf(stdout, nil, _IOLBF, 0)

let router = Router()

router.get("health") { _, _ in "ok" }

let jsonEncoder: JSONEncoder = {
    let encoder = JSONEncoder()
    encoder.dateEncodingStrategy = .iso8601
    encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
    return encoder
}()

func jsonResponse<T: Encodable>(_ value: T, status: HTTPResponse.Status = .ok,
                                headers: HTTPFields = [:]) -> Response {
    // An encode failure (e.g. a NaN from an upstream feed) used to become a 200
    // with an empty body: invisible to 5xx alerting, and Android cached the empty
    // body over the lake's last good response. Now it's a logged 500.
    guard let data = try? jsonEncoder.encode(value) else {
        print(#"{"severity":"ERROR","message":"response encode failed","component":"server"}"#)
        return Response(status: .internalServerError)
    }
    var buffer = ByteBuffer()
    buffer.writeBytes(data)
    var fields = headers
    fields[.contentType] = "application/json"
    return Response(status: status, headers: fields, body: .init(byteBuffer: buffer))
}

struct ErrorBody: Encodable { let reason: String }

/// A coordinate we can actually score: finite and on the globe. Garbage used to
/// fall through to a 503, which read as "upstream down" and hid real outages in
/// the 5xx rate.
func validCoordinate(_ lat: Double?, _ lon: Double?) -> (Double, Double)? {
    guard let lat, let lon, lat.isFinite, lon.isFinite,
          (-90...90).contains(lat), (-180...180).contains(lon) else { return nil }
    return (lat, lon)
}

// Full render payload for one coordinate. Fronted by a short-TTL, single-flight
// response cache (see ConditionsResponseCache): the My Lakes preload hits this
// once per saved lake every launch. `?fresh=1` bypasses the cache read for
// pull-to-refresh.
router.get("conditions") { request, _ -> Response in
    let q = request.uri.queryParameters
    guard let (lat, lon) = validCoordinate(q.get("lat").flatMap { Double(String($0)) },
                                           q.get("lon").flatMap { Double(String($0)) }) else {
        return jsonResponse(ErrorBody(reason: "invalid_coordinate"), status: .badRequest)
    }
    let fresh = q.get("fresh").map { $0 == "1" || $0 == "true" } ?? false
    guard let payload = await ConditionsResponseCache.shared.conditions(
        lat: lat, lon: lon, fresh: fresh,
        compute: { await SectorEngineAPI.conditions(lat: lat, lon: lon, fresh: fresh) }
    ) else {
        // No weather → no honest score. Clients already fall back to their last
        // good response on any non-200; the body and Retry-After say why and when.
        return jsonResponse(ErrorBody(reason: "weather_unavailable"),
                            status: .serviceUnavailable, headers: [.retryAfter: "60"])
    }
    return jsonResponse(payload)
}

// Slim score+band for many coordinates in one request — My Lakes list rings.
// Body: {"points":[{"lat":..,"lon":..}, …]}  →  {"results":[{lat,lon,score,band}, …]}
struct BatchRequest: Decodable { struct Point: Decodable { let lat: Double; let lon: Double }; let points: [Point] }
struct BatchResult: Encodable { let results: [BatchScore] }
router.post("conditions/batch") { request, _ -> Response in
    var body = try await request.body.collect(upTo: 64 * 1024)
    let data = body.readData(length: body.readableBytes) ?? Data()
    guard let req = try? JSONDecoder().decode(BatchRequest.self, from: data), !req.points.isEmpty else {
        return jsonResponse(ErrorBody(reason: "invalid_body"), status: .badRequest)
    }
    // Validate, dedupe to the ~100 m cache key, and cap — each point fans out a
    // full snapshot, so an unbounded list could hold an instance for minutes.
    var seen = Set<String>()
    var points: [(lat: Double, lon: Double)] = []
    for p in req.points {
        guard let (lat, lon) = validCoordinate(p.lat, p.lon) else { continue }
        guard seen.insert(String(format: "%.3f,%.3f", lat, lon)).inserted else { continue }
        points.append((lat, lon))
        if points.count == SectorEngineAPI.batchMaxPoints { break }
    }
    guard !points.isEmpty else {
        return jsonResponse(ErrorBody(reason: "invalid_coordinate"), status: .badRequest)
    }
    let scores = await SectorEngineAPI.batch(points: points)
    return jsonResponse(BatchResult(results: scores))
}

// Cloud Run injects PORT and expects the server to bind 0.0.0.0 (all interfaces).
// Locally, without PORT set, that's still reachable as localhost:8080 for the A/B.
let port = ProcessInfo.processInfo.environment["PORT"].flatMap(Int.init) ?? 8080
let app = Application(
    router: router,
    configuration: .init(address: .hostname("0.0.0.0", port: port)))

try await app.runService()
