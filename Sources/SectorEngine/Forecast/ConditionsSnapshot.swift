//
//  ConditionsSnapshot.swift
//  Sector
//
//  ONE fetch of the live inputs both conditions surfaces need.
//
//  The dashboard gauge (ShootingConditionsModel) and Tonight's window
//  (ConditionsForecastService) are independent singletons that each used to
//  pull the SAME five readings — Open-Meteo current conditions plus four USGS
//  gages — on every dashboard load. That cost twice the network for identical
//  data, and because the two races were independent, the window regularly
//  resolved before the score, announcing a prime time above a still-spinning
//  gauge.
//
//  This coalesces both callers onto a single in-flight fetch and caches the
//  result briefly, so they see the SAME snapshot and can't disagree.
//
//  Lives in SwiftData/Models/ so Xcode picks it up automatically — every other
//  folder needs a manual project.pbxproj entry.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

/// A fetch that can tell "the upstream failed" from "there's nothing here".
/// The USGS lookups throw on transport, HTTP and decode failures and return nil
/// only when no gage is within range; `try?` used to collapse both into nil, so a
/// failed USGS minute looked like a complete render and was cached for 5 minutes.
enum Probe<Value: Sendable>: Sendable {
    case found(Value?)
    case failed

    static func attempt(_ operation: () async throws -> Value?) async -> Probe {
        do { return .found(try await operation()) } catch { return .failed }
    }

    var value: Value? {
        if case let .found(v) = self { return v }
        return nil
    }

    var isFailure: Bool {
        if case .failed = self { return true }
        return false
    }
}

/// Generation for a point and whether some was expected there.
struct GenerationLookup: Sendable {
    let generation: DamGeneration?
    let expected: Bool
}

/// The live inputs a conditions evaluation is built from.
struct ConditionsSnapshot {
    let weather: WeatherReading?
    let water: WaterLevelReading?
    let discharge: WaterLevelReading?
    let waterTemp: WaterLevelReading?
    /// Modeled surface temp (air-temp thermal lag) — the always-available layer
    /// used when no gage is close, which is almost everywhere.
    let waterTempModel: WaterTempModel?
    let turbidity: WaterLevelReading?
    /// TVA's schedule + release for the nearest dam, when this is a TVA
    /// tailwater. nil everywhere else, and the USGS trend carries the current.
    let generation: DamGeneration?
    /// Active NWS alerts for the point — shown as pills AND (for severe-wind
    /// Warnings) fed into the score via `alertWindFloorMph`, so the pill and the
    /// number can never disagree. Fetched here in the SHARED snapshot so every
    /// surface (gauge, 7-night, lake alerts, trips) scores the same night the same.
    let alerts: [WeatherAlert]
    /// MRMS radar-gauge rainfall (watershed 72 h + 14-day point series) for the
    /// clarity model — catches localized/upstream rain Open-Meteo's point model
    /// misses. nil when IEM is unreachable (clarity falls back to Open-Meteo).
    let mrms: MrmsPrecip?
    /// Inputs that are missing because their upstream failed or stalled — a
    /// transient gap, not "nothing here" (a thrown fetch, a blown deadline, an
    /// expected dam feed that came back empty).
    let timedOut: Set<String>
    /// False when the NWS alerts fetch failed: `alerts` is then empty because we
    /// don't know, not because nothing is active.
    let alertsKnown: Bool
    let fetchedAt: Date

    /// Whether this snapshot can honestly be scored. Weather is required: wind,
    /// sky, pressure, humidity and four safety gates all come from it, and
    /// without it the builder used to substitute a calm, clear, 1016 hPa night —
    /// so an Open-Meteo outage during a storm scored Good or Prime. (The old
    /// rule, `weather != nil || water != nil`, let a lone gage reading carry
    /// that fabricated weather into a 200.)
    var canScore: Bool { weather != nil }

    /// What's missing or unreliable in this snapshot, for the response and logs.
    /// Empty means complete.
    var degradedInputs: [String] {
        var out = timedOut
        if weather == nil { out.insert("weather") }
        if !alertsKnown { out.insert("alerts") }
        return out.sorted()
    }

    var isComplete: Bool { degradedInputs.isEmpty }

    /// Highest wind floor (mph) implied by an active severe-wind Warning, or nil.
    /// A live warning outranks the smoothed forecast wind (a Severe Thunderstorm
    /// Warning = 58+ mph gusts NOW that Open-Meteo's hourly often misses).
    var alertWindFloorMph: Double? { alerts.compactMap(\.impliedWindFloorMph).max() }

    /// The most-urgent active safety WARNING (tornado / severe thunderstorm / flash
    /// flood / marine) covering the point, if any — feeds the storm safety gate so
    /// a warned night can never read Prime, even when the forecast model missed the
    /// storm entirely. `alerts` is sorted most-severe-first, so the first match is
    /// the one to surface as the binding "why".
    var severeWarningLabel: String? { alerts.first(where: { $0.impliesUnsafeToFish })?.event }
}

/// Serialises and caches the shared fetch. An actor so concurrent callers
/// can't both start one.
actor ConditionsSnapshotProvider {
    static let shared = ConditionsSnapshotProvider()
    private init() {}

    /// How long a snapshot stays good. These inputs move on the order of an
    /// hour (USGS posts every 15–60 min); 5 minutes keeps a tab-switch or a
    /// second card free while never showing meaningfully stale weather.
    static let defaultMaxAge: TimeInterval = 5 * 60

    /// How long a DEGRADED snapshot (something timed out, weather or alerts
    /// missing) is reused. Long enough to stop a burst of renders re-fanning out
    /// to an upstream that's struggling; short enough that one transient stall
    /// doesn't pin a lake to missing data for five minutes on every phone.
    static let degradedMaxAge: TimeInterval = 45

    /// Bound on cached coordinates; expired entries go first, then the oldest.
    static let maxEntries = 2_000

    private var cache: [String: ConditionsSnapshot] = [:]
    /// In-flight fetches by location key — the coalescing that makes two
    /// simultaneous callers share one network round trip instead of racing.
    private var inFlight: [String: Task<ConditionsSnapshot, Never>] = [:]

    /// ~100 m of precision: enough that drifting around a ramp reuses the
    /// snapshot, not so coarse that picking another city does.
    private nonisolated func key(_ c: CLLocationCoordinate2D) -> String {
        String(format: "%.3f,%.3f", c.latitude, c.longitude)
    }

    /// The shared snapshot for `coordinate`.
    /// - Parameter force: pull-to-refresh — bypass the cache, but still join an
    ///   in-flight fetch rather than starting a third one.
    func snapshot(for coordinate: CLLocationCoordinate2D,
                  force: Bool = false,
                  maxAge: TimeInterval = defaultMaxAge) async -> ConditionsSnapshot {
        let k = key(coordinate)

        if let running = inFlight[k] { return await running.value }
        if !force, let hit = cache[k],
           Date().timeIntervalSince(hit.fetchedAt) < (hit.isComplete ? maxAge : Self.degradedMaxAge) {
            return hit
        }

        let task = Task<ConditionsSnapshot, Never> {
            // Every input is bounded independently (see Deadline.swift): a single
            // stalled upstream drops to nil — a dormant factor — instead of
            // holding the whole snapshot (and the HTTP response behind it) open
            // until Cloud Run's 60s guillotine. A partial score beats no score.
            //
            // Budgets. Weather and the water-temp model are Open-Meteo, hedged:
            // a 1.5s hedge + an 8s attempt must fit, so 11s. USGS inputs and
            // generation get 12s — USGS waterservices takes ~4–8s per query
            // regardless of what it finds, and generation federates across
            // operator feeds + a CWMS hop.
            //
            // Each input also reports whether it FAILED (a thrown fetch, an
            // expected dam feed that came back empty) — not only whether it timed
            // out — so a snapshot missing data because an upstream erred is never
            // cached as complete. A nil that means "no gage / no dam here" stays a
            // clean nil.
            async let weather = withDeadlineOutcome(11, "weather") {
                try? await WeatherService.shared.conditions(near: coordinate)
            }
            async let water = withDeadlineOutcome(12, "water") {
                await Probe.attempt { try await WaterLevelService.shared.latestReading(near: coordinate) }
            }
            async let discharge = withDeadlineOutcome(12, "discharge") {
                await Probe.attempt { try await WaterLevelService.shared.nearestDischarge(near: coordinate) }
            }
            async let temp = withDeadlineOutcome(12, "waterTemp") {
                await Probe.attempt { try await WaterLevelService.shared.nearestWaterTemp(near: coordinate) }
            }
            async let tempModel = withDeadlineOutcome(11, "waterTempModel") {
                await WaterTemperatureService.model(near: coordinate)
            }
            async let turbidity = withDeadlineOutcome(12, "turbidity") {
                await Probe.attempt { try await WaterLevelService.shared.nearestTurbidity(near: coordinate) }
            }
            async let generation = withDeadlineOutcome(12, "generation") { () -> GenerationLookup? in
                let result = await GenerationService.shared.lookup(near: coordinate)
                return GenerationLookup(generation: result.generation, expected: result.expected)
            }
            // A 9s alerts budget sits just above HTTP.get's 8s default, so a slow
            // NWS answer that does arrive isn't cut off by the deadline first.
            async let alerts = withDeadlineOutcome(9, "alerts") { () -> [WeatherAlert]? in
                await WeatherAlertsService.shared.activeAlerts(near: coordinate)
            }
            async let mrms = withDeadlineOutcome(8, "mrms") {
                await MrmsPrecipService.shared.recent(near: coordinate)
            }

            let w = await weather, wl = await water, d = await discharge, t = await temp
            let tm = await tempModel, tb = await turbidity, g = await generation
            let a = await alerts, m = await mrms

            // MRMS/IEM covers the contiguous US; outside it a nil is expected.
            let inCONUS = (24.0...50.0).contains(coordinate.latitude)
                && (-125.5 ... -66.0).contains(coordinate.longitude)

            var failed = Set<String>()
            let checks: [(String, Bool)] = [
                ("weather", w.timedOut),
                ("water", wl.timedOut || wl.value?.isFailure == true),
                ("discharge", d.timedOut || d.value?.isFailure == true),
                ("waterTemp", t.timedOut || t.value?.isFailure == true),
                // The model is built from Open-Meteo, which covers everywhere: nil
                // is always a failed fetch.
                ("waterTempModel", tm.value == nil),
                ("turbidity", tb.timedOut || tb.value?.isFailure == true),
                ("generation", g.timedOut || (g.value.map { $0.expected && $0.generation == nil } ?? false)),
                ("alerts", a.timedOut),
                ("mrms", m.timedOut || (m.value == nil && inCONUS)),
            ]
            for (name, isFailure) in checks where isFailure { failed.insert(name) }

            return ConditionsSnapshot(weather: w.value,
                                      water: wl.value?.value,
                                      discharge: d.value?.value,
                                      waterTemp: t.value?.value,
                                      waterTempModel: tm.value,
                                      turbidity: tb.value?.value,
                                      generation: g.value?.generation,
                                      alerts: a.value ?? [],
                                      mrms: m.value,
                                      timedOut: failed,
                                      alertsKnown: a.value != nil,
                                      fetchedAt: Date())
        }
        inFlight[k] = task
        let result = await task.value
        inFlight[k] = nil
        // A forced refresh that came back worse never replaces a still-good cached
        // snapshot — one user's pull-to-refresh during a blip mustn't hand every
        // other user a degraded or unscorable lake. (Re-read after the await.)
        if force, !result.isComplete, let old = cache[k], old.isComplete,
           Date().timeIntervalSince(old.fetchedAt) < maxAge {
            return old
        }
        // Degraded snapshots are cached too, but only for `degradedMaxAge` (see
        // the hit check above): that briefly shields a struggling upstream from
        // every render re-fanning out, without pinning a lake to a gap for long.
        cache[k] = result
        if cache.count > Self.maxEntries { prune() }
        return result
    }

    private func prune() {
        let now = Date()
        cache = cache.filter { now.timeIntervalSince($0.value.fetchedAt) < Self.defaultMaxAge }
        guard cache.count > Self.maxEntries else { return }
        let overflow = cache.count - Self.maxEntries
        for key in cache.sorted(by: { $0.value.fetchedAt < $1.value.fetchedAt }).prefix(overflow).map(\.key) {
            cache.removeValue(forKey: key)
        }
    }
}
