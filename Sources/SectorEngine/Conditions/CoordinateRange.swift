//
//  CoordinateRange.swift
//  SectorEngine
//
//  The coordinate check for `GET /conditions` and `POST /conditions/batch` (Sector_Ops #51, owner approval
//  2026-11-10 ~23:57Z). A latitude outside [-90, 90] or a longitude outside [-180, 180] is a bad request (400),
//  not "no live data" (503). NaN and infinities fail too: `Double("nan")` parses, so the route's number check
//  alone lets them through. Released apps never send such a coordinate, so the phone contract is unchanged.
//

public enum CoordinateRange {
    public static func isValid(lat: Double, lon: Double) -> Bool {
        (-90.0...90.0).contains(lat) && (-180.0...180.0).contains(lon)
    }
}
