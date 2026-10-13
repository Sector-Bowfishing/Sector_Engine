import XCTest
@testable import SectorEngine

/// The hydrology/clarity bucket slug must be the one lake-key algorithm the writing job uses.
final class LakeSurfaceSlugTests: XCTestCase {
    func testSlugIsTheCanonicalLakeKey() {
        XCTAssertEqual(LakeSurfaceBucket.slug("Guntersville|AL"), "Guntersville_AL")
        XCTAssertEqual(LakeSurfaceBucket.slug("Big Lake|AK"), "Big_Lake_AK")          // was "Big Lake_AK"
        XCTAssertEqual(LakeSurfaceBucket.slug("Lake O' the Pines|TX"), "Lake_O_the_Pines_TX")
        for lake in LakeDirectory.all { XCTAssertEqual(LakeSurfaceBucket.slug(lake.id), BrainPlatform.lakeKey(lake.id)) }
    }
}
