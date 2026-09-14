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
    /// Inputs whose deadline fired — the upstream stalled, so their nil is a
    /// transient gap, not "nothing here".
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
            // Budgets: the weather family is 9s (each host already fails fast at
            // 8s and the two race), generation is 12s because it federates across
            // operator feeds + a CWMS enrich hop.
            async let weather = withDeadlineOutcome(9, "weather") {
                try? await WeatherService.shared.conditions(near: coordinate)
            }
            // USGS inputs get 12s — the same budget generation already has, so the
            // snapshot's worst case doesn't grow — because USGS waterservices takes
            // ~4–8s per query regardless of what it finds (see WaterLevelService).
            async let water = withDeadlineOutcome(12, "water") {
                try? await WaterLevelService.shared.latestReading(near: coordinate)
            }
            async let discharge = withDeadlineOutcome(12, "discharge") {
                try? await WaterLevelService.shared.nearestDischarge(near: coordinate)
            }
            async let temp = withDeadlineOutcome(12, "waterTemp") {
                try? await WaterLevelService.shared.nearestWaterTemp(near: coordinate)
            }
            async let tempModel = withDeadlineOutcome(9, "waterTempModel") {
                await WaterTemperatureService.model(near: coordinate)
            }
            async let turbidity = withDeadlineOutcome(12, "turbidity") {
                try? await WaterLevelService.shared.nearestTurbidity(near: coordinate)
            }
            async let generation = withDeadlineOutcome(12, "generation") {
                await GenerationService.shared.generation(near: coordinate)
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

            var timedOut = Set<String>()
            for (name, late) in [("weather", w.timedOut), ("water", wl.timedOut), ("discharge", d.timedOut),
                                 ("waterTemp", t.timedOut), ("waterTempModel", tm.timedOut),
                                 ("turbidity", tb.timedOut), ("generation", g.timedOut),
                                 ("alerts", a.timedOut), ("mrms", m.timedOut)] where late {
                timedOut.insert(name)
            }

            return ConditionsSnapshot(weather: w.value,
                                      water: wl.value,
                                      discharge: d.value,
                                      waterTemp: t.value,
                                      waterTempModel: tm.value,
                                      turbidity: tb.value,
                                      generation: g.value,
                                      alerts: a.value ?? [],
                                      mrms: m.value,
                                      timedOut: timedOut,
                                      alertsKnown: a.value != nil,
                                      fetchedAt: Date())
        }
        inFlight[k] = task
        let result = await task.value
        inFlight[k] = nil
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
