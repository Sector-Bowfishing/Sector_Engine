//
//  MoonSpecTests.swift
//  SectorEngineTests
//
//  Sector_Ops #53 Step 0.3: Moon Phase is a class 3 tile (computed in the app). One spec, contracts/moon/moon-v1.json,
//  holds the algorithm and shared test vectors that iOS, Android, Web and the Engine (darkness factor and the
//  /conditions `moonIllumination` field) must all pass, so the four copies cannot drift apart.
//
//  The Engine is the reference. Regenerate the vectors only for a deliberate algorithm change:
//      SECTOR_UPDATE_GOLDEN=1 swift test --filter MoonSpecTests
//  and then every app must pass the new vectors before it ships.
//

import XCTest
@testable import SectorEngine

final class MoonSpecTests: XCTestCase {

    private static let specURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        .appendingPathComponent("contracts/moon/moon-v1.json")

    private static let synodic = 29.530588853
    private static let knownNewMoon = 947182440.0   // 2000-01-06 18:14 UTC

    /// Fixed instants: every 3 days from 2026-11-01 for 60 days at 03:00Z (evening in US time zones), plus one minute
    /// either side of every phase-name boundary in synodic cycles 333 and 334 (about 2026-12-02 to 2027-01-30), where
    /// implementations disagree first.
    private static func instants() -> [Double] {
        var out: [Double] = []
        let start = 1793502000.0   // 2026-11-01T03:00:00Z
        for i in 0..<20 { out.append(start + Double(i) * 3 * 86_400) }
        let bounds = [0.03, 0.22, 0.28, 0.47, 0.53, 0.72, 0.78, 0.97]
        for cycle in [333.0, 334.0] {
            for b in bounds {
                let t = knownNewMoon + (cycle + b) * synodic * 86_400
                out.append((t - 60).rounded())
                out.append((t + 60).rounded())
            }
        }
        return out.sorted()
    }

    private static func iso(_ t: Double) -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f.string(from: Date(timeIntervalSince1970: t))
    }

    private static func round6(_ x: Double) -> Double { (x * 1_000_000).rounded() / 1_000_000 }

    private func vectors() -> [[String: Any]] {
        Self.instants().map { t in
            let d = Date(timeIntervalSince1970: t)
            return ["at": Self.iso(t), "epochSeconds": Int(t),
                    "illumination": Self.round6(Astronomy.moonIllumination(on: d)),
                    "phaseFraction": Self.round6(Astronomy.moonPhaseFraction(on: d)),
                    "phaseName": Astronomy.moonPhaseName(on: d)]
        }
    }

    func testEngineMatchesMoonSpec() throws {
        if ProcessInfo.processInfo.environment["SECTOR_UPDATE_GOLDEN"] == "1" {
            var spec = (try? JSONSerialization.jsonObject(with: Data(contentsOf: Self.specURL)) as? [String: Any]) ?? [:]
            spec["vectors"] = vectors()
            let data = try JSONSerialization.data(withJSONObject: spec, options: [.sortedKeys, .prettyPrinted, .withoutEscapingSlashes])
            try (data + Data("\n".utf8)).write(to: Self.specURL)
            return
        }
        let spec = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: Self.specURL)) as? [String: Any])
        let tol = try XCTUnwrap(spec["tolerance"] as? [String: Any])
        let illumTol = try XCTUnwrap((tol["illumination"] as? NSNumber)?.doubleValue)
        let fracTol = try XCTUnwrap((tol["phaseFraction"] as? NSNumber)?.doubleValue)
        let vs = try XCTUnwrap(spec["vectors"] as? [[String: Any]])
        XCTAssertGreaterThanOrEqual(vs.count, 40)
        for v in vs {
            let t = Double(try XCTUnwrap((v["epochSeconds"] as? NSNumber)?.intValue))
            let d = Date(timeIntervalSince1970: t)
            let at = v["at"] as? String ?? "?"
            XCTAssertEqual(Astronomy.moonIllumination(on: d), try XCTUnwrap((v["illumination"] as? NSNumber)?.doubleValue),
                           accuracy: illumTol, "illumination at \(at)")
            XCTAssertEqual(Astronomy.moonPhaseFraction(on: d), try XCTUnwrap((v["phaseFraction"] as? NSNumber)?.doubleValue),
                           accuracy: fracTol, "phaseFraction at \(at)")
            XCTAssertEqual(Astronomy.moonPhaseName(on: d), v["phaseName"] as? String, "phaseName at \(at)")
        }
    }
}
