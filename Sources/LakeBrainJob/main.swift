//
//  LakeBrainJob — one run of the Lake Brain (no schedule; on demand)
//
//  usage: LakeBrainJob [--dry-run DIR | --rtdb URL] [--archive gs://BUCKET | --archive DIR]
//                      [--seed-archive gs://BUCKET] [--presence gs://BUCKET | DIR]
//                      [--scope pilots|fleet] [--lake ID]... [--force] [--backfill] [--no-shared-tva-archive]
//                      [--include-candidates]   (ONLY with --dry-run DIR) [--no-ledger]
//    --no-ledger        do NOT write the prospective prediction ledger (dry runs, debugging, replay, local tests). The ledger is ON by
//                       default and the production job (jobs/lake-brain/deploy-job.sh) never passes this; the run prints `ledger: disabled`.
//    --dry-run DIR      write every Brain RTDB path as a JSON file under DIR (no database)
//    --read-rtdb URL    with --dry-run: read the live Brain RTDB (GET only) for plan()/previous profiles
//    --rtdb URL         write the Brain RTDB (default $SECTOR_BRAIN_RTDB_URL)
//    --archive X        history/baselines store; gs://… or a local directory (default: none)
//    --seed-archive X   read-only fallback for --archive (dry runs start from the real bucket)
//    --presence X       where presence/latest.json lives (private; default: --archive)
//    --scope            pilots (default: the 5 reviewed lakes) or fleet (all 621 directory lakes)
//    --lake ID          only this canonical lake id (repeatable); per-lake nodes only
//    --force            ignore plan() and recompute every lake in scope
//    --backfill         pull the full operator history (decades of CWMS daily)
//    --include-candidates  DRY RUN ONLY: evaluate the CANDIDATE bindings (the generated MACHINE_VERIFIED table) as if reviewed.
//                       Refused with --rtdb. Local files only: the history archive is a local directory (default DIR/_archive;
//                       a gs:// --archive / --seed-archive is refused), the shared TVA archive is not read, and every output is
//                       marked dryRunCandidate. Combine with --lake ID (repeatable) to exercise a few lakes.
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

func refuse(_ message: String) -> Never {
    FileHandle.standardError.write(Data("LakeBrainJob: \(message)\n".utf8))
    exit(2)
}

let includeCandidates = argv.contains("--include-candidates")
if includeCandidates {
    guard flag("--dry-run") != nil else { refuse("--include-candidates is valid only together with --dry-run DIR") }
    if argv.contains("--rtdb") { refuse("--include-candidates is refused with --rtdb: candidates never publish") }
    for name in ["--archive", "--seed-archive", "--presence"] where (flag(name) ?? "").hasPrefix("gs://") {
        refuse("--include-candidates uses LOCAL files only; \(name) \(flag(name)!) is a bucket")
    }
}

var options = LakeBrainRunOptions()
options.includeCandidates = includeCandidates
options.scope = LakeBrainRunOptions.Scope(rawValue: flag("--scope") ?? "pilots") ?? .pilots
let lakeArgs = flags("--lake")
if !lakeArgs.isEmpty { options.lakeIds = lakeArgs }
options.force = argv.contains("--force")
options.backfill = argv.contains("--backfill")
LakeBrainJobFlags.apply(argv: argv, to: &options)
options.processingVersion = env["SECTOR_ENGINE_REVISION"] ?? env["K_REVISION"] ?? env["SECTOR_ENGINE_COMMIT"]

var store: BrainStore? = nil
var rest: RTDBRestStore? = nil
if let dir = flag("--dry-run") {
    if let live = flag("--read-rtdb") {
        rest = try RTDBRestStore(databaseURL: live, brainId: LakeBrainSpec.brainId)
        store = ReadThroughDryRunStore(reader: rest!, writer: LocalDirectoryStore(directory: dir, brainId: LakeBrainSpec.brainId))
        print("▶ dry run → \(dir) (reads \(live), GET only)")
    } else {
        store = LocalDirectoryStore(directory: dir, brainId: LakeBrainSpec.brainId)
        print("▶ dry run → \(dir)")
    }
} else if let url = flag("--rtdb") ?? env["SECTOR_BRAIN_RTDB_URL"] {
    rest = try RTDBRestStore(databaseURL: url, brainId: LakeBrainSpec.brainId); store = rest
    print("▶ Brain RTDB → \(url)")
} else {
    FileHandle.standardError.write(Data("LakeBrainJob: give --dry-run DIR or --rtdb URL (or SECTOR_BRAIN_RTDB_URL)\n".utf8))
    exit(2)
}

var hist = archive(flag("--archive") ?? (includeCandidates ? flag("--dry-run").map { $0 + "/_archive" } : nil))
if let seed = archive(flag("--seed-archive"), readOnly: true) {
    hist = hist.map { LayeredLakeBrainArchive(primary: $0, seed: seed) } ?? seed
}
let presenceArchive = archive(flag("--presence")) ?? hist
// Read-only, one instance per bucket (only the Water Temp lane's TVA archive today).
let sharedTVA = GCSLakeBrainArchive(bucket: "sector-water-temp-archive", readOnly: true)
let shared: (String) -> LakeBrainArchive? = (argv.contains("--no-shared-tva-archive") || includeCandidates) ? { _ in nil }
    : { $0 == sharedTVA.bucket ? sharedTVA : nil }
let feeds = PublicLakeLevelFeeds(sharedArchive: shared)
if includeCandidates { print("▶ CANDIDATE DRY RUN: unreviewed bindings evaluated as if reviewed; local files only; outputs marked dryRunCandidate") }
print("▶ \(LakeBrainJobFlags.ledgerLine(enabled: options.ledgerEnabled))")
if let w = LakeBrainJobFlags.publishWithoutLedgerWarning(argv: argv, hasRTDB: rest != nil && flag("--dry-run") == nil) {
    FileHandle.standardError.write(Data("LakeBrainJob: \(w)\n".utf8))
}
print("▶ archive \(hist?.uri ?? "none") · presence \(presenceArchive?.uri ?? "none") · scope \(options.scope.rawValue)\(options.force ? " · force" : "")\(options.backfill ? " · backfill" : "")")

let r = await LakeBrainRunner.run(store: store, feeds: feeds, archive: hist, presenceArchive: presenceArchive, options: options)
for l in r.lakes {
    let s = l.state
    print("  \(l.lakeId): \(l.plan.map { $0.action == .skip && options.force ? "SKIP→forced" : $0.action.rawValue } ?? "PROFILE") · \(s?.kind.rawValue ?? "-") \(s?.currentElevationFt.map { String(format: "%.2f ft", $0) } ?? "")"
          + " · level \(s?.levelState.rawValue ?? "-") · trend \(s?.trendState.rawValue ?? "-") · hist \(s?.historicalState.rawValue ?? "-")"
          + " · flood \(s?.floodPoolState.rawValue ?? "-") · baseline \(l.baseline?.status.rawValue ?? s?.baselineStatus.rawValue ?? "-") (\(l.historyRows) days)"
          + " · readiness \(l.profile.readiness["lake"] ?? "-") · presence \(l.presence.count)"
          + ((s?.provenance.qualityFlags).map { " · flags \($0.joined(separator: ","))" } ?? "")
          + (l.dryRunCandidate ? " · dryRunCandidate" : ""))
}
for e in r.archiveErrors { print("  ! \(e)") }
if let e = r.presenceError { print("  ! presence: \(e)") }
print("  \(LakeBrainJobFlags.ledgerLine(enabled: r.ledgerStatus == "enabled"))"
      + (r.ledgerObject.map { " · \($0) (\(r.ledgerRecords) records)" } ?? ""))
print("\(r.ok ? "✓" : "✗") \(r.lakes.count) lakes in \(r.durationMs) ms · health \(r.health)")
if let e = r.writeError { print("✗ \(e)") }
await rest?.shutdown()
exit(r.ok ? 0 : 1)
