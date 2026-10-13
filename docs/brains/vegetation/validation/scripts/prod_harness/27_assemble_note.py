import re, json
from pathlib import Path
R = Path("{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain")
H = R/"experiments/adoption/prod_harness"
T = (H/"out/tables.md").read_text(); X = (H/"out/tables_extra.md").read_text()
GT = (H/"out/tables_guntersville.md").read_text() if (H/"out/tables_guntersville.md").exists() else "(pilot not run)"
def sect(txt, start, nxt=None):
    a = txt.index(start); b = txt.index(nxt, a + 1) if nxt else len(txt); return txt[a:b].strip()
def tbl(title_start):          # one **title** block of tables.md up to the next ** title
    a = T.index(title_start); m = re.search(r"\n\*\*(?!.*\| )", T[a + 5:]); b = a + 5 + m.start() if m else len(T); return T[a:b].strip()
S1 = tbl("**Snohomish, PRIMARY"); S2 = tbl("**Snohomish, bare production"); S3 = tbl("**Snohomish, v1 with dark-water fix"); S4 = tbl("**Snohomish, v1, production scene gate OFF")
S5 = tbl("**Snohomish, v1, production daily 36 m"); S6 = tbl("**Snohomish, v1, buffered-none")
F1 = tbl("**FWC points, PRIMARY"); F2 = tbl("**FWC points, bare production, 50 m"); F3 = tbl("**FWC points, v1 with dark fix"); F4 = tbl("**FWC points, bare production, production scene gate OFF")
PA = tbl("**PAC/PVI, PRIMARY"); PB = tbl("**PAC/PVI, bare production**"); PC = tbl("**PAC/PVI, bare production, gate OFF"); PD = tbl("**PAC/PVI, v1 with dark fix")
rep = json.load(open(H/"out/replica_vs_production.json")); tot = rep["per_scene_cell_agreement"]["total"]
e0 = json.load(open(H/"out/e2e_build_clarity_lead0.json")); e7 = json.load(open(H/"out/e2e_build_clarity_lead7.json"))
def e2e(e):
    s = "| lake | pass used | open-water read | grass % of lake (of which bed-to-bank strip) | whole-lake truth+ / TP / FP | P, R whole lake | clarity-40 m truth+ / TP / FP | P, R clarity-40 m |\n|---|---|---|---|---|---|---|---|\n"
    for nm, v in e.items():
        if "error" in v: s += f"| {nm} | none: `{v['error']}` | | | | | | |\n"; continue
        w, c = v["whole_lake"], v["clarity_40m"]
        s += f"| {nm} | {v['pass_date']} | {v['openWaterReadPct']}% | {v['grassPct']}% ({v['grassToBankPct']}%) | {w['npos']} / {w['tp']} / {w['fp']} | {w['P']}, {w['R']} | {c['npos']} / {c['tp']} / {c['fp']} | {c['P']}, {c['R']} |\n"
    return s
orig = rep["note05_original"]["win45"]; pr = rep["note05_metric_code_on_prod_arrays"]["prod_arrays_all_scenes"]["win45"]; pg = rep["note05_metric_code_on_prod_arrays"]["prod_arrays_minus_gate_rejected"]["win45"]
def rrow(k, lab):
    o, a = orig[k], pr[k]; return f"| {lab} | {o['tp']}/{o['fp']}/{o['fn']} P {o['P']} F1 {o['F1']} | {a['tp']}/{a['fp']}/{a['fn']} P {a['P']:.3f} F1 {a['F1']:.3f} |"
note = open(H/"note_template.md").read()
for k, v in {"S1": S1, "S2": S2, "S3": S3, "S4": S4, "S5": S5, "S6": S6, "F1": F1, "F2": F2, "F3": F3, "F4": F4, "PA": PA, "PB": PB, "PC": PC, "PD": PD, "X": X, "GT": GT,
             "E2E0": e2e(e0), "E2E7": e2e(e7), "REPTOT": json.dumps(tot),
             "RREP1": rrow("single (closest clear date)", "single, closest clear date"), "RREP2": rrow("SHIPPED pass (cov>=0.5, closest to survey)", "SHIPPED-style pass (cov>=0.5)"),
             "RREP3": rrow("median g' >= 0.5", "median g' >= 0.5"), "RREP4": rrow("max g' >= 0.5 (any date)", "max g' >= 0.5 (negative control)")}.items():
    note = note.replace("{{" + k + "}}", v)
(R/"notes/06_production_observer_scoring.md").write_text(note); print(len(note), "bytes")
