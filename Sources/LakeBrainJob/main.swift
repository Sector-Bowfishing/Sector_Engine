//
//  LakeBrainJob — one run of the Lake Brain (no schedule; on demand)
//
//  usage: LakeBrainJob [--dry-run DIR | --rtdb URL] [--archive gs://BUCKET | --archive DIR]
//                      [--seed-archive gs://BUCKET] [--presence gs://BUCKET | DIR]
//                      [--scope pilots|fleet] [--lake ID]... [--force] [--backfill] [--no-shared-tva-archive]
//    --dry-run DIR      write every Brain RTDB path as a JSON file under DIR (no database)
//    --rtdb URL         write the Brain RTDB (default $SECTOR_BRAIN_RTDB_URL)
//    --archive X        history/baselines store; gs://… or a local directory (default: none)
//    --seed-archive X   read-only fallback for --archive (dry runs start from the real bucket)
//    --presence X       where presence/latest.json lives (private; default: --archive)
//    --scope            pilots (default: the 5 reviewed lakes) or fleet (all 621 directory lakes)
//    --lake ID          only this canonical lake id (repeatable); per-lake nodes only
//    --force            ignore plan() and recompute every lake in scope
//    --backfill         pull the full operator history (decades of CWMS daily)
//
//  GCS token: $SECTOR_GCS_ACCESS_TOKEN or the metadata server. RTDB token:
//  $SECTOR_BRAIN_ACCESS_TOKEN or the metadata server. Exits non-zero on failure.
//

import Foundation
import SectorEngine

let argv = CommandLine.arguments
func flag(_ name: String) -> String? { argv.firstIndex(of: name).flatMap { $0 + 1 < argv.count ? argv[$0 + 1] : nil } }
func flags(_ name: String) -> [String] { argv.indices.filter { argv[$0] == name && $0 + 1 < argv.count }.map { argv[$0 + 1] } }
let env = ProcessInfo.processInfo.environment

func archive(_ spec: String?, readOnly: Bool = false) -> LakeBrainArchive? {
    guard let s = spec else { return nil }
    if s.hasPrefix("gs://") { return GCSLakeBrainArchive(bucket: String(s.dropFirst(5)).trimmingCharacters(in: CharacterSet(charactersIn: "/")), readOnly: readOnly) }
    return LocalLakeBrainArchive(directory: s)
}

var options = LakeBrainRunOptions()
options.scope = LakeBrainRunOptions.Scope(rawValue: flag("--scope") ?? "pilots") ?? .pilots
let lakeArgs = flags("--lake")
if !lakeArgs.isEmpty { options.lakeIds = lakeArgs }
options.force = argv.contains("--force")
options.backfill = argv.contains("--backfill")
options.processingVersion = env["SECTOR_ENGINE_REVISION"] ?? env["K_REVISION"] ?? env["SECTOR_ENGINE_COMMIT"]

var store: BrainStore? = nil
var rest: RTDBRestStore? = nil
if let dir = flag("--dry-run") {
    store = LocalDirectoryStore(directory: dir)
    print("▶ dry run → \(dir)")
} else if let url = flag("--rtdb") ?? env["SECTOR_BRAIN_RTDB_URL"] {
    rest = RTDBRestStore(databaseURL: url); store = rest
    print("▶ Brain RTDB → \(url)")
} else {
    FileHandle.standardError.write(Data("LakeBrainJob: give --dry-run DIR or --rtdb URL (or SECTOR_BRAIN_RTDB_URL)\n".utf8))
    exit(2)
}

var hist = archive(flag("--archive"))
if let seed = archive(flag("--seed-archive"), readOnly: true) {
    hist = hist.map { LayeredLakeBrainArchive(primary: $0, seed: seed) } ?? seed
}
let presenceArchive = archive(flag("--presence")) ?? hist
// Read-only, one instance per bucket (only the Water Temp lane's TVA archive today).
let sharedTVA = GCSLakeBrainArchive(bucket: "sector-water-temp-archive", readOnly: true)
let shared: (String) -> LakeBrainArchive? = argv.contains("--no-shared-tva-archive") ? { _ in nil }
    : { $0 == sharedTVA.bucket ? sharedTVA : nil }
let feeds = PublicLakeLevelFeeds(sharedArchive: shared)
print("▶ archive \(hist?.uri ?? "none") · presence \(presenceArchive?.uri ?? "none") · scope \(options.scope.rawValue)\(options.force ? " · force" : "")\(options.backfill ? " · backfill" : "")")

let r = await LakeBrainRunner.run(store: store, feeds: feeds, archive: hist, presenceArchive: presenceArchive, options: options)
for l in r.lakes {
    let s = l.state
    print("  \(l.lakeId): \(l.plan.map { $0.action == .skip && options.force ? "SKIP→forced" : $0.action.rawValue } ?? "PROFILE") · \(s?.kind.rawValue ?? "-") \(s?.currentElevationFt.map { String(format: "%.2f ft", $0) } ?? "")"
          + " · level \(s?.levelState.rawValue ?? "-") · trend \(s?.trendState.rawValue ?? "-") · hist \(s?.historicalState.rawValue ?? "-")"
          + " · flood \(s?.floodPoolState.rawValue ?? "-") · baseline \(l.baseline?.status.rawValue ?? s?.baselineStatus.rawValue ?? "-") (\(l.historyRows) days)"
          + " · readiness \(l.profile.readiness["lake"] ?? "-") · presence \(l.presence.count)"
          + ((s?.provenance.qualityFlags).map { " · flags \($0.joined(separator: ","))" } ?? ""))
}
for e in r.archiveErrors { print("  ! \(e)") }
if let e = r.presenceError { print("  ! presence: \(e)") }
print("\(r.ok ? "✓" : "✗") \(r.lakes.count) lakes in \(r.durationMs) ms · health \(r.health)")
if let e = r.writeError { print("✗ \(e)") }
await rest?.shutdown()
exit(r.ok ? 0 : 1)
