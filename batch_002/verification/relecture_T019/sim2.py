import numpy as np
rng=np.random.default_rng(2)
S=40_000
centers=rng.uniform(0,1e6,(300,2)); w=rng.pareto(1.2,300)+1; w/=w.sum()
idx=rng.choice(300,S,p=w); sites=centers[idx]+rng.normal(0,1,(S,2))*rng.choice([500,3000,20000],S)[:,None]
mult=rng.choice([1,2,2,2,4,4,6,8],S)  # EVSE per site
pts=np.repeat(sites,mult,axis=0); N=len(pts); print('N',N)
K=10
qs=sites[rng.integers(0,S,3000)]+rng.normal(0,300,(3000,2))
res=[]
for q in qs:
    d=np.hypot(*(pts-q).T); d.sort(); dk=d[K-1]
    res.append(np.searchsorted(d,1.5*dk,side='right'))
res=np.array(res); print('within 1.5dk p50',np.percentile(res,50),'p90',np.percentile(res,90),'p99',np.percentile(res,99))
