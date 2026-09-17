//
//  WhereToLookEngine.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Composes 2–4 contextual "where to look" cards from the active signals, in
//  bowfishing priority order (§10): spawn → clarity → current (tailwater) → water
//  temp → moon → wind → level. Everything is framed for SIGHT-SHOOTING — finding
//  fish you can see and reach in the shallows — not bait or the bite. The closing
//  "look for life" line is preserved.
//

import Foundation

public enum WhereToLookEngine {

    public static let closingLine =
        "Look for shad flickers, gar rolling, rising bubbles and mud puffs — then stay on that life."

    public static func cards(_ input: ConditionsInput,
                             regime: ConditionsRegime,
                             spawn: SpawnResult?,
                             generationLevel: GenerationLevel?) -> [WhereToLookCard] {
        var cards: [WhereToLookCard] = []

        // 1) Spawn card (only in spawn regime, with a real legal contributor).
        if regime == .spawn, let species = spawn?.species {
            var body = species.habitat.prefix(1).capitalized + species.habitat.dropFirst() + "."
            if spawn?.needsDisclaimer == true { body += " " + SpeciesLegality.disclaimer }
            cards.append(WhereToLookCard(
                kind: .spawn,
                title: (spawn?.isStaging == true ? "\(species.name) staging" : "\(species.name) spawn on"),
                body: String(body)))
        }

        // 2) Clarity — the MASTER factor. When it's the limiter, "where's the
        //    shootable water" is the most useful thing on the screen.
        if let clarity = clarityCard(input) { cards.append(clarity) }

        // 3) Current card (tailwater).
        if input.isTailwater {
            switch generationLevel ?? .low {
            case .low:
                cards.append(WhereToLookCard(
                    kind: .current, title: "Settled water — fish roaming",
                    body: "Little current — fish roam the shallows. Hunt food and warmth, not current: mud flats, grass lines, coves, riprap and scum lines."))
            case .moderate, .high:
                cards.append(WhereToLookCard(
                    kind: .current, title: "Generators running — fish on the seams",
                    body: "Current is pushing — fish pin to current seams, eddies behind structure and slack pockets. Shoot the slick edge where smooth water meets the ripple."))
            }
        }

        // 4) Water temp — cold pulls fish OFF the shallow flats; heat sends them to
        //    cooler, moving water. Both change WHERE the shootable fish are.
        if let temp = tempCard(input) { cards.append(temp) }

        // 5) Moonlight — a bright, high moon changes the approach.
        if let moon = moonCard(input) { cards.append(moon) }

        // 6) Wind card.
        cards.append(windCard(input))

        // 7) Level card. Prefer the reservoir pool trend on a lake (the water you're
        //    on), fall back to the river-stage gage — same source the level factor uses.
        if let delta = (input.isTailwater ? nil : input.reservoirTrend12hFt) ?? input.stageTrend12hFt {
            if delta > input.windowQuietBand {
                cards.append(WhereToLookCard(
                    kind: .level, title: "Rising water — hit fresh cover",
                    body: "Push into newly flooded grass and timber edges — fish move up fast onto fresh forage."))
            } else if delta < -input.windowQuietBand {
                cards.append(WhereToLookCard(
                    kind: .level, title: "Flats thinning — work the outer edge",
                    body: "Fish are sliding off the shallow flats and out of range. Work the OUTER edge of the grass and the first drop, not the very back of the flat — that's the first water they leave."))
            }
        }

        // Keep it to the top 4 by the priority order above.
        return Array(cards.prefix(4))
    }

    /// Clarity is what you can shoot through. Fires only when it's actionable —
    /// muddy (go hunt clear water) or gin-clear (fish spook, ease in).
    private static func clarityCard(_ input: ConditionsInput) -> WhereToLookCard? {
        let vis = ClarityFactor.visibilityFt(input)
        if vis < 2.5 {
            return WhereToLookCard(kind: .clarity, title: "Muddy water — hunt the clear edges",
                body: "You can only shoot what you can see. Find the clearest water on the lake: wind-sheltered lee pockets, the clean side of a mud line, and creek or spring mouths still running clear. Skip the chocolate-milk backs of the coves.")
        }
        if vis > 12, input.windMph <= 3 {
            return WhereToLookCard(kind: .clarity, title: "Gin-clear — ease in slow",
                body: "Fish see you coming in water this clean. Drift instead of running the motor, keep the big lights off until you're set, and work shade lines, lightly stained edges and any surface chop that breaks the glare.")
        }
        return nil
    }

    /// Water temperature decides depth. Cold pulls rough fish off the flats;
    /// heat pushes them to cooler, oxygenated water.
    private static func tempCard(_ input: ConditionsInput) -> WhereToLookCard? {
        guard let t = input.waterTempF else { return nil }
        if t < 58 {
            return WhereToLookCard(kind: .temp, title: "Cold water — drop to the edges",
                body: "Rough fish have pulled off the shallow flats. Work the first drop, channel edges and heat-holding riprap — and check any warm-water discharge, spring or creek mouth, where they'll stack in the warmest water they can find.")
        }
        if t > 86 {
            return WhereToLookCard(kind: .temp, title: "Hot water — find cooler, moving water",
                body: "In the heat fish slide off the baked flats. Work shade, deeper cuts, current seams and wind-blown or inflowing water — anywhere it runs cooler and better oxygenated.")
        }
        return nil
    }

    /// A bright, high, uncovered moon puts fish on edge in the open — send them
    /// to shade. Only fires when the moon is actually lighting the water.
    private static func moonCard(_ input: ConditionsInput) -> WhereToLookCard? {
        guard input.moonIllumPct >= 55, input.moonAltitudeAtWindow >= 0.25,
              input.cloudPct < 60 else { return nil }
        return WhereToLookCard(kind: .darkness, title: "Bright moon — work the shade",
            body: "Moonlight makes fish jumpy in the open. Stay tight to shade — bank lines, under docks, overhanging timber and the dark side of points — where your lights, not the moon, light the water.")
    }

    private static func windCard(_ input: ConditionsInput) -> WhereToLookCard {
        let dir = compass(input.windDirDeg)
        switch input.windMph {
        case ..<4:
            return WhereToLookCard(kind: .wind, title: "Slick calm — cover water",
                body: "No wind to break the glare or move shad — fish scattered, and slick water gives you no cover on the approach. Cover water and watch for surface life.")
        case ..<11:
            return WhereToLookCard(kind: .wind, title: "Go to the calm side (\(dir) wind)",
                body: "Wind's out of the \(dir), so the upwind \(dir) shore stays glassy — short fetch, no chop. The downwind bank is where the waves build and stir the shallows muddy. You shoot THROUGH the surface, so glass beats everything: fish the calm side and skip the windward chop.")
        default:
            return WhereToLookCard(kind: .wind, title: "Get protected (\(dir) wind)",
                body: "Wind is wrecking the sightline. Fish only the calm, upwind shorelines, behind islands and short-fetch pockets where the surface still lays down flat enough to shoot through.")
        }
    }

    private static func compass(_ deg: Int) -> String {
        let points = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
        let normalized = (Double(deg).truncatingRemainder(dividingBy: 360) + 360).truncatingRemainder(dividingBy: 360)
        return points[Int((normalized / 22.5).rounded()) % points.count]
    }
}

private extension ConditionsInput {
    /// Small dead-band so a flat stage trend doesn't trigger a level card.
    var windowQuietBand: Double { 0.2 }
}
