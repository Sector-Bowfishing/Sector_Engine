"""Compose notes/08_seasonal_backtest.md from out/*.json and out/table_*.md"""
import json, datetime as dt, numpy as np
from common import *
A = json.load(open(H/"out/analysis.json"))["lakes"]; S = json.load(open(H/"out/summary.json"))
T = lambda n: open(H/f"out/{n}").read()
def d2s(doy): return (dt.date(2021, 1, 1)+dt.timedelta(days=int(round(doy))-1)).strftime("%b %d")
def f(x, n=2): return "-" if x is None else f"{x:.{n}f}"
# peak table
pk = ["| Lake (class) | Note-03 expert row | expert D window | lake climatology peak (full data) | per-year peak median [IQR], n years | inside expert window (clim / share of years) | signal? |", "|---|---|---|---|---|---|---|"]
for lk, cls, lab in LAKES:
    d = S["peak"].get(lk)
    if not d: continue
    w = "; ".join(f"{d2s(a)}-{d2s(b)}" for a, b in d.get("expert_win", []))
    yr = f"{d2s(d['by_year_median'])} [{d2s(d['by_year_iqr'][0])}-{d2s(d['by_year_iqr'][1])}], {d['n_years']}" if d.get("by_year_median") else "-"
    pk.append(f"| {lab} ({cls}) | {d.get('expert_row','-')} | {w} | {d2s(d['clim_peak_doy'])} (u>=0.8 window {d2s(d['peak_window'][0])}-{d2s(min(d['peak_window'][1],365))}) | {yr} | {'yes' if d.get('in_expert_win_clim') else 'no'} / {f(d.get('in_expert_win_years'))} | {'yes' if d['signal'] else 'NO (<5 % belt share)'} |")
# ring table
rg = ["| Lake | 35-50 m | 50-70 m | 70-90 m | 90-150 m | 150-300 m | >300 m |", "|---|---|---|---|---|---|---|"]
for lk, cls, lab in LAKES:
    r = A[lk]["rings_summer"]; rg.append(f"| {lab} | " + " | ".join(f"{r[k]['share']*100:.1f}%" for k in r) + " |")
# winter / amplitude / peaks
wt = ["| Lake | accepted scenes | belt share median [p10-p90] | clim min-max | Dec-Feb accepted n | winter median / clim max | local maxima (prominence >= 25 % amp) | accept rate legacy baseline (<04.00) vs modern |", "|---|---|---|---|---|---|---|---|"]
for lk, cls, lab in LAKES:
    L = A[lk]; b = L["belt_summary"]; w = L["winter"]; ab = L["acc_by_baseline"]
    wt.append(f"| {lab} | {L['n_accepted']} | {b['median']*100:.1f}% [{b['p10']*100:.1f}-{b['p90']*100:.1f}] | {L['clim_amp'][0]*100:.1f}-{L['clim_amp'][1]*100:.1f}% | {w['n']} | {f(w['ratio_to_peak']) if w['ratio_to_peak'] is not None else '-'} | {L['n_peaks_prom25']} | {ab.get('legacy(<04.00)',{}).get('acc',float('nan'))*100:.0f}% (n={ab.get('legacy(<04.00)',{}).get('n',0)}) vs {ab.get('modern(>=04.00)',{}).get('acc',float('nan'))*100:.0f}% (n={ab.get('modern(>=04.00)',{}).get('n',0)}) |")
# sensitivity table
sens = ["| Variant | lakes | n scenes | clim exact [95 % CI over lakes] | calendar exact [CI] | delta pts [CI] | clim within-1 [CI] |", "|---|---|---|---|---|---|---|"]
def row(name, d):
    if not d: return
    c = d["ci"]; sens.append(f"| {name} | {len(d['lakes'])} | {d['n']} | {d['clim']:.3f} [{c['clim'][0]:.2f}-{c['clim'][1]:.2f}] | {d['cal']:.3f} [{c['cal'][0]:.2f}-{c['cal'][1]:.2f}] | {(d['clim']-d['cal'])*100:+.1f} [{c['diff'][0]*100:+.0f} to {c['diff'][1]*100:+.0f}] | {d['w1']:.3f} [{c['w1'][0]:.2f}-{c['w1'][1]:.2f}] |")
row("PRIMARY: belt share, DOY climatology, 6 testable lakes", S["pooled_testable"])
row("all 8 lakes incl. 2 no-signal lakes", S["pooled_all8"])
row("whole-lake plant-cell share instead of belt", S["pooled_testable_lake_share"])
row("GDD-proxy thermal-time warp (Open-Meteo air temp)", S["pooled_testable_belt_share_gdd"])
row("excluding scenes from legacy processing baselines (<04.00)", S["pooled_testable_belt_share_modern"])
cl = ["| Lake class | lakes (testable) | pooled clim exact | pooled calendar exact | pooled clim within-1 | bootstrap over lakes (delta pts) | class verdict |", "|---|---|---|---|---|---|---|"]
for c, d in S["classes"].items():
    if d["verdict"] == "NOT_TESTABLE": cl.append(f"| {c} | {', '.join(LABEL[k] for k in d['lakes'])} (none) | - | - | - | - | **NOT_TESTABLE** (all member lakes no signal) |"); continue
    ci = d.get("ci"); cl.append(f"| {c} | {', '.join(LABEL[k] for k in d['lakes'])} ({', '.join(LABEL[k] for k in d['testable'])}) | {d['clim']:.2f} | {d['cal']:.2f} | {d['w1']:.2f} | {('[%+.0f, %+.0f]' % (ci['diff'][0]*100, ci['diff'][1]*100)) if ci else 'n/a (1 lake)'} | **{d['verdict']}** (lakes passing: {len(d['lakes_pass'])}/{len(d['testable'])}) |")
lv = ["| Lake | verdict | detail |", "|---|---|---|"] + [f"| {LABEL[k]} | **{v['verdict']}** | {v['reason']} |" for k, v in S["lakes"].items()]
pa = ["| Age of last accepted observation | n scenes | persistence exact | lake climatology exact | calendar exact | persistence within-1 | climatology within-1 |", "|---|---|---|---|---|---|---|"]
for k, v in S["persistence_by_age"].items(): pa.append(f"| {k} | {v['n']} | {f(v['pers'])} | {f(v['clim'])} | {f(v['cal'])} | {f(v['pers_w1'])} | {f(v['clim_w1'])} |")
mjt = ["| Lake | most frequent observed state (share) | lake climatology exact |", "|---|---|---|"]
for lk, cls, lab in LAKES:
    m = S["majority"][lk]; i = A[lk]["loyo"]["belt_share"]; mjt.append(f"| {lab} | {m['label']} ({m['exact']:.2f}) | {i['clim_vs_obs']['exact']:.2f} |")
N = lambda x, n=0: f"{x:.{n}f}"
P = S["pooled_testable"]; cp = S["common_pooled"]
txt = open(H/"scripts/note_template.md").read()
rep = {"{{GATE}}": T("table_gate.md"), "{{STATUS}}": T("table_status.md"), "{{USABLE}}": T("table_usable.md"), "{{AGE}}": T("table_age.md"), "{{PEAK}}": "\n".join(pk), "{{RINGS}}": "\n".join(rg), "{{WINTER}}": "\n".join(wt),
       "{{SENS}}": "\n".join(sens), "{{CLASSES}}": "\n".join(cl), "{{LAKEVERD}}": "\n".join(lv), "{{PERSAGE}}": "\n".join(pa), "{{MAJ}}": "\n".join(mjt),
       "{{P_N}}": str(P["n"]), "{{P_CLIM}}": f"{P['clim']:.3f}", "{{P_CAL}}": f"{P['cal']:.3f}", "{{P_W1}}": f"{P['w1']:.3f}", "{{P_CI_D}}": f"{P['ci']['diff'][0]*100:+.0f} to {P['ci']['diff'][1]*100:+.0f}",
       "{{P_CI_C}}": f"{P['ci']['clim'][0]:.2f}-{P['ci']['clim'][1]:.2f}", "{{P_CI_W}}": f"{P['ci']['w1'][0]:.2f}-{P['ci']['w1'][1]:.2f}", "{{MAJ_P}}": f"{S['majority_pooled_testable']:.2f}",
       "{{CP_N}}": str(cp["n"]), "{{CP_PERS}}": f"{cp['pers']:.3f}", "{{CP_CLIM}}": f"{cp['clim']:.3f}", "{{CP_CAL}}": f"{cp['cal']:.3f}"}
for k, v in rep.items(): txt = txt.replace(k, v)
open(R/"notes/08_seasonal_backtest.md", "w").write(txt); print("written", len(txt))
