FIXTURE ONLY. Fake lakes ('FIXTURE <Name> Lake|ZZ') for tests/test_preseed_fleet.py. Written by fixture_lib.make_fixture_batch, i.e. by the real
jobs/lake-brain/review/ingest_review_result.py run on a synthetic pack. Not a review result, not a bindings table. preseed_fleet.py refuses these files
without --allow-fixture, and always with --gcs-prefix. Regenerate with: python3 -c 'import fixture_lib as F; F.make_fixture_batch(out_dir, scratch_dir)'.
