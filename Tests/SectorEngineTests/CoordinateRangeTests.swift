//
//  CoordinateRangeTests.swift
//  SectorEngineTests
//
//  `GET /conditions` and `POST /conditions/batch` answer 400 for an out-of-range coordinate (Sector_Ops #51). The
//  deploy smoke (`/conditions?lat=95&lon=0` must return 400) checks the route end to end; this checks the rule.
//

import XCTest
@testable import SectorEngine

final class CoordinateRangeTests: XCTestCase {

    func testInRangeCoordinatesAreValid() {
        XCTAssertTrue(CoordinateRange.isValid(lat: 34.4, lon: -86.3))      // Guntersville
        XCTAssertTrue(CoordinateRange.isValid(lat: 0, lon: 0))
        XCTAssertTrue(CoordinateRange.isValid(lat: 90, lon: 180))          // bounds are inclusive
        XCTAssertTrue(CoordinateRange.isValid(lat: -90, lon: -180))
    }

    func testOutOfRangeLatitudeIsInvalid() {
        XCTAssertFalse(CoordinateRange.isValid(lat: 95, lon: 0))           // the deploy smoke's request
        XCTAssertFalse(CoordinateRange.isValid(lat: -90.0001, lon: 0))
        XCTAssertFalse(CoordinateRange.isValid(lat: 90.0001, lon: 0))
    }

    func testOutOfRangeLongitudeIsInvalid() {
        XCTAssertFalse(CoordinateRange.isValid(lat: 0, lon: 180.0001))
        XCTAssertFalse(CoordinateRange.isValid(lat: 0, lon: -181))
        XCTAssertFalse(CoordinateRange.isValid(lat: 0, lon: 360))
    }

    func testNonFiniteValuesAreInvalid() {
        XCTAssertFalse(CoordinateRange.isValid(lat: .nan, lon: 0))
        XCTAssertFalse(CoordinateRange.isValid(lat: 0, lon: .nan))
        XCTAssertFalse(CoordinateRange.isValid(lat: .infinity, lon: 0))
        XCTAssertFalse(CoordinateRange.isValid(lat: 0, lon: -.infinity))
        XCTAssertFalse(CoordinateRange.isValid(lat: Double("nan")!, lon: 0))   // what the route's parse accepts
    }
}
