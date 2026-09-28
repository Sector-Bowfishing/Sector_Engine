"""Developer-only validation images of the within-arm zones and observed zone
change (Clarity Fusion Stage 3A, item 11). NOT a Water Clarity prediction and
never shown to users: every image carries that banner, uses a grey/blue/red
scheme unlike the production clarity palette, and shows only what the
satellite observed on a pass against that zone's own dry baseline.

usage: geo/bin/python zone_map.py <positions dir> <zone_events.json-producing inputs...>
       geo/bin/python zone_map.py <positions dir> <zone_history.json> <events.json> <out dir> [date:arm ...]
"""
import os, sys, json, math
import numpy as np
from PIL import Image, ImageDraw

pos_dir, zh_p, ev_p, out = sys.argv[1:5]
picks = sys.argv[5:] or ["2026-01-11:town-creek-marshall", "2026-01-11:south-sauty-creek", "2026-01-11:browns-creek"]
os.makedirs(out, exist_ok=True)
P = np.load(os.path.join(pos_dir, "arm_positions.npz"))
Z = json.load(open(os.path.join(pos_dir, "arm_zones.json")))
zone, lake, norm = P["zone"], P["lake"], P["norm"]
zh = json.load(open(zh_p)); ev = json.load(open(ev_p))
BANNER = "DEVELOPER VALIDATION - NOT A WATER CLARITY PREDICTION - NOT FOR USERS"
zmeta = {z["zone"]: z for z in Z["zones"]}


def banner(img, lines):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, img.width, 16 + 12 * len(lines)], fill=(20, 20, 20))
    d.text((6, 3), BANNER, fill=(255, 210, 0))
    for i, t in enumerate(lines):
        d.text((6, 16 + 12 * i), t, fill=(230, 230, 230))
    return img


def crop_for(arm_ids, pad=40):
    m = np.isin(zone, [z["zone"] for z in Z["zones"] if z["arm"] in arm_ids])
    rr, cc = np.nonzero(m)
    return max(0, rr.min() - pad), min(zone.shape[0], rr.max() + pad), max(0, cc.min() - pad), min(zone.shape[1], cc.max() + pad)


# 1. zones overview: position within each arm, head dark -> mouth light
rgb = np.full(zone.shape + (3,), 255, np.uint8)
rgb[lake] = (205, 205, 205)                                      # main stem / unzoned water
for z in Z["zones"]:
    m = zone == z["zone"]
    t = z["index"] / max(1, z["of"] - 1) if z["of"] > 1 else 0.5
    rgb[m] = (int(40 + 160 * t), int(40 + 120 * t), int(90 + 140 * t))
img = Image.fromarray(rgb).resize((zone.shape[1] // 3, zone.shape[0] // 3), Image.NEAREST)
banner(img, ["Within-arm zones (equal-area bins of through-water distance from the head).",
             "Dark = head/back of the arm, light = mouth. Grey = main stem or unzoned water."]).save(os.path.join(out, "zones_overview.png"))

# 2. observed zone change on chosen passes
events = {}
for e in json.load(open(ev_p)).get("zoneEventDump", []):
    events[(e["date"], e["zone"])] = e
for pk in picks:
    date, arm = pk.split(":")
    key = next((k for k in zh["passes"] if k.startswith(date)), None)
    if key is None:
        continue
    r0, r1, c0, c1 = crop_for([arm])
    sub = np.full((r1 - r0, c1 - c0, 3), 255, np.uint8)
    lk = lake[r0:r1, c0:c1]; zn = zone[r0:r1, c0:c1]
    sub[lk] = (215, 215, 215)
    lines = [f"{arm}  pass {key}  change vs the zone's own dry baseline (observed cells only)"]
    for z in [z for z in Z["zones"] if z["arm"] == arm]:
        e = events.get((date, str(z["zone"])))
        m = zn == z["zone"]
        if e is None or e.get("anom") is None:
            sub[m] = (150, 150, 150)
            lines.append(f"  {z['name']:6s} not measurable or no baseline")
            continue
        a = max(-0.6, min(0.6, e["anom"]))
        if a >= 0:
            col = (255, int(255 - 350 * a), int(255 - 350 * a))
        else:
            col = (int(255 + 350 * a), int(255 + 350 * a), 255)
        sub[m] = tuple(max(0, min(255, v)) for v in col)
        lines.append(f"  {z['name']:6s} x{10 ** e['anom']:.2f}  ({e['observedCells']} cells observed, lag {e['lag']} d)")
    scale = max(1, int(700 / max(sub.shape)))
    im = Image.fromarray(sub).resize((sub.shape[1] * scale, sub.shape[0] * scale), Image.NEAREST)
    canvas = Image.new("RGB", (max(im.width, 560), im.height + 20 + 12 * (len(lines) + 1)), (255, 255, 255))
    canvas.paste(im, (0, 20 + 12 * (len(lines) + 1)))
    banner(canvas, lines).save(os.path.join(out, f"zone_change_{date}_{arm}.png"))
print("wrote", os.listdir(out))
