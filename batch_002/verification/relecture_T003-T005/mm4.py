import unicodedata, re
def rotl(x,r): return ((x<<r)|(x>>(32-r)))&0xFFFFFFFF
def fmix(h):
    h^=h>>16; h=(h*0x85ebca6b)&0xFFFFFFFF; h^=h>>13; h=(h*0xc2b2ae35)&0xFFFFFFFF; h^=h>>16; return h
def m3(data, seed):
    c1,c2=0xcc9e2d51,0x1b873593; h=seed&0xFFFFFFFF; n=len(data)//4
    for i in range(n):
        k=int.from_bytes(data[4*i:4*i+4],'little'); k=(k*c1)&0xFFFFFFFF; k=rotl(k,15); k=(k*c2)&0xFFFFFFFF
        h^=k; h=rotl(h,13); h=(h*5+0xe6546b64)&0xFFFFFFFF
    t=data[4*n:]; k=0
    if len(t)>=3: k^=t[2]<<16
    if len(t)>=2: k^=t[1]<<8
    if len(t)>=1:
        k^=t[0]; k=(k*c1)&0xFFFFFFFF; k=rotl(k,15); k=(k*c2)&0xFFFFFFFF; h^=k
    h^=len(data); return fmix(h)
# test vectors (Guava / reference)
assert m3(b"",0)==0 and m3(b"",1)==0x514E28B7 and m3(b"hello",0)==0x248bfa47
def normalize(raw):
    s=(raw or "").lower()
    s=unicodedata.normalize('NFD', s)
    s=''.join(ch for ch in s if unicodedata.category(ch)!='Mn')
    s=re.sub(r'[^\w ]|_', ' ', s)  # approx \p{L}\p{Nd}
    s=re.sub(r'\s+',' ',s).strip()
    return s
SEED=0x2017DF00
for q in [None,"🔥🔥","???","iPhone","iphone","coque","airpods pro","lego","Coque","AirPods Pro"]:
    nq=normalize(q)
    print(repr(q), repr(nq), m3(nq.encode(),SEED)%64)
