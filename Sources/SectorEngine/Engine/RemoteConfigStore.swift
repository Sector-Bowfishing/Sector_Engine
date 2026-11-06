//
//  RemoteConfigStore.swift
//  SectorEngine
//
//  Phase 6 Stage 4: drive the engine's tuning from Firebase Remote Config, so
//  scoring can change WITHOUT a redeploy. Reads the `conditions_config` parameter
//  (a JSON ConditionsConfigOverrides blob), applies it onto ConditionsConfig.default,
//  and caches the result for a short TTL. Both the gauge and the forecast ask this
//  store for the current config.
//
//  There is no Firebase Admin SDK for Swift, so this uses the Remote Config REST
//  API, authenticated by the Cloud Run service account via the GCP metadata server.
//  Every failure path falls back to the last good config (or the compiled default),
//  so a Remote Config outage — or running locally, off Cloud Run — is harmless.
//

import Foundation

actor RemoteConfigStore {
    static let shared = RemoteConfigStore()

    private var cached: ConditionsConfig = .default
    private var fetchedAt: Date?
    private let ttl: TimeInterval = 10 * 60
    private var inFlight: Task<ConditionsConfig, Never>?


    /// The current tuned config. Never blocks the conditions request on Firebase
    /// once we've fetched at least once.
    ///
    /// Within the TTL: served straight from cache. Stale, but we have a prior
    /// value: that value is returned NOW and a refresh runs in the background —
    /// Remote Config must not sit on the request's latency path, because a slow
    /// metadata/Firebase round trip (token 5s + config 10s) would delay a score
    /// we can already compute from the last good tuning. First read of the
    /// process (only the compiled default in hand): we wait for the initial
    /// fetch, but BOUNDED — if Firebase is slow we serve the default and let the
    /// refresh finish in the background rather than block the first user after a
    /// cold start. Never throws.
    func current() async -> ConditionsConfig {
        if let at = fetchedAt, Date().timeIntervalSince(at) < ttl { return cached }

        // Launch, or join, the single in-flight refresh.
        let task = inFlight ?? {
            let t = Task { await fetchAndApply() }
            inFlight = t
            return t
        }()

        // Already have a last-good config: serve it, let the refresh update the
        // cache for next time.
        if fetchedAt != nil { return cached }

        // First-ever read: wait for the initial fetch, capped so a slow Firebase
        // can't hang the cold-start request — fall back to the compiled default.
        let fetched = await withDeadline(3, "remoteConfig", slowThreshold: 2) {
            () -> ConditionsConfig? in await task.value
        }
        return fetched ?? cached
    }

    private func fetchAndApply() async -> ConditionsConfig {
        // Mark the attempt time either way so a persistent failure backs off to the
        // TTL instead of hammering the metadata server on every request, and clear
        // the in-flight slot so the NEXT stale read starts a fresh refresh.
        defer { fetchedAt = Date(); inFlight = nil }
        guard let overrides = await fetchOverrides() else { return cached }
        cached = overrides.apply(to: .default)
        return cached
    }

    private func fetchOverrides() async -> ConditionsConfigOverrides? {
        // template → parameters → conditions_config → defaultValue → value (a JSON string)
        guard case .value(let value) = await RemoteConfigREST.parameter("conditions_config"),
              let valueData = value.data(using: .utf8) else { return nil }
        return try? JSONDecoder().decode(ConditionsConfigOverrides.self, from: valueData)
    }
}

/// One Remote Config parameter as read from the template: its default value, absent from the template, or unreadable.
public enum RemoteConfigParameter: Equatable, Sendable {
    case value(String)
    /// The template was read and has no such parameter (or it has no default string value).
    case absent
    /// No token (off Cloud Run), an HTTP error, or a template that is not JSON.
    case unreadable
}

/// The Remote Config REST read shared by `RemoteConfigStore` (`conditions_config`) and `TileFlagsStore`
/// (`conditions_tiles_v1`). There is no Firebase Admin SDK for Swift: this reads the template over REST, authenticated by
/// the Cloud Run service account via the GCP metadata server. Read-only. Both parameters come from ONE template read:
/// `RemoteConfigTemplateCache` makes one token fetch and one template fetch per TTL, shared by both stores.
enum RemoteConfigREST {
    /// Firebase project id (same as the GCP project). Overridable via env for staging.
    static var defaultProjectId: String { ProcessInfo.processInfo.environment["GCP_PROJECT"] ?? "sector-9393c" }

    static func parameter(_ name: String, cache: RemoteConfigTemplateCache = .shared) async -> RemoteConfigParameter {
        guard let defaults = await cache.defaults() else { return .unreadable }
        guard let value = defaults[name] else { return .absent }
        return .value(value)
    }

    /// One template fetch: every parameter's default string value, or nil when unreadable.
    static func fetchDefaults(projectId: String = defaultProjectId) async -> [String: String]? {
        guard let token = await accessToken(),
              let url = URL(string: "https://firebaseremoteconfig.googleapis.com/v1/projects/\(projectId)/remoteConfig")
        else { return nil }
        do {
            let result = try await HTTP.get(url, headers: ["Authorization": "Bearer \(token)"])
            guard result.status == 200,
                  let root = try JSONSerialization.jsonObject(with: result.body) as? [String: Any] else { return nil }
            return defaults(inTemplate: root)
        } catch {
            return nil
        }
    }

    /// Pure: template → parameters → name → defaultValue → value, for every parameter that has a string default.
    static func defaults(inTemplate root: [String: Any]) -> [String: String] {
        guard let params = root["parameters"] as? [String: Any] else { return [:] }
        var out: [String: String] = [:]
        for (name, raw) in params {
            if let param = raw as? [String: Any], let dv = param["defaultValue"] as? [String: Any],
               let value = dv["value"] as? String { out[name] = value }
        }
        return out
    }

    /// Pure: one parameter from a template.
    static func parameter(_ name: String, inTemplate root: [String: Any]) -> RemoteConfigParameter {
        defaults(inTemplate: root)[name].map(RemoteConfigParameter.value) ?? .absent
    }

    /// OAuth access token for the Cloud Run service account, from the metadata server.
    /// Returns nil off Cloud Run (local dev), so callers just serve their defaults.
    static func accessToken() async -> String? {
        guard let url = URL(string: "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token")
        else { return nil }
        do {
            let result = try await HTTP.get(url, headers: ["Metadata-Flavor": "Google"], timeout: 5)
            guard result.status == 200,
                  let obj = try JSONSerialization.jsonObject(with: result.body) as? [String: Any],
                  let token = obj["access_token"] as? String else { return nil }
            return token
        } catch {
            return nil
        }
    }
}

/// One Remote Config template read per TTL for the whole process (single-flight). The result of the last attempt,
/// readable or not, is reused within the TTL; each store keeps its own last-good value when it is unreadable.
actor RemoteConfigTemplateCache {
    static let shared = RemoteConfigTemplateCache()

    private let ttl: TimeInterval
    private let now: @Sendable () -> Date
    private let fetch: @Sendable () async -> [String: String]?
    private var last: (at: Date, defaults: [String: String]?)?
    private var inFlight: Task<[String: String]?, Never>?

    init(ttl: TimeInterval = 10 * 60, now: @escaping @Sendable () -> Date = { Date() },
         fetch: @escaping @Sendable () async -> [String: String]? = { await RemoteConfigREST.fetchDefaults() }) {
        self.ttl = ttl
        self.now = now
        self.fetch = fetch
    }

    func defaults() async -> [String: String]? {
        if let last, now().timeIntervalSince(last.at) < ttl { return last.defaults }
        if let inFlight { return await inFlight.value }
        let task = Task { await fetch() }
        inFlight = task
        let value = await task.value
        last = (now(), value)
        inFlight = nil
        return value
    }
}
