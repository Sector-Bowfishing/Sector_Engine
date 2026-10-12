//
//  WaterTempBrainJob — one fleet run of the Water Temperature Brain
//
//  usage: WaterTempBrainJob [--dry-run DIR] [--rtdb URL] [--lake ID] [--limit N] [--concurrency N]
//    --dry-run DIR  write every Brain RTDB path as a JSON file under DIR (no database)
//    --rtdb URL     write the Brain RTDB (default $SECTOR_BRAIN_RTDB_URL)
//    --lake ID      one canonical lake id, e.g. "Guntersville|AL" (repeatable); per-lake nodes only
//    --limit N      the first N directory lakes; per-lake nodes only
//
//  Runs the production water-temperature path (sensor → nearby USGS gauge →
//  surface-energy-balance-v2 → WaterTemperatureResolver) for each lake and
//  publishes it. Exits non-zero if the run failed or any write failed.
//

import Foundation
import SectorEngine

let argv = CommandLine.arguments
func flag(_ name: String) -> String? { argv.firstIndex(of: name).flatMap { $0 + 1 < argv.count ? argv[$0 + 1] : nil } }
func flags(_ name: String) -> [String] { argv.indices.filter { argv[$0] == name && $0 + 1 < argv.count }.map { argv[$0 + 1] } }
let env = ProcessInfo.processInfo.environment

var options = WaterTemperatureBrainRunOptions()
let lakeArgs = flags("--lake")
if !lakeArgs.isEmpty { options.lakeIds = lakeArgs }
options.limit = flag("--limit").flatMap(Int.init)
options.concurrency = flag("--concurrency").flatMap(Int.init) ?? 6
options.processingVersion = env["SECTOR_ENGINE_REVISION"] ?? env["K_REVISION"] ?? env["SECTOR_ENGINE_COMMIT"]

let store: BrainStore
var rest: RTDBRestStore? = nil
if let dir = flag("--dry-run") {
    store = LocalDirectoryStore(directory: dir)
    print("▶ dry run → \(dir)")
} else if let url = flag("--rtdb") ?? env["SECTOR_BRAIN_RTDB_URL"] {
    rest = RTDBRestStore(databaseURL: url)
    store = rest!
    print("▶ Brain RTDB → \(url)")
} else {
    FileHandle.standardError.write(Data("WaterTempBrainJob: give --dry-run DIR or --rtdb URL (or SECTOR_BRAIN_RTDB_URL)\n".utf8))
    exit(2)
}

let r = await WaterTemperatureBrainRunner.run(store: store, options: options)
print("✓ \(r.lakes) lakes in \(r.durationMs) ms · health \(r.health) · kinds \(r.kindCounts.sorted { $0.key < $1.key })"
      + " · readiness \(r.readinessCounts.sorted { $0.key < $1.key }) · model failures \(r.modelFailures) · stale \(r.staleLakes)")
if let e = r.writeError { print("✗ \(e)") }
await rest?.shutdown()
exit(r.ok ? 0 : 1)
