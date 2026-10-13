import datetime as dt, csv, collections, json
ROOT='../../../'
LAKES=['Lake_Minnetonka_MN','Mille_Lacs_Lake_MN','Lake_Winnibigoshish_MN','Gull_Lake_MN']
def refs(lake):
    """unique (survey date) refs with point counts, from out/umn_fleet_points.csv"""
    c=collections.Counter()
    for r in csv.DictReader(open('out/umn_fleet_points.csv')):
        if r['lake']==lake: c[r['date']]+=1
    return c
def scene_years(y):
    """-> list of (scene_year, tier). tier E exact-year, N near-substitute (survey 2014-2016), F far substitute (<=2013), A adjacent-year substitute for an S2-era survey"""
    if y>=2017: return [(y,'E'),(y+1,'A')]
    if y>=2014: return [(2017,'N'),(2018,'N')]
    return [(2018,'F')]
def shift(d,sy):
    d=dt.date.fromisoformat(d)
    try: return d.replace(year=sy)
    except ValueError: return d.replace(year=sy,day=28)

# --- SFWMD (Florida) lakes: single reference month-day, substitute scene years, bounded scene counts
FL_CFG={'Okeechobee_FL':dict(refs=['2016-06-10'],years=[2018,2019],cloud=40,maxdates=5),
        'Kissimmee_FL':dict(refs=['2015-06-15'],years=[2018,2019],cloud=50,maxdates=6),
        'Tohopekaliga_Toho_FL':dict(refs=['2016-04-15'],years=[2018,2019],cloud=50,maxdates=6)}
