#!/usr/bin/env python3
"""Automatic research discovery for the eight-Brain campaign coordinator (owner directive 2026-10-23: "the entire research flow works
automatically"). Stdlib + numpy-free. Used by tools/research/campaign.py; never run against production.

  gaps         each Brain's open gaps: Engine brains/<dir>/research/GAPS.json, or, when it is missing, RECONSTRUCTED from the frozen score
               blockers, the latest research closeout's Blockers section and candidate blockers -> <folder>/research/GAPS.generated.json
  inputs       a Brain's declared research inputs (discovery.json): present / reconstructed (git show of a research branch) / LIMITATION
               (external private data). A missing input never stops the campaign.
  acquire      per-Brain connectors download legitimate public evidence from ALLOWLISTED hosts only (USGS, WQP, Open-Meteo archive, GBIF,
               Crossref), with retries, a per-host rate limit, a size cap, and provenance (url, sha256, bytes, retrievedAt, license) in
               <folder>/sources/<campaign>/PROVENANCE.json, registered in the Brain's manifest.json (RECONSTRUCTABLE). Idempotent on resume.
  analyze      OFFLINE, deterministic: reads only the saved evidence and existing research inputs; returns metrics, auto-generated findings
               (sector-research-findings-v1, thresholds pre-declared in discovery.json), weak areas for follow-up, limitations and the
               score impact. The validate stage re-runs it from the hashed evidence (reproducibility) before applying the thresholds.

Nothing here approves knowledge, writes to Firebase/Cloud, reads sealed holdouts or opens protected-truth values: the Water Temp
protected-lake connector reads WQP *activity metadata* only (dates, depths) and reports an approval-gated recount, never temperatures.
"""
from __future__ import annotations

import csv
import datetime as dt
import glob
import gzip
import hashlib
import io
import json
import math
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ALLOWED_HOSTS = ("waterservices.usgs.gov", "www.waterqualitydata.us", "archive-api.open-meteo.com", "api.gbif.org", "api.crossref.org")   # built-in floor
DENY_HOSTS = ("firebaseio.com", "googleapis.com", "cloud.google.com", "run.app", "cloudfunctions.net", "appspot.com", "gstatic.com", "localhost")
SOURCES_JSON = os.path.join(HERE, "sources.json")


def _registry_entries(home: str | None) -> list:
    out = []
    for p in (SOURCES_JSON, os.path.join(home, "shared", "sources", "registry.json") if home else None):
        if p and os.path.exists(p):
            try:
                out += json.load(open(p, encoding="utf-8")).get("sources") or []
            except (ValueError, OSError):
                pass
    return out


def allowed_hosts(home: str | None = None) -> tuple:
    """Built-in floor + every ACTIVE registered source (reviewed tools/research/sources.json, and the research-home overlay written by
    `campaign.py register-source`). A host is never allowed by being mentioned in a document, a response or a redirect."""
    hosts = set(ALLOWED_HOSTS)
    for e in _registry_entries(home):
        if e.get("status") == "ACTIVE":
            hosts |= {h for h in e.get("hosts") or [] if not any(h == d or h.endswith("." + d) for d in DENY_HOSTS)}
    return tuple(sorted(hosts))


def register_source(home: str, sid: str, hosts: list, licence: str, purpose: str, rationale: str, adapter: str = "http-json", probe: bool = True) -> dict:
    """Explicit, controlled source registration: https public DNS names only (no IP literals, no cloud/Firebase hosts), a licence, a purpose, a
    rationale; a live reachability probe unless disabled; recorded with who/when in the research-home overlay (shared/sources/registry.json)."""
    import ipaddress
    for h in hosts:
        try:
            ipaddress.ip_address(h)
            raise ValueError(f"refused: {h} is an IP literal")
        except ValueError as e:
            if "refused" in str(e):
                raise
        if not re.fullmatch(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+", h) or any(h == d or h.endswith("." + d) for d in DENY_HOSTS):
            raise ValueError(f"refused: {h} is not an allowed public research host")
    if not (licence and purpose and rationale):
        raise ValueError("refused: licence, purpose and rationale are required")
    reach = None
    if probe:
        try:
            urllib.request.urlopen(urllib.request.Request(f"https://{hosts[0]}/", headers={"User-Agent": USER_AGENT}), timeout=30).read(1)
            reach = "reachable"
        except urllib.error.HTTPError as e:
            reach = f"reachable (HTTP {e.code})"
        except Exception as e:                                       # noqa: BLE001
            raise ValueError(f"refused: {hosts[0]} did not answer ({type(e).__name__})")
    p = os.path.join(home, "shared", "sources", "registry.json")
    doc = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"schema": "sector-research-sources-v1", "sources": []}
    doc["sources"] = [x for x in doc["sources"] if x.get("id") != sid] + [{"id": sid, "hosts": hosts, "license": licence, "purpose": purpose, "rationale": rationale,
                                                                          "adapter": adapter, "status": "ACTIVE", "registeredAt": now_iso(), "probe": reach,
                                                                          "registeredBy": "campaign.py register-source"}]
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(doc, open(p + ".tmp", "w", encoding="utf-8"), indent=1)
    os.replace(p + ".tmp", p)
    return doc["sources"][-1]
LICENSES = {"waterservices.usgs.gov": "US Government public domain (USGS)", "www.waterqualitydata.us": "US Government public domain (WQP: USGS/EPA)",
            "archive-api.open-meteo.com": "CC BY 4.0 (Open-Meteo)", "api.gbif.org": "GBIF occurrence metadata (record licences CC0/CC BY/CC BY-NC)",
            "api.crossref.org": "Crossref metadata (CC0); article texts are not downloaded"}
MAX_BYTES = 50 * 1024 * 1024
USER_AGENT = "SectorResearchCampaign/1.0 (research discovery; contact via repository owner)"
STOP = {"lake", "lakes", "reservoir", "res", "the", "of", "at", "near", "pond", "lk", "dam", "and", "river", "county", "no", "is", "a", "an", "in",
        "on", "for", "to", "not", "has", "have", "been", "with", "by", "be", "are", "or", "its", "it", "any", "from", "that", "this", "only", "can",
        "per", "one", "two", "all", "each", "yet", "than", "sector"}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_config(path: str | None = None) -> dict:
    with open(path or os.path.join(HERE, "discovery.json"), encoding="utf-8") as fh:
        return json.load(fh)


def safe_key(s: str) -> str:
    """Metric paths are dotted: keys never contain a dot."""
    return re.sub(r"[^A-Za-z0-9_-]", "", s.replace(".", "").replace(" ", "_"))


# ------------------------------------------------------------------------------------------------------------------------------- fetcher
class FetchError(RuntimeError):
    pass


class Fetcher:
    """HTTP GET restricted to ALLOWED_HOSTS: retries with backoff, >= `gap` seconds between requests to one host, size cap. 404 -> None."""

    def __init__(self, retries: int = 3, timeout: int = 90, gap: float = 0.35, home: str | None = None):
        self.retries, self.timeout, self.gap, self.home = retries, timeout, gap, home
        self._last: dict = {}
        self._lock = threading.Lock()
        self.requests = 0

    def url(self, base: str, params=None) -> str:
        host = urllib.parse.urlparse(base).hostname
        if urllib.parse.urlparse(base).scheme != "https" or host not in allowed_hosts(self.home):
            raise FetchError(f"refused: {host} is not an allowlisted research source")
        return base + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")

    def get(self, base: str, params=None, accept: str | None = None) -> bytes | None:
        url = self.url(base, params)
        host = urllib.parse.urlparse(url).hostname
        err = None
        for attempt in range(self.retries):
            with self._lock:
                wait = self._last.get(host, 0) + self.gap - time.time()
                if wait > 0:
                    time.sleep(wait)
                self._last[host] = time.time()
                self.requests += 1
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity", **({"Accept": accept} if accept else {})})
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    data = r.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise FetchError(f"response over {MAX_BYTES} bytes: {url[:120]}")
                return data
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None
                err = f"HTTP {e.code}"
                if e.code not in (429, 500, 502, 503, 504):
                    break
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                err = f"{type(e).__name__}: {e}"
            time.sleep(min(20, 2 ** attempt * 1.5))
        raise FetchError(f"{err} after {self.retries} attempts: {url[:160]}")


class OfflineFetcher(Fetcher):
    """Used by tests and by `--offline`: every request fails (the campaign must still complete)."""

    def get(self, base, params=None, accept=None):
        self.url(base, params)
        raise FetchError("offline: network acquisition disabled")


# ------------------------------------------------------------------------------------------------------------------------------- evidence store
class Evidence:
    """Downloads for one Brain and campaign: <folder>/sources/<campaign>/<connector>/<name> + PROVENANCE.json; resumable."""

    def __init__(self, home: str, folder: str, cid: str, fetcher: Fetcher):
        self.home, self.folder, self.cid, self.fetcher = home, folder, cid, fetcher
        src = os.path.join(home, folder, "sources")
        # a read-only sources/ is protected (immutable reference data): never chmod it, write beside it under research/
        self.base = "sources" if (os.access(src, os.W_OK) if os.path.isdir(src) else os.access(os.path.join(home, folder), os.W_OK)) \
            else os.path.join("research", "discovery-sources")
        self.root = os.path.join(home, folder, self.base, cid)
        self.prov_path = os.path.join(self.root, "PROVENANCE.json")
        self.prov = json.load(open(self.prov_path, encoding="utf-8")) if os.path.exists(self.prov_path) else {"campaignId": cid, "files": {}}
        self.failures: list = []
        self.new = 0

    def rel(self, connector: str, name: str) -> str:
        return os.path.join(self.folder, self.base, self.cid, connector, name)

    def _earlier(self, url: str):
        """Evidence already collected for the same URL by an earlier campaign (same bytes on disk): reused, never re-downloaded."""
        if not hasattr(self, "_idx"):
            self._idx = {}
            for pat in ("sources/*/PROVENANCE.json", "research/discovery-sources/*/PROVENANCE.json"):
                for pp in sorted(glob.glob(os.path.join(self.home, self.folder, pat))):
                    if os.path.basename(os.path.dirname(pp)) == self.cid:
                        continue
                    try:
                        for r, rec in json.load(open(pp, encoding="utf-8")).get("files", {}).items():
                            if rec.get("status") == "SAVED" and os.path.exists(os.path.join(self.home, r)) and sha256(os.path.join(self.home, r)) == rec.get("sha256"):
                                self._idx[rec["url"]] = (r, rec)
                    except (ValueError, OSError):
                        continue
        return self._idx.get(url)

    def fetch(self, connector: str, name: str, base: str, params=None, purpose: str = "", accept: str | None = None) -> str | None:
        """Returns the research-home-relative path of the saved file (None when the source has no data or the request failed)."""
        rel = self.rel(connector, name)
        full = os.path.join(self.home, rel)
        if rel in self.prov["files"] and os.path.exists(full):
            return rel if self.prov["files"][rel].get("bytes") else None
        url0 = self.fetcher.url(base, params)
        old = self._earlier(url0)
        if old:
            os.makedirs(os.path.dirname(full), exist_ok=True)
            if subprocess.run(["cp", "-c", os.path.join(self.home, old[0]), full], capture_output=True).returncode:
                import shutil
                shutil.copy2(os.path.join(self.home, old[0]), full)
            self.prov["files"][rel] = {**old[1], "reusedFrom": old[0], "reusedAt": now_iso(), "connector": connector, "purpose": purpose or old[1].get("purpose")}
            self.reused = getattr(self, "reused", 0) + 1
            return rel
        try:
            data = self.fetcher.get(base, params, accept)
        except FetchError as e:
            self.failures.append({"connector": connector, "name": name, "error": str(e)[:300]})
            return None
        url = self.fetcher.url(base, params)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        if data is None:                                  # the source answered "no data" (404): recorded, nothing saved
            self.prov["files"][rel] = {"url": url, "bytes": 0, "status": "NO_DATA", "retrievedAt": now_iso(), "connector": connector}
            return None
        tmp = full + ".part"
        open(tmp, "wb").write(data)
        os.replace(tmp, full)
        self.new += 1
        self.prov["files"][rel] = {"url": url, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "retrievedAt": now_iso(),
                                   "license": LICENSES.get(urllib.parse.urlparse(url).hostname, "see source"), "connector": connector,
                                   "purpose": purpose, "status": "SAVED"}
        return rel

    def save(self) -> None:
        os.makedirs(self.root, exist_ok=True)
        tmp = self.prov_path + ".tmp"
        json.dump(self.prov, open(tmp, "w", encoding="utf-8"), indent=1, sort_keys=True)
        os.replace(tmp, self.prov_path)

    def register(self, manifest_lock) -> int:
        """RS-02: every saved source file is registered in the Brain's manifest.json (RECONSTRUCTABLE: re-download from the recorded URL)."""
        saved = {r: p for r, p in self.prov["files"].items() if p.get("status") == "SAVED"}
        if not saved:
            return 0
        mpath = os.path.join(self.home, self.folder, "manifest.json")
        with manifest_lock:
            m = json.load(open(mpath, encoding="utf-8"))
            ids = {f"{self.cid}:source:{os.path.relpath(r, os.path.join(self.folder, self.base, self.cid))}": r for r in saved}
            m["items"] = [i for i in m.get("items") or [] if i.get("id") not in ids]
            for iid, r in sorted(ids.items()):
                p = saved[r]
                m["items"].append({"id": iid, "workspacePath": os.path.relpath(r, self.folder), "sha256": p["sha256"], "bytes": p["bytes"],
                                   "source": p["url"], "retrievedAt": p["retrievedAt"], "license": p["license"], "retention": "RECONSTRUCTABLE",
                                   "provenance": f"tools/research/discovery.py connector {p['connector']} (campaign {self.cid})",
                                   "reconstruction": "re-download from the recorded source URL"})
            m["lastUpdated"] = now_iso()
            tmp = mpath + ".tmp"
            json.dump(m, open(tmp, "w", encoding="utf-8"), indent=1)
            os.replace(tmp, mpath)
        return len(saved)

    def saved(self, connector: str | None = None) -> dict:
        return {r: p for r, p in self.prov["files"].items() if p.get("status") == "SAVED" and (connector is None or p["connector"] == connector)}


# ------------------------------------------------------------------------------------------------------------------------------- gaps
def _closeout_blockers(folder_path: str) -> list[str]:
    out = []
    for p in sorted(glob.glob(os.path.join(folder_path, "closeouts", "*.md")))[-2:]:
        text = open(p, encoding="utf-8").read()
        m = re.search(r"^##\s*Blockers\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
        if not m:
            continue
        for line in m.group(1).splitlines():
            line = line.strip(" -*\t")
            if len(line) > 25 and not line.lower().startswith(("none", "candidate score")):
                out.append((os.path.basename(p), line[:300]))
    return out


def load_gaps(engine: str, home: str, bid: str, folder: str, brain_dir: str) -> dict:
    """Open gaps for a Brain. A missing GAPS.json is RECONSTRUCTED (never a campaign stop)."""
    p = os.path.join(engine, "brains", brain_dir, "research", "GAPS.json")
    if os.path.exists(p):
        doc = json.load(open(p, encoding="utf-8"))
        gaps = [g for g in doc.get("gaps") or [] if str(g.get("status", "OPEN")).upper() not in ("CLOSED", "DONE", "RESOLVED")]
        return {"source": os.path.relpath(p, engine), "reconstructed": False, "gaps": gaps}
    prefix = re.sub(r"[^A-Z]", "", bid.upper()) or "GAP"
    gaps, sources = [], []
    fz = os.path.join(engine, "docs", "brains", "scoring", "frozen-scores.json")
    if os.path.exists(fz):
        rec = json.load(open(fz, encoding="utf-8")).get(bid) or {}
        for b in rec.get("scoreBlockers") or []:
            gaps.append({"id": f"{prefix}-GEN-{safe_key(b.get('gate', 'score')).upper()}", "type": "score", "title": b.get("why") or b.get("gate"),
                         "source": "docs/brains/scoring/frozen-scores.json scoreBlockers", "nextOpportunity": rec.get("nextScoreOpportunity")})
        if rec:
            sources.append("frozen-scores.json")
    fpath = os.path.join(home, folder)
    for i, (name, line) in enumerate(_closeout_blockers(fpath)):
        gaps.append({"id": f"{prefix}-GEN-CLOSEOUT-{i + 1}", "type": "research", "title": line, "source": f"closeouts/{name} Blockers"})
        sources.append(f"closeouts/{name}")
    for c in sorted(glob.glob(os.path.join(fpath, "candidates", "**", "*.json"), recursive=True))[-20:]:
        try:
            doc = json.load(open(c, encoding="utf-8"))
        except (ValueError, OSError):
            continue
        for b in (doc.get("blockers") or [])[:5] if isinstance(doc, dict) else []:
            t = b if isinstance(b, str) else (b.get("why") or b.get("title") or json.dumps(b)[:200])
            gaps.append({"id": f"{prefix}-GEN-CAND-{len(gaps) + 1}", "type": "candidate", "title": str(t)[:300],
                         "source": os.path.relpath(c, home)})
            sources.append(os.path.relpath(c, home))
    seen, uniq = set(), []
    for g in gaps:
        k = g["title"].lower()[:120]
        if k not in seen:
            seen.add(k)
            uniq.append(g)
    doc = {"schemaVersion": 1, "brainId": bid, "generatedAt": now_iso(), "generatedBy": "tools/research/discovery.py load_gaps",
           "note": f"Engine brains/{brain_dir}/research/GAPS.json is missing: reconstructed from the sources below. Review before copying into the Engine.",
           "sources": sorted(set(sources)), "gaps": uniq}
    out = os.path.join(fpath, "research", "GAPS.generated.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".tmp"
    json.dump(doc, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, out)
    return {"source": os.path.relpath(out, home), "reconstructed": True, "gaps": uniq}


# ------------------------------------------------------------------------------------------------------------------------------- inputs
def check_inputs(engine: str, home: str, spec: list) -> dict:
    """Declared inputs: present, reconstructed (git show <ref>:<path> from this repository), or a recorded LIMITATION. Never raises."""
    present, rebuilt, limits = [], [], []
    env = {}
    dev_root = os.environ.get("SECTOR_DEV_ROOT") or os.path.dirname(os.path.abspath(home))        # sibling research/repo folders are looked for here, never hard-coded
    for it in spec or []:
        if it.get("env"):
            v = os.environ.get(it["env"], "")
            if not (v and os.path.exists(v)):
                for rel_ in it.get("search") or []:                                              # an input that exists locally is CONNECTED automatically
                    cand_ = os.path.join(dev_root, rel_)
                    if os.path.exists(cand_):
                        v = cand_
                        env[it["env"]] = cand_
                        break
            (present if v and os.path.exists(v) else limits).append(
                it["env"] if v and os.path.exists(v) else {"input": f"${it['env']}", "limitation": it.get("limitation", "external input not available")})
            continue
        full = os.path.join(home, it["path"])
        if os.path.exists(full):
            present.append(it["path"])
            continue
        rc = it.get("reconstruct") or {}
        if rc.get("gitShow"):
            r = subprocess.run(["git", "-C", engine, "show", rc["gitShow"]], capture_output=True)
            if r.returncode == 0 and r.stdout:
                os.makedirs(os.path.dirname(full), exist_ok=True)
                open(full + ".part", "wb").write(r.stdout)
                os.replace(full + ".part", full)
                rebuilt.append({"input": it["path"], "from": f"git show {rc['gitShow']}", "sha256": sha256(full)})
                continue
        limits.append({"input": it["path"], "limitation": it.get("limitation") or "missing and not reconstructable here",
                       "reconstructionTried": rc or None})
    return {"present": present, "reconstructed": rebuilt, "limitations": limits, "env": env}


# ------------------------------------------------------------------------------------------------------------------------------- shared helpers
def fleet(home: str, cfg: dict) -> list[dict]:
    """The Sector lake fleet with coordinates (research-home forcing files: <Name>_<ST>.json with latitude/longitude)."""
    rows = []
    for p in sorted(glob.glob(os.path.join(home, cfg["fleetForcingDir"], "*.json"))):
        stem = os.path.basename(p)[:-5]
        try:
            d = json.load(open(p, encoding="utf-8"))
        except (ValueError, OSError):
            continue
        st = stem.rsplit("_", 1)[-1] if re.search(r"_[A-Z]{2}$", stem) else ""
        rows.append({"key": safe_key(stem), "stem": stem, "name": stem[: -3].replace("_", " ") if st else stem.replace("_", " "), "state": st,
                     "lat": d.get("latitude"), "lon": d.get("longitude"), "forcing": os.path.relpath(p, home)})
    return [r for r in rows if isinstance(r["lat"], (int, float)) and isinstance(r["lon"], (int, float))]


def tokens(s: str) -> set:
    return {t for t in re.split(r"[^a-z0-9]+", s.lower()) if len(t) >= 4 and t not in STOP}


def parse_rdb(data: bytes) -> list[dict]:
    lines = [ln for ln in data.decode("utf-8", "replace").splitlines() if ln and not ln.startswith("#")]
    if len(lines) < 2:
        return []
    head = lines[0].split("\t")
    return [dict(zip(head, ln.split("\t"))) for ln in lines[2:]]


def usgs_sites(ev: Evidence, connector: str, states: list[str], params: str) -> dict:
    """USGS lake sites (siteType LK) with daily values of `params`, per state (one request per state; 404 = no sites)."""
    sites = {}
    for stc in sorted(set(s for s in states if s)):
        rel = ev.fetch(connector, f"sites_{stc}.rdb", "https://waterservices.usgs.gov/nwis/site/",
                       {"format": "rdb", "stateCd": stc, "siteType": "LK", "parameterCd": params, "hasDataTypeCd": "dv", "siteStatus": "all"},
                       purpose=f"USGS lake sites with daily {params} in {stc}")
        if rel:
            for r in parse_rdb(open(os.path.join(ev.home, rel), "rb").read()):
                try:
                    sites[r["site_no"]] = {"site": r["site_no"], "name": r.get("station_nm", ""), "lat": float(r["dec_lat_va"]),
                                           "lon": float(r["dec_long_va"]), "state": stc}
                except (KeyError, ValueError):
                    continue
    return sites


def match_sites(lake: dict, sites: dict, radius: float, exclude: set) -> list[dict]:
    """Name-matched USGS sites within `radius` degrees of the lake (a distance-only match picks up other water bodies)."""
    lt = tokens(lake["name"])
    out = []
    for s in sites.values():
        if s["site"] in exclude or abs(s["lat"] - lake["lat"]) > radius or abs(s["lon"] - lake["lon"]) > radius:
            continue
        if lt & tokens(s["name"]):
            out.append({**s, "dist": round(math.hypot(s["lat"] - lake["lat"], s["lon"] - lake["lon"]), 4)})
    return sorted(out, key=lambda s: (s["dist"], s["site"]))


def dv_series(path: str, prefer_stat: str = "00003") -> tuple[dict, str]:
    """USGS DV JSON -> {date: value} for the preferred statistic (mean); max/min midrange when no mean is published."""
    d = json.load(open(path, encoding="utf-8"))
    series = {}
    for ts in d.get("value", {}).get("timeSeries", []):
        stat = ts["name"].split(":")[-1]
        for blk in ts.get("values", []):
            desc = ((blk.get("method") or [{}])[0].get("methodDescription") or "").strip()
            vals = {}
            for v in blk.get("value", []):
                try:
                    x = float(v["value"])
                except (TypeError, ValueError):
                    continue
                if x <= -999 or any(q in ("Ice", "Eqp", "Dis", "Mnt", "Bkw", "Ssn", "***") for q in v.get("qualifiers") or []):
                    continue
                vals[v["dateTime"][:10]] = x
            if vals:
                series.setdefault(stat, []).append((desc, vals))
    def pick(lst):
        def rank(d):                                      # near-surface first: explicit top/surface, then the shallowest stated depth
            d = d.lower()
            m = re.search(r"([\d.]+)\s*(ft|feet|m)\b", d)
            return (0 if re.search(r"top|surface|upper", d) else 2 if re.search(r"bottom|lower|deep", d) else 1, float(m.group(1)) if m else 0.0)
        return sorted(lst, key=lambda x: (rank(x[0]), -len(x[1])))[0]
    if prefer_stat in series:
        desc, vals = pick(series[prefer_stat])
        return vals, f"mean{(' ' + desc) if desc else ''}"
    if "00001" in series and "00002" in series:
        mx, mn = pick(series["00001"])[1], pick(series["00002"])[1]
        return {k: (mx[k] + mn[k]) / 2 for k in mx if k in mn}, "midrange of daily max/min"
    return {}, "none"


def stats(errors: list[float]) -> dict:
    n = len(errors)
    if not n:
        return {"n": 0}
    mean = sum(errors) / n
    return {"n": n, "biasC": round(mean, 4), "maeC": round(sum(abs(e) for e in errors) / n, 4),
            "rmseC": round(math.sqrt(sum(e * e for e in errors) / n), 4), "within2F": round(sum(abs(e) <= 2 / 1.8 for e in errors) / n, 4)}


def finding(fid: str, claim: str, kind: str, evidence: list[str], home: str, method: str, metric: str, op: str, thr, tier: str | None = None,
            change: dict | None = None, capability: dict | None = None, resolves: list | None = None) -> dict:
    f = {"id": fid, "claim": claim, "kind": kind, "auto": True, "method": method,
         "evidence": [{"path": p, "sha256": sha256(os.path.join(home, p))} for p in evidence],
         "validation": {"metric": metric, "op": op, "threshold": thr}}
    if tier:
        f["tier"] = tier
    if change:
        f["change"] = change
    if capability:
        f["capability"] = capability
    if resolves:
        f["resolves"] = resolves
    return f


def window_end(cfg: dict) -> str:
    return cfg.get("endDate") or (dt.date.today() - dt.timedelta(days=int(cfg.get("archiveLagDays", 8)))).isoformat()


# ------------------------------------------------------------------------------------------------------------------------------- water temp
def m0_daily(forcing: dict) -> dict:
    """Production M0 inputs from an Open-Meteo daily block (metric): {date: (airF, Teq)}. Days without air temperature are dropped."""
    out = {}
    d = forcing
    for i, t in enumerate(d["time"]):
        a = d["temperature_2m_mean"][i]
        if a is None:
            continue
        airF = a * 1.8 + 32
        sw, w, rh = d["shortwave_radiation_sum"][i], d["wind_speed_10m_mean"][i], d["relative_humidity_2m_mean"][i]
        teq = airF + 4.0 if (sw is None or w is None or rh is None) else airF + 5.0 + 0.11 * sw - 1.0 * w * max(0.0, min(1.0, 1 - rh / 100))
        out[t] = (airF, teq)
    return out


def m0_for_date(forc: dict, date: str, past: int = 45, seed_n: int = 7, k: float = 0.09):
    """Production M0 (Sources/SectorEngine/Fetchers/WaterTemperatureService.swift): window D-45..D, 7-day seed, daily relaxation k=0.09."""
    if date not in forc:
        return None
    d0 = dt.date.fromisoformat(date)
    rows = [forc[x] for x in ((d0 - dt.timedelta(days=past - j)).isoformat() for j in range(past + 1)) if x in forc]
    if len(rows) < seed_n:
        return None
    tw = max(32.0, sum(r[0] for r in rows[:seed_n]) / seed_n)
    for _, teq in rows:
        tw = max(32.0, tw + k * (teq - tw))
    return (tw - 32) / 1.8


def wt_calibration_sites(home: str, cfg: dict) -> tuple[set, bool]:
    p = os.path.join(home, cfg["calibrationSnapshot"])
    if not os.path.exists(p):
        return set(), False
    rows = json.load(open(p, encoding="utf-8")).get("rows") or []
    return {str(r.get("sensor", "")).split(":", 1)[-1] for r in rows if r.get("inM0CalibrationSet")}, True


def acquire_water_temp(ev: Evidence, home: str, cfg: dict, it: int, targets) -> dict:
    lakes = fleet(home, cfg)
    if targets is not None:
        lakes = [l for l in lakes if l["key"] in set(targets)]
    radius = cfg["radiusDeg"][min(it, len(cfg["radiusDeg"])) - 1]
    calib, _ = wt_calibration_sites(home, cfg)
    used = set(cfg.get("_usedSites") or [])
    sites = usgs_sites(ev, "usgs-sites-00010", [l["state"] for l in lakes], "00010")
    start, end = cfg["startDate"], window_end(cfg)
    fstart = (dt.date.fromisoformat(start) - dt.timedelta(days=46)).isoformat()
    matched = {}
    for l in lakes:
        cand = match_sites(l, sites, radius, calib | used)[: cfg.get("maxSitesPerLake", 2)]
        if not cand:
            continue
        got = []
        for s in cand:
            rel = ev.fetch("usgs-dv-00010", f"{l['key']}__{s['site']}.json", "https://waterservices.usgs.gov/nwis/dv/",
                           {"format": "json", "sites": s["site"], "parameterCd": "00010", "statCd": "00003,00001,00002", "startDT": start, "endDT": end},
                           purpose=f"daily water temperature, USGS {s['site']} ({s['name']}), for {l['name']}")
            if rel:
                got.append({"site": s["site"], "siteName": s["name"], "dist": s["dist"], "path": rel})
        if not got:
            continue
        f = ev.fetch("open-meteo-archive", f"{l['key']}.json", "https://archive-api.open-meteo.com/v1/archive",
                     {"latitude": l["lat"], "longitude": l["lon"], "start_date": fstart, "end_date": end, "timezone": "auto",
                      "daily": "temperature_2m_mean,shortwave_radiation_sum,wind_speed_10m_mean,relative_humidity_2m_mean"},
                     purpose=f"Open-Meteo archive daily forcing for {l['name']} (production M0 inputs)")
        if f:
            matched[l["key"]] = {"lake": l["name"], "sites": got, "forcing": f}
    prot = {}
    if it == 1:                                                    # Level-4 protected-truth gap: WQP ACTIVITY METADATA only (no values)
        for name, pc in (cfg.get("protectedTruth") or {}).get("lakes", {}).items():
            rel = ev.fetch("wqp-activity-metadata", f"{safe_key(name)}_activities.csv", "https://www.waterqualitydata.us/data/Activity/search",
                           {"bBox": ",".join(str(x) for x in pc["bbox"]), "siteType": "Lake, Reservoir, Impoundment", "characteristicName": "Temperature, water",
                            "startDateLo": cfg["protectedTruth"]["sinceMMDDYYYY"], "mimeType": "csv"},
                           purpose=f"activity metadata (dates/depths, no result values) for protected lake {name}")
            prot[name] = rel
    return {"lakesSearched": len(lakes), "radiusDeg": radius, "statesQueried": len({l['state'] for l in lakes}), "sitesInStates": len(sites),
            "lakesMatched": len(matched), "matched": matched, "protectedMetadata": prot, "calibrationSitesExcluded": len(calib)}


def analyze_water_temp(home: str, cfg: dict, acq: list[dict]) -> dict:
    metrics, findings, weak, limits = {"lakes": {}}, [], [], []
    calib, known = wt_calibration_sites(home, cfg)
    if not known:
        limits.append({"limitation": "M0 calibration-site list missing: sensors cannot be certified out-of-sample", "input": cfg["calibrationSnapshot"]})
    # 1) implementation check: our M0 reproduces the stored production M0 values (existing research residuals, stored forcing)
    resid = os.path.join(home, cfg["storedResiduals"])
    if os.path.exists(resid):
        diffs, cache = [], {}
        with gzip.open(resid, "rt") as fh:
            for i, r in enumerate(csv.DictReader(fh)):
                if i >= cfg.get("implCheckRows", 3000):
                    break
                stem = r["lake"].replace("|", "_").replace("/", "-").replace(" ", "_")
                if stem not in cache:
                    p = os.path.join(home, cfg["fleetForcingDir"], stem + ".json")
                    cache[stem] = m0_daily(json.load(open(p))["daily"]) if os.path.exists(p) else None
                if cache[stem] is None or not r.get("m0"):
                    continue
                v = m0_for_date(cache[stem], r["date"])
                if v is not None:
                    diffs.append(abs(v - float(r["m0"])))
        if diffs:
            metrics["implRows"] = len(diffs)
            metrics["implMaxAbsDiffC"] = round(max(diffs), 9)
            findings.append(finding("WT-AUTO-IMPL", f"The campaign's M0 implementation reproduces the stored production M0 on {len(diffs)} lake-days "
                                    f"(max |diff| {max(diffs):.2e} C), so its sensor comparisons evaluate the production model.", "EVIDENCE",
                                    [cfg["storedResiduals"]], home, "re-implementation of WaterTemperatureService.swift M0 vs stored m0 column",
                                    "discovery.implMaxAbsDiffC", "<=", cfg["implMaxAbsDiffC"]))
    else:
        limits.append({"limitation": "stored M0 residuals missing: implementation check skipped", "input": cfg["storedResiduals"]})
    # 2) out-of-sample sensor validation per lake (all iterations' downloads)
    per_lake = {}
    for a in acq:
        for key, m in (a.get("matched") or {}).items():          # a follow-up iteration adds sites for the same lake
            per_lake[key] = {**m, "sites": per_lake[key]["sites"] + m["sites"]} if key in per_lake else m
    thr = cfg["lakeRmseC"]
    for key in sorted(per_lake):
        m = per_lake[key]
        fp = os.path.join(home, m["forcing"])
        forc = m0_daily(json.load(open(fp, encoding="utf-8"))["daily"])
        best = None
        for s in m["sites"]:
            series, how = dv_series(os.path.join(home, s["path"]))
            errs = [m0 - obs for d, obs in sorted(series.items()) if (m0 := m0_for_date(forc, d)) is not None]
            st = stats(errs)
            if st["n"] >= cfg["minDays"] and (best is None or st["n"] > best[0]["n"]):
                best = (st, s, how, sorted(series)[0], sorted(series)[-1])
        if best is None:
            weak.append(key)
            metrics["lakes"][key] = {"n": 0, "reason": f"fewer than {cfg['minDays']} paired sensor days"}
            continue
        st, s, how, first, last = best
        metrics["lakes"][key] = {**st, "site": s["site"], "series": how, "first": first, "last": last, "outOfSample": known and s["site"] not in calib}
        findings.append(finding(f"WT-AUTO-SENSOR-{key}", f"Production M0 tracks the independent USGS continuous sensor {s['site']} ({s['siteName']}) at "
                                f"{m['lake']} with RMSE <= {thr} C over {st['n']} days {first}..{last} (observed RMSE {st['rmseC']} C, bias {st['biasC']} C; "
                                "sensor not in the M0 calibration set).", "EVIDENCE", [s["path"], m["forcing"]], home,
                                "production M0 from Open-Meteo archive forcing vs USGS daily-mean water temperature (paired days)",
                                f"discovery.lakes.{key}.rmseC", "<=", thr))
        if st["rmseC"] > thr:
            weak.append(key)
    ok = [v for v in metrics["lakes"].values() if v.get("n")]
    metrics["lakesValidated"] = len(ok)
    if len(ok) >= cfg["pooledMinLakes"]:
        metrics["pooledEqualLakeRmseC"] = round(math.sqrt(sum(v["rmseC"] ** 2 for v in ok) / len(ok)), 4)
        metrics["medianLakeBiasC"] = round(sorted(v["biasC"] for v in ok)[len(ok) // 2], 4)
        metrics["lakesRmseLeThreshold"] = sum(v["rmseC"] <= thr for v in ok)
        paths = sorted({p for a in acq for m in (a.get("matched") or {}).values() for p in [m["forcing"]] + [s["path"] for s in m["sites"]]})
        findings.append(finding("WT-AUTO-SENSOR-POOLED", f"Across {len(ok)} independent continuous-sensor lakes, production M0's equal-lake RMSE is <= "
                                f"{cfg['pooledRmseC']} C (observed {metrics['pooledEqualLakeRmseC']} C; fleet grab-sample validation W1: "
                                f"{cfg['fleetReferenceRmseC']} C): out-of-sample continuous evidence for the deployed model.", "EVIDENCE", paths, home,
                                "equal-lake pooled RMSE over the per-lake sensor comparisons", "discovery.pooledEqualLakeRmseC", "<=", cfg["pooledRmseC"]))
    # 3) protected truth (Level-4 gate): metadata-only recount signal; the frozen-rule recount opens protected values -> owner approval
    pt = cfg.get("protectedTruth") or {}
    for a in acq:
        for name, rel in (a.get("protectedMetadata") or {}).items():
            n_act, dates = 0, set()
            if rel:
                for r in csv.DictReader(io.StringIO(open(os.path.join(home, rel), encoding="utf-8", errors="replace").read())):
                    n_act += 1
                    dates.add((r.get("MonitoringLocationIdentifier"), r.get("ActivityStartDate")))
            metrics.setdefault("protectedMetadata", {})[safe_key(name)] = {"activities": n_act, "siteDates": len(dates),
                                                                           "recorded": pt["lakes"][name]["recorded"], "needed": pt["needed"]}
            limits.append({"limitation": f"{name}: {len(dates)} new WQP temperature site-dates since {pt['sinceMMDDYYYY']} (metadata only; recorded "
                           f"qualifying casts {pt['lakes'][name]['recorded']}/{pt['needed']}). Counting them with the frozen rule-v3 cast rules reads "
                           "protected-truth values: OWNER APPROVAL REQUIRED (Stage 3C.3 hard stop); not done automatically.",
                           "gap": "WATERTEMP-GEN-LEVEL4PROTECTEDTRUTH", "kind": "approval",
                           "nextSource": "TVA reservoir forebay temperature profiles for Wheeler, a prospective logger network for Wilson (decision D3), and owner approval to "
                                         "recount under the frozen rule-v3 cast rules"})
    metrics["scoreImpact"] = {"score": "water-temp-level-ladder-v1 3.0 (frozen) unchanged",
                              "why": "the only score blocker is the Level-4 protected-truth sufficiency gate; sensor evidence does not change it",
                              "gapClosedCandidate": "independent continuous-sensor validation (W5 caveat: n=1 snapshot is not validation)"
                              if metrics.get("pooledEqualLakeRmseC") is not None else None}
    return {"metrics": metrics, "findings": findings, "weak": sorted(set(weak)), "limitations": limits}


# ------------------------------------------------------------------------------------------------------------------------------- lake levels
def acquire_lake(ev: Evidence, home: str, cfg: dict, it: int, targets) -> dict:
    lakes = fleet(home, cfg)
    if targets is not None:
        lakes = [l for l in lakes if l["key"] in set(targets)]
    radius = cfg["radiusDeg"][min(it, len(cfg["radiusDeg"])) - 1]
    sites = usgs_sites(ev, "usgs-sites-level", [l["state"] for l in lakes], cfg["parameterCodes"])
    end = window_end({"archiveLagDays": 1})
    start = (dt.date.fromisoformat(end) - dt.timedelta(days=cfg["windowDays"] - 1)).isoformat()
    matched = {}
    for l in lakes:
        for s in match_sites(l, sites, radius, set())[:1]:
            rel = ev.fetch("usgs-dv-level", f"{l['key']}__{s['site']}.json", "https://waterservices.usgs.gov/nwis/dv/",
                           {"format": "json", "sites": s["site"], "parameterCd": cfg["parameterCodes"], "startDT": start, "endDT": end},
                           purpose=f"daily lake/reservoir elevation, USGS {s['site']} ({s['name']}), for {l['name']}")
            if rel:
                matched[l["key"]] = {"lake": l["name"], "site": s["site"], "siteName": s["name"], "path": rel, "start": start, "end": end}
    return {"lakesSearched": len(lakes), "radiusDeg": radius, "sitesInStates": len(sites), "lakesMatched": len(matched), "matched": matched}


def analyze_lake(home: str, cfg: dict, acq: list[dict]) -> dict:
    metrics, findings, weak = {"lakes": {}}, [], []
    per = {}
    for a in acq:
        for k, m in (a.get("matched") or {}).items():
            per.setdefault(k, m)
    for k in sorted(per):
        m = per[k]
        d = json.load(open(os.path.join(home, m["path"]), encoding="utf-8"))
        dates = set()
        for ts in d.get("value", {}).get("timeSeries", []):
            for blk in ts.get("values", []):
                dates |= {v["dateTime"][:10] for v in blk.get("value", []) if v.get("value") not in (None, "", "-999999")}
        end = dt.date.fromisoformat(m["end"])
        last30 = {(end - dt.timedelta(days=i)).isoformat() for i in range(30)}
        cov = round(len(dates & last30) / 30, 4)
        metrics["lakes"][k] = {"site": m["site"], "days": len(dates), "coverage30": cov, "last": max(dates) if dates else None}
        findings.append(finding(f"LAKE-AUTO-LEVEL-{k}", f"USGS publishes an independent daily water-surface elevation for {m['lake']} (site {m['site']}, "
                                f"{m['siteName']}) with >= {cfg['coverage30']:.0%} of the last 30 days present (observed {cov:.0%}): a fallback "
                                "level source when the primary (CWMS) fetch fails.", "EVIDENCE", [m["path"]], home,
                                "USGS NWIS daily values, lake/reservoir elevation parameter codes", f"discovery.lakes.{k}.coverage30", ">=", cfg["coverage30"]))
        if cov < cfg["coverage30"]:
            weak.append(k)
    metrics["lakesWithFreshLevel"] = sum(v["coverage30"] >= cfg["coverage30"] for v in metrics["lakes"].values())
    metrics["scoreImpact"] = {"score": "lake-brain-score-v1 candidate (non-authoritative)", "why": "evidence for source redundancy; no rubric dimension recomputed"}
    return {"metrics": metrics, "findings": findings, "weak": weak, "limitations": []}


# ------------------------------------------------------------------------------------------------------------------------------- clarity (WQP Secchi)
SECCHI_TO_M = {"m": 1.0, "ft": 0.3048, "in": 0.0254, "cm": 0.01, "mm": 0.001}


def acquire_clarity(ev: Evidence, home: str, cfg: dict, it: int, targets) -> dict:
    lakes = fleet(home, cfg)
    n = cfg["lakesPerIteration"]
    batch = lakes[(it - 1) * n: it * n]
    got = {}
    for l in batch:
        b = cfg["bboxHalfDeg"]
        rel = ev.fetch("wqp-secchi", f"{l['key']}_secchi.csv", "https://www.waterqualitydata.us/data/Result/search",
                       {"bBox": f"{l['lon'] - b:.4f},{l['lat'] - b:.4f},{l['lon'] + b:.4f},{l['lat'] + b:.4f}", "siteType": "Lake, Reservoir, Impoundment",
                        "characteristicName": "Depth, Secchi disk depth", "startDateLo": cfg["sinceMMDDYYYY"], "dataProfile": "narrowResult", "mimeType": "csv"},
                       purpose=f"Secchi depth observations since {cfg['sinceMMDDYYYY']} near {l['name']}")
        got[l["key"]] = {"lake": l["name"], "path": rel}
    return {"iteration": it, "lakesSearched": len(batch), "lakesWithData": sum(1 for v in got.values() if v["path"]), "lakes": got}


def analyze_clarity(home: str, cfg: dict, acq: list[dict]) -> dict:
    metrics, paths, valid, total, lakes = {}, [], 0, 0, set()
    for a in acq:
        for k, m in (a.get("lakes") or {}).items():
            if not m["path"]:
                continue
            for r in csv.DictReader(io.StringIO(open(os.path.join(home, m["path"]), encoding="utf-8", errors="replace").read())):
                total += 1
                try:
                    v = float(r.get("ResultMeasureValue") or "")
                except ValueError:
                    continue
                f = SECCHI_TO_M.get((r.get("ResultMeasure/MeasureUnitCode") or "").strip().lower())
                if f and 0 < v * f <= cfg["maxSecchiM"] and (r.get("ResultStatusIdentifier") or "") != "Rejected":
                    valid += 1
                    lakes.add(k)
            paths.append(m["path"])
    metrics.update({"rows": total, "validObs": valid, "lakesWithValidObs": len(lakes), "saneShare": round(valid / total, 4) if total else 0.0,
                    "lakesSearched": sum(a.get("lakesSearched", 0) for a in acq)})
    findings = []
    if paths:
        findings.append(finding("CLARITY-AUTO-SECCHI", f"{valid} quality-screened Secchi observations (0 < depth <= {cfg['maxSecchiM']} m, not Rejected) since "
                                f"{cfg['sinceMMDDYYYY']} at {len(lakes)} fleet lakes are available from WQP for the next clarity re-certification.",
                                "DATASET", sorted(paths), home, "WQP narrowResult Secchi depth, unit-normalised and range-screened",
                                "discovery.validObs", ">=", cfg["minValidObs"]))
    weak = ["more-lakes"] if valid < cfg["minValidObs"] * 3 and metrics["lakesSearched"] < len(fleet(home, cfg)) else []
    metrics["scoreImpact"] = {"score": "Clarity r3.1 candidate unchanged", "why": "new observations are inputs for a re-certification run, not a re-score"}
    return {"metrics": metrics, "findings": findings, "weak": weak, "limitations": []}


# ------------------------------------------------------------------------------------------------------------------------------- fish (GBIF)
def acquire_fish(ev: Evidence, home: str, cfg: dict, it: int, targets) -> dict:
    years = cfg["years"][min(it, len(cfg["years"])) - 1]
    got = {}
    for sp in (targets if targets is not None else cfg["species"]):
        rel = ev.fetch("gbif-occurrence-facets", f"{safe_key(sp)}_{years.replace(',', '-')}.json", "https://api.gbif.org/v1/occurrence/search",
                       {"scientificName": sp, "country": "US", "year": years, "hasCoordinate": "true", "occurrenceStatus": "PRESENT", "limit": 0,
                        "facet": "month", "facetLimit": 12},
                       purpose=f"US occurrence counts by month (national aggregate; no locations) for {sp}, years {years}")
        got[sp] = {"path": rel, "years": years}
    return {"iteration": it, "years": years, "species": got}


def analyze_fish(home: str, cfg: dict, acq: list[dict]) -> dict:
    metrics, findings, weak = {"species": {}}, [], []
    per = {}
    for a in acq:
        for sp, m in (a.get("species") or {}).items():
            if m["path"]:
                per[sp] = m                                       # the latest (widest) window wins
    for sp in sorted(per):
        m = per[sp]
        d = json.load(open(os.path.join(home, m["path"]), encoding="utf-8"))
        months = {int(c["name"]): c["count"] for f in d.get("facets") or [] if f.get("field") == "MONTH" for c in f.get("counts") or []}
        n = d.get("count", 0)
        k = safe_key(sp)
        peak = sorted(months, key=lambda x: -months[x])[:3]
        metrics["species"][k] = {"records": n, "monthCounts": {str(x): months[x] for x in sorted(months)}, "peakMonths": peak, "years": m["years"]}
        findings.append(finding(f"FISH-AUTO-GBIF-{k}", f"{sp}: {n} georeferenced US occurrence records ({m['years']}) give a national observation-season "
                                f"profile (peak months {peak}) with >= {cfg['minRecords']} records — a field-observation reference for the spawn/season "
                                "rules (observation effort is seasonal; not a spawning measurement).", "DATASET", [m["path"]], home,
                                "GBIF occurrence search, month facet, national aggregate", f"discovery.species.{k}.records", ">=", cfg["minRecords"]))
        if n < cfg["minRecords"]:
            weak.append(sp)
    metrics["scoreImpact"] = {"score": "fish rubric 2.1.0 frozen baseline unchanged", "why": "observation profiles are not field outcomes for FISH-VAL-001"}
    return {"metrics": metrics, "findings": findings, "weak": weak, "limitations": []}


# ------------------------------------------------------------------------------------------------------------------------------- literature (Crossref)
def acquire_literature(ev: Evidence, home: str, cfg: dict, it: int, targets, gaps: list[dict]) -> dict:
    sel = [g for g in gaps if targets is None or g.get("id") in set(targets)][: cfg["gapsPerIteration"]]
    nterms = cfg["queryTerms"][min(it, len(cfg["queryTerms"])) - 1]
    got = {}
    for g in sel:
        terms = [t for t in re.split(r"[^a-z0-9]+", (g.get("title") or "").lower()) if len(t) >= 4 and t not in STOP][:nterms]
        q = " ".join(cfg["domainTerms"] + terms)
        rel = ev.fetch("crossref-works", f"{safe_key(g['id'])}_i{it}.json", "https://api.crossref.org/works",
                       {"query": q, "rows": cfg["rows"], "filter": f"from-pub-date:{cfg['fromYear']},type:journal-article",
                        "select": "DOI,title,issued,container-title,license,subject,type"},
                       purpose=f"peer-reviewed literature leads for gap {g['id']}")
        got[g["id"]] = {"path": rel, "query": q, "terms": terms, "title": g.get("title")}
    return {"iteration": it, "gaps": got}


def analyze_literature(home: str, cfg: dict, acq: list[dict]) -> dict:
    metrics, findings, weak = {"gaps": {}}, [], []
    per = {}
    for a in acq:
        for gid, m in (a.get("gaps") or {}).items():
            if m["path"]:
                per.setdefault(gid, []).append(m)
    for gid in sorted(per):
        leads, paths = {}, []
        for m in per[gid]:
            paths.append(m["path"])
            need = 2 if len(m["terms"]) > 3 else 1
            for it in json.load(open(os.path.join(home, m["path"]), encoding="utf-8")).get("message", {}).get("items") or []:
                title = " ".join(it.get("title") or [])
                year = ((it.get("issued") or {}).get("date-parts") or [[None]])[0][0]
                if it.get("DOI") and title and year and len(tokens(title) & set(m["terms"])) >= need:
                    leads[it["DOI"].lower()] = {"doi": it["DOI"], "title": title[:200], "year": year}
        k = safe_key(gid)
        metrics["gaps"][k] = {"leads": len(leads), "dois": sorted(leads)[:15]}
        findings.append(finding(f"{gid}-AUTO-LIT", f"Gap {gid}: {len(leads)} peer-reviewed journal articles (Crossref, {cfg['fromYear']}+) match the gap's "
                                f"terms (>= {cfg['minLeads']} required) — literature LEADS for a reviewer, not adopted knowledge.", "EVIDENCE", sorted(paths), home,
                                "Crossref works search; title-term relevance screen", f"discovery.gaps.{k}.leads", ">=", cfg["minLeads"]))
        findings[-1]["addresses"] = [gid]
        if len(leads) < cfg["minLeads"]:
            weak.append(gid)
    metrics["scoreImpact"] = {"score": "unchanged", "why": "literature leads need reviewer reading before any rule or score change"}
    return {"metrics": metrics, "findings": findings, "weak": weak, "limitations": []}


# ------------------------------------------------------------------------------------------------------------------------------- intelligence
def analyze_intelligence(home: str, cfg: dict, upstream: dict) -> dict:
    """Sector Intelligence consumes the specialists' results; it never invents their outputs."""
    paths, brains = [], []
    for bid, cand in sorted((upstream or {}).items()):
        if cand and cand.get("packaged"):
            p = os.path.join(cand["path"], "findings.json")
            if os.path.exists(os.path.join(home, p)):
                paths.append(p)
                brains.append(bid)
    metrics = {"upstreamBrainsWithCandidates": len(brains), "upstreamBrains": brains,
               "scoreImpact": {"score": "unchanged", "why": "Intelligence integrates approved specialist knowledge only; these are candidates"}}
    findings = [finding("INT-AUTO-UPSTREAM", f"{len(brains)} specialist Brains produced validated candidate knowledge this campaign ({', '.join(brains)}); "
                        "Intelligence's integration review can start from these packages once they are approved.", "EVIDENCE", paths, home,
                        "campaign upstream candidate packages (digest-verified by the candidate stage)", "discovery.upstreamBrainsWithCandidates", ">=",
                        cfg["minUpstream"])] if paths else []
    return {"metrics": metrics, "findings": findings, "weak": [], "limitations": [] if paths else
            [{"limitation": "no specialist candidate packages this campaign: nothing to integrate", "kind": "dependency"}]}


# ------------------------------------------------------------------------------------------------------------------------------- dispatch
def acquire(kind: str, ev: Evidence, home: str, cfg: dict, it: int, targets, gaps: list[dict]) -> dict:
    if kind == "water-temp-sensors":
        return acquire_water_temp(ev, home, cfg, it, targets)
    if kind == "lake-levels":
        return acquire_lake(ev, home, cfg, it, targets)
    if kind == "wqp-secchi":
        return acquire_clarity(ev, home, cfg, it, targets)
    if kind == "gbif-species":
        return acquire_fish(ev, home, cfg, it, targets)
    if kind == "literature":
        return acquire_literature(ev, home, cfg, it, targets, gaps)
    return {}


# what each connector's findings can honestly claim: acquisition and data quality are NOT scientific support, a literature lead is not a rule
DEFAULT_TIER = {"water-temp-sensors": "SCIENTIFIC_SUPPORT", "lake-levels": "QUALITY_CHECKED", "wqp-secchi": "QUALITY_CHECKED", "gbif-species": "QUALITY_CHECKED",
                "literature": "EVIDENCE_LEAD", "upstream": "EVIDENCE_LEAD"}


def analyze(kind: str, home: str, cfg: dict, acq: list[dict], upstream: dict | None = None) -> dict:
    r = _analyze(kind, home, cfg, acq, upstream)
    for f in r["findings"]:
        f.setdefault("tier", "QUALITY_CHECKED" if f["id"] == "WT-AUTO-IMPL" else DEFAULT_TIER.get(kind, "ACQUIRED"))
    return r


def _analyze(kind: str, home: str, cfg: dict, acq: list[dict], upstream: dict | None = None) -> dict:
    fn = {"water-temp-sensors": analyze_water_temp, "lake-levels": analyze_lake, "wqp-secchi": analyze_clarity, "gbif-species": analyze_fish,
          "literature": analyze_literature}.get(kind)
    if kind == "upstream":
        return analyze_intelligence(home, cfg, upstream or {})
    return fn(home, cfg, acq) if fn else {"metrics": {}, "findings": [], "weak": [], "limitations": []}


# ------------------------------------------------------------------------------------------------------------------------------- owner action
def owner_action(home: str, folder: str, cid: str, aid: str, gap: str, publisher: str, what: str, access: str, verified: bool, checked: list, addresses: str) -> dict:
    """An actionable data-acquisition record for evidence the system cannot fetch itself: who publishes it, how to get it (marked verified or
    not), what was already checked, and which scientific gap it would address. 'Not found by a connector' is never 'does not exist'."""
    rec = {"id": aid, "gap": gap, "status": "OWNER_ACTION_REQUIRED", "publisher": publisher, "dataset": what, "accessInstructions": access,
           "accessVerified": verified, "alreadyChecked": checked, "wouldAddress": addresses, "campaign": cid, "at": now_iso()}
    p = os.path.join(home, folder, "research", "data-acquisition", safe_key(aid) + ".json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(rec, open(p + ".tmp", "w", encoding="utf-8"), indent=1)
    os.replace(p + ".tmp", p)
    rec["path"] = os.path.relpath(p, home)
    return rec
