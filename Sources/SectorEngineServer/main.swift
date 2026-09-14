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

let router = Router()

router.get("health") { _, _ in "ok" }

func jsonResponse<T: Encodable>(_ value: T) -> Response {
    let encoder = JSONEncoder()
    encoder.dateEncodingStrategy = .iso8601
    encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
    let data = (try? encoder.encode(value)) ?? Data()
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
          let lon = request.uri.queryParameters.get("lon").flatMap({ Double(String($0)) }) else {
        return Response(status: .badRequest)
    }
    let fresh = request.uri.queryParameters.get("fresh").map { $0 == "1" || $0 == "true" } ?? false
    guard let payload = await ConditionsResponseCache.shared.conditions(
        lat: lat, lon: lon, fresh: fresh,
        compute: { await SectorEngineAPI.conditions(lat: lat, lon: lon) }
    ) else {
        return Response(status: .serviceUnavailable)   // no live data to score
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
        return Response(status: .badRequest)
    }
    let points = req.points.prefix(50).map { (lat: $0.lat, lon: $0.lon) }   // cap the list
    let scores = await SectorEngineAPI.batch(points: Array(points))
    return jsonResponse(BatchResult(results: scores))
}

// Cloud Run injects PORT and expects the server to bind 0.0.0.0 (all interfaces).
// Locally, without PORT set, that's still reachable as localhost:8080 for the A/B.
let port = ProcessInfo.processInfo.environment["PORT"].flatMap(Int.init) ?? 8080
let app = Application(
    router: router,
    configuration: .init(address: .hostname("0.0.0.0", port: port)))

try await app.runService()
