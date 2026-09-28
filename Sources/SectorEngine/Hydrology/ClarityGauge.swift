//
//  ClarityGauge.swift
//  Sector — the one discharge gauge clarity may read at a spot
//
//  THE ARM'S OWN GAUGE, OR NONE (Clarity Fusion Stage 1, approved 2026-09-27).
//  The clarity factor's "rising inflow" shave used the nearest USGS discharge
//  gauge by straight line, of any river: Browns Creek ran on Town Creek's gauge
//  38 km away in another arm, and Town Creek's own arm on South Sauty's. Now a
//  spot resolves through the lake's hydrologic arm graph to its arm, and only
//  that arm's USGS discharge site counts. A nested creek does not borrow its
//  parent's gauge (it measures another creek's inflow); the main stem and every
//  lake without a graph have none, so the shave does not apply there.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

enum ClarityGauge {

    /// The arm's own USGS discharge site at this spot, or nil.
    static func site(near c: CLLocationCoordinate2D) -> String? {
        guard case .arm(let id)? = Hydrology.guntersvilleGrid.membership(lat: c.latitude, lon: c.longitude),
              let arm = Hydrology.guntersville.arm(id) else { return nil }
        return arm.usgsDischargeSite
    }

    /// That gauge's latest discharge with its 12 h change (the lookback the
    /// conditions engine uses for discharge everywhere), or nil.
    static func reading(near c: CLLocationCoordinate2D) async -> WaterLevelReading? {
        guard let site = site(near: c) else { return nil }
        let readings = try? await WaterLevelService.shared.nearbyReadings(
            near: c, parameterCd: "00060", sites: site, sitesPeriod: "PT12H",
            absThreshold: 20, pctThreshold: 0.08)
        return readings?.max { $0.dateTime < $1.dateTime }
    }
}
