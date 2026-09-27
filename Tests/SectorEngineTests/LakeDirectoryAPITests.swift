//
//  LakeDirectoryAPITests.swift
//  SectorEngineTests
//
//  `GET /lakes` serves the directory the apps now take as their lake list: every
//  lake, in the shape the apps read, under a version that moves only when a
//  lake does.
//

import XCTest
@testable import SectorEngine

final class LakeDirectoryAPITests: XCTestCase {

    func testServesEveryLakeOnce() {
        let r = SectorEngineAPI.lakeDirectory.response
        XCTAssertEqual(r.count, LakeDirectory.all.count)
        XCTAssertEqual(r.lakes.count, r.count)
        XCTAssertGreaterThan(r.count, 600, "the directory lost lakes")
        XCTAssertEqual(Set(r.lakes.map(\.id)).count, r.count, "a lake is listed twice")
    }

    func testALakeKeepsItsFields() throws {
        let r = SectorEngineAPI.lakeDirectory.response
        let g = try XCTUnwrap(r.lakes.first { $0.id == "Guntersville|AL" })
        XCTAssertEqual(g.name, "Guntersville")
        XCTAssertEqual(g.states, ["AL"])
        XCTAssertEqual(g.lat, 34.42, accuracy: 1e-9)
        XCTAssertEqual(g.lon, -86.26, accuracy: 1e-9)
        XCTAssertTrue(g.hasDam)
        XCTAssertEqual(g.operatorName, "TVA")
        XCTAssertEqual(g.apiLevel, "dedicated")
        XCTAssertNil(g.cwmsOffice)
        // TVA's top of the summer operating zone — not the sheet's 595.44, which
        // is top of gates and would read a full lake as 0.4 ft low.
        XCTAssertEqual(g.fullPoolFt, 595)
        XCTAssertEqual(g.poolBasis, "fullPool")
        XCTAssertEqual(g.poolConfidence, "high")
        // A lake on a state line is one entry carrying every state.
        let pickwick = try XCTUnwrap(r.lakes.first { $0.name.hasPrefix("Pickwick") })
        XCTAssertGreaterThan(pickwick.states.count, 1)
    }

    /// The body is what the apps parse: the same lakes, and a null — not a
    /// missing key — where a lake has no CWMS office.
    func testTheBodyDecodesToTheSameList() throws {
        let d = SectorEngineAPI.lakeDirectory
        let decoded = try JSONDecoder().decode(LakeDirectoryResponse.self, from: d.body)
        XCTAssertEqual(decoded, d.response)
        let json = try XCTUnwrap(String(data: d.body, encoding: .utf8))
        XCTAssertTrue(json.contains("\"cwmsOffice\":null"), "nil offices are left out of the JSON")
        XCTAssertTrue(json.contains("\"cwmsOffice\":\"SAM\""))
    }

    /// Every lake carries a full pool — the operator's normal pool, never top
    /// of gates — except the few the research found no figure for at all.
    func testEveryLakeHasAFullPool() throws {
        let lakes = SectorEngineAPI.lakeDirectory.response.lakes
        let missing = lakes.filter { $0.fullPoolFt == nil }
        // 13 on 2026-09-26, each documented in full_pool.csv; a jump means the
        // column went missing, not that 50 lakes lost their dams.
        XCTAssertLessThan(missing.count, 20, "no full pool for \(missing.map(\.id))")
        for l in lakes {
            XCTAssertEqual(l.poolBasis == nil, l.fullPoolFt == nil, l.id)
            XCTAssertEqual(l.poolConfidence == nil, l.fullPoolFt == nil, l.id)
        }
        let byID = Dictionary(uniqueKeysWithValues: lakes.map { ($0.id, $0) })
        // TVA tributaries fill to their June target, far under top of gates.
        XCTAssertEqual(byID["Fontana Lake|NC"]?.fullPoolFt, 1703)
        XCTAssertEqual(byID["Douglas Lake|TN"]?.fullPoolFt, 993.88)
        // A Corps flood-control lake's full pool is its SUMMER pool (the top of
        // its guide curve), not the winter conservation pool.
        XCTAssertEqual(byID["Grenada Lake|MS"]?.fullPoolFt, 215)
    }

    /// The version is a digest of the lakes: the same list gives the same
    /// version, and one changed lake gives a different one.
    func testTheVersionFollowsTheLakes() throws {
        let r = SectorEngineAPI.lakeDirectory.response
        XCTAssertEqual(r.version.count, 16)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        let same = try encoder.encode(r.lakes)
        XCTAssertEqual(SectorEngineAPI.fnv1a64Hex(same), r.version)
        var changed = r.lakes
        let first = changed[0]
        changed[0] = LakeDTO(id: first.id, name: first.name + " Lake", state: first.state,
                             states: first.states, lat: first.lat, lon: first.lon,
                             hasDam: first.hasDam, operatorName: first.operatorName,
                             apiLevel: first.apiLevel, usgsGage: first.usgsGage,
                             tempSource: first.tempSource, cwmsOffice: first.cwmsOffice,
                             fullPoolFt: first.fullPoolFt, poolBasis: first.poolBasis,
                             poolConfidence: first.poolConfidence)
        XCTAssertNotEqual(SectorEngineAPI.fnv1a64Hex(try encoder.encode(changed)), r.version)
    }
}
