import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))      # jobs/lake-brain/history (preseed_fleet)
sys.path.insert(0, HERE)                       # fixture_lib
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "review"))   # ingest_review_result, held_lakes
