//
//  RegionResolver.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Coarse latitude→region mapping that selects each species' spawn-calendar
//  window. Temperature gates stay the same nationwide; only the calendar shifts.
//  The arid/mountain West (timing tracks when local water crosses each
//  threshold) is split off by longitude. §9.
//

import Foundation

public enum RegionResolver: Sendable {

    public static func region(latitude: Double, longitude: Double) -> Region {
        // Interior / mountain West runs on its own clock — split it off first.
        if longitude <= -104, latitude >= 34 { return .west }
        switch latitude {
        case ..<34:    return .south
        case 34..<39:  return .lowerMid
        default:       return .north
        }
    }
}
