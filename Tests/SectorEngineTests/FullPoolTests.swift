//
//  FullPoolTests.swift
//  SectorEngineTests
//
//  Every lake carries its normal full pool, and a live pool reads against it:
//  above full is water into the flood pool, below it a drawdown. The pool and
//  the full pool have to be the SAME lake's.
//

import XCTest
@testable import SectorEngine

final class FullPoolTests: XCTestCase {

    private func dam(_ id: String, _ name: String, _ lat: Double, _ lon: Double,
                     op: GenerationOperator = .tva, lake: String? = nil) -> GenerationDam {
        GenerationDam(id: id, operatorID: op, name: name, latitude: lat, longitude: lon,
                      river: "Test", lakeNameOverride: lake)
    }

    private func generation(_ d: GenerationDam, pool: Double?) -> DamGeneration {
        DamGeneration(dam: d, distanceMiles: 1, windows: [], dischargeCfs: nil,
                      dischargeTrend12hCfs: nil, reservoirElevationFt: pool,
                      tailwaterElevationFt: nil, observedAt: nil, history: [])
    }

    private let guntersvilleDam = GenerationDam(id: "GVDA1", operatorID: .tva, name: "Guntersville Dam",
                                                latitude: 34.4211, longitude: -86.3931, river: "Tennessee")

    /// A dam finds the lake it holds back by name — including a lake the
    /// directory lists under two names — and never the one next door.
    func testADamFindsItsOwnLake() {
        XCTAssertEqual(LakeDirectory.impounded(by: guntersvilleDam)?.id, "Guntersville|AL")
        // TVA calls it Wolf Creek Dam; the lake is Lake Cumberland.
        XCTAssertEqual(LakeDirectory.impounded(by: dam("WLCK2", "Wolf Creek Dam", 36.8689, -85.1458))?.id,
                       "Lake Cumberland|KY")
        // Kentucky and Barkley dams stand two miles apart: each gets its own lake.
        XCTAssertEqual(LakeDirectory.impounded(by: dam("KYDK2", "Kentucky Dam", 37.0144, -88.2678))?.id,
                       "Kentucky Lake|KY")
        XCTAssertEqual(LakeDirectory.impounded(by: dam("BARK2", "Barkley Dam", 37.0244, -88.2228))?.id,
                       "Lake Barkley|KY")
        // Alabama Power's "Smith Lake" is the directory's "Smith (Lewis Smith)".
        XCTAssertEqual(LakeDirectory.impounded(by: dam("SMITH", "Smith", 33.9423, -87.1072,
                                                       op: .apc, lake: "Smith Lake"))?.id,
                       "Smith (Lewis Smith)|AL")
        // A flume diversion with no reservoir has no lake.
        XCTAssertNil(LakeDirectory.impounded(by: dam("OCBT1", "Ocoee No. 2 Dam", 35.095, -84.5347)))
    }

    /// The full pool rides along only with a pool reading from that lake.
    func testTheFullPoolComesWithThePool() throws {
        XCTAssertEqual(generation(guntersvilleDam, pool: 594.2).fullPoolFt, 595)
        XCTAssertNil(generation(guntersvilleDam, pool: nil).fullPoolFt, "no pool reading, nothing to compare")
        XCTAssertNil(generation(guntersvilleDam, pool: 181.4).fullPoolFt,
                     "a pool in metres is not a 414 ft drawdown")
        // A natural lake has a usual surface, not a pool anyone holds.
        let natural = try XCTUnwrap(LakeDirectory.all.first { $0.poolBasis == .naturalSurface && $0.fullPoolFt != nil })
        let onNatural = dam("N", natural.name, natural.lat, natural.lon, op: .usace, lake: natural.name)
        XCTAssertNil(generation(onNatural, pool: natural.fullPoolFt).fullPoolFt)
        // An unverified full pool is kept as a reference but never makes a claim.
        let unsourced = try XCTUnwrap(LakeDirectory.all.first {
            $0.poolBasis == .fullPool && $0.poolConfidence == .low && $0.fullPoolFt != nil })
        let onUnsourced = dam("U", unsourced.name, unsourced.lat, unsourced.lon, op: .usace, lake: unsourced.name)
        XCTAssertNil(generation(onUnsourced, pool: unsourced.fullPoolFt).fullPoolFt, unsourced.id)
    }

    /// The level factor says where the pool sits against full; its label is
    /// still the pool itself, and its score still follows the trend.
    func testTheLevelFactorSaysFloodedOrDrawnDown() throws {
        let plain = try XCTUnwrap(WaterLevelFactor.score(CE.input(reservoirElev: 597.3, reservoirTrend: 0.4)))
        var input = CE.input(reservoirElev: 597.3, reservoirTrend: 0.4)
        input.fullPoolFt = 595
        let f = try XCTUnwrap(WaterLevelFactor.score(input))
        XCTAssertEqual(f.label, "597.30 ft")
        XCTAssertEqual(f.score, plain.score)
        XCTAssertTrue(f.why.hasSuffix(" · 2.3 ft above full pool"), f.why)
        XCTAssertFalse(plain.why.contains("full pool"), "no full pool on file, no claim about it")

        XCTAssertEqual(WaterLevelFactor.poolRelation(pool: 594.7, full: 595), "at full pool")
        XCTAssertEqual(WaterLevelFactor.poolRelation(pool: 587, full: 595), "8.0 ft below full pool")
    }
}
