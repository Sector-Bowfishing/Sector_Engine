//
//  ConditionsGates.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Gates / vetoes (§6). A great score on a night you literally can't fish
//  destroys trust, so these hard caps are applied AFTER the weighted blend and
//  cap the final score regardless of how good the other factors look. The
//  binding gate is surfaced as the top "why".
//

import Foundation

public enum ConditionsGates: Sendable {

    public static func evaluate(_ input: ConditionsInput,
                                config: ConditionsConfig = .default,
                                generationLevel: GenerationLevel?) -> [GateHit] {
        let g = config.gates
        var hits: [GateHit] = []

        let vis = ClarityFactor.visibilityFt(input, config: config)
        if vis < g.blownOutVisibilityFt {
            hits.append(GateHit(reason: "Water blown out — \(String(format: "%.1f", vis)) ft visibility",
                                cap: Int(g.blownOutCap)))
        }
        if input.windMph > g.highWindMph {
            hits.append(GateHit(reason: "High wind — \(Int(input.windMph.rounded())) mph",
                                cap: Int(g.highWindCap)))
        }
        if input.isTailwater, generationLevel == .high {
            hits.append(GateHit(reason: "Heavy dam generation across the window",
                                cap: Int(g.tailwaterHighGenCap)))
        }
        // Cold water pushes rough fish deep and inactive — nothing shallow to
        // shoot. A LIVE gage caps hard at the real threshold. A gage-less lake
        // scores off a MODELED/air estimate, so it gets its own COLDER trigger and
        // a SOFTER cap: a guess shouldn't hard-cap a night, but a clearly-cold
        // estimate must not read Prime (the old live-only gate let a 40°F winter
        // night blend to green on the many lakes with no temp gage). §6.
        if let wt = input.waterTempF {
            if !input.waterTempEstimated, wt < g.coldWaterF {
                hits.append(GateHit(reason: "Water too cold — \(Int(wt.rounded()))°F, no target species active",
                                    cap: Int(g.coldWaterCap)))
            } else if input.waterTempEstimated, wt < g.coldWaterEstimatedF {
                hits.append(GateHit(reason: "Water likely cold — ~\(Int(wt.rounded()))°F estimated, few fish shallow",
                                    cap: Int(g.coldWaterEstimatedCap)))
            }
        }
        // Storm gate requires corroboration — never trust the categorical code
        // alone (it over-reports storms on clear, dry nights).
        if g.stormWeatherCodes.contains(input.weatherCode),
           input.precipitationInchNow >= g.stormMinPrecipInch || input.cloudPct >= g.stormMinCloudPct {
            hits.append(GateHit(reason: "Thunderstorms",
                                cap: Int(g.stormCap)))
        }
        // Active NWS safety WARNING — the authoritative real-time catch. The
        // forecast-only storm gate above missed the case that started all this: a
        // squall line overhead while the model still read "winding down, dry", so
        // the night scored Prime. A human meteorologist issuing a warning is the
        // signal that survives the model miss, so cap hard whenever one is active.
        if let label = input.severeWarningLabel {
            hits.append(GateHit(reason: "\(label) — stay off the water",
                                cap: Int(g.severeWarningCap)))
        }
        // Rain measurably falling NOW, independent of the categorical code — the
        // code often mislabels active rain (or lags it), so cap on the measured
        // current precip too, not just a 95/96/99 storm code.
        if input.precipitationInchNow >= g.rainNowInch {
            hits.append(GateHit(reason: "Rain falling now — \(String(format: "%.2f", input.precipitationInchNow))\"",
                                cap: Int(g.rainNowCap)))
        }
        // Fog on the water — the "you can't fish this" signal that isn't weather-violent.
        // Fog is already a low-weight factor (HumidityFactor, 0.03), but it ENDS the night
        // (no sightlines, can't run the boat), so it also gates. Uses the forecast
        // air–dewpoint spread (the fog predictor); graduated so a tight spread caps hard
        // and a moderate spread soft-caps. Only fires when a dewpoint series exists.
        if let spread = input.fogSpreadF {
            if spread < g.fogLikelySpreadF {
                hits.append(GateHit(reason: "Fog likely — forms on the water, can't shoot or run the boat",
                                    cap: Int(g.fogLikelyCap)))
            } else if spread < g.fogPatchySpreadF {
                hits.append(GateHit(reason: "Patchy fog possible late — can't read Prime",
                                    cap: Int(g.fogPatchyCap)))
            }
        }
        return hits
    }
}
