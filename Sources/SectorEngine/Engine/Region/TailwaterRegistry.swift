//
//  TailwaterRegistry.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Tailwater detection — "is this spot below a dam?", answered from a static
//  roster. Separate from whether that dam is GENERATING right now, which
//  TVAGenerationService reads live; this file only decides whether the current
//  factor applies at all.
//
//  DIRECTION-AWARE (2026-07-08): proximity alone misclassified reservoir spots —
//  the town of Guntersville sits on the LAKE side of Guntersville Dam but fell
//  inside the old 12-mile radius. Each dam now carries the compass bearing of
//  the river LEAVING it; a spot is tailwater only when it's inside the radius
//  AND within ±`coneHalfAngleDeg` of that downstream bearing (rivers bend, so
//  the cone is wide). Within `nearDamAlwaysMiles` of the dam the flag is granted
//  regardless — generation dominates both faces of a dam at that range, and the
//  seed coordinates are only ~2-decimal precise.
//
//  A spot between two chained dams (below Wheeler = the top of Wilson Lake) is
//  tested against EVERY dam in radius, so the upstream dam's cone correctly
//  flags it even when the downstream dam is nearer.
//
//  Pure math (haversine + forward azimuth) — no CoreLocation. Expand the seed
//  list as coverage grows; the engine logic doesn't change. §5.7.
//

import Foundation

public struct Dam: Equatable, Sendable {
    public let name: String
    public let latitude: Double
    public let longitude: Double
    /// Compass bearing (° clockwise from north) of the river leaving the dam —
    /// distinguishes true below-dam tailwater from the reservoir behind it.
    public let downstreamBearingDeg: Double
    public init(_ name: String, _ latitude: Double, _ longitude: Double, downstream: Double) {
        self.name = name; self.latitude = latitude; self.longitude = longitude
        self.downstreamBearingDeg = downstream
    }
}

public enum TailwaterRegistry: Sendable {

    /// Radius (miles) below a dam still treated as tailwater.
    public static let tailwaterRadiusMiles: Double = 12
    /// Half-angle (°) of the downstream cone. Wide, because tailwater reaches bend.
    public static let coneHalfAngleDeg: Double = 75
    /// Inside this range the flag is granted regardless of bearing — generation
    /// dominates both faces of the dam, and seed coordinates are approximate.
    public static let nearDamAlwaysMiles: Double = 1.0

    /// Roster of TVA / USACE generating dams (dam coordinates + the approximate
    /// bearing of the river immediately downstream). Covers all 29 TVA
    /// hydropower dams plus three USACE Cumberland projects.
    public static let dams: [Dam] = [
        Dam("Fort Loudoun Dam", 35.79, -84.24, downstream: 250),   // Tennessee R. SW toward Watts Bar
        Dam("Watts Bar Dam", 35.62, -84.78, downstream: 215),      // SW toward Chickamauga
        Dam("Chickamauga Dam", 35.10, -85.23, downstream: 240),    // SW through Chattanooga
        Dam("Nickajack Dam", 35.00, -85.60, downstream: 228),      // SW toward Guntersville
        Dam("Guntersville Dam", 34.42, -86.39, downstream: 295),   // WNW toward Wheeler/Decatur
        Dam("Wheeler Dam", 34.80, -87.39, downstream: 270),        // W toward Wilson
        Dam("Wilson Dam", 34.80, -87.63, downstream: 298),         // WNW toward Pickwick
        Dam("Pickwick Dam", 35.07, -88.26, downstream: 355),       // N toward Kentucky Lake
        Dam("Kentucky Dam", 37.01, -88.27, downstream: 315),       // NW to the Ohio
        Dam("Norris Dam", 36.22, -84.09, downstream: 225),         // Clinch R. SW
        Dam("Cherokee Dam", 36.18, -83.49, downstream: 235),       // Holston R. SW
        Dam("Douglas Dam", 35.96, -83.54, downstream: 300),        // French Broad WNW
        Dam("Blue Ridge Dam", 34.87, -84.28, downstream: 345),     // Toccoa R. N
        Dam("Center Hill Dam", 36.10, -85.83, downstream: 355),    // Caney Fork N
        Dam("Old Hickory Dam", 36.29, -86.65, downstream: 245),    // Cumberland SW to Nashville
        Dam("J. Percy Priest Dam", 36.14, -86.62, downstream: 340), // Stones R. N

        // The rest of TVA's hydro fleet, added 2026-08-03 so every dam
        // TVAGenerationService can pull a schedule for is also recognised as a
        // tailwater — without these, generation was fetched and thrown away.
        // Coordinates come straight from TVA's /RestApi/locations (4 dp, better
        // than the 2 dp seeds above). Bearings were DERIVED, not eyeballed:
        //   • "river-mile" — TVA publishes River + RiverMile, and river mile
        //     counts up from the mouth, so the next dam with a lower mile is
        //     downstream. Reproduced the hand bearings above to within 1° on
        //     Watts Bar, Nickajack, Guntersville, Wheeler and Wilson.
        //   • "OSM channel" — OpenStreetMap draws waterways in the direction of
        //     flow; walk the nearest named river 5 km forward. Agreed with the
        //     river-mile bearings to a median of 8° on the dams where both
        //     methods answered.
        //   • "→ X" — no channel geometry near the dam, so the bearing points
        //     at a dam known to sit downstream. Coarsest of the three, but the
        //     cone is ±75° and these three are all well inside it.
        Dam("Boone Dam", 36.4417, -82.4364, downstream: 313),       // S.F. Holston; OSM channel
        Dam("Chatuge Dam", 35.0197, -83.7906, downstream: 292),     // Hiwassee; river-mile
        Dam("Fontana Dam", 35.4503, -83.8053, downstream: 274),     // Little Tennessee; OSM channel
        Dam("Fort Patrick Henry Dam", 36.4989, -82.5091, downstream: 306), // S.F. Holston; OSM channel
        Dam("Great Falls Dam", 35.8075, -85.6342, downstream: 297), // Caney Fork; OSM channel
        Dam("Hiwassee Dam", 35.1472, -84.1786, downstream: 282),    // Hiwassee; → Apalachia Dam
        Dam("Apalachia Dam", 35.1681, -84.2953, downstream: 282),   // Hiwassee; OSM channel
        Dam("Melton Hill Dam", 35.8844, -84.3006, downstream: 288), // Clinch; OSM channel
        Dam("Nottely Dam", 34.9608, -84.0869, downstream: 338),     // Nottely; → Hiwassee Dam
        Dam("Ocoee No. 1 Dam", 35.0956, -84.6475, downstream: 329), // Ocoee; OSM channel
        Dam("Ocoee No. 2 Dam", 35.0950, -84.5347, downstream: 270), // Ocoee; river-mile
        Dam("Ocoee No. 3 Dam", 35.0406, -84.4667, downstream: 314), // Ocoee; river-mile
        Dam("South Holston Dam", 36.5203, -82.0953, downstream: 254), // S.F. Holston; river-mile
        Dam("Tims Ford Dam", 35.1956, -86.2789, downstream: 265),   // Elk; OSM channel
        Dam("Watauga Dam", 36.3292, -82.1253, downstream: 357),     // Watauga; river-mile
        Dam("Wilbur Dam", 36.3424, -82.1261, downstream: 292),      // Watauga; → Boone Dam

        // The five USACE Cumberland projects TVA publishes schedules for but
        // labels `Non-hydropower`, added 2026-08-03. They were invisible until
        // the dam filter stopped trusting that label — Center Hill, Old Hickory
        // and J. Percy Priest were already above. Same derivation methods.
        // Cumberland river miles order the mainstem unambiguously
        // (Wolf Creek 460 → Cordell Hull 313 → Old Hickory 216 → Cheatham 148
        // → Barkley 30), so the next-lower-mile dam is downstream.
        Dam("Barkley Dam", 37.0244, -88.2228, downstream: 330),     // Cumberland; see note below
        Dam("Cheatham Dam", 36.3144, -87.2161, downstream: 312),    // Cumberland; river-mile (OSM agreed, 20°)
        Dam("Cordell Hull Dam", 36.2867, -85.9408, downstream: 271), // Cumberland; river-mile → Old Hickory
        Dam("Dale Hollow Dam", 36.5414, -85.4564, downstream: 260), // Obey; see note below
        Dam("Wolf Creek Dam", 36.8689, -85.1458, downstream: 228)   // Cumberland; river-mile → Cordell Hull
        //
        // Two of those bearings are compromises, and worth knowing about:
        //
        // Barkley — the reach below the dam leaves NORTH (OSM channel, 2°) but
        // the Cumberland's mouth on the Ohio sits WNW (292°); 30.6 river miles
        // cover only 10.7 straight-line, so the reach meanders hard. 330° is
        // chosen to span both, and its cone still cleanly excludes Lake Barkley,
        // which extends SE from the dam.
        //
        // Dale Hollow — the Obey runs WNW to the Cumberland (285°, 2.7 mi out)
        // then turns SW toward Cordell Hull (237°). 260° covers both legs.
        //
        // Cordell Hull's OSM walk returned 168°, 103° off the river-mile answer
        // and outside the cone. That's a meander below Carthage, not a flow
        // direction — river mile wins, so 271° (west, toward Old Hickory).
    ]

    public static func nearestDam(toLatitude lat: Double, longitude lon: Double) -> (dam: Dam, miles: Double)? {
        dams
            .map { ($0, haversineMiles(lat1: lat, lon1: lon, lat2: $0.latitude, lon2: $0.longitude)) }
            .min { $0.1 < $1.1 }
    }

    /// True only for spots genuinely BELOW a dam: inside the radius and inside
    /// the dam's downstream cone (or right at the dam). Every dam in radius is
    /// tested, so chained dams (below Wheeler = top of Wilson Lake) still flag.
    public static func isTailwater(latitude lat: Double, longitude lon: Double) -> Bool {
        dams.contains { dam in
            let miles = haversineMiles(lat1: dam.latitude, lon1: dam.longitude, lat2: lat, lon2: lon)
            guard miles <= tailwaterRadiusMiles else { return false }
            if miles <= nearDamAlwaysMiles { return true }
            let toSpot = bearingDeg(lat1: dam.latitude, lon1: dam.longitude, lat2: lat, lon2: lon)
            return angularDifferenceDeg(toSpot, dam.downstreamBearingDeg) <= coneHalfAngleDeg
        }
    }

    /// Forward azimuth from point 1 to point 2, ° clockwise from north (0–360).
    static func bearingDeg(lat1: Double, lon1: Double, lat2: Double, lon2: Double) -> Double {
        let φ1 = lat1 * .pi / 180, φ2 = lat2 * .pi / 180
        let dλ = (lon2 - lon1) * .pi / 180
        let y = sin(dλ) * cos(φ2)
        let x = cos(φ1) * sin(φ2) - sin(φ1) * cos(φ2) * cos(dλ)
        let θ = atan2(y, x) * 180 / .pi
        return (θ + 360).truncatingRemainder(dividingBy: 360)
    }

    /// Smallest separation between two compass bearings (0–180°).
    static func angularDifferenceDeg(_ a: Double, _ b: Double) -> Double {
        let d = abs(a - b).truncatingRemainder(dividingBy: 360)
        return Swift.min(d, 360 - d)
    }

    static func haversineMiles(lat1: Double, lon1: Double, lat2: Double, lon2: Double) -> Double {
        let r = 3958.8   // Earth radius, miles
        let dLat = (lat2 - lat1) * .pi / 180
        let dLon = (lon2 - lon1) * .pi / 180
        let a = sin(dLat / 2) * sin(dLat / 2)
            + cos(lat1 * .pi / 180) * cos(lat2 * .pi / 180) * sin(dLon / 2) * sin(dLon / 2)
        return r * 2 * atan2(a.squareRoot(), (1 - a).squareRoot())
    }
}
