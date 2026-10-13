import Foundation
import SectorEngine

func utc(_ y: Int, _ mo: Int, _ d: Int, _ h: Int = 0, _ mi: Int = 0) -> Date {
    var c = DateComponents(); c.year = y; c.month = mo; c.day = d; c.hour = h; c.minute = mi
    var cal = Calendar(identifier: .gregorian); cal.timeZone = TimeZone(identifier: "UTC")!
    return cal.date(from: c)!
}
/// Synthetic baseline: a clear, calm, dark, mid-summer southern-reservoir night (SYNTHETIC; not a real lake).
func inp(date: Date = utc(2024, 7, 15, 2), wind: Double = 2, gust: Double? = nil, waterTemp: Double? = 78, tempEst: Bool = false,
         turb: Double? = 5, hasGage: Bool? = nil, rain48: Double = 0, rainWS: Double? = nil, rainAvail: Bool = true,
         moonIllum: Double = 0, moonAlt: Double = 0, cloud: Double = 10, code: Int = 0, stageTrend: Double? = 0, resTrend: Double? = nil,
         fcDay: Int = 0, pressure: Double = 30.1, level: Bool = true) -> ConditionsInput {
    ConditionsInput(date: date, latitude: 34.4, longitude: -86.3, region: RegionResolver.region(latitude: 34.4, longitude: -86.3),
        windMph: wind, windGustMph: gust, windDirDeg: 180, airTempF: 80, cloudPct: cloud, humidityPct: 60, pressureInHg: pressure,
        pressureTrend: .steady, pressureChange12hInHg: 0, weatherCode: code, cityGlowFactor: 0.2,
        waterTempF: waterTemp, waterTempEstimated: tempEst, stageFt: level ? 10 : nil, stageTrend12hFt: level ? stageTrend : nil,
        turbidityFNU: turb, turbidityType: .unknown, rainLast48hIn: rain48, rainWatershed72hIn: rainWS, rainDataAvailable: rainAvail,
        reservoirTrend12hFt: resTrend,
        sunset: utc(2024, 7, 15, 1), sunrise: utc(2024, 7, 15, 11), civilDusk: utc(2024, 7, 15, 1, 30), astronomicalDusk: utc(2024, 7, 15, 2, 30),
        moonIllumPct: moonIllum, moonAltitudeAtWindow: moonAlt, windowStart: utc(2024, 7, 15, 2, 30), windowEnd: utc(2024, 7, 15, 9),
        hasTurbidityGage: hasGage ?? (turb != nil), forecastDayIndex: fcDay)
}
func ev(_ i: ConditionsInput) -> ConditionsResult { ConditionsAggregator.evaluate(i) }
func row(_ cols: [Any]) { print(cols.map { "\($0)" }.joined(separator: ",")) }

print("## E1 water temp sweep (live gage vs estimated), all else clear/calm/dark")
row(["tempF", "score_live", "conf_live", "gate_live", "score_est", "conf_est", "gate_est"])
for t in stride(from: 40.0, through: 95.0, by: 1.0) {
    let a = ev(inp(waterTemp: t)); let b = ev(inp(waterTemp: t, tempEst: true))
    row([t, a.score, a.confidence, a.gates.first?.cap ?? "", b.score, b.confidence, b.gates.first?.cap ?? ""])
}
print("## E2 wind sweep (gate/ceiling cliffs)")
row(["windMph", "score", "conf", "gateCap", "windFactor"])
for w in stride(from: 0.0, through: 26.0, by: 1.0) {
    let r = ev(inp(wind: w)); row([w, r.score, r.confidence, r.gates.first?.cap ?? "", r.factors.first { $0.key == .wind }?.score ?? ""])
}
print("## E3 turbidity sweep (live gage)")
row(["fnu", "score", "conf", "gateCap"])
for f in [1.0, 3, 5, 8, 12, 20, 30, 45, 60, 90, 120] { let r = ev(inp(turb: f)); row([f, r.score, r.confidence, r.gates.first?.cap ?? ""]) }
print("## E4 missing-data renormalisation: what happens to the score when a BAD factor is unknown")
row(["case", "score", "conf", "factorsPresent"])
let bad = ev(inp(waterTemp: 55, stageTrend: -1.5, resTrend: -1.5))
let noTempNoLevel = ev(inp(waterTemp: nil, stageTrend: nil, level: false))
let goodOnly = ev(inp(waterTemp: 78))
row(["cool55+falling-1.5ft", bad.score, bad.confidence, bad.factors.count])
row(["temp unknown + level unknown", noTempNoLevel.score, noTempNoLevel.confidence, noTempNoLevel.factors.count])
row(["warm78 steady", goodOnly.score, goodOnly.confidence, goodOnly.factors.count])
print("## E5 confidence vs evidence quality")
row(["case", "score", "conf", "confBand"])
let cases: [(String, ConditionsInput)] = [
  ("all measured, tonight", inp()),
  ("clarity estimated (no gage) fresh rain data", inp(turb: nil, hasGage: false, rainWS: 0.0)),
  ("clarity estimated + temp estimated", inp(waterTemp: 78, tempEst: true, turb: nil, hasGage: false, rainWS: 0.0)),
  ("clarity estimated + temp estimated + night+3", inp(waterTemp: 78, tempEst: true, turb: nil, hasGage: false, rainWS: 0.0, fcDay: 3)),
  ("no rain data at all, no gage, no temp", inp(waterTemp: nil, turb: nil, hasGage: false, rainAvail: false)),
]
for (n, i) in cases { let r = ev(i); row([n, r.score, r.confidence, r.confidenceBand]) }
print("## E6 whole-lake averaging: the same night seen at lake-point wind vs a protected-pocket wind")
row(["lakePointWind", "protectedPocketWind", "scoreLake", "scorePocket", "delta"])
for w in [6.0, 9, 12, 15, 18] { let a = ev(inp(wind: w)).score, b = ev(inp(wind: 3)).score; row([w, 3, a, b, b - a]) }
print("## E7 species invariance: score is one number; only the spawn factor touches species")
row(["date", "waterTemp", "score", "regime", "spawnSpecies"])
for (m, d) in [(3, 20), (4, 20), (5, 15), (6, 10), (7, 15), (9, 15)] {
  for t in [58.0, 66, 72, 80] { let r = ev(inp(date: utc(2024, m, d, 2), waterTemp: t)); row(["2024-\(m)-\(d)", t, r.score, r.regime, r.spawnSpeciesName ?? ""]) }
}
print("## E8 forecast-day confidence decay and score invariance")
row(["fcDay", "score", "conf"])
for d in 0...6 { let r = ev(inp(waterTemp: 78, tempEst: d > 0, fcDay: d)); row([d, r.score, r.confidence]) }
print("## E9 moon in non-spawn month")
row(["moonIllum", "moonAlt", "cloud", "score"])
for (m, a, c) in [(0.0, 0.0, 10.0), (100, 0.9, 0), (100, 0.9, 80), (50, 0.5, 20)] { row([m, a, c, ev(inp(moonIllum: m, moonAlt: a, cloud: c)).score]) }
