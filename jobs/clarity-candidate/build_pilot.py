"""Build pilot_lakes.json: the shadow job's lakes, fixed sample points, ACOLITE crops and crop elevations.

The lakes were chosen for environmental diversity (region, water type, lake form, latitude, Sentinel-2 tiles) before any
candidate output existed for them. No model output, Secchi value or field report enters this file.

Points (value-blind, outline only):
  Guntersville  the Stage 10 survey targets (G01..), so the scoring-only acceptance survey has candidate answers at its
                exact locations; they were picked from imagery, never from a measured value.
  every other   the open-water point farthest from shore (the lake's pole of inaccessibility on a 30 m grid), then up to
                four more by farthest-point sampling among cells >= 300 m from shore, >= 1.5 km apart, all inside one
                ACOLITE crop (|dlat| < 0.07, |dlon| < 0.09 of the first point).
Crops keep the research geometry (stage14/cert/run_cert_aco.py: +-0.08 lat, +-0.10 lon around a point; members within
|dlat| < 0.07, |dlon| < 0.09), grouped by greedy set cover; elevation from USGS EPQS at the crop centre (as Stages 12-17).
  python build_pilot.py polygons.geojson.gz survey_targets.gpx > pilot_lakes.json"""
import gzip, json, math, re, sys, time, urllib.request
import numpy as np
from scipy import ndimage
from shapely.geometry import shape, Point
from shapely.ops import transform
import pyproj

PILOT = [  # (directory id, slug, why: region / water type / form)
    ("Guntersville|AL", "guntersville", "Tennessee River mainstem reservoir (TVA), Southeastern Plains; dense submerged grass; the beta lake"),
    ("Okeechobee|FL", "okeechobee", "Peninsular Florida, subtropical; very large and shallow, wind-resuspended; cyanobacteria blooms"),
    ("Lake Pontchartrain|LA", "pontchartrain", "Gulf Coast estuary; brackish, turbid, tidal exchange"),
    ("Toledo Bend Reservoir|TX", "toledo-bend", "Western Gulf Coastal Plain; tannin-stained, standing timber"),
    ("Lake Marion|SC", "marion", "Atlantic Coastal Plain (Santee Cooper); blackwater swamp reservoir, cypress"),
    ("Lake Texoma|TX", "texoma", "Southern Great Plains (Red River); red-clay sediment, saline"),
    ("Ouachita (L. Ouachita)|AR", "ouachita", "Ouachita Mountains; deep, clear, oligotrophic"),
    ("Lake of the Ozarks|MO", "ozarks", "Ozark Highlands; long dendritic reservoir, moderate clarity"),
    ("Lanier (Sidney Lanier)|GA", "lanier", "Piedmont; deep reservoir, red-clay inflows"),
    ("Lake Winnebago|WI", "winnebago", "Upper Midwest; large shallow natural lake, eutrophic, algal"),
    ("Mille Lacs Lake|MN", "mille-lacs", "Northern Lakes and Forests; glacial natural lake, ice-covered winters"),
    ("Lake Champlain|VT", "champlain", "Northeast; long deep natural lake, clear"),
    ("Lake Sakakawea|ND", "sakakawea", "Northwestern Great Plains (Missouri River mainstem); sediment, cold"),
    ("Utah Lake|UT", "utah-lake", "Great Basin; shallow, alkaline, very turbid"),
    ("Elephant Butte Reservoir|NM", "elephant-butte", "Chihuahuan Desert (Rio Grande); arid, sediment-laden inflows, large drawdowns"),
    ("Lake Mead|NV", "mead", "Mojave Desert (Colorado River); deep, very clear"),
    ("Clear Lake|CA", "clear-lake-ca", "Mediterranean California; hypereutrophic natural lake, cyanobacteria"),
]
CROP_DLAT, CROP_DLON = 0.07, 0.09
GRID_M, MIN_SHORE_M, MIN_SEP_M, N_POINTS = 30.0, 300.0, 1500.0, 5


def epqs(lat, lon):
    for i in range(5):
        try:
            u = f"https://epqs.nationalmap.gov/v1/json?x={lon}&y={lat}&wkid=4326&units=Meters&includeDate=false"
            with urllib.request.urlopen(u, timeout=30) as r:
                v = float(json.load(r).get("value"))
                return v if v > -100 else None
        except Exception:
            time.sleep(2 * (i + 1))
    return None


def crops_of(points):
    """Same crop geometry as the research (centred on a point; members within |dlat| < 0.07, |dlon| < 0.09), grouped by
    greedy set cover (the centre covering the most remaining points; ties to the earlier point) to need fewer runs."""
    out, left = [], list(points)
    near = lambda c, p: abs(p[0] - c[0]) < CROP_DLAT and abs(p[1] - c[1]) < CROP_DLON
    while left:
        c = max(left, key=lambda c: (sum(near(c, p) for p in left), -left.index(c)))
        inside = [p for p in left if near(c, p)]
        out.append({"lat": c[0], "lon": c[1], "points": [list(p) for p in inside]}); left = [p for p in left if p not in inside]
    return out


def outline_points(geom):
    c = geom.representative_point()
    aeqd = pyproj.Transformer.from_crs("EPSG:4326", f"+proj=aeqd +lat_0={c.y} +lon_0={c.x} +units=m", always_xy=True)
    back = pyproj.Transformer.from_crs(f"+proj=aeqd +lat_0={c.y} +lon_0={c.x} +units=m", "EPSG:4326", always_xy=True)
    g = transform(aeqd.transform, geom)
    x0, y0, x1, y1 = g.bounds
    nx, ny = int((x1 - x0) / GRID_M) + 3, int((y1 - y0) / GRID_M) + 3
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    tr = from_origin(x0 - GRID_M, y1 + GRID_M, GRID_M, GRID_M)
    water = rasterize([(g, 1)], out_shape=(ny, nx), transform=tr, fill=0, dtype="uint8").astype(bool)
    dist = ndimage.distance_transform_edt(water) * GRID_M
    r, cidx = np.unravel_index(np.argmax(dist), dist.shape)
    xy = lambda rr, cc: (tr.c + (cc + 0.5) * GRID_M, tr.f - (rr + 0.5) * GRID_M)
    lon0, lat0 = back.transform(*xy(r, cidx))
    rows, cols = np.nonzero(dist >= MIN_SHORE_M)
    pts = np.array([xy(a, b) for a, b in zip(rows, cols)])
    ll = np.array([back.transform(px, py) for px, py in pts]) if len(pts) else np.zeros((0, 2))
    inside = (np.abs(ll[:, 1] - lat0) < CROP_DLAT) & (np.abs(ll[:, 0] - lon0) < CROP_DLON) if len(ll) else np.zeros(0, bool)
    pts, ll = pts[inside], ll[inside]
    chosen = [np.array(xy(r, cidx))]; out = [(round(lat0, 6), round(lon0, 6))]
    while len(out) < N_POINTS and len(pts):
        dmin = np.min(np.stack([np.hypot(*(pts - q).T) for q in chosen]), axis=0)
        k = int(np.argmax(dmin))
        if dmin[k] < MIN_SEP_M: break
        chosen.append(pts[k]); out.append((round(float(ll[k, 1]), 6), round(float(ll[k, 0]), 6)))
    return out, float(dist.max())


def main():
    polys = {f["properties"]["id"]: f for f in json.load(gzip.open(sys.argv[1]))["features"]}
    gpx = open(sys.argv[2]).read()
    survey = [(float(a), float(b), n) for a, b, n in re.findall(r'<wpt lat="([^"]+)" lon="([^"]+)">\s*<name>([^<]+)</name>', gpx)]
    lakes = []
    for lid, slug, why in PILOT:
        f = polys[lid]; geom = shape(f["geometry"])
        if slug == "guntersville":
            pts = [(la, lo, f"{slug}:{n}") for la, lo, n in survey]; pole = None
        else:
            o, pole = outline_points(geom)
            pts = [(la, lo, f"{slug}:P{i + 1}") for i, (la, lo) in enumerate(o)]
        cr = crops_of(pts)
        for c in cr: c["elev"] = epqs(c["lat"], c["lon"])
        lakes.append({"slug": slug, "directory_id": lid, "why": why, "area_km2": f["properties"].get("areaKm2"),
                      "points": [{"key": k, "lat": la, "lon": lo} for la, lo, k in pts], "crops": cr,
                      "max_shore_distance_m": pole})
        print(slug, len(pts), "points", len(cr), "crops", [c["elev"] for c in cr], file=sys.stderr)
    json.dump({"schema": "clarity-candidate-pilot/1", "selection": __doc__.split("\n\n")[1], "lakes": lakes}, sys.stdout, indent=1)


if __name__ == "__main__":
    main()
