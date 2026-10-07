# Water Temp TVA discharge archiver

**Status: built and tested, NOT DEPLOYED.** Deploying needs Michael's explicit
approval (`deploy-job.sh` refuses to run without `I_HAVE_MICHAELS_APPROVAL=yes`).

Hourly, append-only archive of TVA RestApi `observed-data` (hourly reservoir/tailwater
elevation and discharge) and `predicted-data` (3-day inflow/outflow outlook) for the
Water Temp development cascade: NKJT1 (Nickajack), GVDA1 (Guntersville), WHLA1
(Wheeler), WLSA1 (Wilson), PICT1 (Pickwick). TVA keeps only today's ~8 hourly rows,
so without this the history is lost.

Separate from Clarity's `hydrology-hourly`: own private bucket
(`sector-water-temp-archive`), service account, job and schedule. No Cloud Run
service or production traffic is touched.

Guarantees: exact raw responses kept (`raw/<DAM>/<observed|predicted>/<hour>Z.json`);
an archived hour is never overwritten (later differing values go to `revisions`);
no gap filling; any schema change or empty response raises and the run exits
non-zero; reruns are idempotent; Cloud Storage writes use generation preconditions.

    python -m pytest jobs/water-temp-tva-archive -q        # 13 tests
    python jobs/water-temp-tva-archive/archive.py --local-dir /tmp/wt   # live dry run, local only
