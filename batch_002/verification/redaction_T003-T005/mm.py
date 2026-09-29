def rotl(x, r): return ((x << r) | (x >> (32 - r))) & 0xFFFFFFFF
def murmur3_32(data: bytes, seed: int) -> int:
    c1, c2 = 0xcc9e2d51, 0x1b873593
    h = seed & 0xFFFFFFFF
    n = len(data) // 4
    for i in range(n):
        k = int.from_bytes(data[4*i:4*i+4], 'little')
        k = (k * c1) & 0xFFFFFFFF; k = rotl(k, 15); k = (k * c2) & 0xFFFFFFFF
        h ^= k; h = rotl(h, 13); h = (h * 5 + 0xe6546b64) & 0xFFFFFFFF
    tail = data[4*n:]; k = 0
    if len(tail) >= 3: k ^= tail[2] << 16
    if len(tail) >= 2: k ^= tail[1] << 8
    if len(tail) >= 1:
        k ^= tail[0]; k = (k * c1) & 0xFFFFFFFF; k = rotl(k, 15); k = (k * c2) & 0xFFFFFFFF; h ^= k
    h ^= len(data)
    h ^= h >> 16; h = (h * 0x85ebca6b) & 0xFFFFFFFF; h ^= h >> 13; h = (h * 0xc2b2ae35) & 0xFFFFFFFF; h ^= h >> 16
    return h
# sanity: known vectors
assert murmur3_32(b"", 0) == 0
assert murmur3_32(b"", 1) == 0x514E28B7
assert murmur3_32(b"hello", 0) == 0x248bfa47
cands = []
for seed in list(range(1, 100000)):
    if murmur3_32(b"", seed) % 64 == 17 and murmur3_32(b"iphone", seed) % 64 == 17:
        cands.append(seed)
print(cands[:40])
for s in [2017, 20170412, 0x4C545232, 1709, 42, 0x2017]:
    print(s, hex(s), murmur3_32(b"", s) % 64, murmur3_32(b"iphone", s) % 64)
