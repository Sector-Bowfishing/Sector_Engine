//
//  ClarityCells.swift
//  Sector — the lake's water cells, each scene's evidence at them, and the
//  current composite (Clarity Fusion Stage 4)
//
//  ONE INDEX. Every cell the Water Clarity layer colours, in row-major order
//  on the layer's frame, with its hydrologic region and zone
//  (CurrentClarityRegionsData.swift, from scripts/hydrology/current_cells.py).
//  Each scene's cells file is aligned to it and carries its hash.
//
//  THE COMPOSITE. Each region takes the scene its arm state chose
//  (ClarityHistory.selectAnchor: the newest that reads it at least
//  moderately), so Town Creek can stand on Sep 17 while the main stem stands
//  on Sep 20. Cells are never mixed across scenes within a region.
//

import Foundation

/// The cells file encoding (current_cells.py).
public enum ClarityCellCode {
    public static let valueLo = log10(0.5), valueHi = log10(200.0), valueTop = 254.0
    public static let distanceStepM = 100.0

    public static func fnu(_ q: UInt8) -> Double? {
        guard q > 0 else { return nil }
        return pow(10, valueLo + (Double(q) - 1) / (valueTop - 1) * (valueHi - valueLo))
    }
    public static func distanceM(_ d: UInt8) -> Double? {
        guard d > 0 else { return nil }
        return d >= 254 ? .infinity : (Double(d) - 1) * distanceStepM
    }
    public static func evidence(value: UInt8, code: UInt8, dist: UInt8) -> ClarityCellEvidence {
        let f = fnu(value)
        switch code {
        case 255: return ClarityCellEvidence(kind: .direct, fnu: f, distanceToObservedM: 0)
        case 1: return ClarityCellEvidence(kind: .filled, fnu: f, distanceToObservedM: distanceM(dist), fillReason: "unreadable")
        case 2: return ClarityCellEvidence(kind: .filled, fnu: f, distanceToObservedM: distanceM(dist), fillReason: "cloud")
        case 3: return ClarityCellEvidence(kind: .grassBed, fnu: f, distanceToObservedM: distanceM(dist))
        default: return ClarityCellEvidence(kind: .none, fnu: nil, distanceToObservedM: nil)
        }
    }
}

/// The fixed index: which frame cells are water, and what each belongs to.
public struct ClarityRegionsIndex {
    public struct Zone: Decodable, Equatable { public let zone: Int; public let arm: String; public let name: String; public let index: Int; public let of: Int }
    struct Tables: Decodable {
        let lakeId: String; let width: Int; let height: Int; let cells: Int; let indexHash: UInt32
        let cornersLonLat: [[Double]]; let cellGroundM: Double; let regions: [String]; let zones: [Zone]
    }

    public let lakeId: String
    public let width: Int
    public let height: Int
    public let count: Int
    public let hash: UInt32
    public let cornersLonLat: [[Double]]
    public let cellGroundM: Double
    /// Region index → arm id ("_mainStem" at 0).
    public let regionIds: [String]
    public let zones: [Int: Zone]
    public let region: [UInt8]
    /// -1 = main stem.
    public let zone: [Int16]
    /// The mask's run-length form, as stored (the cells endpoint repeats it).
    public let maskRLE: [UInt8]
    /// Per frame row: (first column, run length, index of its first cell).
    let rows: [[(col: Int, len: Int, at: Int)]]

    public static let guntersville: ClarityRegionsIndex = {
        guard let blob = Data(base64Encoded: currentClarityGuntersvilleBlob),
              let t = try? JSONDecoder().decode(Tables.self, from: Data(currentClarityGuntersvilleTables.utf8)),
              let idx = ClarityRegionsIndex(blob: [UInt8](blob), tables: t) else {
            fatalError("CurrentClarityRegionsData.swift does not decode — regenerate it (current_cells.py swift)")
        }
        return idx
    }()

    public static func forLake(_ id: String) -> ClarityRegionsIndex? {
        id == Hydrology.guntersville.lakeId ? guntersville : nil
    }

    init?(blob b: [UInt8], tables t: Tables) {
        var r = ByteReader(b)
        guard r.bytes(4) == Array("SCR1".utf8), let w = r.u32(), let h = r.u32(), let n = r.u32(), let hsh = r.u32(),
              let ml = r.u32(), let mask = r.bytes(Int(ml)), let ral = r.u32(), let ra = r.bytes(Int(ral)),
              let rzl = r.u32(), let rz = r.bytes(Int(rzl)) else { return nil }
        guard Int(w) == t.width, Int(h) == t.height, Int(n) == t.cells, hsh == t.indexHash else { return nil }
        // rows from the mask runs (alternating out, in; starting with out)
        var rows = Array(repeating: [(col: Int, len: Int, at: Int)](), count: Int(h))
        var mr = VarintReader(mask)
        var pos = 0, inWater = false, at = 0
        while let run = mr.next() {
            if inWater {
                var p = pos, left = run
                while left > 0 {
                    let row = p / Int(w), col = p % Int(w)
                    let take = Swift.min(left, Int(w) - col)
                    rows[row].append((col, take, at))
                    at += take; p += take; left -= take
                }
            }
            pos += run; inWater.toggle()
        }
        guard at == Int(n), pos == Int(w) * Int(h) else { return nil }
        func expand(_ bytes: [UInt8]) -> [Int]? {
            var v = VarintReader(bytes), out: [Int] = []
            out.reserveCapacity(Int(n))
            while let value = v.next() { guard let run = v.next() else { return nil }; out.append(contentsOf: repeatElement(value, count: run)) }
            return out.count == Int(n) ? out : nil
        }
        guard let reg = expand(ra), let zon = expand(rz) else { return nil }
        lakeId = t.lakeId; width = Int(w); height = Int(h); count = Int(n); hash = hsh
        cornersLonLat = t.cornersLonLat; cellGroundM = t.cellGroundM; regionIds = t.regions
        zones = Dictionary(uniqueKeysWithValues: t.zones.map { ($0.zone, $0) })
        region = reg.map { UInt8($0) }; zone = zon.map { Int16($0 - 1) }; maskRLE = mask; self.rows = rows
    }

    /// The frame cell under a coordinate (Web Mercator, as the layer is drawn).
    public func frameCell(lat: Double, lon: Double) -> (row: Int, col: Int)? {
        func merc(_ lon: Double, _ lat: Double) -> (Double, Double) {
            (lon * .pi / 180 * 6_378_137, log(tan(.pi / 4 + lat * .pi / 360)) * 6_378_137)
        }
        let (l, t) = merc(cornersLonLat[0][0], cornersLonLat[0][1])
        let (r, b) = merc(cornersLonLat[2][0], cornersLonLat[2][1])
        let (x, y) = merc(lon, lat)
        let col = Int(((x - l) / (r - l) * Double(width)).rounded(.down))
        let row = Int(((t - y) / (t - b) * Double(height)).rounded(.down))
        guard col >= 0, col < width, row >= 0, row < height else { return nil }
        return (row, col)
    }

    /// The water cell at a frame cell, if it is one.
    public func index(row: Int, col: Int) -> Int? {
        guard row >= 0, row < height else { return nil }
        for s in rows[row] where col >= s.col && col < s.col + s.len { return s.at + (col - s.col) }
        return nil
    }

    public func index(lat: Double, lon: Double) -> Int? {
        frameCell(lat: lat, lon: lon).flatMap { index(row: $0.row, col: $0.col) }
    }

    /// The centre of a water cell (for tests and the replay).
    public func coordinate(of i: Int) -> (lat: Double, lon: Double)? {
        for (row, spans) in rows.enumerated() {
            for s in spans where i >= s.at && i < s.at + s.len {
                let col = s.col + (i - s.at)
                func unmerc(_ x: Double, _ y: Double) -> (Double, Double) {
                    (atan(sinh(y / 6_378_137)) * 180 / .pi, x / 6_378_137 * 180 / .pi)
                }
                let l = cornersLonLat[0][0] * .pi / 180 * 6_378_137, r = cornersLonLat[2][0] * .pi / 180 * 6_378_137
                let t = log(tan(.pi / 4 + cornersLonLat[0][1] * .pi / 360)) * 6_378_137
                let b = log(tan(.pi / 4 + cornersLonLat[2][1] * .pi / 360)) * 6_378_137
                let x = l + (Double(col) + 0.5) / Double(width) * (r - l)
                let y = t - (Double(row) + 0.5) / Double(height) * (t - b)
                return unmerc(x, y)
            }
        }
        return nil
    }
}

/// One scene's cells on the index.
public struct ClaritySceneCells: Equatable {
    public let ref: ClaritySceneRef
    public let value: [UInt8]
    public let code: [UInt8]
    public let dist: [UInt8]

    public enum DecodeError: Error, Equatable { case notACellsFile, wrongIndex(expected: UInt32, got: UInt32), truncated }

    public init(ref: ClaritySceneRef, data: [UInt8], index: ClarityRegionsIndex) throws {
        var r = ByteReader(data)
        guard r.bytes(4) == Array("SCC1".utf8), let n = r.u32(), let h = r.u32() else { throw DecodeError.notACellsFile }
        guard h == index.hash, Int(n) == index.count else { throw DecodeError.wrongIndex(expected: index.hash, got: h) }
        guard let v = r.bytes(Int(n)), let c = r.bytes(Int(n)), let d = r.bytes(Int(n)) else { throw DecodeError.truncated }
        self.ref = ref; value = v; code = c; dist = d
    }

    public init(ref: ClaritySceneRef, value: [UInt8], code: [UInt8], dist: [UInt8]) {
        self.ref = ref; self.value = value; self.code = code; self.dist = dist
    }
}

/// Each region on its own chosen scene.
public struct ClarityComposite {
    public let index: ClarityRegionsIndex
    public let scenes: [ClaritySceneCells]
    /// Region index → position in `scenes` (nil = no scene).
    public let sceneForRegion: [Int?]

    public init(index: ClarityRegionsIndex, scenes: [ClaritySceneCells], sceneForRegion: [Int?]) {
        self.index = index; self.scenes = scenes; self.sceneForRegion = sceneForRegion
    }

    public func scene(atCell i: Int) -> Int? {
        let r = Int(index.region[i])
        return r < sceneForRegion.count ? sceneForRegion[r] : nil
    }

    public func evidence(atCell i: Int) -> ClarityCellEvidence {
        guard let s = scene(atCell: i) else { return ClarityCellEvidence(kind: .none, fnu: nil, distanceToObservedM: nil) }
        let sc = scenes[s]
        return ClarityCellCode.evidence(value: sc.value[i], code: sc.code[i], dist: sc.dist[i])
    }

    /// The composite as one file for the map (GET /clarity/current/cells):
    ///   "SCCC" | u32 version 1 | u32 width | u32 height | u32 N | u32 index hash
    ///   | u32 mask RLE length | mask RLE | u8[N] value | u8[N] code | u8[N] dist
    ///   | u8[N] region | i16[N] zone (little-endian) | u8[N] scene (255 = none)
    public func encoded() -> [UInt8] {
        var out: [UInt8] = Array("SCCC".utf8)
        func u32(_ v: Int) { var x = UInt32(v).littleEndian; withUnsafeBytes(of: &x) { out.append(contentsOf: $0) } }
        u32(1); u32(index.width); u32(index.height); u32(index.count); u32(Int(index.hash))
        u32(index.maskRLE.count); out.append(contentsOf: index.maskRLE)
        let n = index.count
        var v = [UInt8](repeating: 0, count: n), c = v, d = v, sc = [UInt8](repeating: 255, count: n)
        for i in 0..<n {
            guard let s = scene(atCell: i) else { continue }
            v[i] = scenes[s].value[i]; c[i] = scenes[s].code[i]; d[i] = scenes[s].dist[i]; sc[i] = UInt8(s)
        }
        out += v; out += c; out += d; out += index.region
        out.reserveCapacity(out.count + 3 * n)
        for z in index.zone { let x = UInt16(bitPattern: z).littleEndian; out.append(UInt8(x & 0xFF)); out.append(UInt8(x >> 8)) }
        out += sc
        return out
    }
}

struct ByteReader {
    let b: [UInt8]
    var i = 0
    init(_ b: [UInt8]) { self.b = b }
    mutating func bytes(_ n: Int) -> [UInt8]? {
        guard n >= 0, i + n <= b.count else { return nil }
        defer { i += n }
        return Array(b[i..<(i + n)])
    }
    mutating func u32() -> UInt32? {
        guard let x = bytes(4) else { return nil }
        return UInt32(x[0]) | UInt32(x[1]) << 8 | UInt32(x[2]) << 16 | UInt32(x[3]) << 24
    }
}

struct VarintReader {
    let b: [UInt8]
    var i = 0
    init(_ b: [UInt8]) { self.b = b }
    mutating func next() -> Int? {
        guard i < b.count else { return nil }
        var shift = 0, out = 0
        while i < b.count {
            let x = b[i]; i += 1
            out |= Int(x & 0x7F) << shift
            if x & 0x80 == 0 { return out }
            shift += 7
        }
        return nil
    }
}
