//
//  ForecastRainGateTests.swift
//  SectorTests
//
//  The rain rule for a night that hasn't happened yet. The old gate fed the
//  "rain falling now" measurement a whole CALENDAR DAY's forecast total, so an
//  8%-chance afternoon shower capped that night at exactly 40 — and a week with
//  four such days showed four identical 40s with no order between them.
//

import XCTest
@testable import SectorEngine

final class ForecastRainGateTests: XCTestCase {

    private func eval(_ i: ConditionsInput) -> ConditionsResult { ConditionsAggregator.evaluate(i) }

    /// A forecast night with rain only during the DAY — nothing in the fishing
    /// window — scores as the clear night it is.
    func testDaytimeRainOutsideTheWindowDoesNotGate() {
        var night = CE.input()
        night.isForecast = true
        night.forecastWindowRainIn = 0          // the day's 0.3" all fell by 4 PM
        night.forecastRainChancePct = 70
        let r = eval(night)
        XCTAssertFalse(r.isCapped)
        XCTAssertGreaterThan(r.score, 70)
    }

    /// Rain in the window but an 8% chance: the night is left alone. It still pays
    /// for the runoff through clarity, which is scored separately.
    func testUnlikelyRainDoesNotGate() {
        var night = CE.input()
        night.isForecast = true
        night.forecastWindowRainIn = 0.2
        night.forecastRainChancePct = 8
        XCTAssertFalse(eval(night).isCapped)
    }

    /// A 60% chance of 0.2" in the window holds the night back — but softly, so it
    /// doesn't land exactly on the cap.
    func testLikelyRainHoldsTheNightBackSoftly() {
        var night = CE.input()
        night.isForecast = true
        night.forecastWindowRainIn = 0.2
        night.forecastRainChancePct = 60
        let rained = eval(night)
        let dry = eval(CE.input())
        XCTAssertTrue(rained.isCapped)
        XCTAssertLessThan(rained.score, dry.score)
        XCTAssertGreaterThan(rained.score, 40)          // not pinned to the cap
        XCTAssertTrue(rained.topReasons.first?.hasPrefix("Held back:") ?? false)
        XCTAssertTrue(rained.primaryGate?.reason.contains("Rain likely in the window") ?? false)
    }

    /// Two rained-out nights keep their order instead of flattening onto one number
    /// — the whole point of the soft cap.
    func testRainedOutNightsKeepTheirOrder() {
        var good = CE.input(wind: 2, moonIllum: 0, moonAlt: 0)          // calm, dark
        good.isForecast = true
        good.forecastWindowRainIn = 0.2
        good.forecastRainChancePct = 60
        var poor = CE.input(wind: 14, moonIllum: 100, moonAlt: 0.9)     // windy, bright
        poor.isForecast = true
        poor.forecastWindowRainIn = 0.2
        poor.forecastRainChancePct = 60
        XCTAssertGreaterThan(eval(good).score, eval(poor).score)
    }

    /// A middling chance shaves the night without calling it rained out.
    func testMaybeRainSitsBetween() {
        func night(chance: Int) -> Int {
            var i = CE.input()
            i.isForecast = true
            i.forecastWindowRainIn = 0.2
            i.forecastRainChancePct = chance
            return eval(i).score
        }
        let dry = eval(CE.input()).score
        XCTAssertLessThan(night(chance: 35), dry)
        XCTAssertGreaterThan(night(chance: 35), night(chance: 60))
    }

    /// Rain measured falling right now is still a hard cap — that one is a fact,
    /// not a forecast.
    func testLiveRainStillHardCaps() {
        let r = eval(CE.input(precipNow: 0.2))
        XCTAssertTrue(r.isCapped)
        XCTAssertLessThanOrEqual(r.score, 40)
        XCTAssertTrue(r.topReasons.first?.hasPrefix("Capped:") ?? false)
    }
}
