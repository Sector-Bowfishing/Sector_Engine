//
//  LakeLevelFeedsUSGSStage.swift
//  Sector — Lake Brain: USGS gage height (00065) at a lake site turned into a lake elevation with the site's published altitude
//
//  A gage height is a stage above the gage's own datum, not an elevation (`usgs` refuses it). It becomes one only by adding the
//  altitude of that gage datum, which USGS publishes per site in the site service (`alt_va`, in the vertical datum `alt_datum_cd`).
//  This client reads that altitude at run time and:
//    • refuses when the site publishes no altitude or no altitude datum;
//    • refuses when the datum is not the one the binding names (`series`, e.g. `NAVD88`): USGS has been moving gages from NGVD29
//      to NAVD88, and a silent datum change would step the series by the NGVD29 → NAVD88 shift;
//    • refuses gage height that is not in feet.
//  The site record is read once per site per 15 minutes (one site-service GET per site and run).
//
//  Legacy WaterServices (`/nwis/site/`, `/nwis/iv/`, `/nwis/dv/`) is the same service the `usgs` provider already reads.
//

import Foundation

/// The altitude USGS publishes for a site's gage datum.
struct USGSSiteDatum: Equatable, Sendable {
    var site: String
    var name: String?
    /// `site_tp_cd` (`LK` lake / reservoir / impoundment, `ST` stream, ...). Informational: the binding review establishes on-lake.
    var siteType: String?
    var altitudeFt: Double
    var accuracyFt: Double?
    var datum: String
}

enum USGSSiteDatumResult: Equatable, Sendable {
    case ok(USGSSiteDatum)
    case refused(String)
}

/// Run-scoped cache of site records; concurrent callers join the same fetch.
actor USGSSiteCache {
    private var inflight: [String: Task<USGSSiteDatumResult, Never>] = [:]
    private var done: [String: (at: Date, value: USGSSiteDatumResult)] = [:]
    private let ttl: TimeInterval
    init(ttl: TimeInterval = 15 * 60) { self.ttl = ttl }

    func site(_ site: String, fetch: @escaping @Sendable (String) async -> USGSSiteDatumResult) async -> USGSSiteDatumResult {
        if let d = done[site], Date().timeIntervalSince(d.at) < ttl { return d.value }
        if let t = inflight[site] { return await t.value }
        let t = Task { await fetch(site) }
        inflight[site] = t
        let v = await t.value
        inflight[site] = nil
        done[site] = (Date(), v)
        return v
    }
}

struct LakeUSGSStageClient: Sendable {
    static let gageHeight = "00065"
    static let siteBase = "https://waterservices.usgs.gov/nwis/site/"

    var fetch: @Sendable (_ url: String, _ accept: String) async -> LakeFeedHTTP.Response?
    var cache: USGSSiteCache
    /// Which USGS API this reader uses (`LAKE_USGS_API`; LakeLevelFeedsUSGSWaterData.swift). `legacy` unless `live()` reads otherwise.
    var mode: LakeUSGSAPIMode = .legacy
    var waterData: LakeUSGSWaterDataClient = .live()
    /// Site records from `monitoring-locations` (v1), kept apart from the legacy site-service records.
    var v1Cache = USGSSiteCache()
    var shadowLog: @Sendable (String) -> Void = { print($0) }

    static func live() -> LakeUSGSStageClient {
        LakeUSGSStageClient(fetch: { url, accept in await LakeFeedHTTP.get(url, accept: accept, timeout: 60) }, cache: USGSSiteCache(),
                            mode: .fromEnvironment())
    }

    static func isSiteNumber(_ s: String) -> Bool { (8...15).contains(s.count) && s.allSatisfy { $0.isASCII && $0.isNumber } }

    // MARK: site altitude

    /// The site service's tab-separated RDB (`siteOutput=expanded`): `#` comments, a header row, a field-width row, data rows.
    static func parseSiteRDB(_ data: Data, site: String) -> USGSSiteDatumResult {
        let lines = String(decoding: data, as: UTF8.self).split(whereSeparator: \.isNewline).map(String.init).filter { !$0.hasPrefix("#") }
        guard lines.count >= 3 else { return .refused("USGS \(site): site record not found") }
        let cols = lines[0].split(separator: "\t", omittingEmptySubsequences: false).map { $0.trimmingCharacters(in: .whitespaces) }
        func idx(_ n: String) -> Int? { cols.firstIndex(of: n) }
        guard let siteI = idx("site_no"), let altI = idx("alt_va"), let datumI = idx("alt_datum_cd") else {
            return .refused("USGS \(site): site record has no alt_va / alt_datum_cd columns")
        }
        for line in lines.dropFirst(2) {
            let c = line.split(separator: "\t", omittingEmptySubsequences: false).map { $0.trimmingCharacters(in: .whitespaces) }
            guard c.count > max(siteI, altI, datumI), c[siteI] == site else { continue }
            func field(_ n: String) -> String? { idx(n).flatMap { $0 < c.count && !c[$0].isEmpty ? c[$0] : nil } }
            guard let alt = Double(c[altI]), alt.isFinite else { return .refused("USGS \(site): no published altitude (alt_va); gage height is not an elevation") }
            let datum = c[datumI]
            guard !datum.isEmpty else { return .refused("USGS \(site): altitude \(c[altI]) has no published datum (alt_datum_cd)") }
            return .ok(USGSSiteDatum(site: site, name: field("station_nm"), siteType: field("site_tp_cd"), altitudeFt: alt,
                                     accuracyFt: field("alt_acy_va").flatMap(Double.init), datum: datum))
        }
        return .refused("USGS \(site): site record not found")
    }

    func siteDatum(_ site: String) async -> USGSSiteDatumResult {
        let fetch = self.fetch
        return await cache.site(site) { s in
            let url = "\(Self.siteBase)?format=rdb&sites=\(s)&siteOutput=expanded&siteStatus=all"
            guard let r = await fetch(url, "text/plain") else { return .refused("USGS \(s): site service unreachable") }
            guard r.isSuccess else { return .refused("USGS \(s): site service HTTP \(r.status)") }
            return Self.parseSiteRDB(r.body, site: s)
        }
    }

    /// The site record from `monitoring-locations` (v1), read once per site per 15 minutes.
    func siteDatumV1(_ site: String) async -> USGSSiteDatumResult {
        let client = waterData
        return await v1Cache.site(site) { s in await client.siteDatum(s) }
    }

    /// The site record the switch says to use; in `shadow` the legacy record is used and the v1 record compared (kind=site).
    func siteDatumByMode(_ site: String) async -> USGSSiteDatumResult {
        await LakeUSGSRouting.run(mode,
            legacy: { await siteDatum(site) },
            v1: { await siteDatumV1(site) },
            adopt: { $0 },
            compare: { l, o in LakeUSGSShadow.line(site: site, param: Self.gageHeight, kind: "site", LakeUSGSShadow.compareSite(legacy: l, ogc: o)) },
            log: shadowLog)
    }

    /// The site's altitude when its datum is the one the binding expects; otherwise why not.
    func altitude(site: String, expectedDatum: String?) async -> (ft: Double?, refusal: String?) {
        await altitude(site: site, expectedDatum: expectedDatum, record: { await siteDatumByMode($0) })
    }

    func altitude(site: String, expectedDatum: String?, record: (String) async -> USGSSiteDatumResult) async -> (ft: Double?, refusal: String?) {
        guard Self.isSiteNumber(site) else { return (nil, "USGS stage binding needs a USGS site number (got \(site))") }
        guard let want = expectedDatum?.trimmingCharacters(in: .whitespaces), !want.isEmpty else {
            return (nil, "USGS \(site) 00065: the binding names no altitude datum (series), so the stage cannot be checked against alt_datum_cd")
        }
        switch await record(site) {
        case .refused(let why): return (nil, why)
        case .ok(let d):
            guard d.datum.uppercased() == want.uppercased() else {
                return (nil, "USGS \(site): altitude datum is \(d.datum), binding expects \(want) (datum changed or wrong binding)")
            }
            // 0 is the usual placeholder of an unsurveyed gage, and the history reader treats a zero offset as "no offset": refused in both.
            guard d.altitudeFt != 0 else { return (nil, "USGS \(site): published altitude is 0 (unsurveyed gage datum); gage height is not an elevation") }
            return (d.altitudeFt, nil)
        }
    }

    // MARK: live

    /// Gage height of the last `hours`, shifted by the site's altitude. `ref.series` is the expected altitude datum.
    func recent(_ ref: LevelSeriesRef, hours: Int) async -> FeedResult {
        let site = ref.station
        return await LakeUSGSRouting.run(mode,
            legacy: { await recentLegacy(ref, hours: hours) },
            v1: { await recentV1(ref, hours: hours) },
            adopt: { $0 },
            compare: { l, o in LakeUSGSShadow.line(site: site, param: Self.gageHeight, kind: "live", LakeUSGSShadow.compareLive(legacy: l, ogc: o)) },
            log: shadowLog)
    }

    /// v1: the `monitoring-locations` altitude and the `continuous` gage height, with the same refusals as the legacy reader.
    func recentV1(_ ref: LevelSeriesRef, hours: Int) async -> FeedResult {
        let site = ref.station
        let (alt, refusal) = await altitude(site: site, expectedDatum: ref.series, record: { await siteDatumV1($0) })
        guard let alt else { return .failed(refusal ?? "USGS \(site): no altitude") }
        switch await waterData.recentStage(site: site, hours: hours) {
        case .failure(let e): return .failed("USGS \(site) 00065: \(e.why)")
        case .success(let obs):
            let shifted = obs.map { LevelObservation(at: $0.at, ft: $0.ft + alt) }
            return shifted.isEmpty ? .failed("USGS \(site) 00065: no readings") : FeedResult(observations: LakeLevelSeries.merge(shifted), error: nil)
        }
    }

    /// The WaterServices reads (the `legacy` switch value). The altitude comes from `altitude(site:expectedDatum:)`, which in `shadow`
    /// also compares the v1 site record.
    func recentLegacy(_ ref: LevelSeriesRef, hours: Int) async -> FeedResult {
        let site = ref.station
        let (alt, refusal) = await altitude(site: site, expectedDatum: ref.series)
        guard let alt else { return .failed(refusal ?? "USGS \(site): no altitude") }
        let url = "\(LakeFleetClients.usgsBase)/iv/?format=json&sites=\(site)&parameterCd=\(Self.gageHeight)&period=PT\(max(1, hours))H"
        guard let r = await fetch(url, "application/json") else { return .failed("USGS \(site) 00065 unreachable") }
        guard r.isSuccess else { return .failed("USGS \(site) 00065: HTTP \(r.status)") }
        return Self.stageReadings(r.body, site: site, altitudeFt: alt)
    }

    static func stageReadings(_ data: Data, site: String, altitudeFt: Double) -> FeedResult {
        if let u = ivUnit(data), u.lowercased() != "ft" { return .failed("USGS \(site) 00065: unit \(u) is not feet") }
        let n = LakeFleetClients.usgsSeriesPerStatistic(data)
        if n > 1 { return .failed("USGS \(site) 00065: \(n) gage-height series at this site (sub-locations); the binding cannot tell which is the lake") }
        guard let obs = LakeFleetClients.parseUSGSIV(data) else { return .failed("USGS \(site) 00065: unreadable JSON") }
        let shifted = obs.map { LevelObservation(at: $0.at, ft: $0.ft + altitudeFt) }
        return shifted.isEmpty ? .failed("USGS \(site) 00065: no readings") : FeedResult(observations: LakeLevelSeries.merge(shifted), error: nil)
    }

    /// `value.timeSeries[0].variable.unit.unitCode` of a WaterServices JSON response.
    // MARK: history

    /// Gage-height history shifted by the site's altitude (read now, on the binding's datum). One series per statistic only.
    func daily(site: String, datum: String, stat: String, since: String?, now: Date, timeZone: TimeZone, fleet: LakeFleetClients) async -> [DailyLevel]? {
        guard let alt = await altitude(site: site, expectedDatum: datum).ft else { return nil }
        return await fleet.usgsDaily(site: site, param: Self.gageHeight, stat: stat, offsetFt: alt, since: since, now: now,
                                     timeZone: timeZone, singleSeries: true)
    }

    static func ivUnit(_ data: Data) -> String? {
        guard let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
              let series = (obj["value"] as? [String: Any])?["timeSeries"] as? [[String: Any]],
              let unit = ((series.first?["variable"] as? [String: Any])?["unit"] as? [String: Any])?["unitCode"] as? String else { return nil }
        return unit
    }
}
