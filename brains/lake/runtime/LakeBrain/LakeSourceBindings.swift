//
//  LakeSourceBindings.swift
//  Sector — Lake Brain: the reviewed lake → water-level source table
//
//  Production resolves a lake's dam / CWMS project / USGS gage at request time
//  (nearest within a radius). The Lake Brain does NOT: a LakeState is published
//  only from a binding that was probed and reviewed by hand, so a river gage or
//  the next dam over can never be presented as this lake's level.
//
//  Every other directory lake gets a CANDIDATE class from its directory hints
//  (operator, cwmsOffice, apiLevel). A candidate never publishes a state.
//
//  Probe record for the v1 pilots (2026-10-12) is in
//  docs/brains/LAKE_BRAIN_INTEGRATION.md §5.
//
//  Two sources of bindings:
//    • `pilots`     the five hand-written, hand-reviewed rows (REVIEWED).
//    • `generated`  the MACHINE_VERIFIED table (LakeSourceBindingsGenerated.swift,
//                   from jobs/lake-brain/data/bindings.proposed.v1.json). Every row
//                   is CANDIDATE unless its lakeId is in jobs/lake-brain/data/
//                   accepted_batch.json (written only after Michael's review).
//  `reviewed` — the only list a run publishes from — contains REVIEWED rows only.
//

import Foundation
import SectorEngine

/// One named water-level series.
public struct LevelSeriesRef: Codable, Equatable, Sendable {
    public enum Provider: String, Codable, Sendable { case tva, cwms, usgs, a2w, rise, nwps }
    public var provider: Provider
    public var capability: LevelSourceCapability
    /// TVA LocationID, CWMS office, USGS site number, Access2Water `DISTRICT:LocationCode`, RISE item id or NWS location id.
    public var station: String
    /// CWMS / Access2Water time-series id, USGS parameter code, NWPS observed pedts (e.g. `HPIRZ`); nil for TVA and RISE.
    public var series: String?
    public var cadenceMin: Int
    public var lagMin: Int
    /// Added to the reading to put it on the binding's datum (0 when the same datum).
    public var datumOffsetFt: Double = 0
    public var note: String?

    /// Stable, human-readable id: `tva:GVDA1`, `cwms:SAS:Hartwell.Elev-Pool…`, `usgs:02187010:00062`.
    public var sourceId: String {
        switch provider {
        case .tva: return "tva:\(station)"
        case .cwms: return "cwms:\(station):\(series ?? "")"
        case .usgs: return "usgs:\(station):\(series ?? "")"
        case .a2w: return "a2w:\(station):\(series ?? "")"
        case .rise: return "rise:\(station)"
        case .nwps: return "nwps:\(station):\(series ?? "")"
        }
    }

    public var providerName: String {
        switch provider {
        case .tva: return "TVA"; case .cwms: return "USACE CWMS"; case .usgs: return "USGS"
        case .a2w: return "USACE Access2Water"; case .rise: return "USBR RISE"; case .nwps: return "NWS NWPS"
        }
    }
}

/// The operator's seasonal guidance for a lake.
public enum LakeGuideSource: Codable, Equatable, Sendable {
    /// TVA `/operating-guide/{id}`: daily GuideCurve, BtmOpZone, TopOpZone, TopOfGates.
    case tvaOperatingGuide(locationId: String)
    /// CWMS daily series: guide = top of conservation; zone bottom = a drought level.
    case cwms(office: String, guideSeries: String, zoneBottomSeries: String, zoneBottomLabel: String,
              extraLevels: [CWMSNamedSeries])
    /// Operator-published levels from the verified plan / flood join: static constants, Access2Water levels, CWMS levels / series.
    case operatorLevels(OperatorLevels)
}

public struct CWMSNamedSeries: Codable, Equatable, Sendable {
    public var name: String
    public var series: String
}

/// Where a lake's daily history comes from.
public enum LakeHistorySource: Codable, Equatable, Sendable {
    /// TVA operating guide `CurYrElev` / `PrevYrElev`: midnight elevation, current + previous year.
    case tvaOperatingGuide(locationId: String)
    /// The Water Temp lane's hourly TVA archive (shared, read-only; approved 2026-10-12).
    case sharedTVAArchive(bucket: String, prefix: String, locationId: String)
    /// A CWMS daily series (decades for most USACE projects). Sub-daily series are reduced to the median of each lake-local day.
    case cwmsDaily(office: String, series: String)
    /// USGS daily values (`stat` "dv" merges 00003 > 32400 > 30800 > 00001 > 00002; a stat code takes only that statistic) or
    /// instantaneous values reduced to a daily median (`stat` "iv"). `offsetFt` is a datum shift (gage height + site altitude).
    case usgsDaily(site: String, param: String, stat: String, offsetFt: Double)
    /// USBR RISE daily item; 0.0 placeholders dropped. The day is the UTC date of the stamp (as in the research).
    case riseDaily(item: String)
    /// IEM HADS archive of an NWS location id (pool elevation `HP…`), daily median of each lake-local day.
    case hadsDaily(lid: String, pe: String, offsetFt: Double)
}

public struct LakeSourceBinding: Codable, Equatable, Sendable {
    public var lakeId: String
    public var status: LevelBindingStatus
    public var capability: LevelSourceCapability
    /// Live level, best first. The first fresh one is used; using a fallback is flagged.
    public var live: [LevelSeriesRef]
    public var history: [LakeHistorySource]
    public var guide: LakeGuideSource?
    public var datum: String?
    public var timeZone: String
    public var damName: String?
    public var riverSystem: String?
    public var topOfGatesFt: Double?
    /// Facts from the operator that profile `characteristics` may cite.
    public var hydropower: Bool?
    public var floodControl: Bool?
    public var operatorName: String?
    public var reviewedAt: String?
    public var note: String?
    /// NID dam id and the source of the dam facts above (generated rows).
    public var nidId: String?
    public var factsSource: String?
    /// Context features for the profile (research-derived; shown only for a REVIEWED binding or a candidate dry run).
    public var context: LakeContextFeatures?
    /// What the machine probe established; nil for the hand-written pilots.
    public var machine: MachineVerification?
}

public enum LakeSourceBindings {

    /// Bump whenever a reviewed row changes.
    /// 2026-10-13.1: the generated MACHINE_VERIFIED table (all CANDIDATE), provider adapters, operator-level guides and the
    /// profile context. The five pilots republish ONCE on the first run after this bump (planState sees a new binding version).
    /// A non-empty accepted batch adds a suffix (count + fingerprint of the accepted ids), so accepting lakes also republishes.
    public static let baseVersion = "bindings-2026-10-13.1"
    public static var version: String { baseVersion + LakeGeneratedBindings.versionSuffix }

    static let tvaArchiveBucket = "sector-water-temp-archive"
    static let tvaArchivePrefix = "water-temp/tva"

    /// TVA Lake Levels pages: hourly observed reservoir elevation, published about an hour late.
    private static func tvaPilot(_ lakeId: String, _ loc: String, dam: String, topOfGates: Double) -> LakeSourceBinding {
        LakeSourceBinding(
            lakeId: lakeId, status: .reviewed, capability: .directOperatorPool,
            live: [LevelSeriesRef(provider: .tva, capability: .directOperatorPool, station: loc, series: nil,
                                  cadenceMin: 60, lagMin: 60, note: "observed-data-48-hours ReservoirElevation")],
            history: [.sharedTVAArchive(bucket: tvaArchiveBucket, prefix: tvaArchivePrefix, locationId: loc),
                      .tvaOperatingGuide(locationId: loc)],
            guide: .tvaOperatingGuide(locationId: loc),
            datum: nil, timeZone: "America/Chicago", damName: dam, riverSystem: "Tennessee",
            topOfGatesFt: topOfGates, hydropower: true, floodControl: nil, operatorName: "TVA",
            reviewedAt: "2026-10-12",
            note: "TVA /locations: \(dam) \(loc), DamType Hydropower, River Tennessee. Live + 365-day operating guide probed 2026-10-12.")
    }

    /// Probed and reviewed by hand. Lake ids are canonical directory ids.
    static let handWritten: [LakeSourceBinding] = [
        tvaPilot("Guntersville|AL", "GVDA1", dam: "Guntersville Dam", topOfGates: 595.44),
        tvaPilot("Wheeler|AL", "WHLA1", dam: "Wheeler Dam", topOfGates: 556.28),
        tvaPilot("Wilson|AL", "WLSA1", dam: "Wilson Dam", topOfGates: 507.88),
        tvaPilot("Pickwick Lake|TN", "PICT1", dam: "Pickwick Dam", topOfGates: 418),
        LakeSourceBinding(
            lakeId: "Lake Hartwell|SC", status: .reviewed, capability: .directOperatorPool,
            live: [
                LevelSeriesRef(provider: .cwms, capability: .directOperatorPool, station: "SAS",
                               series: "Hartwell.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS", cadenceMin: 60, lagMin: 120,
                               note: "USACE Savannah District pool elevation (NGVD29)"),
                LevelSeriesRef(provider: .usgs, capability: .directLakeGauge, station: "02187010", series: "00062",
                               cadenceMin: 60, lagMin: 60,
                               note: "HARTWELL LAKE NEAR ANDERSON, SC. Agrees with the CWMS pool within 0.03 ft over 2026-10-01..08 (site altitude is listed NAVD88; no offset applied, checked every run)"),
            ],
            history: [.cwmsDaily(office: "SAS", series: "Hartwell.Elev-Pool.Inst.1Day.0.Raw-SHEF_SAS")],
            guide: .cwms(office: "SAS", guideSeries: "Hartwell.Elev-GC.Inst.1Day.0.ARCHIVE-DAILY",
                         zoneBottomSeries: "Hartwell.Elev-L1.Inst.1Day.0.ARCHIVE-DAILY", zoneBottomLabel: "Drought Level 1",
                         extraLevels: [CWMSNamedSeries(name: "Drought Level 2", series: "Hartwell.Elev-L2.Inst.1Day.0.ARCHIVE-DAILY"),
                                       CWMSNamedSeries(name: "Drought Level 3", series: "Hartwell.Elev-L3.Inst.1Day.0.ARCHIVE-DAILY")]),
            datum: "NGVD29", timeZone: "America/New_York", damName: "Hartwell Dam", riverSystem: "Savannah",
            topOfGatesFt: nil, hydropower: nil, floodControl: true, operatorName: "USACE Savannah (SAS)",
            reviewedAt: "2026-10-12",
            note: "CWMS SAS: daily pool since 1960, hourly since 1997; guide curve (top of conservation) and drought levels L1–L3 published daily. Hourly pool feed last reported 2026-10-08 10:00Z at review time (production resolver gap C2), so the USGS on-lake gauge is the reviewed fallback. Flood control from the CWMS 'Bottom of Flood Control' level."),
    ]

    /// The hand-written rows, with the research context features attached for the profile (the state is unaffected).
    public static let pilots: [LakeSourceBinding] = handWritten.map { b in
        var b = b; b.context = LakeGeneratedBindings.context(for: b.lakeId); return b
    }

    /// The MACHINE_VERIFIED table: CANDIDATE unless the lake is in accepted_batch.json.
    public static let generated: [LakeSourceBinding] = LakeGeneratedBindings.bindings

    /// Pilots first, then generated rows for lakes that have no hand-written row.
    public static let all: [LakeSourceBinding] = {
        let hand = Set(pilots.map(\.lakeId))
        return pilots + generated.filter { !hand.contains($0.lakeId) }
    }()

    private static let index: [String: LakeSourceBinding] = Dictionary(all.map { ($0.lakeId, $0) }, uniquingKeysWith: { a, _ in a })

    /// REVIEWED rows only: the list a run publishes from. A CANDIDATE is never in it.
    public static let reviewed: [LakeSourceBinding] = all.filter { $0.status == .reviewed }

    /// CANDIDATE rows (evaluated only by `LakeBrainJob --dry-run --include-candidates`).
    public static let candidates: [LakeSourceBinding] = all.filter { $0.status == .candidate }

    /// The binding of a lake whatever its status (hand-written first, then generated). Check `status` before publishing from it.
    public static func binding(for lakeId: String) -> LakeSourceBinding? { index[lakeId] }

    /// The REVIEWED binding of a lake, or nil.
    public static func reviewedBinding(for lakeId: String) -> LakeSourceBinding? {
        guard let b = index[lakeId], b.status == .reviewed else { return nil }
        return b
    }

    /// Directory hints → a capability class that has NOT been verified. Never publishes a state.
    static func candidateCapability(for lake: DirectoryLake) -> LevelSourceCapability {
        let op = lake.operatorName.lowercased()
        if lake.hasDam, op.contains("tva") || lake.cwmsOffice != nil { return .directOperatorPool }
        switch lake.apiLevel {
        case .dedicated: return lake.hasDam ? .directOperatorPool : .directLakeGauge
        case .usgsOnly: return .nearbyGaugeProxy
        case .none: return .noSource
        }
    }
}
