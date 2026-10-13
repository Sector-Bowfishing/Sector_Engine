//
//  LakeBrainJobFlags.swift
//  Sector — Lake Brain job flags that decide whether the prospective prediction ledger runs
//
//  The `LakeBrainJob` executable cannot be unit-tested, so the one decision that must never regress lives here:
//  the ledger is ON unless the explicit `--no-ledger` flag is present. The production Cloud Run job
//  (jobs/lake-brain/deploy-job.sh) must never carry that flag; a test reads the deploy script and asserts it.
//  See docs/brains/LAKE_BRAIN_PREDICTION_LEDGER.md.
//

import Foundation

public enum LakeBrainJobFlags {
    public static let noLedger = "--no-ledger"

    /// False only when `--no-ledger` is present (dry runs, debugging, replay, local tests). Default: true.
    public static func ledgerEnabled(argv: [String]) -> Bool { !argv.contains(noLedger) }

    /// The line the job prints so a run's output always records which way the ledger went.
    public static func ledgerLine(enabled: Bool) -> String { "ledger: \(enabled ? "enabled" : "disabled")" }

    /// Stderr warning when a run that publishes to a real Brain RTDB (`--rtdb` / the env URL, not a dry run) has the ledger off.
    public static func publishWithoutLedgerWarning(argv: [String], hasRTDB: Bool) -> String? {
        guard !ledgerEnabled(argv: argv), hasRTDB else { return nil }
        return "WARNING: --no-ledger on a run that publishes to the Brain RTDB: this run leaves NO prediction record. Production must not use it."
    }

    /// Applies the flags to run options (only the ledger switch today).
    public static func apply(argv: [String], to options: inout LakeBrainRunOptions) {
        options.ledgerEnabled = ledgerEnabled(argv: argv)
    }
}
