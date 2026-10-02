//
//  CandidateShadow.swift
//  SectorEngine — the UNCERTIFIED Current Clarity candidate, read-only
//
//  The shadow job (jobs/clarity-candidate) runs the frozen Stage 16 candidate
//  and the frozen Stage 17 challenger on new Sentinel-2 passes over the pilot
//  lakes, and writes its JSON to a PRIVATE bucket. This serves that JSON back
//  unchanged, to master accounts only, on the 0%-traffic review tag.
//
//  Nothing scores from it, and production never reads it. The route exists
//  only where SECTOR_CLARITY_CANDIDATE_ROUTES=1.
//
//  ACCESS. Every request carries a Firebase ID token. Google's Identity Toolkit
//  checks it (signature, expiry, revocation), and its uid must be listed in
//  SECTOR_CANDIDATE_UIDS. SECTOR_FIREBASE_API_KEY is the project's key, which
//  identifies the project; it is not a secret. Verified tokens are cached
//  until they expire.
//

import Foundation

public enum CandidateShadow {
    public enum Access: Equatable { case granted(uid: String), unauthenticated, forbidden, unavailable }

    static var env: [String: String] { ProcessInfo.processInfo.environment }
    static var bucket: String { env["SECTOR_CANDIDATE_BUCKET"] ?? "sector-clarity-candidate" }
    static let prefix = "shadow/v1"
    static var allowedUIDs: Set<String> {
        Set((env["SECTOR_CANDIDATE_UIDS"] ?? "").split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty })
    }

    /// Who may read: a valid Firebase ID token whose uid is a listed master account.
    public static func authorize(bearer: String?) async -> Access {
        guard let token = bearer, !token.isEmpty else { return .unauthenticated }
        guard let key = env["SECTOR_FIREBASE_API_KEY"], !allowedUIDs.isEmpty else { return .unavailable }
        guard let uid = await CandidateStore.shared.verify(token: token, apiKey: key) else { return .unauthenticated }
        return allowedUIDs.contains(uid) ? .granted(uid: uid) : .forbidden
    }

    /// One pilot lake's latest shadow answers (the job's latest/<slug>.json, unchanged), by slug or directory id.
    public static func lake(_ idOrSlug: String) async -> Data? {
        let lakes = await CandidateStore.shared.lakes()
        guard let slug = lakes.first(where: { $0.slug == idOrSlug || $0.directoryId == idOrSlug })?.slug else { return nil }
        return await CandidateStore.shared.object("\(prefix)/latest/\(slug).json")
    }

    /// Every pilot lake with its newest summary.
    public static func index() async -> Data? {
        let lakes = await CandidateStore.shared.lakes()
        guard !lakes.isEmpty else { return nil }
        let head: [String: Any] = [
            "schema": "clarity-candidate-index/1",
            "label": "Uncertified candidate (shadow). Not a certified clarity reading.",
            "uncertified": true,
            "revision": env["K_REVISION"] ?? "local",
        ]
        guard var out = try? JSONSerialization.data(withJSONObject: head, options: [.sortedKeys]) else { return nil }
        out.removeLast()                                   // reopen the object: ..."uncertified":true,"lakes":[...]}
        out.append(Data(#","lakes":["#.utf8))
        out.append(Data(lakes.map { $0.entry }.joined(separator: Data(",".utf8))))
        out.append(Data("]}".utf8))
        return out
    }
}

struct CandidateLake: Sendable {
    let slug: String
    let directoryId: String
    /// {slug, directory_id, why, generated_utc, scenes, summary} as JSON, from the lake's latest file.
    let entry: Data
}

/// Bucket reads with the service account's token, a 10-minute object cache, and the verified-token cache.
actor CandidateStore {
    static let shared = CandidateStore()
    private var token: (value: String, expires: Date)?
    private var objects: [String: (data: Data, at: Date)] = [:]
    private var verified: [String: (uid: String, expires: Date)] = [:]
    private var lakeList: (lakes: [CandidateLake], at: Date)?
    private let ttl: TimeInterval = 600

    private func accessToken() async -> String? {
        if let t = token, t.expires > Date().addingTimeInterval(60) { return t.value }
        guard let url = URL(string: "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"),
              let r = try? await HTTP.get(url, headers: ["Metadata-Flavor": "Google"], timeout: 5), r.status == 200,
              let obj = try? JSONSerialization.jsonObject(with: r.body) as? [String: Any],
              let value = obj["access_token"] as? String else { return nil }
        let expiresIn = (obj["expires_in"] as? Double) ?? 300
        token = (value, Date().addingTimeInterval(expiresIn))
        return value
    }

    func object(_ key: String) async -> Data? {
        if let c = objects[key], Date().timeIntervalSince(c.at) < ttl { return c.data }
        let name = key.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? key
        guard let tok = await accessToken(),
              let url = URL(string: "https://storage.googleapis.com/storage/v1/b/\(CandidateShadow.bucket)/o/\(name)?alt=media"),
              let r = try? await HTTP.get(url, headers: ["Authorization": "Bearer \(tok)"]), r.isSuccess else { return nil }
        objects[key] = (r.body, Date())
        return r.body
    }

    private func list(_ prefix: String) async -> [String] {
        let p = prefix.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? prefix
        guard let tok = await accessToken(),
              let url = URL(string: "https://storage.googleapis.com/storage/v1/b/\(CandidateShadow.bucket)/o?prefix=\(p)&fields=items(name)"),
              let r = try? await HTTP.get(url, headers: ["Authorization": "Bearer \(tok)"]), r.isSuccess,
              let obj = try? JSONSerialization.jsonObject(with: r.body) as? [String: Any],
              let items = obj["items"] as? [[String: Any]] else { return [] }
        return items.compactMap { $0["name"] as? String }
    }

    func lakes() async -> [CandidateLake] {
        if let l = lakeList, Date().timeIntervalSince(l.at) < ttl { return l.lakes }
        var out: [CandidateLake] = []
        for name in await list("\(CandidateShadow.prefix)/latest/") where name.hasSuffix(".json") {
            guard let data = await object(name),
                  let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let slug = obj["lake"] as? String, let id = obj["directory_id"] as? String else { continue }
            var j: [String: Any] = ["slug": slug, "directory_id": id]
            for k in ["why", "generated_utc", "scenes", "summary"] { if let v = obj[k] { j[k] = v } }
            guard let entry = try? JSONSerialization.data(withJSONObject: j, options: [.sortedKeys]) else { continue }
            out.append(CandidateLake(slug: slug, directoryId: id, entry: entry))
        }
        let sorted = out.sorted { $0.slug < $1.slug }
        lakeList = (sorted, Date())
        return sorted
    }

    /// The token's uid when Google's Identity Toolkit accepts it; nil otherwise.
    func verify(token: String, apiKey: String) async -> String? {
        if let v = verified[token], v.expires > Date() { return v.uid }
        guard let url = URL(string: "https://identitytoolkit.googleapis.com/v1/accounts:lookup?key=\(apiKey)"),
              let body = try? JSONSerialization.data(withJSONObject: ["idToken": token]),
              let r = try? await HTTP.post(url, json: body), r.status == 200,
              let obj = try? JSONSerialization.jsonObject(with: r.body) as? [String: Any],
              let users = obj["users"] as? [[String: Any]], let uid = users.first?["localId"] as? String else { return nil }
        if verified.count > 256 { verified = verified.filter { $0.value.expires > Date() } }
        verified[token] = (uid, Self.expiry(of: token) ?? Date().addingTimeInterval(300))
        return uid
    }

    /// The `exp` claim of a JWT (already verified by Google), capped at one hour.
    static func expiry(of jwt: String) -> Date? {
        let parts = jwt.split(separator: ".")
        guard parts.count == 3 else { return nil }
        var s = String(parts[1]).replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")
        while s.count % 4 != 0 { s += "=" }
        guard let d = Data(base64Encoded: s), let obj = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
              let exp = obj["exp"] as? Double else { return nil }
        return min(Date(timeIntervalSince1970: exp), Date().addingTimeInterval(3600))
    }
}
