//
//  LakeDirectoryAPI.swift
//  Sector — the lake directory, served to the apps
//
//  THE LAKE LIST LIVES HERE (Michael, 2026-09-26: "wouldn't it be beneficial to
//  have all the lakes in the engine vs on the phone?"). The iOS app, the
//  Android app and the engine each carried their own copy of the 621-lake
//  directory, kept in step by hand, and they had already drifted: Android's
//  "Nickajack" is the engine's "Nickajack Lake". Now the engine serves the one
//  list at `GET /lakes`; a lake added or corrected here reaches every phone on
//  its next launch, with no App Store or Play release. The copies the apps
//  bundle are a snapshot of this response, for a first launch with no network.
//

import Foundation

/// One lake as `GET /lakes` serves it. The field names are the ones the apps
/// already read — Android's bundled `lake_directory.json` has exactly these.
public struct LakeDTO: Codable, Equatable {
    public let id: String            // "Name|ST", as `DirectoryLake.id`
    public let name: String
    public let state: String         // primary state
    public let states: [String]      // every state the water touches, primary first
    public let lat: Double
    public let lon: Double
    public let hasDam: Bool
    public let operatorName: String
    public let apiLevel: String      // dedicated | usgsOnly | none
    public let usgsGage: String      // yes | likely | no
    public let tempSource: String    // buoy | inSitu | satellite | limited
    public let cwmsOffice: String?
    /// Normal full pool, ft above sea level (see `DirectoryLake.fullPoolFt`).
    public let fullPoolFt: Double?
    public let poolBasis: String?      // fullPool | naturalSurface
    public let poolConfidence: String? // high | med | low

    private enum CodingKeys: String, CodingKey {
        case id, name, state, states, lat, lon, hasDam, operatorName, apiLevel
        case usgsGage, tempSource, cwmsOffice, fullPoolFt, poolBasis, poolConfidence
    }

    /// Written out even when nil: a reader that looks the key up should find
    /// an explicit null, not wonder whether the field exists.
    public func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(id, forKey: .id)
        try c.encode(name, forKey: .name)
        try c.encode(state, forKey: .state)
        try c.encode(states, forKey: .states)
        try c.encode(lat, forKey: .lat)
        try c.encode(lon, forKey: .lon)
        try c.encode(hasDam, forKey: .hasDam)
        try c.encode(operatorName, forKey: .operatorName)
        try c.encode(apiLevel, forKey: .apiLevel)
        try c.encode(usgsGage, forKey: .usgsGage)
        try c.encode(tempSource, forKey: .tempSource)
        try c.encode(cwmsOffice, forKey: .cwmsOffice)
        try c.encode(fullPoolFt, forKey: .fullPoolFt)
        try c.encode(poolBasis, forKey: .poolBasis)
        try c.encode(poolConfidence, forKey: .poolConfidence)
    }
}

public struct LakeDirectoryResponse: Codable, Equatable {
    /// A digest of the lakes — the response's ETag. It changes exactly when a
    /// lake does, so an app that has this version already gets a 304.
    public let version: String
    public let count: Int
    public let lakes: [LakeDTO]
}

extension SectorEngineAPI {

    /// The directory and its encoded body, built once: the list only changes
    /// with a deploy.
    public static let lakeDirectory: (response: LakeDirectoryResponse, body: Data) = {
        let lakes = LakeDirectory.all.map {
            LakeDTO(id: $0.id, name: $0.name, state: $0.state, states: $0.states,
                    lat: $0.lat, lon: $0.lon, hasDam: $0.hasDam,
                    operatorName: $0.operatorName, apiLevel: $0.apiLevel.rawValue,
                    usgsGage: $0.usgsGage.rawValue, tempSource: $0.tempSource.rawValue,
                    cwmsOffice: $0.cwmsOffice, fullPoolFt: $0.fullPoolFt,
                    poolBasis: $0.poolBasis?.rawValue, poolConfidence: $0.poolConfidence?.rawValue)
        }
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        let lakeBytes = (try? encoder.encode(lakes)) ?? Data()
        let response = LakeDirectoryResponse(version: fnv1a64Hex(lakeBytes),
                                             count: lakes.count, lakes: lakes)
        return (response, (try? encoder.encode(response)) ?? Data())
    }()

    /// FNV-1a, 64-bit, as hex. A version stamp, not a security digest — and the
    /// same on Linux and macOS, which CryptoKit is not.
    static func fnv1a64Hex(_ data: Data) -> String {
        var h: UInt64 = 0xcbf2_9ce4_8422_2325
        for byte in data {
            h ^= UInt64(byte)
            h = h &* 0x0000_0100_0000_01b3
        }
        let hex = String(h, radix: 16)
        return String(repeating: "0", count: 16 - hex.count) + hex
    }
}
