import XCTest
@testable import SectorEngine
#if canImport(CoreLocation)
import CoreLocation
#endif

/// Clarity reads only its arm's own discharge gauge, or none (Clarity Fusion
/// Stage 1, approved 2026-09-27). Points are interior water cells of each arm.
final class ClarityGaugeTests: XCTestCase {

    private func site(_ lat: Double, _ lon: Double) -> String? {
        ClarityGauge.site(near: CLLocationCoordinate2D(latitude: lat, longitude: lon))
    }

    func testEachGaugedArmReadsItsOwnGauge() {
        XCTAssertEqual(site(34.40823, -86.21072), "03572900")     // Town Creek (Marshall)
        XCTAssertEqual(site(34.52741, -86.10789), "03572690")     // South Sauty Creek
    }

    func testNoArmBorrowsAnotherArmsGauge() {
        XCTAssertNil(site(34.34711, -86.33717))    // Browns Creek: not Town Creek's 03572900
        XCTAssertNil(site(34.41997, -86.19229))    // Minky Creek, inside Town Creek's arm: not its parent's gauge
        XCTAssertNil(site(34.46504, -86.30386))    // Jagger Branch
        XCTAssertNil(site(34.72487, -85.91902))    // Town Creek (Jackson): the other Town Creek
        XCTAssertNil(site(34.38555, -86.32488))    // the main stem
        XCTAssertNil(site(30.42, -97.93))          // a lake with no graph
    }

    private func input(nearestRise: Bool, ownRise: Bool) -> ConditionsInput {
        ConditionsInput(date: Date(), latitude: 34.35, longitude: -86.30, region: .lowerMid,
                        windMph: 4, windDirDeg: 0, airTempF: 75, cloudPct: 0, humidityPct: 50,
                        pressureInHg: 30, pressureTrend: .steady, pressureChange12hInHg: 0, weatherCode: 0,
                        cityGlowFactor: 0.2,
                        dischargeCfs: nearestRise ? 100 : nil, dischargeTrend12hCfs: nearestRise ? 100 : nil,
                        rainLast48hIn: 0, rainWatershed72hIn: 0,
                        clarityDischargeCfs: ownRise ? 100 : nil, clarityDischargeTrend12hCfs: ownRise ? 100 : nil)
    }

    /// The nearest gauge rising no longer shaves clarity; the arm's own does.
    func testOnlyTheArmsOwnGaugeShavesClarity() {
        let calm = ClarityFactor.visibilityFt(input(nearestRise: false, ownRise: false))
        XCTAssertEqual(ClarityFactor.visibilityFt(input(nearestRise: true, ownRise: false)), calm, accuracy: 1e-9)
        XCTAssertLessThan(ClarityFactor.visibilityFt(input(nearestRise: false, ownRise: true)), calm)
    }
}
