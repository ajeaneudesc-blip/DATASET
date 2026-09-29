# Décodeur indépendant, calqué sur le Rust (read_unary_prefix(4), sign_extend)
import datetime
def utc(t): return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
eu = bytes.fromhex("00 f0 00 00 10 1b f4 04 00 00 00 00 00 14 0d c0 00 00 00 08 15 f2 04 00 00".replace(" ",""))
us = bytes.fromhex("00 f0 00 00 10 1b f4 04 00 00 00 00 00 18 81 40 00 00 00 08 15 f2 04 00 00".replace(" ",""))
print(len(eu), len(us))
class R:
    def __init__(s,b): s.bits=''.join(f'{x:08b}' for x in b); s.p=0
    def bits_(s,n):
        v=int(s.bits[s.p:s.p+n],2); s.p+=n; return v
    def unary(s,mx):
        c=0
        while c<mx:
            b=s.bits[s.p]; s.p+=1
            if b=='0': return c
            c+=1
        return c
def sx(raw,w):
    return raw-(1<<w) if raw>>(w-1) else raw
def decode(b, t0, n):
    r=R(b); d=r.bits_(14); ts=[t0, t0+d]; dods=[]
    while len(ts)<n:
        u=r.unary(4)
        if u==0: dod=0
        else:
            w={1:7,2:9,3:12}.get(u,32)
            start=r.p
            dod=sx(r.bits_(w),w)
        dods.append(dod)
        d+=dod; ts.append(ts[-1]+d)
    return ts, dods, r.p
t0=1790229612; n=119
print('t_first', utc(t0), 't_last hdr', utc(1790236756))
te,de,pe=decode(eu,t0,n); tu,du,pu=decode(us,t0,n)
print('bits used eu',pe,'us',pu, 'remaining bits eu', eu and ''.join(f'{x:08b}' for x in eu)[pe:], 'us', ''.join(f'{x:08b}' for x in us)[pu:])
print('last eu', te[-1], utc(te[-1]), 'last us', tu[-1], utc(tu[-1]))
nz=[(i+2,x) for i,x in enumerate(de) if x]; print('eu nonzero dods (point index, dod)', nz)
nz=[(i+2,x) for i,x in enumerate(du) if x]; print('us nonzero dods (point index, dod)', nz)
diff=[i for i in range(n) if te[i]!=tu[i]]
f=diff[0]
print('first divergent index', f, 'eu', utc(te[f]), 'us', utc(tu[f]), 'ecart', te[f]-tu[f])
for i in range(f-2, f+4): print(i, utc(tu[i]), utc(te[i]), te[i]-tu[i])
print('final ecart', te[-1]-tu[-1])
print('non-monotone eu', sum(1 for i in range(1,n) if te[i]<=te[i-1]), 'us', sum(1 for i in range(1,n) if tu[i]<=tu[i-1]))
deltas=[tu[i]-tu[i-1] for i in range(1,n)]
print('us deltas !=60', [(i+1,x) for i,x in enumerate(deltas) if x!=60])
# first differing bit/byte
be=''.join(f'{x:08b}' for x in eu); bu=''.join(f'{x:08b}' for x in us)
fb=[i for i in range(len(be)) if be[i]!=bu[i]]
print('differing bits', fb[:5], '...', fb[-3:], 'bytes', sorted(set(i//8 for i in fb)))
