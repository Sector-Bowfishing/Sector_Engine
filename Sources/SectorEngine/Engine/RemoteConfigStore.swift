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
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

actor RemoteConfigStore {
    static let shared = RemoteConfigStore()

    private var cached: ConditionsConfig = .default
    private var fetchedAt: Date?
    private let ttl: TimeInterval = 10 * 60
    private var inFlight: Task<ConditionsConfig, Never>?

    /// Firebase project id (same as the GCP project). Overridable via env for staging.
    private let projectId = ProcessInfo.processInfo.environment["GCP_PROJECT"] ?? "sector-9393c"

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
        guard let token = await accessToken(),
              let url = URL(string: "https://firebaseremoteconfig.googleapis.com/v1/projects/\(projectId)/remoteConfig")
        else { return nil }
        var req = URLRequest(url: url, timeoutInterval: 10)
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        do {
            let (data, resp) = try await Net.session.data(for: req)
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else { return nil }
            // template → parameters → conditions_config → defaultValue → value (a JSON string)
            guard let root = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let params = root["parameters"] as? [String: Any],
                  let param = params["conditions_config"] as? [String: Any],
                  let defaultValue = param["defaultValue"] as? [String: Any],
                  let value = defaultValue["value"] as? String,
                  let valueData = value.data(using: .utf8) else { return nil }
            return try JSONDecoder().decode(ConditionsConfigOverrides.self, from: valueData)
        } catch {
            return nil
        }
    }

    /// OAuth access token for the Cloud Run service account, from the metadata server.
    /// Returns nil off Cloud Run (local dev), so `current()` just serves defaults.
    private func accessToken() async -> String? {
        guard let url = URL(string: "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token")
        else { return nil }
        var req = URLRequest(url: url, timeoutInterval: 5)
        req.setValue("Google", forHTTPHeaderField: "Metadata-Flavor")
        do {
            let (data, resp) = try await Net.session.data(for: req)
            guard let http = resp as? HTTPURLResponse, http.statusCode == 200,
                  let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let token = obj["access_token"] as? String else { return nil }
            return token
        } catch {
            return nil
        }
    }
}
