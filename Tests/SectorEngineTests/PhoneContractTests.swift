//
//  PhoneContractTests.swift
//  SectorEngineTests
//
//  Sector_Ops #53 rule 1: the phone contract for GET /conditions is frozen. Released apps (iOS 4.1.0 build 28 decodes
//  strictly: one missing key or wrong type fails the whole response and blanks every tile) must keep working through
//  every consolidation step. Additive fields are allowed; nothing in the contract may be removed, renamed, retyped or
//  made null.
//
//  Inputs:
//    contracts/phone/conditions-phone-contract-v1.json          what build 28 decodes (keys, types, required)
//    verification/fixtures/phone-contract/<date>/*.json        golden /conditions responses captured from production
//                                                              (free text redacted; tools/conditions_golden/capture.py)
//
//  Checks:
//    1. every golden satisfies the contract (the contract matches what production really serves);
//    2. every golden decodes into the Engine's ConditionsResponse and re-encodes with the server's encoder settings
//       into JSON that still satisfies the contract AND carries the same value at every contract path. A step that
//       drops, renames or retypes a field, makes it optional-and-absent, or changes date encoding fails here.
//

import XCTest
@testable import SectorEngine

final class PhoneContractTests: XCTestCase {

    private static let root = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()

    private struct Spec { let type: String; let required: Bool }

    private static func loadContract() throws -> [String: Spec] {
        let url = root.appendingPathComponent("contracts/phone/conditions-phone-contract-v1.json")
        let obj = try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as! [String: Any]
        let fields = obj["fields"] as! [String: [String: Any]]
        return fields.mapValues { Spec(type: $0["type"] as! String, required: $0["required"] as! Bool) }
    }

    private static func goldenFiles() throws -> [URL] {
        let dir = root.appendingPathComponent("verification/fixtures/phone-contract")
        let fm = FileManager.default
        var out: [URL] = []
        for sub in try fm.contentsOfDirectory(atPath: dir.path).sorted() {
            let d = dir.appendingPathComponent(sub)
            var isDir: ObjCBool = false
            guard fm.fileExists(atPath: d.path, isDirectory: &isDir), isDir.boolValue else { continue }
            for f in try fm.contentsOfDirectory(atPath: d.path).sorted() where f.hasSuffix(".json") {
                out.append(d.appendingPathComponent(f))
            }
        }
        return out
    }

    // MARK: validator (same rules as tools/conditions_golden/capture.py)

    private static let dateRegex = try! NSRegularExpression(pattern: #"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$"#)

    /// JSON true/false as parsed by JSONSerialization on Darwin (CFBoolean, objCType "c") and Linux (Bool or a "c"/"B" NSNumber).
    private static func isBool(_ v: Any) -> Bool {
        if type(of: v) == Bool.self { return true }
        guard let n = v as? NSNumber else { return false }
        let t = String(cString: n.objCType)
        return t == "c" || t == "B"
    }

    private static func number(_ v: Any) -> Double? {
        guard let n = v as? NSNumber, !isBool(v) else { return nil }
        return Double(n.description) ?? n.doubleValue
    }

    private static func isType(_ v: Any, _ t: String) -> Bool {
        switch t {
        case "int": if let d = number(v) { return d.rounded() == d } else { return false }
        case "number": return number(v) != nil
        case "string": return v is String
        case "bool": return isBool(v)
        case "date":
            guard let s = v as? String else { return false }
            return dateRegex.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) != nil
        case "array": return v is [Any]
        case "object": return v is [String: Any]
        default: return false
        }
    }

    /// Direct child paths of `parent` ("" = root).
    private static func children(_ fields: [String: Spec], _ parent: String) -> [String] {
        fields.keys.filter { p in
            if parent.isEmpty { return !p.contains(".") && !p.contains("[]") }
            guard p.hasPrefix(parent + ".") else { return false }
            let rest = p.dropFirst(parent.count + 1)
            return !rest.contains(".") && !rest.contains("[]")
        }.sorted()
    }

    private static func validate(_ doc: Any, _ fields: [String: Spec]) -> [String] {
        var errors: [String] = []
        func walkObject(_ obj: [String: Any], _ parent: String, _ at: String) {
            for p in children(fields, parent) {
                let key = String(p.split(separator: ".").last!)
                let here = at.isEmpty ? key : "\(at).\(key)"
                guard let v = obj[key], !(v is NSNull) else {
                    if fields[p]!.required { errors.append("\(here): required key missing or null") }
                    continue
                }
                checkValue(v, p, here)
            }
        }
        func checkValue(_ v: Any, _ p: String, _ here: String) {
            let spec = fields[p]!
            guard isType(v, spec.type) else { errors.append("\(here): expected \(spec.type)"); return }
            if spec.type == "object" { walkObject(v as! [String: Any], p, here) }
            if spec.type == "array" {
                let arr = v as! [Any]
                if let elem = fields[p + "[]"] {
                    for (i, e) in arr.enumerated() where e is NSNull || !isType(e, elem.type) {
                        errors.append("\(here)[\(i)]: expected \(elem.type)")
                    }
                } else {
                    for (i, e) in arr.enumerated() {
                        guard let o = e as? [String: Any] else { errors.append("\(here)[\(i)]: expected object"); continue }
                        walkObject(o, p + "[]", "\(here)[\(i)]")
                    }
                }
            }
        }
        guard let root = doc as? [String: Any] else { return ["$: expected object"] }
        walkObject(root, "", "")
        return errors
    }

    /// The document reduced to contract paths only, for value comparison.
    private static func project(_ doc: Any, _ fields: [String: Spec], _ parent: String = "") -> Any {
        if let obj = doc as? [String: Any] {
            var out: [String: Any] = [:]
            for p in children(fields, parent) {
                let key = String(p.split(separator: ".").last!)
                guard let v = obj[key], !(v is NSNull) else { continue }
                out[key] = projectValue(v, p, fields)
            }
            return out
        }
        return doc
    }

    private static func projectValue(_ v: Any, _ p: String, _ fields: [String: Spec]) -> Any {
        switch fields[p]!.type {
        case "object": return project(v, fields, p)
        case "array":
            guard let arr = v as? [Any] else { return v }
            if fields[p + "[]"] != nil { return arr.map { number($0) ?? $0 } }
            return arr.map { project($0, fields, p + "[]") }
        default: return number(v) ?? v
        }
    }

    private static func difference(_ a: Any, _ b: Any, _ path: String = "$") -> String? {
        if let x = a as? [String: Any], let y = b as? [String: Any] {
            if Set(x.keys) != Set(y.keys) { return "\(path): keys \(Set(x.keys).symmetricDifference(Set(y.keys)).sorted())" }
            for k in x.keys.sorted() { if let d = difference(x[k]!, y[k]!, "\(path).\(k)") { return d } }
            return nil
        }
        if let x = a as? [Any], let y = b as? [Any] {
            if x.count != y.count { return "\(path): length \(x.count) vs \(y.count)" }
            for (i, (u, v)) in zip(x, y).enumerated() { if let d = difference(u, v, "\(path)[\(i)]") { return d } }
            return nil
        }
        if let x = a as? Double, let y = b as? Double { return x == y ? nil : "\(path): \(x) vs \(y)" }
        if let x = a as? String, let y = b as? String { return x == y ? nil : "\(path): \"\(x)\" vs \"\(y)\"" }
        if isBool(a) && isBool(b) { return (a as! NSNumber).boolValue == (b as! NSNumber).boolValue ? nil : "\(path): bool differs" }
        return "\(path): \(type(of: a)) vs \(type(of: b))"
    }

    // MARK: tests

    func testThereAreGoldens() throws {
        XCTAssertGreaterThanOrEqual(try Self.goldenFiles().count, 10, "phone-contract goldens are missing")
    }

    func testGoldensSatisfyPhoneContract() throws {
        let fields = try Self.loadContract()
        for f in try Self.goldenFiles() {
            let doc = try JSONSerialization.jsonObject(with: Data(contentsOf: f))
            let errors = Self.validate(doc, fields)
            XCTAssertTrue(errors.isEmpty, "\(f.lastPathComponent): \(errors.prefix(5))")
        }
    }

    func testEngineResponseKeepsPhoneContract() throws {
        let fields = try Self.loadContract()
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        // Same settings as Sources/SectorEngineServer/main.swift.
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        for f in try Self.goldenFiles() {
            let data = try Data(contentsOf: f)
            let response = try decoder.decode(ConditionsResponse.self, from: data)
            let reencoded = try JSONSerialization.jsonObject(with: encoder.encode(response))
            let errors = Self.validate(reencoded, fields)
            XCTAssertTrue(errors.isEmpty, "\(f.lastPathComponent) after Engine round trip: \(errors.prefix(5))")
            let golden = try JSONSerialization.jsonObject(with: data)
            let diff = Self.difference(Self.project(golden, fields), Self.project(reencoded, fields))
            XCTAssertNil(diff, "\(f.lastPathComponent): a contract value changed in the Engine round trip at \(diff ?? "-")")
        }
    }

    /// The validator itself must reject the breakages the contract exists to stop.
    func testValidatorCatchesBreakingChanges() throws {
        let fields = try Self.loadContract()
        let f = try XCTUnwrap(Self.goldenFiles().first)
        let base = try JSONSerialization.jsonObject(with: Data(contentsOf: f)) as! [String: Any]
        XCTAssertTrue(Self.validate(base, fields).isEmpty)

        var missing = base; missing.removeValue(forKey: "moonIllumination")
        XCTAssertFalse(Self.validate(missing, fields).isEmpty, "removed required key")

        var retyped = base; retyped["score"] = "60"
        XCTAssertFalse(Self.validate(retyped, fields).isEmpty, "retyped key")

        var nulled = base; nulled["nights"] = NSNull()
        XCTAssertFalse(Self.validate(nulled, fields).isEmpty, "nulled required key")

        if var w = base["weather"] as? [String: Any] {
            w["windDirection"] = 329.5
            var badInt = base; badInt["weather"] = w
            XCTAssertFalse(Self.validate(badInt, fields).isEmpty, "fractional Int")
        }
        if var t = base["tonight"] as? [String: Any], var hours = t["hours"] as? [[String: Any]], !hours.isEmpty {
            hours[0]["date"] = "2026-11-06T12:00:00.123Z"
            t["hours"] = hours
            var badDate = base; badDate["tonight"] = t
            XCTAssertFalse(Self.validate(badDate, fields).isEmpty, "fractional-second date")
        }

        var added = base; added["tileSources"] = ["moon": ["path": "app"]]
        XCTAssertTrue(Self.validate(added, fields).isEmpty, "additive field must be allowed")
    }
}
