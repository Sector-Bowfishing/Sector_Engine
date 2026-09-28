//
//  HydrologyGraph.swift
//  Sector — the lake's hydrologic arm graph (Clarity Fusion Stage 1)
//
//  WHICH WATER BELONGS TO WHICH CREEK, BY THE WATER. The old lake profile tied
//  a bank to a tributary by name and straight-line distance: every NHD line
//  called "Town Creek" was one creek, and a bank within 6 km of any part of it
//  — its channel on land included — was Town Creek's. Two Town Creeks 36 km
//  apart shared one identity and one gauge. This graph is built from the NHD
//  flow network and the lake's own water lattice (scripts/hydrology): a creek
//  is a connected run of same-named flowlines, a water cell belongs to the arm
//  it is reached from first THROUGH THE WATER, and the main stem is the
//  corridor within 400 m of the Tennessee's own channel.
//
//      head:<arm> → arm:<arm> → mouth:<arm> → arm:<parent> | ms-NN
//      nickajack-dam → ms-00 → … → ms-39 → guntersville-dam → wheeler-lake
//
//  TOPOLOGY ONLY. No velocities, no travel times: Sector measures neither.
//  Stage 1 exposes this; nothing scores from it yet.
//

import Foundation

public struct HydrologyGraph: Codable, Equatable {
    public let lakeId: String
    public let version: Int
    public let mainStem: MainStem
    public let arms: [Arm]
    public let nodes: [Node]
    /// Directed downstream: [from, to].
    public let edges: [[String]]

    public struct MainStem: Codable, Equatable {
        public let id: String
        public let name: String
        public let lengthKm: Double
        public let upstreamDam: Dam
        public let downstreamDam: Dam
        public let regions: [Region]
    }

    public struct Dam: Codable, Equatable {
        public let id: String
        public let name: String
        /// TVA RestApi location id (observed-data-48-hours / generation-releases).
        public let tva: String
        public let lat: Double
        public let lon: Double
    }

    /// A piece of the main-stem channel, cut at every top-level tributary
    /// mouth and at least every 5 km; km measured down the channel from the
    /// upstream dam.
    public struct Region: Codable, Equatable {
        public let id: String
        public let fromKm: Double
        public let toKm: Double
        public let center: [Double]      // [lat, lon]
    }

    public struct Arm: Codable, Equatable {
        public let id: String
        public let name: String
        /// The system its mouth hands the water to: another arm, or the main stem.
        public let parent: String
        /// The ancestor whose mouth is on the main stem.
        public let topLevel: String
        /// The main-stem region the top-level arm's mouth enters.
        public let receivingRegion: String?
        public let mouth: [Double]?      // [lat, lon]
        public let head: [Double]?       // [lat, lon] where the creek enters the lake outline
        public let mouthCounty: String?
        /// Head to mouth, through the water.
        public let reservoirPathKm: Double?
        /// Upstream main channel above the head (NLDI, NHDPlus V2).
        public let naturalChannelKm: Double?
        public let armClass: String
        public let nhdReachCodes: [String]
        public let nhdplusComidAtHead: Int?
        public let drainageKm2AboveHead: Double?
        public let nhdplusComidAtMouth: Int?
        public let drainageKm2AtMouth: Double?
        public let huc12: String?
        public let huc12Name: String?
        /// The National Water Model reach (its feature id is the NHDPlus comid)
        /// whose name matched this creek. nil when no probe matched: never guessed.
        public let nwmFeatureId: String?
        public let nwmReachName: String?
        /// The active USGS discharge gauge on this creek's own network.
        public let usgsDischargeSite: String?
        public let usgsDischargeSiteName: String?
        public let usgsSitesUpstream: [String]
        /// measuredUSGS | modeledNWM | unavailable
        public let flowSource: String
        public let waterCells: Int
        /// What could not be established, stated rather than guessed.
        public let flags: [String]
    }

    public struct Node: Codable, Equatable {
        public let id: String
        /// dam | mainStemRegion | downstream | armHead | arm | armMouth
        public let kind: String
        public let name: String?
        public let tva: String?
        public let arm: String?
        public let at: [Double]?
        public let fromKm: Double?
        public let toKm: Double?
    }

    // MARK: Queries

    public func arm(_ id: String) -> Arm? { arms.first { $0.id == id } }

    public func children(of id: String) -> [Arm] { arms.filter { $0.parent == id } }

    /// The node ids downstream of `node`, in order, to the end of the graph.
    public func downstreamPath(from node: String) -> [String] {
        var next: [String: String] = [:]
        for e in edges where e.count == 2 { next[e[0]] = e[1] }
        var out: [String] = []
        var cur = node
        var seen: Set<String> = [node]
        while let n = next[cur], !seen.contains(n) {
            out.append(n); seen.insert(n); cur = n
        }
        return out
    }

    /// Top-level arms whose mouths enter main-stem region `region`.
    public func arms(enteringRegion region: String) -> [Arm] {
        arms.filter { $0.receivingRegion == region && $0.parent == mainStem.id }
    }
}

/// The coarse cell → arm grid on the Water Clarity frame (~180 m cells).
public struct HydrologyArmGrid: Equatable {
    public let width: Int
    public let height: Int
    /// The Water Clarity frame the grid is a coarse copy of: each coarse cell
    /// is `factor` x `factor` frame cells (the last row/column padded).
    public let factor: Int
    public let fullWidth: Int
    public let fullHeight: Int
    /// Top-left, top-right, bottom-right, bottom-left, as [lon, lat].
    public let cornersLonLat: [[Double]]
    public let arms: [String?]
    let cells: [UInt8]

    public enum Membership: Equatable {
        case mainStem
        case arm(String)
        case notWater
    }

    /// What the water at a coordinate belongs to (nil outside the frame).
    public func membership(lat: Double, lon: Double) -> Membership? {
        guard cornersLonLat.count == 4 else { return nil }
        func merc(_ lon: Double, _ lat: Double) -> (Double, Double) {
            let x = lon * .pi / 180 * 6_378_137
            let y = log(tan(.pi / 4 + lat * .pi / 360)) * 6_378_137
            return (x, y)
        }
        let (l, t) = merc(cornersLonLat[0][0], cornersLonLat[0][1])
        let (r, b) = merc(cornersLonLat[2][0], cornersLonLat[2][1])
        let (x, y) = merc(lon, lat)
        // the frame cell first, then its coarse block: the grid is padded to
        // whole blocks, so scaling straight onto it would drift a block
        let fc = Int(((x - l) / (r - l) * Double(fullWidth)).rounded(.down))
        let fr = Int(((t - y) / (t - b) * Double(fullHeight)).rounded(.down))
        guard fc >= 0, fc < fullWidth, fr >= 0, fr < fullHeight else { return nil }
        let c = fc / factor, row = fr / factor
        guard c < width, row < height else { return nil }
        let v = cells[row * width + c]
        if v == 255 { return .notWater }
        if v == 0 { return .mainStem }
        return Int(v) < arms.count ? arms[Int(v)].map { .arm($0) } ?? .mainStem : .mainStem
    }

    /// LEB128 varint (value, run) pairs, base64 (see embed_swift.py).
    static func decodeRLE(_ b64: String, count: Int) -> [UInt8]? {
        guard let data = Data(base64Encoded: b64) else { return nil }
        let bytes = [UInt8](data)
        var i = 0
        func varint() -> Int? {
            var shift = 0, out = 0
            while i < bytes.count {
                let b = bytes[i]; i += 1
                out |= Int(b & 0x7F) << shift
                if b & 0x80 == 0 { return out }
                shift += 7
            }
            return nil
        }
        var cells: [UInt8] = []
        cells.reserveCapacity(count)
        while i < bytes.count {
            guard let v = varint(), let run = varint() else { return nil }
            cells.append(contentsOf: repeatElement(UInt8(v), count: run))
        }
        return cells.count == count ? cells : nil
    }
}

public enum Hydrology {
    private struct Payload: Decodable {
        let graph: HydrologyGraph
        let grid: Grid
        struct Grid: Decodable {
            let width: Int
            let height: Int
            let factor: Int
            let fullWidth: Int
            let fullHeight: Int
            let cornersLonLat: [[Double]]
            let arms: [String?]
            let cells: String
        }
    }

    private static let payload: (HydrologyGraph, HydrologyArmGrid) = {
        do {
            let p = try JSONDecoder().decode(Payload.self, from: Data(hydrologyGuntersvilleJSON.utf8))
            guard let cells = HydrologyArmGrid.decodeRLE(p.grid.cells, count: p.grid.width * p.grid.height) else {
                fatalError("HydrologyData.swift: the arm grid does not decode — regenerate it")
            }
            return (p.graph, HydrologyArmGrid(width: p.grid.width, height: p.grid.height, factor: p.grid.factor,
                                              fullWidth: p.grid.fullWidth, fullHeight: p.grid.fullHeight,
                                              cornersLonLat: p.grid.cornersLonLat, arms: p.grid.arms, cells: cells))
        } catch {
            fatalError("HydrologyData.swift: the graph JSON does not decode — regenerate it: \(error)")
        }
    }()

    /// Lake Guntersville's graph. The only lake with one so far.
    public static var guntersville: HydrologyGraph { payload.0 }
    public static var guntersvilleGrid: HydrologyArmGrid { payload.1 }

    /// The graph for a directory lake id, when one has been built.
    public static func graph(forLake id: String) -> HydrologyGraph? {
        id == guntersville.lakeId ? guntersville : nil
    }
}
