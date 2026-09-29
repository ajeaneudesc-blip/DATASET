from gor import *
import datetime
t0=1790229612
d=[None]
ts=[t0]
for i in range(1,119):
    ts.append(None)
# build deltas explicitly by index i (delta between i-1 and i)
deltas={}
for i in range(1,119): deltas[i]=60
deltas[23]=61; deltas[24]=59
deltas[71]=124
deltas[101]=62; deltas[102]=58
ts=[t0]
for i in range(1,119): ts.append(ts[-1]+deltas[i])
def hms(t): return datetime.datetime.fromtimestamp(t,datetime.timezone.utc).strftime('%H:%M:%S')
print('count',len(ts),'last',ts[-1],hms(ts[-1]))
wo,po=enc(ts,OLD); wn,pn=enc(ts,NEW)
bo,bn=wo.bytes(),wn.bytes()
print('old bits',len(wo.bits),'bytes',len(bo)); print('new bits',len(wn.bits),'bytes',len(bn))
def hexdump(b):
    out=[]
    for off in range(0,len(b),16):
        chunk=b[off:off+16]
        out.append(f'{off:08x}  '+' '.join(f'{x:02x}' for x in chunk))
    return '\n'.join(out)
print('us-east (old)'); print(hexdump(bo))
print('eu-west (new)'); print(hexdump(bn))
do=dec(bo,t0,len(ts)); dn=dec(bn,t0,len(ts))
assert do==ts
first=[i for i in range(len(ts)) if dn[i]!=ts[i]][0]
print('first divergent index',first, hms(ts[first]), hms(dn[first]), dn[first]-ts[first])
for i in range(first-2,first+5): print(i,hms(ts[i]),hms(dn[i]),dn[i]-ts[i])
print('last', hms(dn[-1]), dn[-1]-ts[-1])
# where does bit diff start
fb=[i for i in range(min(len(wo.bits),len(wn.bits))) if wo.bits[i]!=wn.bits[i]][0]
print('first differing bit',fb,'byte',fb//8)
for i,dod,s,e in pn:
    if dod!=0: print('new',i,dod,s,e)
for i,dod,s,e in po:
    if dod!=0: print('old',i,dod,s,e)
# monotonic?
print('non-monotone count', sum(1 for i in range(1,len(dn)) if dn[i]<=dn[i-1]))
