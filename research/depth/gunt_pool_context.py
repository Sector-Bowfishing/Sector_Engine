"""Guntersville pool context for the IENC audit: pool elevation around the nominal survey dates, and the distribution of pool relative to 593/595 ft. Research only."""
import os,pandas as pd,numpy as np
H=os.path.expanduser('~/Desktop/Development/Sector_Research_Data/lake-brain/history')
g=pd.read_csv(H+'/tva_pilots/GVDA1_daily.csv',parse_dates=['date']).set_index('date')['elevationFt']
print('GVDA1',g.index.min().date(),g.index.max().date(),len(g),'min',g.min(),'max',g.max())
for lab,a,b in [('Jul 2007','2007-06-15','2007-08-15'),('Jul 2008','2008-06-15','2008-08-15'),('May 2014','2014-04-20','2014-05-31'),('Jul 2020','2020-07-01','2020-08-15'),('Jun-Aug 2007','2007-06-01','2007-08-31')]:
    s=g[a:b]; print(lab,len(s), 'min/median/max',s.min(),s.median(),s.max())
print('year coverage', g.groupby(g.index.year).size().to_dict())
print('quantiles all',g.quantile([.01,.05,.25,.5,.75,.95,.99]).round(2).to_dict())
for per,s in [('Jun-Sep',g[g.index.month.isin([6,7,8,9])]),('Dec-Feb',g[g.index.month.isin([12,1,2])])]:
    print(per,s.quantile([.05,.5,.95]).round(2).to_dict(),'frac<593',round((s<593).mean(),3),'frac<594',round((s<594).mean(),3),'frac>=595',round((s>=595).mean(),3))
print('overall frac <593',round((g<593).mean(),4),'<592.5',round((g<592.5).mean(),4),'min date',g.idxmin().date(),g.min())
