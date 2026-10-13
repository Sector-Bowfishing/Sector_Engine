//
//  GaugeClassifierTests.swift
//  SectorEngineTests
//
//  GaugeClassifier decides what water a USGS series measures from its name,
//  site type and method block. The engine used to skip that question: Lake
//  Lanier borrowed 52 °F release water from the gauge AT Buford Dam, and a creek
//  on "Suwanee Dam Road" read as a dam. The first group pins the spec's cases
//  (gauge_final.json, rule step A); the second pins real site names to the
//  answers the Python prototype gave on the 2026-09-14 USGS state IV responses,
//  so the Swift port can't drift from the validated rule.
//

import XCTest
@testable import SectorEngine

final class GaugeClassifierTests: XCTestCase {

    private func role(_ name: String, _ type: String?, _ method: String? = nil) -> GaugeRole {
        GaugeClassifier.classify(siteName: name, siteTypeCode: type, methodDescription: method).role
    }

    private func key(_ name: String, _ type: String? = "ST", _ method: String? = nil) -> [String] {
        GaugeClassifier.classify(siteName: name, siteTypeCode: type, methodDescription: method).nameKey
    }

    private func matches(_ siteName: String, _ lakeName: String) -> Bool {
        GaugeClassifier.keysMatch(key(siteName), GaugeClassifier.lakeAliases(lakeName))
    }

    // MARK: - Spec cases

    func testDamReleaseAtDam() {
        XCTAssertEqual(role("CHATTAHOOCHEE RIVER AT BUFORD DAM, NEAR BUFORD, GA", "ST"), .damRelease)
    }

    func testDamRoadIsNotADam() {
        XCTAssertEqual(role("RICHLAND CREEK AT SUWANEE DAM ROAD, NEAR BUFORD", "ST"), .tributary)
    }

    func testLakeSiteIsPoolWithKey() {
        let c = GaugeClassifier.classify(siteName: "LAKE SIDNEY LANIER NEAR BUFORD, GA",
                                         siteTypeCode: "LK", methodDescription: nil)
        XCTAssertEqual(c.role, .pool)
        XCTAssertEqual(c.nameKey, ["SIDNEY", "LANIER"])
        XCTAssertTrue(GaugeClassifier.keysMatch(c.nameKey, GaugeClassifier.lakeAliases("Lanier (Sidney Lanier)")))
    }

    func testSpringsAndWellsAreNonSurface() {
        XCTAssertEqual(role("Quapaw Spring", "SP"), .nonSurface)
        XCTAssertEqual(role("RRD PZ60 Rough River Dam Tail2-205", "GW"), .nonSurface)
    }

    func testMethodBlocksDecideHeadwaterVsTailwater() {
        XCTAssertEqual(role("Arkansas River at Murray Dam near Little Rock, AR", "ST", "HEADWATER"), .pool)
        XCTAssertEqual(role("Arkansas River at Murray Dam near Little Rock, AR", "ST", "TAILWATER"), .damRelease)
        XCTAssertEqual(role("TAYLORSVILLE LAKE NEAR TAYLORSVILLE, KY", "LK", "Tailwater"), .damRelease)
        XCTAssertEqual(role("TAYLORSVILLE LAKE NEAR TAYLORSVILLE, KY", "LK", "[Lake]"), .pool)
    }

    func testBelowWithoutDamIsRiver_andSpringRiverIsRiver() {
        XCTAssertEqual(role("Passaic River below Pompton Riv at Two Bridges", "ST"), .river)
        XCTAssertEqual(role("Spring River near Mammoth Spring, AR", "ST"), .river)
        XCTAssertEqual(role("Crooked Creek at Kelly Crossing at Yellville, AR", "ST"), .tributary)
        XCTAssertEqual(role("LAKE MOULTRIE TAILRACE NEAR PINOPOLIS, SC", "ST"), .damRelease)
    }

    func testNameKeyNormalizationMatches() {
        XCTAssertTrue(matches("TUTTLE C LK NR MANHATTAN, KS", "Tuttle Creek Lake"))
        XCTAssertTrue(matches("COEUR D ALENE LAKE AT COEUR D ALENE ID", "Coeur d&apos;Alene"))
        XCTAssertTrue(matches("Bayou Darbonne Lake at Dam near Downsville", "Lake D&apos;Arbonne"))
        XCTAssertTrue(matches("LAKE MATTAMUSKEET W OF NC HWY 94 NR FAIRFIELD, NC", "Lake Mattamuskeet"))
        XCTAssertTrue(matches("B. EVERETT JORDAN LAKE NEAR NEW HILL", "Jordan"))
    }

    func testNameKeyRejectsOtherLakes() {
        XCTAssertFalse(matches("CARTERS RE-REGULATION LAKE NEAR CARTERS, GA", "Carters"))
        XCTAssertFalse(matches("Lake Taneycomo at School of the Ozarks, MO", "Table Rock Lake"))
        XCTAssertFalse(matches("LAKE MONONA AT MADISON, WI", "Lake Mendota"))
    }

    // MARK: - Keys, aliases, tokens

    func testLakeAliasesSplitSlashesAndParentheses() {
        XCTAssertEqual(GaugeClassifier.lakeAliases("Lanier (Sidney Lanier)"), [["LANIER"], ["SIDNEY", "LANIER"]])
        XCTAssertEqual(GaugeClassifier.lakeAliases("Eufaula / W.F. George"),
                       [["EUFAULA", "GEORGE"], ["EUFAULA"], ["GEORGE"]])
        XCTAssertEqual(GaugeClassifier.lakeAliases("Clarks Hill / J.S. Thurmond"),
                       [["CLARKS", "HILL", "THURMOND"], ["CLARKS", "HILL"], ["THURMOND"]])
        // A parenthesized state code is not an alias.
        XCTAssertEqual(GaugeClassifier.lakeAliases("Big Lake (AK)"), [["BIG"]])
        XCTAssertEqual(GaugeClassifier.lakeAliases("Devil&apos;s Kitchen Lake"), [["DEVIL", "SKITCHEN"]])
        XCTAssertEqual(GaugeClassifier.lakeAliases("Grand Lake o&apos; the Cherokees"), [["GRAND", "CHEROKEES"]])
    }

    func testKeysMatchIsAnOrderedSuffix() {
        XCTAssertTrue(GaugeClassifier.keysMatch(["B", "EVERETT", "JORDAN"], ["JORDAN"]))
        XCTAssertTrue(GaugeClassifier.keysMatch(["GREEN"], ["BIG", "GREEN"]))
        XCTAssertFalse(GaugeClassifier.keysMatch(["WEST", "OKOBOJI"], ["EAST", "OKOBOJI"]))
        XCTAssertFalse(GaugeClassifier.keysMatch(["LANIER", "SIDNEY"], ["SIDNEY", "LANIER"]))
        XCTAssertFalse(GaugeClassifier.keysMatch([], ["LANIER"]), "an unnamed gauge matches no lake by name")
        XCTAssertFalse(GaugeClassifier.keysMatch(["LANIER"], [[String]]()))
    }

    func testTokensCollapseLockAndDamAndApostrophes() {
        XCTAssertEqual(GaugeClassifier.tokens("Ohio R at L & D 52"), ["OHIO", "R", "AT", "L&D", "52"])
        XCTAssertEqual(GaugeClassifier.tokens("Mississippi River at L&amp;D 10"),
                       ["MISSISSIPPI", "RIVER", "AT", "L&D", "10"])
        XCTAssertEqual(GaugeClassifier.tokens("D’Arbonne"), GaugeClassifier.tokens("D&apos;ARBONNE"))
        XCTAssertEqual(GaugeClassifier.nameKey("Mount Hope"), ["MOUNT", "HOPE"])
    }

    // MARK: - Prototype answers on real site names

    private struct Case {
        let name: String, type: String, method: String?, role: GaugeRole, key: [String]
        init(_ name: String, _ type: String, _ method: String?, _ role: GaugeRole, _ key: [String]) {
            self.name = name; self.type = type; self.method = method; self.role = role; self.key = key
        }
        init(_ name: String, _ type: String, _ role: GaugeRole, _ key: [String]) {
            self.init(name, type, nil, role, key)
        }
    }

    func testRealSiteNamesMatchPrototype() {
        let cases: [Case] = [
            // Dam release: at/below a dam, tailrace, lock, "TW".
            Case("CHATTAHOOCHEE RIVER BUFORD DAM NR BUFORD, GA", "ST", .damRelease, ["CHATTAHOOCHEE", "BUFORD"]),
            Case("White River below Bull Shoals Dam near Fairview", "ST", "[(2)]", .damRelease, ["WHITE"]),
            Case("ETOWAH RIVER ALLATOONA DAM TW, ABV CARTERSVILLE,GA", "ST", .damRelease, ["ETOWAH", "ALLATOONA"]),
            Case("CARTERS LAKE TAILRACE NEAR CARTERS, GA", "ST", .damRelease, ["CARTERS", "TAILRACE"]),
            Case("LINE CREEK BLW LAKE MCINTOSH, NR PEACHTREE CITY,GA", "ST", .damRelease, ["LINE", "CREEK"]),
            Case("Rockaway River below Reservoir at Boonton NJ", "ST", .damRelease, ["ROCKAWAY"]),
            Case("Ramapo River above dam at Pompton Lakes NJ", "LK", .damRelease, ["RAMAPO"]),
            Case("KENTUCKY RIVER AT LOCK 2 AT LOCKPORT, KY", "ST", .damRelease, ["KENTUCKY"]),
            Case("CHATTAHOOCHEE R .36 MI DS WFG DAM NR FT GAINES, GA", "ST", .damRelease, ["CHATTAHOOCHEE"]),
            Case("NF AMERICAN R A AUBURN DAM SITE NR AUBURN CA", "ST", .damRelease, ["AMERICAN"]),
            Case("E. Fk. Black R. bl Lower Taum Sauk Reservoir", "ST", .damRelease, ["EFK", "BLACK"]),
            Case("TAYLORSVILLE LAKE NEAR TAYLORSVILLE, KY", "LK", "Tailwater, [Tailwater]", .damRelease, ["TAYLORSVILLE"]),
            // Pool: LK sites and lake words, even with a dam in the name.
            Case("PHILPOTT RES AT PHILPOTT DAM NR PHILPOTT, VA", "LK", .pool, ["PHILPOTT"]),
            Case("Lake Hamilton at Carpenter Dam nr. Hot Springs, AR", "LK", .pool, ["HAMILTON"]),
            Case("Lake Taneycomo at Ozark Beach Dam, MO", "LK", .pool, ["TANEYCOMO"]),
            Case("LAKE PEACHTREE HEADWATER AT PEACHTREE CITY, GA", "LK", .pool, ["PEACHTREE", "HEADWATER"]),
            Case("CARTERS RE-REGULATION LAKE NEAR CARTERS, GA", "LK", .pool, ["CARTERS", "REGULATION"]),
            Case("Lk Maumelle Raw Water Intake nr Natural Steps,AR", "LK", .pool, ["MAUMELLE", "RAW", "WATER", "INTAKE"]),
            Case("TAYLORSVILLE LAKE NEAR TAYLORSVILLE, KY", "LK", nil, .pool, ["TAYLORSVILLE"]),
            // River: the phrase stops at a locator or a digit; "bl" without a dam is not release.
            Case("CHATTAHOOCHEE R 0.27 MI US WILLEO CR, ROSWELL, GA", "ST", .river, ["CHATTAHOOCHEE"]),
            Case("W Fk Trinity Rv at Grand Prairie, TX", "ST", .river, ["WFK", "TRINITY"]),
            Case("Trinity Rv bl Dallas, TX", "ST", .river, ["TRINITY"]),
            Case("South Fork of Little Red River near Scotland, AR", "ST", .river, ["SOUTH", "FORK", "LITTLE", "RED"]),
            Case("White River at Calico Rock, AR", "ST", "From Thermistor", .river, ["WHITE"]),
            // Tributary.
            Case("Town Br. at S Morningside at Fayetteville, AR", "ST", .tributary, ["TOWN"]),
            Case("Hot Springs Cr DS of Grand Ave at Hot Springs, AR", "ST", .tributary, ["HOT", "SPRINGS"]),
            Case("SHARP MTN CREEK AT OLD GA 5, BELOW BALL GROUND, GA", "ST", .tributary, ["SHARP", "MTN", "CREEK"]),
            Case("RUSSELL CRK 0.3 MI DS HEAD LAKE NR DAWSONVILLE, GA", "ST", "[YSI EXO]", .tributary, ["RUSSELL", "CREEK"]),
            Case("POPE BROOK TRIBUTARY (W-9), NR NORTH DANVILLE, VT", "ST", .tributary, ["POPE", "BROOK", "TRIBUTARY"]),
            // Non-surface, unknown surface, open water.
            Case("Mammoth Spring at Mammoth Spring", "SP", .nonSurface, ["MAMMOTH", "SPRING"]),
            Case("Fordyce Spr. 46 in Fordyce Bath House @ HOSP N.P.", "SP", .nonSurface, ["FORDYCE", "SPR"]),
            Case("Clark Fork ab Little Blackfoot R nr Garrison MT", "ST", .unknownSurface, ["CLARK", "FORK"]),
            Case("ARCADE C NR DEL PASO HEIGHTS CA", "ST", .unknownSurface, ["ARCADE"]),
            Case("AIW AT HIGHWAY 544 AT SOCASTEE, SC", "ST-TS", .unknownSurface, ["AIW"]),
            Case("NURSE SLOUGH A BRADMOOR ISLAND NR BIRDS LANDING CA", "ES", .openWater, ["NURSE", "SLOUGH"]),
            Case("Newark Bay at PVSC at Newark NJ", "ES", .openWater, ["NEWARK", "BAY"]),
        ]
        for c in cases {
            let got = GaugeClassifier.classify(siteName: c.name, siteTypeCode: c.type, methodDescription: c.method)
            XCTAssertEqual(got.role, c.role, c.name)
            XCTAssertEqual(got.nameKey, c.key, c.name)
        }
    }

    /// Where the spec's rule text deliberately differs from the prototype's
    /// regexes: no bare "TAIL" tail word, and one water-body phrase (with the
    /// compass+OF locator) for both role and key.
    func testSpecOverridesPrototype() {
        XCTAssertEqual(role("OTTER TAIL RIVER NEAR ELIZABETH, MN", "ST"), .river)
        XCTAssertEqual(role("EAGLE TAIL DITCH NR MAXWELL, NM", "ST-DCH"), .tributary)
        XCTAssertEqual(role("ERIE(BARGE)CANAL(W OF GENESEE R)AT ROCHESTER NY", "ST"), .tributary)
    }

    func testMissingSiteTypeIsNotRejected() {
        // NWPS readings and legacy fixtures carry no siteTypeCd.
        XCTAssertEqual(role("LAKE SIDNEY LANIER NEAR BUFORD, GA", nil), .pool)
        XCTAssertEqual(role("Arkansas River at Tulsa, OK", nil), .river)
    }
}
