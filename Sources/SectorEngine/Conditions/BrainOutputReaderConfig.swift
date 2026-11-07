//
//  BrainOutputReaderConfig.swift
//  SectorEngine
//
//  Which `BrainOutputReader` `/conditions` reads the Publisher's CUSTOMER-lane copies through (Sector_Ops #53, spec §5).
//
//  Configured by the env `SECTOR_BRAIN_OUTPUT_READER`:
//    unset, or any other value   no reader. Every Brain copy is UNKNOWN (reason NO_READER), which means today's path for
//                                every Brain-backed tile, whatever its flag says. This is the default and what production runs.
//    `rtdb`                      `RTDBCustomerCopyReader`: GET-only reads of `customer/...` in the sector-brain database,
//                                authenticated as the service's own identity (the GCP metadata server). Without a read grant
//                                for that identity every read fails, which is again UNKNOWN. Setting the env and granting the
//                                read are both the owner's steps; nothing here sets or grants either.
//
//  The reader can read ONLY the customer lane: a path outside `customer/` is refused without a request.
//

import Foundation

public enum BrainOutputReaderConfig {
    public static let envKey = "SECTOR_BRAIN_OUTPUT_READER"
    public static let rtdbValue = "rtdb"

    /// The configured reader, or nil (the default).
    public static func reader(from env: [String: String] = ProcessInfo.processInfo.environment) -> BrainOutputReader? {
        guard env[envKey] == rtdbValue else { return nil }
        return RTDBCustomerCopyReader()
    }
}

/// Read-only REST reader for the Publisher's CUSTOMER-lane copies. `get` only; never writes.
public struct RTDBCustomerCopyReader: BrainOutputReader {
    /// GET returning (status, body), or nil on a transport error. Injectable for tests.
    public typealias Fetch = @Sendable (URL, [String: String]) async -> (status: Int, body: Data)?
    /// Returns an OAuth access token, or nil. Injectable for tests.
    public typealias Token = @Sendable () async -> String?

    /// Every path this reader may read starts with this.
    public static let lanePrefix = "customer/"
    /// Per read. The tile's own new-path deadline (3 s) bounds the whole step as well.
    public static let timeoutSeconds: Double = 2

    let databaseURL: String
    let fetch: Fetch
    let token: Token

    public init(databaseURL: String = BrainPlatform.databaseURL,
                fetch: Fetch? = nil,
                token: Token? = nil) {
        self.databaseURL = databaseURL
        self.fetch = fetch ?? { url, headers in
            guard let r = try? await HTTP.get(url, headers: headers, timeout: RTDBCustomerCopyReader.timeoutSeconds) else {
                return nil
            }
            return (r.status, r.body)
        }
        self.token = token ?? { await RemoteConfigREST.accessToken() }
    }

    /// The copy's JSON, or nil when absent (`null`). Throws on a refused path, no token, or any non-200 answer, which the
    /// readers treat as NO_PUBLICATION (UNKNOWN).
    public func get(_ path: String) async throws -> Data? {
        guard Self.allowed(path), BrainPlatform.acceptedDatabaseURL(databaseURL),
              let url = URL(string: "\(databaseURL)/\(path).json") else {
            throw BrainStoreError("refusing to read \(path): only \(Self.lanePrefix) paths in the sector-brain database")
        }
        guard let token = await token() else { throw BrainStoreError("no access token") }
        guard let r = await fetch(url, ["Authorization": "Bearer \(token)"]) else { throw BrainStoreError("read failed") }
        guard r.status == 200 else { throw BrainStoreError("read refused", status: r.status) }
        if r.body.isEmpty || String(data: r.body, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) == "null" {
            return nil
        }
        return r.body
    }

    /// Only plain `customer/...` paths: no query, no traversal, no RTDB key-illegal characters.
    static func allowed(_ path: String) -> Bool {
        guard path.hasPrefix(lanePrefix), path.count > lanePrefix.count else { return false }
        let illegal = CharacterSet(charactersIn: ".#$[]?&=%\\ ")
        guard path.rangeOfCharacter(from: illegal) == nil else { return false }
        return !path.split(separator: "/", omittingEmptySubsequences: false).contains { $0.isEmpty }
    }
}
