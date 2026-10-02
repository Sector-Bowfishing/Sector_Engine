"""Certification matching (protocol section 3 + addendum B): stage6/extract.py unchanged except the collection and the
reflectance offset, set per process from the environment (CERT_COLLECTION, CERT_OFFSET)."""
import os, sys
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage6")
import extract as E
E.dws.S2_COLLECTION = os.environ.get("CERT_COLLECTION", E.dws.S2_COLLECTION)
E.dws.S2_OFFSET = float(os.environ.get("CERT_OFFSET", E.dws.S2_OFFSET))
print("collection", E.dws.S2_COLLECTION, "offset", E.dws.S2_OFFSET, flush=True)
E.main()
