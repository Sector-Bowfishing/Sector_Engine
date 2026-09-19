//
//  LakeEnvironmentAPI.swift
//  SectorEngine
//
//  `GET /lake/environment` — the lake's environmental state, with no score
//  anywhere in it.
//
//  The spatial engine must not reverse-engineer conditions out of a scored
//  `/conditions` response: that couples it to scoring semantics, costs a 7-night
//  forecast fetch it has no use for, and still omits the resolved values the
//  factor scorers actually consumed. This returns those values directly, with
//  their provenance, once per lake per TTL.
//
//  `/conditions` is untouched and keeps its exact contract.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

public struct LakeEnvironmentResponse: Codable, Equatable {
    public let lakeId: String?
    public let lakeName: String?
    public let cacheKey: String
    public let fetchedAt: Date
    public let ttlSeconds: Int
    public let samples: [SampleDTO]

    public struct SampleDTO: Codable, Equatable {
        public let latitude: Double
        public let longitude: Double
        /// The normalized input the scorers consume — post-staleness,
        /// post-distance, post-fallback. Not the raw provider readings.
        public let input: ConditionsInput
        public let provenance: [ProvenanceDTO]
    }

    /// Provenance flattened for the wire. The enums carry associated values, so
    /// they become a small tagged shape rather than a bare string.
    public struct ProvenanceDTO: Codable, Equatable {
        public let variable: String
        public let origin: String          // measured | modelled | derived | userReported | unavailable
        public let detail: String?         // site code, model name, or reason
        public let observedAt: Date?
        public let ingestedAt: Date
        public let coverage: String        // point | lakeWide | watershed | grid | unknown
        public let coverageScaleMiles: Double?
        public let quality: Double
    }
}

public extension SectorEngineAPI {

    /// The lake's environmental state at `lat`/`lon`, plus any extra sample
    /// points a long reservoir needs. One acquisition per lake per TTL.
    static func environment(lat: Double, lon: Double,
                            lakeId: String? = nil,
                            samplePoints: [(latitude: Double, longitude: Double)] = [],
                            force: Bool = false) async -> LakeEnvironmentResponse? {
        guard let snap = await LakeEnvironmentProvider.shared.snapshot(
            latitude: lat, longitude: lon, lakeId: lakeId,
            samplePoints: samplePoints, force: force)
        else { return nil }

        return LakeEnvironmentResponse(
            lakeId: snap.lakeId, lakeName: snap.lakeName, cacheKey: snap.cacheKey,
            fetchedAt: snap.fetchedAt, ttlSeconds: Int(snap.ttl),
            samples: snap.samples.map { s in
                .init(latitude: s.latitude, longitude: s.longitude, input: s.input,
                      provenance: s.provenance.entries.values
                        .sorted { $0.variable < $1.variable }
                        .map(Self.provenanceDTO))
            })
    }

    private static func provenanceDTO(_ e: EnvironmentProvenance.Entry)
        -> LakeEnvironmentResponse.ProvenanceDTO {
        let origin: String, detail: String?
        switch e.origin {
        case .measured(let site):   origin = "measured";     detail = site
        case .modelled(let model):  origin = "modelled";     detail = model
        case .derived(let how):     origin = "derived";      detail = how
        case .userReported:         origin = "userReported"; detail = nil
        case .unavailable(let why):
            origin = "unavailable"
            switch why {
            case .noSourceExists:    detail = "noSourceExists"
            case .fetchFailed:       detail = "fetchFailed"
            case .tooOld(let h):     detail = String(format: "tooOld:%.1fh", h)
            case .tooFar(let m):     detail = String(format: "tooFar:%.1fmi", m)
            case .notApplicableHere: detail = "notApplicableHere"
            }
        }
        let coverage: String, scale: Double?
        switch e.coverage {
        case .point(_, _, let miles):   coverage = "point";     scale = miles
        case .lakeWide:                 coverage = "lakeWide";  scale = nil
        case .watershed(let miles):     coverage = "watershed"; scale = miles
        case .grid(let km):             coverage = "grid";      scale = km * 0.621371
        case .unknown:                  coverage = "unknown";   scale = nil
        }
        return .init(variable: e.variable, origin: origin, detail: detail,
                     observedAt: e.observedAt, ingestedAt: e.ingestedAt,
                     coverage: coverage, coverageScaleMiles: scale, quality: e.quality)
    }
}
