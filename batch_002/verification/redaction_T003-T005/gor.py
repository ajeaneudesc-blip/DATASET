import datetime
class BW:
    def __init__(s): s.bits=[]
    def push(s, v, n):
        for i in range(n-1,-1,-1): s.bits.append((v>>i)&1)
    def bytes(s):
        b=s.bits+[0]*((-len(s.bits))%8)
        return bytes(int(''.join(map(str,b[i:i+8])),2) for i in range(0,len(b),8))
def enc(ts, buckets):
    w=BW(); d0=ts[1]-ts[0]; w.push(d0,14); prev=d0; pos=[]
    for i in range(2,len(ts)):
        d=ts[i]-ts[i-1]; dod=d-prev; prev=d
        start=len(w.bits)
        if dod==0: w.push(0,1)
        else:
            for lo,hi,pre,pl,vl in buckets:
                if lo<=dod<=hi:
                    w.push((pre<<vl)|(dod & ((1<<vl)-1)), pl+vl); break
            else:
                w.push(0b1111,4); w.push(dod & 0xffffffff,32)
        pos.append((i,dod,start,len(w.bits)))
    return w, pos
OLD=[(-64,63,0b10,2,7),(-256,255,0b110,3,9),(-2048,2047,0b1110,4,12)]
NEW=[(-63,64,0b10,2,7),(-255,256,0b110,3,9),(-2047,2048,0b1110,4,12)]
def sx(v,w):
    return v-(1<<w) if v>>(w-1) else v
def dec(data, t0, n):
    bits=[]
    for b in data:
        for i in range(7,-1,-1): bits.append((b>>i)&1)
    p=0
    def rd(k):
        nonlocal p
        v=0
        for _ in range(k): v=(v<<1)|bits[p]; p+=1
        return v
    d=rd(14); ts=[t0,t0+d]
    while len(ts)<n:
        if rd(1)==0: dod=0
        elif rd(1)==0: dod=sx(rd(7),7)
        elif rd(1)==0: dod=sx(rd(9),9)
        elif rd(1)==0: dod=sx(rd(12),12)
        else: dod=sx(rd(32),32)
        d+=dod; ts.append(ts[-1]+d)
    return ts
