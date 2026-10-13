//
//  WaterContext.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  "What water is this point on?" — the lake, the river below a dam, or neither.
//  GaugeSelector asks this before it trusts any USGS series, because the nearest
//  gauge is often the wrong water: the gauge AT Buford Dam reads 52 °F release
//  water, and Lake Lanier borrowed it; a pond in Suwanee borrowed the Buford
//  reach's cold flow from six miles away.
//
//  WHY GEOMETRY, NOT CONES: TailwaterRegistry's ±75° downstream cone is fine for
//  "does the current factor apply", but it can't say which water a point is on.
//  Rivers bend (Bull Shoals runs W then S) and towns sit on the lake side of a
//  dam. Every DamRoster dam carries its real NHDPlus reach — 60 km of downstream
//  flowline starting at the dam — so "below the dam" means "near that line".
//
//  RULE (gauge_final.json, step B), first match wins:
//    1. Within `exactDirectoryMiles` of a LakeDirectory point → that lake. A
//       client that sends the directory coordinate always gets the lake, even
//       where the point sits on the dam (Keystone).
//    2. Walk roster dams within `reachSearchMiles`, nearest first:
//       – a point behind the dam (its nearest reach location is the dam
//         end, projected backwards) is never on the reach, except within
//         `damNoiseMiles`, where dam coordinates are noise;
//       – on-reach: inside the corridor (narrow `faceCorridorMiles` within
//         `faceMiles` of the dam so the reservoir face stays lake, wider beyond),
//         or inside the downstream sector near the dam for tailwater taps off
//         the centerline;
//       – on-reach near the dam but the ground stands `bluffAbovePoolFt` above
//         the pool → the lake (a bluff above the dam, not the tailwater);
//       – on-reach otherwise → belowDam; off-reach within `faceMiles` of a dam
//         with an impoundment → that lake.
//    3. A directory lake within `lakeIdentityMiles` → that lake.
//    4. Otherwise open water.
//
//  Pure and synchronous: evaluated once per snapshot after the fetches, no I/O.
//  TailwaterRegistry.isTailwater remains the only scoring authority; this file
//  only decides which gauges describe the point.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

/// The lake a point resolved to. `directoryLake` is nil only when a roster dam's
/// impoundment isn't listed in LakeDirectory; `dam` is the roster dam that
/// impounds it, when the roster has one (GaugeSelector reads its pool).
struct LakeRef: Equatable, Sendable {
    let name: String
    let directoryLake: DirectoryLake?
    let dam: RosterDam?
}

enum WaterContext: Equatable, Sendable {
    case lake(LakeRef)
    /// `ownLake` is the downstream reservoir the point is also on (a dam's reach
    /// runs into the next lake), so that lake's own pool gauge stays usable.
    case belowDam(dam: RosterDam, damMiles: Double, ownLake: DirectoryLake?)
    case open

    // MARK: Tunables (each justified in gauge_final.json "thresholds")

    /// Snap-to-directory radius. 0.5 mi turned real tailrace taps 0.28–0.48 mi
    /// from the Table Rock, Allatoona and West Point points into lake points;
    /// 0.05 still catches clients that send the directory coordinate verbatim.
    static let exactDirectoryMiles: Double = 0.05
    /// Within this range of a dam the reservoir face is close to the tailwater,
    /// so the narrow corridor and the bluff test apply.
    static let faceMiles: Double = 1.0
    /// Reach corridor within `faceMiles`. 0.35 misclassified four DEM-verified
    /// pool points (Buford 0.35, Tenkiller 0.33, Norfork 0.32, Pinopolis 0.32);
    /// real tailwater near dams stays inside (Denison 0.26, West Point 0.12).
    static let faceCorridorMiles: Double = 0.30
    /// Reach corridor beyond `faceMiles`: 423/425 points on 85 reaches resolved
    /// belowDam, and off-reach ponds (Suwanee, Johns Creek) stay out.
    static let reachCorridorMiles: Double = 0.50
    /// Downstream sector for tailwater taps off the centerline near the dam:
    /// Keystone tailwater is 0.40 mi off at 30°, Bagnell A 0.53 mi off at 34°.
    static let nearDamSectorMiles: Double = 3.0
    static let nearDamSectorDeg: Double = 35
    /// Inside this radius the behind-the-dam test is noise: 67/85 operator dam
    /// coordinates snap to NHDPlus within it, and the Holter gauge sits 0.05 mi
    /// from its dam coordinate.
    static let damNoiseMiles: Double = 0.15
    /// Directory-lake identity radius. The Lanier reported point is 5.3 mi from
    /// its directory point; Lake Acworth (7.0 mi from Allatoona's) must not be.
    static let lakeIdentityMiles: Double = 6
    /// Ground this far above pool, on-reach within `faceMiles`, is a bluff over
    /// the lake (the Bull Shoals production coordinate: 784 ft vs pool 654).
    /// Tailwater banks sit well under it (Buford +19, Table Rock tailrace).
    static let bluffAbovePoolFt: Double = 50
    /// Dams farther than this can't own the point: the 60 km reach rarely
    /// straightens out past 35 straight-line miles.
    static let reachSearchMiles: Double = 35
    /// Name-matched impoundment lookups only consider dams this close to the
    /// lake, so a common name ("Wilson Lake") can't attach a dam in another
    /// state. Same window the roster generator uses for duplicate lake rows.
    static let impoundmentNameMatchMiles: Double = 60

    // MARK: Accessors

    var isBelowDam: Bool {
        if case .belowDam = self { return true }
        return false
    }

    /// The lake a lake context names, or the downstream lake a belowDam point is
    /// also on. nil for open water.
    var lakeName: String? {
        switch self {
        case .lake(let ref): return ref.name
        case .belowDam(_, _, let ownLake): return ownLake?.name
        case .open: return nil
        }
    }

    /// `DirectoryLake.id` of `lakeName`'s lake, when LakeDirectory lists it.
    var lakeID: String? {
        switch self {
        case .lake(let ref): return ref.directoryLake?.id
        case .belowDam(_, _, let ownLake): return ownLake?.id
        case .open: return nil
        }
    }

    /// The dam a belowDam point is under, or the dam impounding a lake context.
    var damName: String? {
        switch self {
        case .lake(let ref): return ref.dam?.name
        case .belowDam(let dam, _, _): return dam.name
        case .open: return nil
        }
    }
}

struct WaterContextResolution: Equatable, Sendable {
    let context: WaterContext
    /// Human-readable evidence for diagnostics (gaugeContext.reason in the API).
    let reason: String
}

extension WaterContext {

    /// Rule step B. `poolFtForDam` supplies P for the bluff test — the caller's
    /// live generation pool when that generation is this dam's lake, else the
    /// roster's normal pool; nil falls back to `dam.normalPoolFt` here too.
    /// Without a ground elevation the bluff test never fires, so the answer is
    /// deterministic (belowDam) rather than guessed.
    static func resolve(latitude lat: Double, longitude lon: Double, groundElevationFt: Double?,
                        poolFtForDam: (RosterDam) -> Double? = { $0.normalPoolFt },
                        roster: [RosterDam] = DamRoster.all,
                        directory: [DirectoryLake] = LakeDirectory.all) -> WaterContextResolution {
        let nearest = directory
            .map { (lake: $0, miles: TailwaterRegistry.haversineMiles(lat1: lat, lon1: lon, lat2: $0.lat, lon2: $0.lon)) }
            .min { $0.miles < $1.miles }

        // 1. The directory coordinate itself.
        if let nearest, nearest.miles <= exactDirectoryMiles {
            return WaterContextResolution(
                context: .lake(LakeRef(name: nearest.lake.name, directoryLake: nearest.lake,
                                       dam: impoundingDam(of: nearest.lake, in: roster))),
                reason: "exact directory coordinate of \(nearest.lake.name) (\(fmt(nearest.miles)) mi)")
        }

        // 2. Roster reaches, nearest dam first.
        let point = CLLocationCoordinate2D(latitude: lat, longitude: lon)
        for (dam, damMiles) in DamRoster.dams(within: reachSearchMiles, of: point, in: roster) {
            guard dam.reach.count >= 2 else { continue }
            let projection = distanceToReach(dam.reach, lat: lat, lon: lon, allowBehind: damMiles <= damNoiseMiles)
            let corridor = damMiles <= faceMiles ? faceCorridorMiles : reachCorridorMiles

            var evidence: String?
            if let projection, projection.miles <= corridor {
                evidence = "\(fmt(projection.miles)) mi from the \(dam.name) reach "
                    + "(\(fmt(projection.alongMiles, 1)) mi along, corridor \(fmt(corridor)))"
            } else if projection != nil, damMiles <= nearDamSectorMiles {
                // Same along-distance as the point's distance from the dam: where
                // the river is by the time it has come that far.
                let onReach = reachPoint(dam.reach, atAlongMiles: min(damMiles, nearDamSectorMiles))
                let reachBearing = TailwaterRegistry.bearingDeg(lat1: dam.latitude, lon1: dam.longitude,
                                                                lat2: onReach.lat, lon2: onReach.lon)
                let pointBearing = TailwaterRegistry.bearingDeg(lat1: dam.latitude, lon1: dam.longitude,
                                                                lat2: lat, lon2: lon)
                if TailwaterRegistry.angularDifferenceDeg(pointBearing, reachBearing) <= nearDamSectorDeg {
                    evidence = "downstream sector of \(dam.name) (\(fmt(damMiles)) mi, bearing "
                        + "\(fmt(pointBearing, 0)) vs reach \(fmt(reachBearing, 0)))"
                }
            }

            if let evidence {
                if damMiles <= faceMiles, let ground = groundElevationFt,
                   let pool = poolFtForDam(dam) ?? dam.normalPoolFt,
                   ground >= pool + bluffAbovePoolFt,
                   let lake = impoundment(of: dam, in: directory) {
                    return WaterContextResolution(
                        context: .lake(lake),
                        reason: "at \(dam.name), ground \(fmt(ground, 0)) ft >= pool \(fmt(pool, 0)) + "
                            + "\(fmt(bluffAbovePoolFt, 0)) ft (bluff above the dam, not tailwater)")
                }
                let ownLake = nearest.flatMap {
                    $0.miles <= lakeIdentityMiles && !isImpoundment($0.lake, of: dam) ? $0.lake : nil
                }
                return WaterContextResolution(
                    context: .belowDam(dam: dam, damMiles: damMiles, ownLake: ownLake),
                    reason: evidence + (ownLake.map { "; also on \($0.name)" } ?? ""))
            }

            if damMiles <= faceMiles, let lake = impoundment(of: dam, in: directory) {
                return WaterContextResolution(
                    context: .lake(lake),
                    reason: "reservoir side of \(dam.name) (\(fmt(damMiles)) mi, off its reach)")
            }
        }

        // 3. A directory lake close enough to be the water the point is on.
        if let nearest, nearest.miles <= lakeIdentityMiles {
            return WaterContextResolution(
                context: .lake(LakeRef(name: nearest.lake.name, directoryLake: nearest.lake,
                                       dam: impoundingDam(of: nearest.lake, in: roster))),
                reason: "directory lake \(nearest.lake.name) \(fmt(nearest.miles, 1)) mi")
        }

        // 4.
        return WaterContextResolution(
            context: .open,
            reason: "off every roster reach; no directory lake within \(fmt(lakeIdentityMiles, 0)) mi")
    }

    // MARK: Reach geometry

    /// Local equirectangular miles per degree of latitude, from the same Earth
    /// radius as TailwaterRegistry.haversineMiles so corridor and dam distances agree.
    private static let milesPerDegree = 3958.8 * Double.pi / 180

    /// Distance from a point to a reach polyline, in a flat frame local to each
    /// segment (segments are tens of metres to a few miles; the error is noise
    /// next to a 0.30 mi corridor).
    ///
    /// Returns nil when the point is BEHIND the dam: its nearest reach location is
    /// the dam end of the first segment, projected backwards (t ≤ 0). That is
    /// the reservoir side, never the reach. A behind test on the first segment's
    /// half-plane alone would be wrong: a simplified reach's first segment can be
    /// a few dozen metres pointing across the river, and the channel beyond it
    /// bends back. `allowBehind` skips the test where the dam coordinate itself
    /// is too noisy to have a side.
    ///
    /// `alongMiles` is the distance along the reach to the nearest location;
    /// `firstSegmentT` is the point's projection parameter on the first segment
    /// (0 at the dam end, 1 at its far vertex), for diagnostics.
    static func distanceToReach(_ reach: [(lat: Double, lon: Double)], lat: Double, lon: Double,
                                allowBehind: Bool) -> (miles: Double, alongMiles: Double, firstSegmentT: Double)? {
        guard reach.count >= 2 else { return nil }
        var bestMiles = Double.infinity, bestIndex = 0, bestT = 0.0, bestAlong = 0.0
        var firstSegmentT = 0.0
        var along = 0.0
        for i in 0..<(reach.count - 1) {
            let a = reach[i], b = reach[i + 1]
            let kx = milesPerDegree * cos(a.lat * .pi / 180)
            let bx = (b.lon - a.lon) * kx, by = (b.lat - a.lat) * milesPerDegree
            let px = (lon - a.lon) * kx, py = (lat - a.lat) * milesPerDegree
            let length = Swift.max((bx * bx + by * by).squareRoot(), 1e-9)
            let t = (px * bx + py * by) / (length * length)
            if i == 0 { firstSegmentT = t }
            let tc = Swift.min(1, Swift.max(0, t))
            let dx = px - tc * bx, dy = py - tc * by
            let miles = (dx * dx + dy * dy).squareRoot()
            if miles < bestMiles {
                bestMiles = miles; bestIndex = i; bestT = t; bestAlong = along + tc * length
            }
            along += length
        }
        if bestIndex == 0, bestT <= 0, !allowBehind { return nil }
        return (bestMiles, bestAlong, firstSegmentT)
    }

    /// The reach location `alongMiles` downstream of the dam (the last vertex when
    /// the reach is shorter). Same segment lengths as `distanceToReach`.
    static func reachPoint(_ reach: [(lat: Double, lon: Double)], atAlongMiles target: Double) -> (lat: Double, lon: Double) {
        guard let first = reach.first else { return (0, 0) }
        var along = 0.0
        for i in 0..<Swift.max(reach.count - 1, 0) {
            let a = reach[i], b = reach[i + 1]
            let kx = milesPerDegree * cos(a.lat * .pi / 180)
            let bx = (b.lon - a.lon) * kx, by = (b.lat - a.lat) * milesPerDegree
            let length = (bx * bx + by * by).squareRoot()
            if along + length >= target {
                let t = length > 0 ? Swift.max(0, target - along) / length : 0
                return (a.lat + t * (b.lat - a.lat), a.lon + t * (b.lon - a.lon))
            }
            along += length
        }
        return reach.last ?? first
    }

    // MARK: Impoundments

    /// True when `lake` is the reservoir `dam` impounds. The generated id is
    /// checked first; the name fallback catches a lake listed once per state
    /// (Kentucky Lake KY and TN are one reservoir behind one dam).
    static func isImpoundment(_ lake: DirectoryLake, of dam: RosterDam) -> Bool {
        if let id = dam.impoundmentLakeID, id == lake.id { return true }
        guard let impoundment = dam.impoundmentName, let key = baseKey(lake.name) else { return false }
        return GaugeClassifier.keysMatch(key, GaugeClassifier.lakeAliases(impoundment))
    }

    /// The lake behind `dam`: its directory row when listed (by id, else by name
    /// near the dam), otherwise just the roster's impoundment name.
    private static func impoundment(of dam: RosterDam, in directory: [DirectoryLake]) -> LakeRef? {
        if let id = dam.impoundmentLakeID, let lake = directory.first(where: { $0.id == id }) {
            return LakeRef(name: lake.name, directoryLake: lake, dam: dam)
        }
        guard let name = dam.impoundmentName else { return nil }
        // Distance first: the name key is the expensive half.
        let named = directory
            .map { (lake: $0, miles: TailwaterRegistry.haversineMiles(lat1: dam.latitude, lon1: dam.longitude,
                                                                      lat2: $0.lat, lon2: $0.lon)) }
            .filter { $0.miles <= impoundmentNameMatchMiles && isImpoundment($0.lake, of: dam) }
            .min { $0.miles < $1.miles }
        return LakeRef(name: named?.lake.name ?? name, directoryLake: named?.lake, dam: dam)
    }

    /// The roster dam impounding a directory lake, for a lake context's `dam`.
    /// Nearest wins when several claim it (a main dam and its re-regulation dam).
    private static func impoundingDam(of lake: DirectoryLake, in roster: [RosterDam]) -> RosterDam? {
        let claims = roster
            .map { (dam: $0, miles: TailwaterRegistry.haversineMiles(lat1: lake.lat, lon1: lake.lon,
                                                                     lat2: $0.latitude, lon2: $0.longitude)) }
        if let byID = claims.filter({ $0.dam.impoundmentLakeID == lake.id }).min(by: { $0.miles < $1.miles }) {
            return byID.dam
        }
        return claims
            .filter { $0.miles <= impoundmentNameMatchMiles && $0.dam.impoundmentName != nil
                && isImpoundment(lake, of: $0.dam) }
            .min { $0.miles < $1.miles }?.dam
    }

    /// A directory name's key without its parenthesized alias:
    /// "Lanier (Sidney Lanier)" → [LANIER].
    private static func baseKey(_ name: String) -> [String]? {
        let base = name.replacingOccurrences(of: #"\([^)]*\)"#, with: " ", options: .regularExpression)
        let key = GaugeClassifier.nameKey(base)
        return key.isEmpty ? nil : key
    }

    private static func fmt(_ value: Double, _ places: Int = 2) -> String {
        String(format: "%.\(places)f", value)
    }
}

// MARK: - Generation and pool

extension WaterContext {

    /// Whether a generation feed describes THIS water: its lake is the context
    /// lake, or the impoundment of the dam the context is about.
    ///
    /// WHY: GenerationService hands back the nearest dam, which is often a
    /// neighbor. Lake Taneycomo's nearest feed is Table Rock, so its level tile
    /// showed Table Rock's ~915 ft pool; below Buford Dam the Lanier pool isn't
    /// the water you're standing in. The pool label, the pool trend, P for the
    /// gauge checks and the CWMS tailwater temp are only trusted on a match.
    /// Open water has no lake to match.
    func matches(_ generation: DamGeneration?) -> Bool {
        guard let generation else { return false }
        switch self {
        case .lake(let ref):
            return Self.namesMatch(generation.dam.lakeName, ref.name)
                || ref.dam.map { Self.generation(generation, isFor: $0) } == true
        case .belowDam(let dam, _, _):
            return Self.generation(generation, isFor: dam)
        case .open:
            return false
        }
    }

    /// A generation feed is `dam`'s when its lake is the dam's impoundment or its
    /// dam carries the same name ("Buford Dam" in both rosters).
    static func generation(_ generation: DamGeneration, isFor dam: RosterDam) -> Bool {
        if let impoundment = dam.impoundmentName, namesMatch(generation.dam.lakeName, impoundment) { return true }
        let key = GenerationService.damKey(generation.dam.name)
        return !key.isEmpty && key == GenerationService.damKey(dam.name)
    }

    /// P for `dam`'s bluff test: the live generation pool when that feed is this
    /// dam's, else the roster's normal pool.
    static func poolFt(for dam: RosterDam, generation: DamGeneration?) -> Double? {
        if let generation, Self.generation(generation, isFor: dam), let live = generation.reservoirElevationFt {
            return live
        }
        return dam.normalPoolFt
    }

    /// P for a lake context's gauge checks, in the rule's order: the matched
    /// generation's live pool, else the roster's normal pool, else the NWPS
    /// table's full pool. nil outside a lake context, where no check reads it.
    func poolFt(generation: DamGeneration?, nwps: WaterLevelReading?) -> Double? {
        guard case .lake(let ref) = self else { return nil }
        if matches(generation), let live = generation?.reservoirElevationFt { return live }
        return ref.dam?.normalPoolFt ?? nwps?.fullPoolFt
    }

    /// Two lake names for the same water: GenerationService's own key ("Chickamauga
    /// Dam" meets "Chickamauga Lake"), or any alias pair whose keys match
    /// ("Lanier (Sidney Lanier)" meets "Lake Sidney Lanier").
    static func namesMatch(_ a: String, _ b: String) -> Bool {
        let key = GenerationService.damKey(a)
        if !key.isEmpty, key == GenerationService.damKey(b) { return true }
        let other = GaugeClassifier.lakeAliases(b)
        return GaugeClassifier.lakeAliases(a).contains { GaugeClassifier.keysMatch($0, other) }
    }
}
