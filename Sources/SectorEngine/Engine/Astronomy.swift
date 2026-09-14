//
//  Astronomy.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Local ephemeris — no network. Computes sun events (sunrise/sunset + civil/
//  nautical/astronomical twilight), moon illumination, and the moon's altitude
//  across the fishing window. The darkness factor uses moon *altitude during
//  the window* — a full moon that rises at 1 AM leaves the early window dark —
//  not raw phase. §3 / §5.3.
//
//  Math follows Paul Schlyter's "How to compute planetary positions"
//  (low-precision, ~1–2 arcmin for the Moon — far better than this model needs).
//  All angles are in degrees unless a name says `Rad`. UT is handled in the
//  Gregorian (UTC) calendar; the Dates returned are absolute instants, so they
//  render correctly in any timezone.
//

import Foundation

public enum Astronomy: Sendable {

    // MARK: - Public API

    public struct SunEvents: Equatable, Sendable {
        public let sunrise: Date?
        public let sunset: Date?
        public let civilDawn: Date?
        public let civilDusk: Date?
        public let nauticalDusk: Date?
        public let astronomicalDawn: Date?
        public let astronomicalDusk: Date?
    }

    /// Sun rise/set and the three twilight ends for the UTC calendar day of `date`.
    public static func sunEvents(on date: Date, lat: Double, lon: Double) -> SunEvents {
        let (dayStart, d) = dayContext(for: date)
        let sun = sunCoords(d)
        // Transit (local solar noon), in UT hours.
        let transit = rev24(sun.ra / 15 - sun.gmst0 / 15 - lon / 15)

        func events(altitude a: Double) -> (rise: Date?, set: Date?) {
            let cosH = (sind(a) - sind(lat) * sind(sun.dec)) / (cosd(lat) * cosd(sun.dec))
            guard cosH >= -1, cosH <= 1 else { return (nil, nil) }  // never reaches `a`
            let hHours = acosd(cosH) / 15
            // Don't wrap: rise/set are anchored to solar-noon transit, so a set
            // after UT midnight (common at US longitudes) correctly spills into
            // the next UTC day, and a pre-dawn rise into the previous one.
            let rise = dateFrom(dayStart: dayStart, utHours: transit - hHours)
            let set = dateFrom(dayStart: dayStart, utHours: transit + hHours)
            return (rise, set)
        }

        let rs = events(altitude: -0.833)
        let civil = events(altitude: -6)
        let nautical = events(altitude: -12)
        let astro = events(altitude: -18)
        return SunEvents(sunrise: rs.rise, sunset: rs.set,
                         civilDawn: civil.rise, civilDusk: civil.set,
                         nauticalDusk: nautical.set,
                         astronomicalDawn: astro.rise, astronomicalDusk: astro.set)
    }

    /// Illuminated fraction of the moon's disk, 0 (new) … 1 (full), from the
    /// true sun–moon elongation (more accurate than the synodic approximation).
    public static func moonIllumination(on date: Date) -> Double {
        let (_, d) = dayContext(for: date)
        let sun = sunCoords(d)
        let moon = moonCoords(d)
        let elong = acosd(cosd(sun.lon - moon.lon) * cosd(moon.lat))
        let phaseAngle = 180 - elong
        return ((1 + cosd(phaseAngle)) / 2).clamped01
    }

    /// Fraction through the synodic (new→new) cycle: 0 = new, 0.5 = full. Used
    /// for the human phase name only.
    public static func moonPhaseFraction(on date: Date) -> Double {
        let synodic = 29.530588853
        let knownNewMoon = Date(timeIntervalSince1970: 947182440)   // 2000-01-06 18:14 UTC
        let days = date.timeIntervalSince(knownNewMoon) / 86_400.0
        let raw = days.truncatingRemainder(dividingBy: synodic)
        return ((raw + synodic).truncatingRemainder(dividingBy: synodic)) / synodic
    }

    public static func moonPhaseName(on date: Date) -> String {
        switch moonPhaseFraction(on: date) {
        case ..<0.03, 0.97...: return "New moon"
        case ..<0.22:          return "Waxing crescent"
        case ..<0.28:          return "First quarter"
        case ..<0.47:          return "Waxing gibbous"
        case ..<0.53:          return "Full moon"
        case ..<0.72:          return "Waning gibbous"
        case ..<0.78:          return "Last quarter"
        default:               return "Waning crescent"
        }
    }

    /// Topocentric altitude of the moon (degrees above the horizon) at `date`.
    public static func moonAltitudeDeg(at date: Date, lat: Double, lon: Double) -> Double {
        let (_, d) = dayContext(for: date)
        let ut = utHours(for: date)
        let moon = moonCoords(d)
        let sun = sunCoords(d)
        let lstDeg = sun.gmst0 + 15 * ut + lon
        let ha = rev360(lstDeg - moon.ra)
        let altGeo = asind(sind(lat) * sind(moon.dec) + cosd(lat) * cosd(moon.dec) * cosd(ha))
        // Topocentric parallax correction (the moon is close — ~1° matters at the horizon).
        let parallax = asind(1 / moon.distanceER)
        return altGeo - parallax * cosd(altGeo)
    }

    /// 0…1 measure of how present/high the moon is across [from, to] — the mean
    /// of `clamp(sin(altitude),0,1)`. 0 if the moon is below the horizon the
    /// whole window; approaches 1 only for a high moon all night. §5.3.
    public static func moonAltitudeFraction(from start: Date, to end: Date,
                                            lat: Double, lon: Double,
                                            sampleMinutes: Double = 15) -> Double {
        guard end > start else {
            return Swift.max(0, sind(moonAltitudeDeg(at: start, lat: lat, lon: lon)))
        }
        let step = sampleMinutes * 60
        var t = start.timeIntervalSince1970
        let endT = end.timeIntervalSince1970
        var sum = 0.0, n = 0.0
        while t <= endT {
            let alt = moonAltitudeDeg(at: Date(timeIntervalSince1970: t), lat: lat, lon: lon)
            sum += Swift.max(0, sind(alt))
            n += 1
            t += step
        }
        return n > 0 ? (sum / n).clamped01 : 0
    }

    /// Moonrise / moonset for the UTC day of `date` (first crossing of each),
    /// found by scanning altitude zero-crossings. For display only.
    public static func moonRiseSet(on date: Date, lat: Double, lon: Double) -> (rise: Date?, set: Date?) {
        let (dayStart, _) = dayContext(for: date)
        let step = 10.0 * 60                 // 10-minute scan
        var prevT = dayStart.timeIntervalSince1970
        var prevAlt = moonAltitudeDeg(at: Date(timeIntervalSince1970: prevT), lat: lat, lon: lon)
        var rise: Date?, set: Date?
        var t = prevT + step
        let endT = prevT + 24 * 3600
        while t <= endT {
            let alt = moonAltitudeDeg(at: Date(timeIntervalSince1970: t), lat: lat, lon: lon)
            if prevAlt < 0, alt >= 0, rise == nil {
                rise = interpolateZero(t0: prevT, a0: prevAlt, t1: t, a1: alt)
            }
            if prevAlt >= 0, alt < 0, set == nil {
                set = interpolateZero(t0: prevT, a0: prevAlt, t1: t, a1: alt)
            }
            if rise != nil, set != nil { break }
            prevT = t; prevAlt = alt; t += step
        }
        return (rise, set)
    }

    // MARK: - Sun & moon position (Schlyter)

    private struct EquatorialBody {
        let ra: Double          // right ascension, degrees
        let dec: Double         // declination, degrees
        let lon: Double         // ecliptic longitude, degrees
        let lat: Double         // ecliptic latitude, degrees
        let distanceER: Double  // geocentric distance, Earth radii
        let gmst0: Double       // sidereal time at Greenwich, 0h — degrees (sun only)
    }

    private static func sunCoords(_ d: Double) -> EquatorialBody {
        let w = 282.9404 + 4.70935e-5 * d
        let e = 0.016709 - 1.151e-9 * d
        let M = rev360(356.0470 + 0.9856002585 * d)
        let oblecl = 23.4393 - 3.563e-7 * d
        let L = rev360(w + M)
        let E = M + (180 / .pi) * e * sind(M) * (1 + e * cosd(M))
        let x = cosd(E) - e
        let y = sind(E) * (1 - e * e).squareRoot()
        let r = (x * x + y * y).squareRoot()
        let v = atan2d(y, x)
        let lon = rev360(v + w)
        let xs = r * cosd(lon), ys = r * sind(lon)
        let xe = xs
        let ye = ys * cosd(oblecl)
        let ze = ys * sind(oblecl)
        let ra = rev360(atan2d(ye, xe))
        let dec = atan2d(ze, (xe * xe + ye * ye).squareRoot())
        let gmst0 = rev360(L + 180)
        return EquatorialBody(ra: ra, dec: dec, lon: lon, lat: 0, distanceER: r, gmst0: gmst0)
    }

    private static func moonCoords(_ d: Double) -> EquatorialBody {
        let oblecl = 23.4393 - 3.563e-7 * d
        // Orbital elements.
        let N = rev360(125.1228 - 0.0529538083 * d)
        let i = 5.1454
        let w = rev360(318.0634 + 0.1643573223 * d)
        let a = 60.2666
        let e = 0.054900
        let M = rev360(115.3654 + 13.0649929509 * d)
        // Eccentric anomaly (iterate once — eccentricity is small).
        var E = M + (180 / .pi) * e * sind(M) * (1 + e * cosd(M))
        for _ in 0..<2 {
            E = E - (E - (180 / .pi) * e * sind(E) - M) / (1 - e * cosd(E))
        }
        let x = a * (cosd(E) - e)
        let y = a * (1 - e * e).squareRoot() * sind(E)
        let r0 = (x * x + y * y).squareRoot()
        let v = atan2d(y, x)
        // Ecliptic coordinates before perturbations.
        var xeclip = r0 * (cosd(N) * cosd(v + w) - sind(N) * sind(v + w) * cosd(i))
        var yeclip = r0 * (sind(N) * cosd(v + w) + cosd(N) * sind(v + w) * cosd(i))
        var zeclip = r0 * (sind(v + w) * sind(i))
        var lon = rev360(atan2d(yeclip, xeclip))
        var lat = atan2d(zeclip, (xeclip * xeclip + yeclip * yeclip).squareRoot())
        var r = r0

        // Perturbations (Schlyter's principal terms).
        let sun = sunCoords(d)
        let Ms = rev360(356.0470 + 0.9856002585 * d)       // sun mean anomaly
        let Mm = M                                          // moon mean anomaly
        let Lm = rev360(N + w + M)                          // moon mean longitude
        let Ls = sun.lon                                    // ~sun true longitude (close enough)
        let D = rev360(Lm - Ls)                             // mean elongation
        let F = rev360(Lm - N)                              // argument of latitude

        lon += -1.274 * sind(Mm - 2 * D)
        lon +=  0.658 * sind(2 * D)
        lon += -0.186 * sind(Ms)
        lon += -0.059 * sind(2 * Mm - 2 * D)
        lon += -0.057 * sind(Mm - 2 * D + Ms)
        lon +=  0.053 * sind(Mm + 2 * D)
        lon +=  0.046 * sind(2 * D - Ms)
        lon +=  0.041 * sind(Mm - Ms)
        lon += -0.035 * sind(D)
        lon += -0.031 * sind(Mm + Ms)
        lon += -0.015 * sind(2 * F - 2 * D)
        lon +=  0.011 * sind(Mm - 4 * D)

        lat += -0.173 * sind(F - 2 * D)
        lat += -0.055 * sind(Mm - F - 2 * D)
        lat += -0.046 * sind(Mm + F - 2 * D)
        lat +=  0.033 * sind(F + 2 * D)
        lat +=  0.017 * sind(2 * Mm + F)

        r += -0.58 * cosd(Mm - 2 * D)
        r += -0.46 * cosd(2 * D)

        // Recompute rectangular ecliptic with perturbed lon/lat/r.
        xeclip = r * cosd(lon) * cosd(lat)
        yeclip = r * sind(lon) * cosd(lat)
        zeclip = r * sind(lat)
        // Rotate to equatorial.
        let xe = xeclip
        let ye = yeclip * cosd(oblecl) - zeclip * sind(oblecl)
        let ze = yeclip * sind(oblecl) + zeclip * cosd(oblecl)
        let ra = rev360(atan2d(ye, xe))
        let dec = atan2d(ze, (xe * xe + ye * ye).squareRoot())
        let dist = (xe * xe + ye * ye + ze * ze).squareRoot()
        return EquatorialBody(ra: ra, dec: dec, lon: rev360(lon), lat: lat, distanceER: dist, gmst0: 0)
    }

    // MARK: - Time helpers

    private static let utcCalendar: Calendar = {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = TimeZone(identifier: "UTC")!
        return c
    }()

    /// Returns the UTC start-of-day for `date` and Schlyter's day number `d` at
    /// the exact instant of `date` (includes the UT fraction).
    private static func dayContext(for date: Date) -> (dayStart: Date, d: Double) {
        let comps = utcCalendar.dateComponents([.year, .month, .day], from: date)
        let dayStart = utcCalendar.date(from: comps) ?? date
        let ut = utHours(for: date)
        let y = comps.year ?? 2000, m = comps.month ?? 1, day = comps.day ?? 1
        // Schlyter's day number (integer divisions), epoch 2000 Jan 0.0 UT.
        let dInt = 367 * y - (7 * (y + ((m + 9) / 12))) / 4 + (275 * m) / 9 + day - 730530
        return (dayStart, Double(dInt) + ut / 24.0)
    }

    private static func utHours(for date: Date) -> Double {
        let comps = utcCalendar.dateComponents([.hour, .minute, .second, .nanosecond], from: date)
        return Double(comps.hour ?? 0)
            + Double(comps.minute ?? 0) / 60
            + Double(comps.second ?? 0) / 3600
            + Double(comps.nanosecond ?? 0) / 3_600_000_000_000
    }

    private static func dateFrom(dayStart: Date, utHours: Double) -> Date {
        Date(timeIntervalSince1970: dayStart.timeIntervalSince1970 + utHours * 3600)
    }

    private static func interpolateZero(t0: Double, a0: Double, t1: Double, a1: Double) -> Date {
        let frac = a1 == a0 ? 0 : a0 / (a0 - a1)
        return Date(timeIntervalSince1970: t0 + (t1 - t0) * frac)
    }

    // MARK: - Degree-based trig

    private static func rev360(_ x: Double) -> Double { let r = x.truncatingRemainder(dividingBy: 360); return r < 0 ? r + 360 : r }
    private static func rev24(_ x: Double) -> Double { let r = x.truncatingRemainder(dividingBy: 24); return r < 0 ? r + 24 : r }
    private static func sind(_ d: Double) -> Double { sin(d * .pi / 180) }
    private static func cosd(_ d: Double) -> Double { cos(d * .pi / 180) }
    private static func asind(_ x: Double) -> Double { asin(Swift.max(-1, Swift.min(1, x))) * 180 / .pi }
    private static func acosd(_ x: Double) -> Double { acos(Swift.max(-1, Swift.min(1, x))) * 180 / .pi }
    private static func atan2d(_ y: Double, _ x: Double) -> Double { atan2(y, x) * 180 / .pi }
}
