t0=1790229612
d={i:60 for i in range(1,119)}; d.update({23:61,24:59,71:124,101:62,102:58})
ts=[t0]
for i in range(1,119): ts.append(ts[-1]+d[i])
def enc(ts, buckets):
    bits=''; first=ts[1]-ts[0]; bits+=format(first,'014b'); prev=first
    for i in range(2,len(ts)):
        dd=ts[i]-ts[i-1]; dod=dd-prev; prev=dd
        if dod==0: bits+='0'; continue
        for lo,hi,pre,pl,vl in buckets:
            if lo<=dod<=hi:
                bits+=format(pre,f'0{pl}b')+format(dod & ((1<<vl)-1), f'0{vl}b'); break
        else:
            bits+='1111'+format(dod & 0xffffffff,'032b')
    bits+='0'*((-len(bits))%8)
    return bytes(int(bits[i:i+8],2) for i in range(0,len(bits),8))
V08=[(-64,63,0b10,2,7),(-256,255,0b110,3,9),(-2048,2047,0b1110,4,12)]
V09=[(-63,64,0b10,2,7),(-255,256,0b110,3,9),(-2047,2048,0b1110,4,12)]
print('v0.9', enc(ts,V09).hex(' '))
print('v0.8', enc(ts,V08).hex(' '))
print('yaml eu 00 f0 00 00 10 1b f4 04 00 00 00 00 00 14 0d c0 00 00 00 08 15 f2 04 00 00')
print('yaml us 00 f0 00 00 10 1b f4 04 00 00 00 00 00 18 81 40 00 00 00 08 15 f2 04 00 00')
print(ts[-1])
