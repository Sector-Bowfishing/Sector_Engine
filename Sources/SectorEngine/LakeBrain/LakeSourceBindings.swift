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

import Foundation

/// One named water-level series.
public struct LevelSeriesRef: Codable, Equatable, Sendable {
    public enum Provider: String, Codable, Sendable { case tva, cwms, usgs }
    public var provider: Provider
    public var capability: LevelSourceCapability
    /// TVA LocationID, CWMS office, or USGS site number.
    public var station: String
    /// CWMS time-series id or USGS parameter code; nil for TVA.
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
        }
    }

    public var providerName: String {
        switch provider { case .tva: return "TVA"; case .cwms: return "USACE CWMS"; case .usgs: return "USGS" }
    }
}

/// The operator's seasonal guidance for a lake.
public enum LakeGuideSource: Codable, Equatable, Sendable {
    /// TVA `/operating-guide/{id}`: daily GuideCurve, BtmOpZone, TopOpZone, TopOfGates.
    case tvaOperatingGuide(locationId: String)
    /// CWMS daily series: guide = top of conservation; zone bottom = a drought level.
    case cwms(office: String, guideSeries: String, zoneBottomSeries: String, zoneBottomLabel: String,
              extraLevels: [CWMSNamedSeries])
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
    /// A CWMS daily series (decades for most USACE projects).
    case cwmsDaily(office: String, series: String)
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
}

public enum LakeSourceBindings {

    /// Bump whenever a reviewed row changes.
    public static let version = "bindings-2026-10-12.1"

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
    public static let reviewed: [LakeSourceBinding] = [
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

    public static func binding(for lakeId: String) -> LakeSourceBinding? {
        reviewed.first { $0.lakeId == lakeId }
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
