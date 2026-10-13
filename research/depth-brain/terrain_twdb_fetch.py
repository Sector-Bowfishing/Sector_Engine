#!/usr/bin/env python3
"""Depth Brain / terrain: fetch TWDB hydrographic-survey truth (area-capacity table .txt + small shapefiles) for every completed survey
listed on the TWDB 'Completed Surveys' page, using HTTP range requests so the 100s-of-MB contour/interp shapefiles are NOT downloaded.
Output (never git): <RAW>/twdb/<LakeDir>_<survey>/{table.txt, zip_members.json, shp/*}.  Polite: 1 req/s."""
import io, json, re, sys, time, zipfile, requests
from pathlib import Path
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/terrain")
BASE = "https://www.twdb.texas.gov"

class RangeFile(io.RawIOBase):
    def __init__(self, url):
        self.url = url; r = requests.head(url, allow_redirects=True, timeout=60); self.size = int(r.headers["Content-Length"]); self.pos = 0
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off; return self.pos
    def readinto(self, b):
        n = len(b)
        if n == 0 or self.pos >= self.size: return 0
        end = min(self.pos + n, self.size) - 1
        for a in range(4):
            try:
                r = requests.get(self.url, headers={"Range": f"bytes={self.pos}-{end}"}, timeout=180)
                if r.status_code in (200, 206): break
            except Exception: time.sleep(2)
        d = r.content[:n]; b[:len(d)] = d; self.pos += len(d); return len(d)

def pick_surveys():
    links = [l.strip() for l in open(RAW / "twdb_links.txt")]
    by = {}
    for l in links:
        m = re.match(r"/surfacewater/surveys/completed/files/([^/]+)/(\d{4}-\d{2})/(.*)", l)
        if not m: continue
        d, sv, rest = m.groups(); by.setdefault(d, {}).setdefault(sv, []).append(rest)
    out = []
    for d, svs in by.items():
        # latest survey with an area table .txt and Shapefiles zip (direct, not Recalculated)
        for sv in sorted(svs, reverse=True):
            rs = svs[sv]
            txt = [r for r in rs if r.endswith(".txt") and "/" not in r]; zp = [r for r in rs if r.lower().endswith(".zip") and "/" not in r]
            if txt and zp:
                out.append((d, sv, txt[0], zp[0])); break
    return out

def main():
    todo = pick_surveys(); print(len(todo), "lakes with table+zip")
    for d, sv, txt, zp in todo:
        o = RAW / "twdb" / f"{d}_{sv}"; o.mkdir(parents=True, exist_ok=True)
        if (o / "zip_members.json").exists(): continue
        try:
            r = requests.get(f"{BASE}/surfacewater/surveys/completed/files/{d}/{sv}/{txt}", timeout=120); (o / "table.txt").write_bytes(r.content)
            rf = RangeFile(f"{BASE}/surfacewater/surveys/completed/files/{d}/{sv}/{zp}")
            z = zipfile.ZipFile(io.BufferedReader(rf, 1 << 16))
            mem = [(i.filename, i.file_size) for i in z.infolist()]
            (o / "zip_members.json").write_text(json.dumps(dict(url=rf.url, size=rf.size, members=mem)))
            (o / "shp").mkdir(exist_ok=True)
            for n, s in mem:
                if s < 3_000_000 and re.search(r"\.(shp|dbf|shx|prj|cpg)$", n, re.I):
                    (o / "shp" / Path(n).name).write_bytes(z.read(n))
            print(d, sv, "ok", len(mem), flush=True)
        except Exception as e:
            print(d, sv, "FAIL", repr(e)[:100], flush=True)
        time.sleep(1)

def more():
    """second pass: lake-boundary polygons between 3 and 40 MB (LiDAR-derived pool outlines) that the first pass skipped"""
    for d in sorted((RAW / "twdb").iterdir()):
        zm = d / "zip_members.json"
        if not zm.exists(): continue
        info = json.loads(zm.read_text()); need = []
        for n, s in info["members"]:
            b = Path(n).name.lower()
            if n.lower().endswith(".shp") and 3_000_000 <= s < 40_000_000 and re.search(r"lake|bndy|bound|poly|shore", b) and not re.search(r"pts|point|land|sound|survey|aeidw|lidar|terr|tin(?!_)", b):
                need.append(n[:-4])
        if not need: continue
        z = zipfile.ZipFile(io.BufferedReader(RangeFile(info["url"]), 1 << 16))
        for base in need:
            for ext in (".shp", ".dbf", ".shx", ".prj", ".cpg"):
                try: (d / "shp" / (Path(base).name + ext)).write_bytes(z.read(base + ext))
                except KeyError: pass
        print(d.name, "more", [Path(b).name for b in need], flush=True)


if __name__ == "__main__":
    more() if len(sys.argv) > 1 and sys.argv[1] == "more" else main()
