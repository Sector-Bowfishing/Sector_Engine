"""Build CURRENT_CLARITY_STAGE17_MULTISCENE_CONSENSUS.md from the frozen Stage 17 JSONs."""
import json
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
D = json.load(open(f"{S}/stage17/analysis/dev17.json")); F = json.load(open(f"{S}/stage17/FREEZE_STAGE17.json"))
V = D["variants"]; B = D["baseline_stage16"]; X = D["extra"]; SEL = "|".join(map(str, D["selected"])); s = V[SEL]
IU, BY = V["M-iuw|10|H0|S-off"], V["M-bayes|10|H0|S-agree"]; xi = X["M-iuw|10|H0|S-off"]
CL = ["clear", "normal", "stained", "limited"]
p1 = lambda v: f"{100 * v:.1f}%"; pc = lambda v: "–" if v is None else f"{v:.0%}"; f3 = lambda v: "–" if v is None else f"{v:.3f}"
ci = lambda c, k=1: f"{c[0] * k:+.3f} to {c[1] * k:+.3f}"
T = {}
T["freeze"] = ("| Step | UTC | What was fixed |\n|---|---|---|\n"
               f"| Pre-registration | {F['prereg_frozen_utc']} | Windows, the 3-nearest cap, rainfall compatibility, 4 methods, S2C variants, the Strong agreement rule, selection, bars (`PREREGISTRATION_STAGE17.md`, `{F['files']['stage17/PREREGISTRATION_STAGE17.md'][:8]}…`) |\n"
               f"| Inputs | {F['inputs_frozen_utc']} | 2,072 neighbour-scene ACOLITE results, ERA5 rainfall, the neighbour list (`scenes/`) |")
T["coverage"] = ("| Window | Events with ≥ 1 valid neighbour (Stage 11 production gates) |\n|---|---:|\n"
                 "| ±3 days | 623 of 1,582 (39%) |\n| ±5 days | 919 (58%) |\n| ±7 days | 1,064 (67%) |\n| ±10 days | 1,215 (77%) |")
def row(lab, v): return f"| {lab} | {v['bal']:.3f} | {p1(v['harm'])} | {p1(v['sev'])} | " + " | ".join(f"{v['per_class'][n]:.3f}" for n in CL) + f" | {pc(v['strong_share_usable'])} / {pc(v['strong_acc'])} |"
hdr = "| Development (whole-lake held out) | Operational | Harmful | Severe | Clear | Normal | Stained | Limited | Strong share / right |\n|---|---:|---:|---:|---:|---:|---:|---:|---|\n"
T["methods"] = hdr + "\n".join([row("**Stage 16 (anchor scene only)**", B)] + [row(f"{m} (±10 d, no rain rule, S2C off)", V[f"{m}|10|H0|S-off"]) for m in ("M-agree", "M-iuw", "M-robust", "M-bayes")] + [row("M-bayes (±10 d, no rain rule, S2C agree)", BY)])
T["windows"] = ("| M-iuw, S2C off | ±3 d | ±5 d | ±7 d | ±10 d |\n|---|---:|---:|---:|---:|\n" +
                "\n".join(f"| {lab} | " + " | ".join(f(V[f'M-iuw|{w}|{h}|S-off']) for w in (3, 5, 7, 10)) + " |" for h in ("H0", "H1") for lab, f in (
                    (f"Operational ({'rain rule' if h == 'H1' else 'no rain rule'})", lambda v: f"{v['bal']:.3f}"), (f"Stained ({'rain rule' if h == 'H1' else 'no rain rule'})", lambda v: f"{v['per_class']['stained']:.3f}"),
                    (f"Harmful ({'rain rule' if h == 'H1' else 'no rain rule'})", lambda v: p1(v["harm"])))))
T["agree"] = ("| Agreement-only (M-agree, S2C off), Strong share / right | ±3 d | ±5 d | ±7 d | ±10 d |\n|---|---|---|---|---|\n" +
              "\n".join(f"| {'rain rule' if h == 'H1' else 'no rain rule'} | " + " | ".join(f"{pc(V[f'M-agree|{w}|{h}|S-off']['strong_share_usable'])} / {pc(V[f'M-agree|{w}|{h}|S-off']['strong_acc'])}" for w in (3, 5, 7, 10)) + " |" for h in ("H1", "H0")))
T["stained"] = ("| Stained water (development) | Stage 16 | Selected (agreement-only) | M-iuw ±10 d (not adopted) |\n|---|---:|---:|---:|\n"
                f"| Operational score | {B['per_class']['stained']:.3f} | {s['per_class']['stained']:.3f} | **{IU['per_class']['stained']:.3f}** |\n"
                f"| Answer right (full-authority answers) | {pc(B['stained_answer_acc'])} | {pc(s['stained_answer_acc'])} | **{pc(IU['stained_answer_acc'])}** |\n"
                f"| Harmful (stained rows) | {p1(B['stained_harm'])} | {p1(s['stained_harm'])} | **{p1(IU['stained_harm'])}** |\n"
                f"| Mean posterior of issued states (all) | {B['mean_conf']:.3f} | {s['mean_conf']:.3f} | **{IU['mean_conf']:.3f}** |\n"
                f"| Exact-feet error, rows with a consensus | ×{10 ** xi['feet_err_anchor_same_rows']:.2f} | ×{10 ** xi['feet_err_anchor_same_rows']:.2f} | **×{10 ** xi['feet_err']:.2f}** |")
T["ci"] = ("| M-iuw ±10 d against Stage 16 (lake bootstrap, 2,000, seed 17) | Difference | 95% CI |\n|---|---:|---|\n"
           f"| Stained score | {IU['per_class']['stained'] - B['per_class']['stained']:+.3f} | {ci(xi['stained_diff_ci'])} |\n"
           f"| Class-balanced operational | {IU['bal'] - B['bal']:+.3f} | {ci(xi['bal_diff_ci'])} |\n"
           f"| Harmful rate | {100 * (IU['harm'] - B['harm']):+.2f} pts | {100 * xi['harm_diff_ci'][0]:+.2f} to {100 * xi['harm_diff_ci'][1]:+.2f} pts |")
ev = lambda v: v["evidence"]; tot = lambda v: sum(ev(v).values())
T["evidence"] = ("| Evidence level (share of all answers) | Stage 16 | Selected (agreement-only) | M-iuw ±10 d |\n|---|---:|---:|---:|\n" +
                 "\n".join(f"| {e.capitalize()} | {pc(ev(B).get(e, 0) / tot(B))} | {pc(ev(s).get(e, 0) / tot(s))} | {pc(ev(IU).get(e, 0) / tot(IU))} |" for e in ("strong", "moderate", "weak", "unavailable")) +
                 f"\n| Strong right | {pc(B['strong_acc'])} | {pc(s['strong_acc'])} | {pc(IU['strong_acc'])} |")
T["bars"] = ("| Bar | Selected (agreement-only) | M-iuw ±10 d (not adopted) | Required |\n|---|---|---|---|\n"
             f"| Operational | {s['bal']:.3f} | {IU['bal']:.3f} | 9/10: ≥ 0.85; Stage 16: ≥ 7/10 |\n"
             f"| Weakest core class | {min(s['per_class'].values()):.3f} (stained) | {min(IU['per_class'].values()):.3f} (stained) | 9/10: ≥ 0.80; Stage 16: ≥ 0.60 |\n"
             f"| Harmful | {p1(s['harm'])} | {p1(IU['harm'])} | 9/10: ≤ 5%; Stage 16: ≤ 15% |\n| Severe | {p1(s['sev'])} | {p1(IU['sev'])} | 9/10: ≤ 0.5%; Stage 16: ≤ 2% |\n"
             f"| Strong share / right | {pc(s['strong_share_usable'])} / {pc(s['strong_acc'])} | {pc(IU['strong_share_usable'])} / {pc(IU['strong_acc'])} | 9/10: ≥ 50% / ≥ 90% |\n"
             f"| **Stage 16 freeze bars** | **no** (stained 0.571) | **yes, on development** | |\n| **True 9/10** | **no** | **no** | |")
md = f"""# Current Clarity Stage 17: Multi-Scene Consensus

**Development only.**
- The single-scene engine is unchanged: C-gbm and its scene predictions are not refitted, and fold models are used
  exactly as in Stages 14–16.
- No field report, Stage 16 fresh row or Stage 14/15 certification row was used.
- Production is unchanged, and nothing was deployed.
- Water Temperature is not started.

{T['freeze']}

## The answer

**Combining neighbouring satellite views does help, but under the rule I froze it is not adopted.**
- **What combining gains.** Weighting each frozen scene prediction by its uncertainty, over ±10 days (M-iuw), raises
  stained water from **0.571 to 0.667** (+0.096, CI +0.054 to +0.143) and the operational score from 0.693 to 0.743.
- **The Stage 16 freeze bars.** With it, every core class clears 0.60, so it
  **meets the Stage 16 freeze bars on development** for the first time.
- **What else it improves.**
  - Stained answers are right more often: 79%, from 72%.
  - Stained harm falls from 22% to 18.5%.
  - Exact feet tighten from ×1.36 to ×1.33.
- **The cost.** It answers about 100 rows that Stage 16 left Unknown, and some of those answers are wrong. The overall
  harmful rate rises **from 10.6% to 11.6%**. The CI of that change (−0.2 to +2.1 points) includes zero.
- **The frozen rule.** It admitted only variants that do not raise the harmful rate at all. That leaves only
  agreement-only variants, which keep every Stage 16 answer, so **MULTI-SCENE CONSENSUS USEFUL is NO**.

**Two pre-registered ideas do not hold up:**
- **The rainfall rule makes every method worse.** ERA5 point rainfall discards scenes that were in fact still
  informative.
- **Strong evidence reaches at most 24%,** at 95% right. That is far from the 50% target.

**Sentinel-2C cannot be tested on development:** only 49 of the 2,072 neighbour scenes are S2C.

**Bars.** The true 9/10 bar is far away. Readiness to move to Water Temperature is **NO**.

**The decision this leaves you.** Accepting about one extra harmful answer per hundred, a change that is not
statistically significant, would buy a material stained-water gain. That needs a new, unseen certification pool either
way.

## 1. How the consensus was built

**Which scenes.** Each development event gets up to its **3 nearest valid neighbouring passes** within ±10 days. These
are the Stage 11 production-gated passes with ≥ 5 valid water pixels, excluding the matched pass.
- **The run.** 2,487 neighbour scenes for 1,215 events, run through the unchanged K4 ACOLITE path: 2,072 L1C items, 15
  failures (6 had no L1C).
- **The predictor.** Each scene is predicted by the fold C-gbm trained without its lake.

{T['coverage']}

**How each scene is weighted.** Each scene carries its prediction, tier, platform and Δt. Its variance is
σ²_tier + κ·|Δt|, fitted on training lakes:
- σ ≈ 0.19 (tier 1) and 0.17–0.20 (tier 2);
- κ ≈ 0.0015–0.0020 per day.

That growth is small: a scene 10 days away is only about 20% noisier than the matched one.

**Calibration.** Posteriors are re-calibrated (nested) by the number of contributing scenes, and the frozen Stage 16
gate (0.70 / 0.70) issues the state.

## 2. The four methods (±10 days, no rain rule, S2C off)

{T['methods']}

- **Combining matters, the method does not.** The three combining methods are within 0.003 of one another. Down-weighting
  outliers (M-robust) and a population prior (M-bayes) add nothing over plain inverse-uncertainty weighting.
- **The lesson of Stage 11 holds.** Combining helps because it averages several independent errors. It does not help
  by discarding the matched scene.

## 3. Windows and hydrology

{T['windows']}

- **The widest window is best.** Most events have a valid neighbour only beyond ±3 days.
- **The rainfall rule (≥ 20 mm, or a day ≥ 12.7 mm) lowers the score at every window.** At the scale of an ERA5 cell,
  rain is a poor proxy for whether a lake's clarity changed. Hydrology may still decide compatibility, but this rule
  does not earn its place.

## 4. Stained water, the primary question

{T['stained']}

{T['ci']}

- **For stained water, every measure improves.** That includes the stained harmful rate, which falls.
- **Where the overall harm increase comes from.** About 100 former Unknowns now get answers (Unknown falls from 13% to
  6%), and a few of those are wrong.

## 5. Strong evidence

{T['agree']}

{T['evidence']}

**What agreement buys.**
- **The rule:** at least 2 compatible full-authority scenes whose states contain the answer, no disagreeing scene, and a
  posterior ≥ 0.90.
- **What it gives:** at ±10 days, Strong rises from Stage 16's 11% to 21–24% of usable answers, at 95% right. With only
  ±3 days (the selected variant) it stays at 11%.
- **The target is out of reach.** It is not close to 50%: half of events have at most one valid neighbour (23% have
  none), and agreement often still leaves the posterior below 0.90.
- **Why not loosen it.** Lowering the bar to hit 50% would trade accuracy for coverage, which the pre-registration
  forbids.

## 6. Sentinel-2C

**S2C AGREEMENT CAN UPGRADE AUTHORITY: NO.**
- **The test.** S-agree against S-off, at the selected variant.
- **The result.** S2C raised **{D['s2c_upgrade']['n_upgraded']}** answers' evidence level, against the 30 required.
  Development contains almost no S2C: 49 of 2,072 neighbour scenes, and 38 anchors.
- **What it would take.** Adding agreeing S2C scenes changes the consensus very little (M-bayes S2C-agree against S2C-off:
  0.745 against 0.745). The question can only be answered on 2025–2026 data, where S2C is a third of scenes.
- **No S2C scene regains authority alone,** and no S2C bias correction was fitted.

## 7. What the user would see (logic first)

| Underlying evidence | Display |
|---|---|
| Strong: ≥ 2 compatible full-authority views agree, posterior ≥ 0.90 | **2.7 ft · Normal-to-Stained** · High confidence — recent satellite views agree |
| Moderate: one view, or views that do not all agree but none disagree | **2.7 ft · Normal-to-Stained** |
| A compatible full-authority view disagrees | **~2.7 ft · Normal-to-Stained** · Lower confidence — recent views disagree |
| Weak (Sentinel-2C only, or tier 3) | **~2.7 ft · Normal-to-Stained** · Lower confidence |
| Unknown | Visibility unknown — no reliable recent view |

- **No scene counts.** The confidence line already says what the count would.
- **The algal warning** stays a separate line.

## 8. Bars

{T['bars']}

- **The selected variant is Stage 16's answers with better evidence labels.** It meets neither bar.
- **The combining method meets the Stage 16 freeze bars on development, but not the 9/10 bar.** Stained (0.67) is still
  far from 0.80, harmful far above 5%, and Strong far below 50%.

## 9. Certification (none here)

**What exists.** Stage 16's 108 fresh rows are historical context only: 7/10 operational, insufficient. They were not
used.

**What a Stage 17 design needs.** A completely unseen pool. The immediate sources for US stained and limited reservoir
Secchi are:
1. **Oklahoma Water Resources Board, Beneficial Use Monitoring Program.** About 130 reservoirs sampled quarterly on a
   five-year rotation, many of them turbid. Data are served through the University of Oklahoma OKH2O water-quality
   portal (OWRB BUMP: `oklahoma.gov/owrb/data-and-maps/beneficial-use-monitoring-program.html`,
   OU portal: `ou.edu/okh2o/monitoring/data-portal/water-quality-data.html`).
2. **Texas TCEQ SWQMIS.** Reservoir Secchi from TCEQ and the river authorities, downloadable directly from TCEQ ahead of
   WQP's lag (TCEQ SWQM data: `www.tceq.texas.gov/waterquality/data-management/swqm_data.html`).
3. **TVA reservoir monitoring and USACE district water-quality programs:** a direct records request. There is no public
   bulk download.
4. **A WQP re-pull around April 2027** for the 2026 state uploads.

**Before anything is retrieved,** each needs the Stage 16 protocol: sites in no earlier file, a value-blind index, and
frozen minima.

---

MULTI-SCENE CONSENSUS USEFUL: NO (by the frozen rule. Every combining method raised the harmful rate and was excluded; the selected agreement-only variant keeps Stage 16's answers, so stained is unchanged. The best combining method, inverse-uncertainty weighting over ±10 days, raised stained by +0.096 (CI +0.054 to +0.143) and operational by +0.050 (CI +0.035 to +0.066), with harmful +0.95 points (CI −0.19 to +2.08): useful on the evidence, but not adopted)
BEST CONSENSUS METHOD: Agreement-only evidence upgrade (±3 days, rainfall rule on, S2C off), the simplest pre-registered variant that does not raise harm. If a ~1-point harmful increase is accepted: inverse-uncertainty weighting of frozen scene predictions over ±10 days without the rainfall rule (M-robust and M-bayes add nothing over it)
STAINED SCORE: {s['per_class']['stained']:.3f} selected (unchanged from Stage 16); {IU['per_class']['stained']:.3f} with inverse-uncertainty weighting ±10 d (not adopted)
LIMITED SCORE: {s['per_class']['limited']:.3f} selected; {IU['per_class']['limited']:.3f} with weighting ±10 d
OPERATIONAL SCORE: {s['bal']:.3f} ({int(round(10 * s['bal'] + 1e-9))}/10) selected; {IU['bal']:.3f} ({int(round(10 * IU['bal'] + 1e-9))}/10) with weighting ±10 d
HARMFUL RATE: {p1(s['harm'])} selected; {p1(IU['harm'])} with weighting ±10 d
SEVERE RATE: {p1(s['sev'])} selected; {p1(IU['sev'])} with weighting ±10 d
STRONG EVIDENCE SHARE: {pc(s['strong_share_usable'])} of usable answers selected; at most {pc(BY['strong_share_usable'])} for any variant (Stage 16: {pc(B['strong_share_usable'])}); the 50% target is not met
STRONG EVIDENCE ACCURACY: {pc(s['strong_acc'])} selected; {pc(IU['strong_acc'])} with weighting ±10 d
S2C AGREEMENT CAN UPGRADE AUTHORITY: NO (development holds almost no Sentinel-2C: {D['s2c_upgrade']['n_upgraded']} upgraded answers against the 30 needed; testable only on 2025–2026 data)
DEVELOPMENT CAPABILITY: {D['capability']}/10
TRUE 9/10 DEVELOPMENT BAR PASSED: NO
NEXT UNSEEN CERTIFICATION SOURCE: Oklahoma OWRB Beneficial Use Monitoring Program reservoirs (OU OKH2O portal) and Texas TCEQ SWQMIS reservoir Secchi, retrieved directly for sites in no earlier file under the Stage 16 protocol. Then a TVA/USACE records request and a WQP re-pull around April 2027
READY TO MOVE TO WATER TEMPERATURE: NO (the 9/10 bar is not passed; the selected variant misses the Stage 16 bars (stained 0.571); the combining method meets them on development, but no unseen certification pool exists yet)
"""
open(f"{S}/stage17/CURRENT_CLARITY_STAGE17_MULTISCENE_CONSENSUS.md", "w", encoding="utf-8").write(md)
head, sep, tail = md.rpartition("\n---\n")
open(f"{S}/stage17/_print.md", "w", encoding="utf-8").write(head + sep + "\n" + "\n\n".join(l for l in tail.strip().split("\n") if l.strip()) + "\n")
print("ok", len(md))
