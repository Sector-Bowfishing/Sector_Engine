//
//  GaugeClassifier.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  "What water does this USGS series measure?" — answered from metadata the IV
//  response already carries: the site name, siteProperty.siteTypeCd, and each
//  values[] block's methodDescription. No extra network calls.
//
//  WHY: the engine used to take the nearest gauge of each kind, whatever it
//  measured. A spot on Lake Lanier borrowed 52 °F release water from the
//  Chattahoochee gauge AT Buford Dam; a creek gauge on "Suwanee Dam Road" read as
//  a dam; springs and wells fed water temperature. The role computed here is one
//  of three tests (role, water context, freshness/distance) GaugeSelector applies
//  before a series may drive an input.
//
//  The name key is the other half: it lets a pool gauge prove it is THIS lake's
//  pool ("LAKE SIDNEY LANIER NEAR BUFORD" ~ "Lanier (Sidney Lanier)") without
//  accepting a neighbour ("CARTERS RE-REGULATION LAKE" is not Carters).
//
//  Rules were validated in a Python prototype against every cached state IV
//  response (2026-09-14, ~12.9k site/type/method triples) and 85 NLDI dam reaches;
//  the spec is gauge_final.json, rule step A. Pure and Foundation-only, and the
//  inputs are the source-agnostic triple, so it ports unchanged to the new
//  api.waterdata.usgs.gov responses.
//

import Foundation

/// What a gauge series measures, relative to dams and lakes. Order of the rules
/// that assign it matters; see `GaugeClassifier.classify`.
enum GaugeRole: String, Equatable, Sendable {
    /// A reservoir pool / lake surface (headwater, forebay, LK site).
    case pool
    /// Water leaving a dam: tailwater, tailrace, lower pool, "below X dam".
    case damRelease
    /// A named river (not a tributary creek).
    case river
    /// A creek, branch, bayou, ditch, spring run… — local, not the main stem.
    case tributary
    /// Estuary, wetland, coastal ocean (ES / WE / OC-CO).
    case openWater
    /// Surface water whose name says nothing usable.
    case unknownSurface
    /// Springs (SP), wells (GW) and every other non-surface site type. Never
    /// describes the water a bowfisher is standing over.
    case nonSurface
}

struct GaugeClassification: Equatable, Sendable {
    let role: GaugeRole
    /// Distinctive words of the water-body phrase, in order (see `nameKey`).
    /// Compared against lake names with `GaugeClassifier.keysMatch`.
    let nameKey: [String]
    /// Every token of the site name — dam-name evidence ("naming D") is a subset test.
    let nameTokens: Set<String>
}

enum GaugeClassifier: Sendable {

    // MARK: - Token sets

    /// USGS siteTypeCd values that are surface water. Anything else (SP spring,
    /// GW well, AT atmosphere…) is `.nonSurface`. A missing code is not rejected:
    /// NWPS readings and older fixtures carry none.
    static let surfaceTypes: Set<String> = ["ST", "ST-CA", "ST-DCH", "ST-TS", "LK", "ES", "WE", "OC-CO"]
    static let openWaterTypes: Set<String> = ["ES", "WE", "OC-CO"]

    static let lakeWords: Set<String> = [
        "LAKE", "LAKES", "LK", "RESERVOIR", "RES", "RESV", "POND", "IMPOUNDMENT", "FOREBAY", "HEADWATER", "POOL",
    ]
    static let riverWords: Set<String> = ["RIVER", "R", "RIV", "RV", "WW", "WATERWAY"]
    static let tributaryWords: Set<String> = [
        "CREEK", "CR", "CK", "CRK", "BROOK", "BR", "BRANCH", "RUN", "BAYOU", "SLOUGH", "TRIBUTARY", "TRIB",
        "DITCH", "DRAIN", "SWAMP", "CANAL", "SPRING", "SPRINGS", "SPGS", "SPG", "GULCH", "WASH", "HOLLOW", "HOLW",
    ]
    static let belowWords: Set<String> = ["BELOW", "BL", "BLW", "BLO"]
    /// No bare "TAIL": "OTTER TAIL RIVER" and "EAGLE TAIL DITCH" are not tailraces.
    static let tailWords: Set<String> = ["TAILRACE", "TAILWATER", "TW"]
    static let damWords: Set<String> = ["DAM", "L&D", "LOCK", "POWERHOUSE", "SPILLWAY"]
    /// A dam word followed by one of these is a road name: "SUWANEE DAM ROAD".
    static let roadWords: Set<String> = [
        "RD", "ROAD", "ST", "HWY", "HIGHWAY", "BRIDGE", "AVE", "PIKE", "LANE", "LN", "DR", "DRIVE",
    ]
    /// Words that end the water-body phrase ("X RIVER *AT* Y"). "A" is the
    /// California district's "at" ("TRUCKEE R A FARAD CA").
    static let locators: Set<String> = [
        "AT", "NR", "NEAR", "BL", "BLW", "BELOW", "ABV", "ABOVE", "AB", "IN", "ON", "US", "DS",
        "UPSTREAM", "DOWNSTREAM", "OFF", "BTWN", "BETWEEN", "BY", "A",
    ]
    /// A compass word ends the phrase only when followed by OF ("LAKE MATTAMUSKEET
    /// W OF NC HWY 94"); otherwise it's part of the name ("W F GEORGE").
    static let compassWords: Set<String> = ["N", "S", "E", "W", "NE", "NW", "SE", "SW"]
    /// Words that say what kind of water it is, not which one — dropped from keys.
    static let genericWords: Set<String> = [
        "LAKE", "LAKES", "LK", "L", "RESERVOIR", "RES", "RESV", "POND", "THE", "OF", "POOL", "IMPOUNDMENT",
        "DAM", "RIVER", "R", "RIV", "RV",
    ]
    static let keyStopWords: Set<String> = ["AND", "LCRA"]
    static let keyNormalization: [String: String] = [
        "CK": "CREEK", "CR": "CREEK", "CRK": "CREEK", "MT": "MOUNT", "ST": "SAINT", "FT": "FORT",
    ]

    // MARK: - Classification

    /// Rule step A, first match wins:
    /// 1. nonSurface by site type; 2. the method block (per series block);
    /// 3. dam release by name; 4. pool (LK site or lake word); 5. open water by
    /// type; 6. river word; 7. tributary word; 8. unknownSurface.
    static func classify(siteName: String, siteTypeCode: String?, methodDescription: String?) -> GaugeClassification {
        let tks = tokens(siteName)
        let phrase = waterBodyPhrase(tks)
        let result = { (role: GaugeRole) in
            GaugeClassification(role: role, nameKey: nameKey(tokens: phrase), nameTokens: Set(tks))
        }

        let siteType = (siteTypeCode ?? "").uppercased()
        if !siteType.isEmpty && !surfaceTypes.contains(siteType) { return result(.nonSurface) }

        // One site can publish both faces of a dam as separate blocks
        // (Murray L&D: HEADWATER / TAILWATER); the block label beats the site name.
        let method = (methodDescription ?? "").uppercased()
        let methodWords = wordRuns(method)
        if method.contains("TAILWATER") || method.contains("TAILRACE") || method.contains("LOWER POOL")
            || methodWords.contains("TW") {
            return result(.damRelease)
        }
        if method.contains("HEADWATER") || method.contains("UPPER POOL") || method.contains("FOREBAY")
            || methodWords.contains("POOL") || methodWords.contains("LAKE") || method.contains("RESERVOIR") {
            return result(.pool)
        }

        let all = Set(tks)
        let phraseSet = Set(phrase)
        let damHit = tks.indices.contains { i in
            damWords.contains(tks[i]) && !(i + 1 < tks.count && roadWords.contains(tks[i + 1]))
        }
        let phraseHasRiver = !phraseSet.isDisjoint(with: riverWords)
        let phraseHasLake = !phraseSet.isDisjoint(with: lakeWords)

        if !all.isDisjoint(with: tailWords)
            || (!all.isDisjoint(with: belowWords) && (damHit || !all.isDisjoint(with: lakeWords)))
            || (damHit && phraseHasRiver && !phraseHasLake) {
            return result(.damRelease)
        }
        // An LK site on a river-only phrase is a riverine transect, not a pool.
        if siteType == "LK" && !(phraseHasRiver && !phraseHasLake) { return result(.pool) }
        if phraseHasLake { return result(.pool) }
        if openWaterTypes.contains(siteType) { return result(.openWater) }
        // Any river word wins over a creek word: "Spring River" is a river.
        if phraseHasRiver { return result(.river) }
        if !phraseSet.isDisjoint(with: tributaryWords) { return result(.tributary) }
        return result(.unknownSurface)
    }

    // MARK: - Tokens and phrases

    /// Upper-cased name tokens of `[A-Z0-9&]`. Apostrophes (raw, curly, backtick,
    /// `&apos;`, `&#39;`) become spaces so "D&apos;Arbonne" and "D'ARBONNE" tokenize
    /// alike; "L & D" collapses to one "L&D" token.
    static func tokens(_ text: String) -> [String] {
        var s = text
        for apostrophe in ["&apos;", "&#39;", "'", "\u{2019}", "`"] {
            s = s.replacingOccurrences(of: apostrophe, with: " ")
        }
        s = s.replacingOccurrences(of: "&amp;", with: "&").uppercased()

        let scalars = Array(s.unicodeScalars)
        var cleaned = String.UnicodeScalarView()
        var i = 0
        while i < scalars.count {
            if scalars[i] == "L", let end = lockAndDamEnd(scalars, afterL: i) {
                cleaned.append(contentsOf: " L&D ".unicodeScalars)
                i = end + 1
                continue
            }
            let c = scalars[i]
            let keep = ("A"..."Z").contains(c) || ("0"..."9").contains(c) || c == "&"
            cleaned.append(keep ? c : " ")
            i += 1
        }
        return String(cleaned).split(separator: " ").map(String.init)
    }

    /// Index of the "D" when `L`, optional whitespace, `&`, optional whitespace,
    /// `D` starts at `start`.
    private static func lockAndDamEnd(_ s: [Unicode.Scalar], afterL start: Int) -> Int? {
        var j = start + 1
        while j < s.count, s[j].properties.isWhitespace { j += 1 }
        guard j < s.count, s[j] == "&" else { return nil }
        j += 1
        while j < s.count, s[j].properties.isWhitespace { j += 1 }
        return j < s.count && s[j] == "D" ? j : nil
    }

    /// The tokens naming the water body: everything before the first locator, a
    /// token containing a digit, or a compass word followed by OF. The first token
    /// is always kept.
    static func waterBodyPhrase(_ tokens: [String]) -> [String] {
        var out: [String] = []
        for (i, t) in tokens.enumerated() {
            let next = i + 1 < tokens.count ? tokens[i + 1] : ""
            let endsPhrase = locators.contains(t)
                || t.unicodeScalars.contains { ("0"..."9").contains($0) }
                || (compassWords.contains(t) && next == "OF")
            if endsPhrase && !out.isEmpty { break }
            out.append(t)
        }
        return out
    }

    /// Words of the method description as maximal runs of letters/digits/underscore,
    /// so "TW" and "[LAKE]" match as whole words but "TWIN" does not.
    private static func wordRuns(_ text: String) -> Set<String> {
        Set(text.split { !($0.isLetter || $0.isNumber || $0 == "_") }.map(String.init))
    }

    // MARK: - Name keys

    /// Ordered distinctive words of a token list, for lake-identity matching.
    ///  - A single-letter token merges into the next non-generic one, so
    ///    "COEUR D ALENE" and "Coeur d&apos;Alene" both give COEUR DALENE.
    ///  - "C" before a lake word is CREEK ("TUTTLE C LK").
    ///  - Generic, stop, single-letter and two-letter tokens are dropped. Two-letter
    ///    tokens are dropped BEFORE normalization: they are indistinguishable from
    ///    state codes ("FT PECK LAKE MT"), so only CRK survives to become CREEK.
    ///    The prototype's golden runs used this order; keep it.
    static func nameKey(tokens phrase: [String]) -> [String] {
        var merged: [String] = []
        var i = 0
        while i < phrase.count {
            let t = phrase[i]
            let next = i + 1 < phrase.count ? phrase[i + 1] : nil
            if t == "C", let next, lakeWords.contains(next) {
                merged.append("CREEK"); i += 1; continue
            }
            if t.count == 1, let next, !genericWords.contains(next) {
                merged.append(t + next); i += 2; continue
            }
            merged.append(t); i += 1
        }
        return merged
            .filter { !genericWords.contains($0) && !keyStopWords.contains($0) && $0.count > 1 && !isTwoLetterWord($0) }
            .map { keyNormalization[$0] ?? $0 }
    }

    /// Key of a whole name (a directory lake or dam name). Not cut at locators:
    /// those are gauge-name grammar, and a lake name has none.
    static func nameKey(_ name: String) -> [String] {
        nameKey(tokens: tokens(name))
    }

    private static func isTwoLetterWord(_ t: String) -> Bool {
        t.unicodeScalars.count == 2 && t.unicodeScalars.allSatisfy { ("A"..."Z").contains($0) }
    }

    /// Every key a directory lake answers to: the whole name without parentheses,
    /// each "/"-separated part, and each parenthesized alias that isn't a state
    /// code. "Lanier (Sidney Lanier)" → [LANIER], [SIDNEY LANIER];
    /// "Eufaula / W.F. George" → [EUFAULA GEORGE], [EUFAULA], [GEORGE].
    static func lakeAliases(_ name: String) -> [[String]] {
        let (base, inners) = splitParentheses(name)
        var aliases = [nameKey(base)]
        for part in base.split(separator: "/", omittingEmptySubsequences: false) {
            let key = nameKey(String(part))
            if !key.isEmpty && !aliases.contains(key) { aliases.append(key) }
        }
        for inner in inners {
            let trimmed = inner.trimmingCharacters(in: .whitespaces)
            let isStateCode = trimmed.unicodeScalars.count == 2
                && trimmed.unicodeScalars.allSatisfy { ("A"..."Z").contains($0) || ("a"..."z").contains($0) }
            if !isStateCode { aliases.append(nameKey(inner)) }
        }
        return aliases.filter { !$0.isEmpty }
    }

    /// `name` with each "(…)" group (shortest match, same line) replaced by a space,
    /// plus the text inside each group.
    private static func splitParentheses(_ name: String) -> (base: String, inners: [String]) {
        let chars = Array(name)
        var base = ""
        var inners: [String] = []
        var i = 0
        while i < chars.count {
            if chars[i] == "(" {
                var j = i + 1
                while j < chars.count, chars[j] != ")", !chars[j].isNewline { j += 1 }
                if j < chars.count, chars[j] == ")" {
                    inners.append(String(chars[(i + 1)..<j]))
                    base.append(" ")
                    i = j + 1
                    continue
                }
            }
            base.append(chars[i])
            i += 1
        }
        return (base, inners)
    }

    /// One ordered key is a suffix of the other: "B EVERETT JORDAN" ~ "JORDAN",
    /// "SIDNEY LANIER" ~ "LANIER"; but "CARTERS REGULATION" !~ "CARTERS" and
    /// "WEST OKOBOJI" !~ "EAST OKOBOJI". An empty key matches nothing.
    static func keysMatch(_ a: [String], _ b: [String]) -> Bool {
        guard !a.isEmpty, !b.isEmpty else { return false }
        return a.count <= b.count ? Array(b.suffix(a.count)) == a : Array(a.suffix(b.count)) == b
    }

    /// True when `key` matches any of a lake's aliases (see `lakeAliases`).
    static func keysMatch(_ key: [String], _ aliases: [[String]]) -> Bool {
        aliases.contains { keysMatch(key, $0) }
    }
}
