"""Build the 621-lake Depth evidence matrix from verified outputs of this campaign (research only).
Never creates a match: contour evidence requires matchConfidence == verified_spatial; GLOBathy requires match_tier verified|weak.
"""
import pandas as pd, json, os, collections
D = 'docs/research/depth-brain/data/'
feat = pd.read_csv('/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain/data/lake_features.csv')
poly_ids = set(json.load(open(os.path.expanduser('~/Desktop/Development/Sector_Research_Data/depth-brain/ienc/poly_ids.json')))) if os.path.exists(os.path.expanduser('~/Desktop/Development/Sector_Research_Data/depth-brain/ienc/poly_ids.json')) else None
gm = pd.read_csv(D + 'globathy_fleet_match.csv').set_index('id')
ct = pd.read_csv(D + 'contour_truth_lakes.csv').drop_duplicates('lakeId').set_index('lakeId')
cm = pd.read_csv(D + 'contour_matches_verified.csv')
ver = cm[cm.matchConfidence == 'verified_spatial'].groupby('lakeId').src.apply(lambda s: ';'.join(sorted(set(s))))
nameonly = set(cm[cm.matchConfidence == 'name_only_unverified'].lakeId)
ienc = pd.read_csv(D + 'ienc_fleet_overlap.csv').set_index('id')
apf = pd.read_csv(D + 'acres_per_ft_by_lake.csv').set_index('id')
spl = pd.read_csv(D + 'shallow_proxy_lake_table.csv')
hyps = set(spl[spl.set.isin(['CWMS', 'TWDB'])].lake)
hyps_set = spl[spl.set.isin(['CWMS', 'TWDB'])].set_index('lake').set
orng = pd.read_csv(D + 'operating_range_by_lake.csv').set_index('lake')
scout = pd.read_csv('docs/research/depth-brain/scout/fleet_candidate_matches.csv')
scout_any = scout[scout.matchConfidence != 'none'].groupby('lakeId').size()
rows = []
for _, f in feat.iterrows():
    i = f.id
    g = gm.loc[i] if i in gm.index else None
    geom = (g is not None and g.poly_area_km2 == g.poly_area_km2)
    t = ct.loc[i] if i in ct.index else None
    tier_truth = t.tier if t is not None else None
    glob_ok = g is not None and g.match_tier in ('verified', 'weak') and g.glob_dmax_source == 'modeled_estimate'
    glob_supplied = g is not None and g.match_tier in ('verified', 'weak') and g.glob_dmax_source != 'modeled_estimate' and pd.notna(g.glob_dmax_source)
    pool_ok = i in apf.index and apf.loc[i, 'delta_possible'] == True
    hist = i in orng.index
    ienc_in = i in ienc.index
    terr = i in apf.index and pd.notna(apf.loc[i, 'acres_per_ft_pred'])
    # evidence tier (proposed)
    if tier_truth == 'A': tier, best = 'A', 'contour:' + ver.get(i, '')
    elif tier_truth == 'B': tier, best = 'B', 'contour:' + ver.get(i, '')
    elif tier_truth == 'C': tier, best = 'B-partial', 'contour(partial/coarse):' + ver.get(i, '')
    elif i in hyps: tier, best = 'C', 'measured hypsometry (' + hyps_set.get(i, '?') + ')'
    elif ienc_in: tier, best = 'B-binary', 'USACE IENC 9ft contour (intersects footprint; interior coverage unverified)'
    elif glob_ok or glob_supplied or terr: tier, best = 'D', ('GLOBathy supplied-observed Dmax' if glob_supplied and not glob_ok else 'GLOBathy modeled prior + 3DEP shoreline slope' if glob_ok else '3DEP shoreline slope')
    else: tier, best = 'U', 'none'
    absc = {'A': 'high', 'B': 'medium', 'B-partial': 'low', 'C': 'low', 'B-binary': 'low'}.get(tier, 'none')
    relc = {'A': 'high', 'B': 'medium', 'B-partial': 'low', 'C': 'medium' if i in hyps else 'low', 'B-binary': 'low', 'D': 'very_low', 'U': 'none'}[tier]
    src = (ver.get(i, '') or '')
    lic = 'unreviewed'
    if 'FL' in src.split(';') and tier in ('A', 'B', 'B-partial'): lic = 'internal_only(FL FWC no-redistribute)'
    elif tier in ('A', 'B', 'B-partial'): lic = 'state_open_data_no_explicit_licence; derived metrics only'
    elif tier == 'C' and hyps_set.get(i) == 'CWMS': lic = 'federal_public'
    elif tier == 'C': lic = 'TWDB public; not-for-navigation/fishing disclaimer'
    elif tier == 'B-binary': lic = 'federal_public'
    elif tier == 'D': lic = 'GLOBathy CC0 / 3DEP public'
    review = bool((t is not None and (pd.notna(t.get('flags')) and str(t.get('flags')) != '')) or i in nameonly or tier == 'B-partial' or (g is not None and g.match_tier == 'suspect'))
    rows.append(dict(lakeId=i, lakeName=f['name'], state=f.state1, regime=f.regime, geometryAvailable=bool(geom),
        authoritativeDepthAvailable=tier in ('A', 'B'), contoursAvailable=i in ver.index, contourSources=src,
        ienc9ftFootprint=ienc_in, hypsometryTruthAvailable=i in hyps,
        globathyAvailable=bool(glob_ok), globathyMatchTier=(g.match_tier if g is not None else 'none'),
        terrainInferencePossible=bool(terr), poolRefAndLevelBoundForShift=bool(pool_ok), levelHistory10y=hist,
        bestDepthSource=best, evidenceTier=tier, absoluteDepthConfidence=absc, relativeDepthConfidence=relc,
        scoutCandidateOnly=(i in scout_any.index and i not in ver.index), manualReviewNeeded=review, licenseStatus=lic))
m = pd.DataFrame(rows)
m.to_csv(D + 'depth_fleet_evidence_matrix.csv', index=False)
s = {'n': len(m), 'tier': m.evidenceTier.value_counts().to_dict(),
     'contoursAvailable': int(m.contoursAvailable.sum()), 'authoritative_AB': int(m.authoritativeDepthAvailable.sum()),
     'globathyModeledUsable': int(m.globathyAvailable.sum()), 'terrain': int(m.terrainInferencePossible.sum()),
     'shiftPossible': int(m.poolRefAndLevelBoundForShift.sum()), 'shift_hist10y': int((m.poolRefAndLevelBoundForShift & m.levelHistory10y).sum()),
     'scoutOnly': int(m.scoutCandidateOnly.sum()), 'review': int(m.manualReviewNeeded.sum()),
     'abBy_state': m[m.authoritativeDepthAvailable].state.value_counts().to_dict(),
     'tier_by_regime': m.groupby(['regime', 'evidenceTier']).size().unstack(fill_value=0).to_dict('index'),
     'anyShiftOrZones': int((m.poolRefAndLevelBoundForShift | m.authoritativeDepthAvailable).sum())}
json.dump(s, open(D + 'depth_fleet_evidence_summary.json', 'w'), indent=1, default=int)
print(json.dumps(s, indent=1, default=int))
