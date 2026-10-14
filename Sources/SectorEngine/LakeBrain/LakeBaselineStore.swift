//
//  LakeBaselineStore.swift
//  Sector — Lake Brain: baseline recompute policy, content fingerprint, immutable objects and the `latest.json` pointer
//
//  Layout in gs://sector-lake-brain:
//    baselines/{lakeKey}/latest.json                          small pointer (this file's `LakeBaselinePointer`), overwritten in place
//    baselines-archive/{lakeKey}/{method}_{end}_{fp16}.json   immutable baseline artifact, named by its INPUT fingerprint
//    baselines/{lakeKey}/{baselineVersion}.json               LEGACY (one object per lake per day of change): no longer written, still readable
//
//  Why: the old writer made a new object whenever the history advanced, i.e. every day. Now
//    • an artifact is a pure function of its inputs (builder version, method, pool basis, calendar year, history rows up to `historyEnd`),
//      so identical inputs always give identical bytes and the same name: writing the same inputs twice writes nothing;
//    • the artifact is recomputed at most weekly, or at once when an input changes (method/builder bump, a new calendar year, a pool
//      basis change, or a row at or before the stored `historyEnd` was revised or backfilled);
//    • `latest.json` names the current artifact and carries its SHA-256, so a reader detects a torn or corrupted object;
//    • a rollback is a pointer rewrite (pinned) to an older artifact: the artifact bytes never change;
//    • the artifact is read-verified; a missing, unparsable or hash-mismatching pointer or object falls back to today's behaviour
//      (rebuild from the merged history and write fresh).
//  See docs/brains/LAKE_BRAIN_ARTIFACT_HYGIENE.md and LAKE_BRAIN_STORAGE_LIFECYCLE_AND_COST.md.
//

import Foundation

// MARK: - SHA-256 (no crypto dependency in this package)

public enum LakeSHA256 {
    private static let k: [UInt32] = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
    ]

    private static func rotr(_ x: UInt32, _ n: UInt32) -> UInt32 { (x >> n) | (x << (32 - n)) }

    /// Lower-case hex SHA-256 of `data`.
    public static func hex(_ data: Data) -> String {
        var h: [UInt32] = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]
        var msg = [UInt8](data)
        let bitLength = UInt64(msg.count) * 8
        msg.append(0x80)
        while msg.count % 64 != 56 { msg.append(0) }
        for i in (0..<8).reversed() { msg.append(UInt8((bitLength >> (UInt64(i) * 8)) & 0xff)) }
        var w = [UInt32](repeating: 0, count: 64)
        for chunk in stride(from: 0, to: msg.count, by: 64) {
            for i in 0..<16 {
                let j = chunk + i * 4
                w[i] = UInt32(msg[j]) << 24 | UInt32(msg[j + 1]) << 16 | UInt32(msg[j + 2]) << 8 | UInt32(msg[j + 3])
            }
            for i in 16..<64 {
                let s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3)
                let s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10)
                w[i] = w[i - 16] &+ s0 &+ w[i - 7] &+ s1
            }
            var a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7]
            for i in 0..<64 {
                let s1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)
                let ch = (e & f) ^ (~e & g)
                let t1 = hh &+ s1 &+ ch &+ k[i] &+ w[i]
                let s0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)
                let maj = (a & b) ^ (a & c) ^ (b & c)
                let t2 = s0 &+ maj
                hh = g; g = f; f = e; e = d &+ t1; d = c; c = b; b = a; a = t1 &+ t2
            }
            h[0] = h[0] &+ a; h[1] = h[1] &+ b; h[2] = h[2] &+ c; h[3] = h[3] &+ d
            h[4] = h[4] &+ e; h[5] = h[5] &+ f; h[6] = h[6] &+ g; h[7] = h[7] &+ hh
        }
        return h.map { String(format: "%08x", $0) }.joined()
    }

    public static func hex(_ s: String) -> String { hex(Data(s.utf8)) }
}

// MARK: - Pointer

/// `baselines/{lakeKey}/latest.json`. Small (about 0.6 KB); everything a reader or an operator needs to find, verify and reproduce the artifact.
public struct LakeBaselinePointer: Codable, Equatable, Sendable {
    public static let schema = 1
    public var pointerSchema: Int
    public var lakeId: String
    public var method: String
    /// `LakeBaselineBuilder.builderVersion` when the artifact was built.
    public var builderVersion: String
    /// The artifact's own `baselineVersion` (`method@historyEnd#csvFingerprint`), as cited by published LakeStates.
    public var baselineVersion: String
    /// SHA-256 over the canonical inputs (`LakeBaselineBuilder.inputFingerprint`).
    public var inputFingerprint: String
    /// Calendar year the baseline was computed in (decides which years count as complete).
    public var asOfYear: Int
    public var poolBasisIsFullPool: Bool
    public var historyEnd: String?
    public var observationCount: Int
    /// Immutable artifact object (path inside the bucket) and the SHA-256 / size of its exact bytes.
    public var objectPath: String
    public var objectSha256: String
    public var objectBytes: Int
    /// When the artifact was computed (ISO 8601 UTC). The weekly recompute clock.
    public var computedAt: String
    /// Last time the writer re-uploaded the same artifact bytes so a bucket age rule never retires the current object.
    public var refreshedAt: String
    /// The previous `objectPath` (one step of provenance for a rollback); nil on the first pointer.
    public var supersedes: String?
    /// A rollback pins the pointer: the runner reuses the pinned artifact and never recomputes or moves the pointer until an operator unpins.
    public var pinned: Bool
    public var pinnedReason: String?

    public init(pointerSchema: Int = LakeBaselinePointer.schema, lakeId: String, method: String, builderVersion: String, baselineVersion: String,
                inputFingerprint: String, asOfYear: Int, poolBasisIsFullPool: Bool, historyEnd: String?, observationCount: Int,
                objectPath: String, objectSha256: String, objectBytes: Int, computedAt: String, refreshedAt: String,
                supersedes: String? = nil, pinned: Bool = false, pinnedReason: String? = nil) {
        self.pointerSchema = pointerSchema; self.lakeId = lakeId; self.method = method; self.builderVersion = builderVersion
        self.baselineVersion = baselineVersion; self.inputFingerprint = inputFingerprint; self.asOfYear = asOfYear
        self.poolBasisIsFullPool = poolBasisIsFullPool; self.historyEnd = historyEnd; self.observationCount = observationCount
        self.objectPath = objectPath; self.objectSha256 = objectSha256; self.objectBytes = objectBytes
        self.computedAt = computedAt; self.refreshedAt = refreshedAt; self.supersedes = supersedes
        self.pinned = pinned; self.pinnedReason = pinnedReason
    }
}

// MARK: - Fingerprint and paths

extension LakeBaselineBuilder {
    /// Bump on ANY change to `build` that can change the artifact bytes for the same history (a rule, a filter, a cut point, a rounding).
    /// The first value covers the rate-climatology RVD filter: it changed artifact content without changing `baselineMethod`, so a
    /// name keyed on method + history alone cannot tell the two apart.
    public static let builderVersion = "builder-2026-10-13-rate-rvd-filter"

    /// SHA-256 (hex) over the canonical input text: builder, method, pool basis, calendar year, and the history rows (deduplicated, in date order).
    /// `daily` must already be limited to the rows the build uses (date <= today). Identical inputs, identical fingerprint, on every platform.
    public static func inputFingerprint(daily: [DailyLevel], asOfYear: Int, poolBasisIsFullPool: Bool) -> String {
        let head = "lake-baseline-input/1\nbuilder=\(builderVersion)\nmethod=\(LakeBrainSpec.baselineMethod)\nfullPool=\(poolBasisIsFullPool)\nasOfYear=\(asOfYear)\n"
        return LakeSHA256.hex(Data(head.utf8) + LakeDailyHistory.encode(daily))
    }

    /// The rows of `history` the build for `today` would use.
    static func inputRows(_ history: [DailyLevel], through end: String) -> [DailyLevel] {
        LakeDailyHistory.dedupe(history).filter { $0.date <= end }
    }

    /// Immutable object name: keyed on the input fingerprint, so equal inputs share one object and a builder or method bump cannot collide with an older one.
    public static func archivePath(lakeId: String, method: String, historyEnd: String?, inputFingerprint fp: String) -> String {
        "baselines-archive/\(BrainPlatform.lakeKey(lakeId))/\(BrainPlatform.lakeKey(method))_\(historyEnd ?? "none")_\(fp.prefix(16)).json"
    }

    public static func pointerPath(_ lakeId: String) -> String { "baselines/\(BrainPlatform.lakeKey(lakeId))/latest.json" }
}

// MARK: - Store

public enum LakeBaselineStore {

    /// The stored baseline is recomputed at most this often (unless an input changed).
    public static let recomputeDays = 7
    /// A still-current artifact whose bytes were last uploaded this long ago is re-uploaded unchanged (resets the bucket `age` clock).
    /// Must be well below the archive retention in `jobs/lake-brain/history/lake_brain_bucket_lifecycle_proposed.json` (90 days).
    public static let refreshDays = 45

    public enum Reason: String, Sendable {
        case noPointer, pointerCorrupt, objectUnreadable, methodOrBuilderChanged, newCalendarYear, poolBasisChanged
        case forced, weeklyDue, historyRevised, badTimestamp
        case pinned, current
    }

    /// What the runner did with the baseline this run.
    public enum Action: String, Sendable {
        /// Stored artifact reused, nothing written.
        case reused
        /// Inputs equal to the stored ones after a recompute: nothing written.
        case unchanged
        /// New immutable object and a moved pointer.
        case published
        /// Same artifact bytes re-uploaded and `refreshedAt` bumped.
        case refreshed
        /// Built but not stored (no archive, status none, or a pinned pointer).
        case builtNotStored
    }

    public struct Resolved: Sendable {
        public var pointer: LakeBaselinePointer
        public var baseline: LakeLevelBaseline
        public var bytes: Data
    }

    public struct Outcome: Sendable {
        public var baseline: LakeLevelBaseline
        public var reason: Reason
        public var action: Action
        public var pointer: LakeBaselinePointer?
        public var errors: [String]
    }

    // MARK: read

    /// Reads and verifies the pointer and its artifact. nil with `corrupt == true` when something is present but unusable; nil with false when absent.
    public static func resolve(archive: LakeBrainArchive, lakeId: String) async -> (resolved: Resolved?, corrupt: Bool, detail: String?) {
        guard let raw = (try? await archive.read(LakeBaselineBuilder.pointerPath(lakeId))) ?? nil else { return (nil, false, nil) }
        guard let p = try? JSONDecoder().decode(LakeBaselinePointer.self, from: raw), p.pointerSchema == LakeBaselinePointer.schema,
              p.lakeId == lakeId, p.objectPath.hasPrefix("baselines-archive/"), !p.objectPath.contains("..") else {
            return (nil, true, "latest.json unreadable or not for this lake")
        }
        guard let bytes = (try? await archive.read(p.objectPath)) ?? nil else { return (nil, true, "pointer names a missing object \(p.objectPath)") }
        guard bytes.count == p.objectBytes, LakeSHA256.hex(bytes) == p.objectSha256 else { return (nil, true, "object \(p.objectPath) does not match the pointer hash") }
        guard let b = try? JSONDecoder().decode(LakeLevelBaseline.self, from: bytes), b.lakeId == lakeId, b.baselineVersion == p.baselineVersion else {
            return (nil, true, "object \(p.objectPath) does not decode as this lake's baseline")
        }
        return (Resolved(pointer: p, baseline: b, bytes: bytes), false, nil)
    }

    // MARK: decide (pure)

    /// Whether the stored artifact can be used as is. `merged` is the full merged history of this run.
    public static func decide(pointer p: LakeBaselinePointer?, objectReadable: Bool, merged: [DailyLevel], today: String,
                              poolBasisIsFullPool: Bool, now: Date, forceRecompute: Bool) -> Reason {
        guard let p else { return .noPointer }
        guard objectReadable else { return .objectUnreadable }
        if p.pinned { return .pinned }
        if p.method != LakeBrainSpec.baselineMethod || p.builderVersion != LakeBaselineBuilder.builderVersion { return .methodOrBuilderChanged }
        if p.asOfYear != (Int(today.prefix(4)) ?? 0) { return .newCalendarYear }
        if p.poolBasisIsFullPool != poolBasisIsFullPool { return .poolBasisChanged }
        if forceRecompute { return .forced }
        guard let at = BrainPlatform.parseTime(p.computedAt) else { return .badTimestamp }
        if now.timeIntervalSince(at) >= Double(recomputeDays) * 86_400 { return .weeklyDue }
        guard let end = p.historyEnd else { return .historyRevised }
        let basis = LakeBaselineBuilder.inputRows(merged, through: end)
        if LakeBaselineBuilder.inputFingerprint(daily: basis, asOfYear: p.asOfYear, poolBasisIsFullPool: p.poolBasisIsFullPool) != p.inputFingerprint { return .historyRevised }
        return .current
    }

    // MARK: ensure (read, decide, build, write)

    /// The one entry point of the runner. Never throws; failures are returned in `errors` and the in-memory baseline is still usable.
    public static func ensure(lakeId: String, merged rawMerged: [DailyLevel], today: String, poolBasisIsFullPool: Bool,
                              archive: LakeBrainArchive?, now: Date, forceRecompute: Bool = false) async -> Outcome {
        // The artifact is built from exactly what `history/{key}/daily.csv` stores (deduplicated, elevations at two decimals), not from the
        // in-memory feed values, so it can be re-derived byte for byte from a pinned copy of that file.
        let merged = LakeDailyHistory.decode(LakeDailyHistory.encode(rawMerged))
        func build() -> LakeLevelBaseline {
            LakeBaselineBuilder.build(lakeId: lakeId, daily: merged, today: today, poolBasisIsFullPool: poolBasisIsFullPool)
        }
        guard let archive else {
            return Outcome(baseline: build(), reason: .noPointer, action: .builtNotStored, pointer: nil, errors: [])
        }
        var errors: [String] = []
        let r = await resolve(archive: archive, lakeId: lakeId)
        if r.corrupt, let d = r.detail { errors.append("baseline pointer: \(d); rebuilding") }
        let reason = decide(pointer: r.resolved?.pointer, objectReadable: r.resolved != nil || !r.corrupt, merged: merged, today: today,
                            poolBasisIsFullPool: poolBasisIsFullPool, now: now, forceRecompute: forceRecompute)
        let effective: Reason = (r.corrupt && r.resolved == nil) ? .pointerCorrupt : reason

        if let res = r.resolved, reason == .pinned || reason == .current {
            return Outcome(baseline: res.baseline, reason: reason, action: .reused, pointer: res.pointer, errors: errors)
        }

        // Recompute.
        let b = build()
        let asOfYear = Int(today.prefix(4)) ?? 0
        let fp = LakeBaselineBuilder.inputFingerprint(daily: LakeBaselineBuilder.inputRows(merged, through: today),
                                                      asOfYear: asOfYear, poolBasisIsFullPool: poolBasisIsFullPool)
        guard b.status != .none else { return Outcome(baseline: b, reason: effective, action: .builtNotStored, pointer: r.resolved?.pointer, errors: errors) }
        do {
            let bytes = try BrainJSON.encode(b)
            let path = LakeBaselineBuilder.archivePath(lakeId: lakeId, method: b.method, historyEnd: b.historyEnd, inputFingerprint: fp)
            let sha = LakeSHA256.hex(bytes)
            // Same inputs as the stored pointer: byte-identical object, nothing to write.
            if let old = r.resolved?.pointer, old.objectPath == path, old.objectSha256 == sha {
                // A stalled lake (history not advancing) never moves its pointer, so the bucket `age` clock of the current object is reset here:
                // the same bytes are uploaded again every `refreshDays`, well inside the archive retention.
                if let at = BrainPlatform.parseTime(old.refreshedAt), now.timeIntervalSince(at) >= Double(refreshDays) * 86_400 {
                    var p = old; p.refreshedAt = BrainPlatform.iso(now)
                    try await archive.write(path, bytes, contentType: "application/json")
                    try await archive.write(LakeBaselineBuilder.pointerPath(lakeId), try BrainJSON.encode(p), contentType: "application/json")
                    return Outcome(baseline: b, reason: effective, action: .refreshed, pointer: p, errors: errors)
                }
                return Outcome(baseline: b, reason: effective, action: .unchanged, pointer: old, errors: errors)
            }
            if let existing = (try? await archive.read(path)) ?? nil, LakeSHA256.hex(existing) == sha {
                // The object already exists (a previous run died before it moved the pointer): only the pointer moves.
            } else {
                try await archive.write(path, bytes, contentType: "application/json")
            }
            let iso = BrainPlatform.iso(now)
            let p = LakeBaselinePointer(lakeId: lakeId, method: b.method, builderVersion: LakeBaselineBuilder.builderVersion,
                                        baselineVersion: b.baselineVersion, inputFingerprint: fp, asOfYear: asOfYear,
                                        poolBasisIsFullPool: poolBasisIsFullPool, historyEnd: b.historyEnd, observationCount: b.observationCount,
                                        objectPath: path, objectSha256: sha, objectBytes: bytes.count, computedAt: iso, refreshedAt: iso,
                                        supersedes: r.resolved?.pointer.objectPath)
            try await archive.write(LakeBaselineBuilder.pointerPath(lakeId), try BrainJSON.encode(p), contentType: "application/json")
            return Outcome(baseline: b, reason: effective, action: .published, pointer: p, errors: errors)
        } catch {
            errors.append("baseline write: \(error)")
            return Outcome(baseline: b, reason: effective, action: .builtNotStored, pointer: r.resolved?.pointer, errors: errors)
        }
    }

    // MARK: rollback

    public enum RollbackError: Error, CustomStringConvertible {
        case objectMissing(String), notThisLake, badPath(String), writeFailed(String)
        public var description: String {
            switch self {
            case .objectMissing(let p): return "rollback target \(p) does not exist"
            case .notThisLake: return "rollback target is another lake's baseline"
            case .badPath(let p): return "rollback target must be under baselines-archive/: \(p)"
            case .writeFailed(let m): return m
            }
        }
    }

    /// Operator action: point `latest.json` at an older immutable artifact and pin it, so the runner keeps using it (never recomputes, never moves the
    /// pointer) until an operator removes the pin. The artifact bytes are untouched; the pointer is rebuilt from the artifact itself, so the
    /// same classifier inputs come back. `inputFingerprint` is then only the 16-hex prefix carried in the object name and `builderVersion` is
    /// "unknown": both are informational while pinned. Un-pin by deleting `latest.json` (the next run rebuilds and moves it) or by rewriting it.
    public static func rollback(archive: LakeBrainArchive, lakeId: String, toObjectPath path: String, reason: String, now: Date) async throws -> LakeBaselinePointer {
        let key = BrainPlatform.lakeKey(lakeId)
        guard path.hasPrefix("baselines-archive/\(key)/"), !path.contains("..") else { throw RollbackError.badPath(path) }
        guard let bytes = (try? await archive.read(path)) ?? nil, let b = try? JSONDecoder().decode(LakeLevelBaseline.self, from: bytes) else {
            throw RollbackError.objectMissing(path)
        }
        guard b.lakeId == lakeId else { throw RollbackError.notThisLake }
        let fp16 = path.replacingOccurrences(of: ".json", with: "").split(separator: "_").last.map(String.init) ?? ""
        let current = (await resolve(archive: archive, lakeId: lakeId)).resolved?.pointer
        let iso = BrainPlatform.iso(now)
        let p = LakeBaselinePointer(lakeId: lakeId, method: b.method, builderVersion: "unknown", baselineVersion: b.baselineVersion,
                                    inputFingerprint: fp16, asOfYear: Int(b.historyEnd?.prefix(4) ?? "") ?? 0,
                                    poolBasisIsFullPool: current?.poolBasisIsFullPool ?? true, historyEnd: b.historyEnd,
                                    observationCount: b.observationCount, objectPath: path, objectSha256: LakeSHA256.hex(bytes),
                                    objectBytes: bytes.count, computedAt: iso, refreshedAt: iso,
                                    supersedes: current?.objectPath == path ? current?.supersedes : current?.objectPath,
                                    pinned: true, pinnedReason: reason)
        do { try await archive.write(LakeBaselineBuilder.pointerPath(lakeId), try BrainJSON.encode(p), contentType: "application/json") }
        catch { throw RollbackError.writeFailed("\(error)") }
        return p
    }
}
