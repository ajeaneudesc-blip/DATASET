import numpy as np, heapq
rng=np.random.default_rng(1)
N=139_000; LEAF=32; K=10
# clustered points (cities) + uniform background
centers=rng.uniform(0,1e6,(400,2)); w=rng.pareto(1.2,400)+1; w/=w.sum()
idx=rng.choice(400,N,p=w); pts=centers[idx]+rng.normal(0,1,(N,2))*rng.choice([500,3000,20000],N)[:,None]
nodes=[]
def build(ix,depth):
    if len(ix)<=LEAF:
        nodes.append(('L',ix)); return len(nodes)-1
    ax=depth%2; v=pts[ix,ax]; mid=len(ix)//2
    piv=np.partition(v,mid)[mid]
    lo=ix[v<piv]; hi=ix[v>=piv]
    if len(lo)==0 or len(hi)==0:
        nodes.append(('L',ix)); return len(nodes)-1
    l=build(lo,depth+1); r=build(hi,depth+1)
    nodes.append(('I',ax,piv,l,r)); return len(nodes)-1
import sys; sys.setrecursionlimit(10000)
root=build(np.arange(N),0)
sizes=[len(n[1]) for n in nodes if n[0]=='L']
print('leaves',len(sizes),'p50',np.percentile(sizes,50),'p99',np.percentile(sizes,99))
def knn(q):
    best=[] # max-heap of (-d, id)
    cands=0
    def rec(n):
        nonlocal cands
        nd=nodes[n]
        if nd[0]=='L':
            ix=nd[1]; cands+=len(ix)
            d=np.hypot(*(pts[ix]-q).T)
            for di,i in zip(d,ix):
                if len(best)<K: heapq.heappush(best,(-di,i))
                elif di< -best[0][0]: heapq.heapreplace(best,(-di,i))
            return
        _,ax,piv,l,r=nd
        diff=q[ax]-piv
        first,second=(l,r) if diff<0 else (r,l)
        rec(first)
        if len(best)<K or abs(diff)< -best[0][0]: rec(second)
    rec(root); return cands
# queries near points (users near chargers) with jitter
qs=pts[rng.integers(0,N,3000)]+rng.normal(0,300,(3000,2))
c=np.array([knn(q) for q in qs])
print('cands p50',np.percentile(c,50),'p90',np.percentile(c,90),'mean',c.mean(), 'frac single leaf',(c<=32).mean())
