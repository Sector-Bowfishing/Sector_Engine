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
    let fetchedAt: Date

    /// With no weather AND no gage there's nothing real to score — callers use
    /// this to avoid showing a misleading moon-only result.
    var hasAnyLiveInput: Bool { weather != nil || water != nil }

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
        if !force, let hit = cache[k], Date().timeIntervalSince(hit.fetchedAt) < maxAge {
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
            async let weather = withDeadline(9, "weather") {
                try? await WeatherService.shared.conditions(near: coordinate)
            }
            async let water = withDeadline(9, "water") {
                try? await WaterLevelService.shared.latestReading(near: coordinate)
            }
            async let discharge = withDeadline(9, "discharge") {
                try? await WaterLevelService.shared.nearestDischarge(near: coordinate)
            }
            async let temp = withDeadline(9, "waterTemp") {
                try? await WaterLevelService.shared.nearestWaterTemp(near: coordinate)
            }
            async let tempModel = withDeadline(9, "waterTempModel") {
                await WaterTemperatureService.model(near: coordinate)
            }
            async let turbidity = withDeadline(9, "turbidity") {
                try? await WaterLevelService.shared.nearestTurbidity(near: coordinate)
            }
            async let generation = withDeadline(12, "generation") {
                await GenerationService.shared.generation(near: coordinate)
            }
            async let alerts = withDeadline(8, "alerts") { () -> [WeatherAlert]? in
                await WeatherAlertsService.shared.activeAlerts(near: coordinate)
            }
            async let mrms = withDeadline(8, "mrms") {
                await MrmsPrecipService.shared.recent(near: coordinate)
            }
            return ConditionsSnapshot(weather: await weather,
                                      water: await water,
                                      discharge: await discharge,
                                      waterTemp: await temp,
                                      waterTempModel: await tempModel,
                                      turbidity: await turbidity,
                                      generation: await generation,
                                      alerts: await alerts ?? [],
                                      mrms: await mrms,
                                      fetchedAt: Date())
        }
        inFlight[k] = task
        let result = await task.value
        inFlight[k] = nil
        // Only cache something worth reusing — caching a total failure would
        // pin the dashboard to "no data" for the whole TTL.
        if result.hasAnyLiveInput { cache[k] = result }
        return result
    }
}
