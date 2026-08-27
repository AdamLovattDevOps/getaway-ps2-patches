import struct,re,sys
data=open('disc/SCUS_971.33','rb').read(); BASE=0x100000; img=data[0x1000:0x1000+0x2d9464]
def u32(a): return struct.unpack_from('<I',img,a-BASE)[0]
# map __tf function -> class via strings.txt (Ghidra xrefs)
tf={}
for line in open('ghidra/strings.txt'):
    m=re.match(r'^00([0-9a-f]{6}) \|(\d+)(\w+)\|(.*)$',line.rstrip('\n'))
    if not m: continue
    n,cls,refs=int(m.group(2)),m.group(3),m.group(4).split()
    if len(cls)!=n: continue
    for r in refs:
        if r.startswith('FUN_'): tf.setdefault(int(r[4:],16),set()).add(cls)
rx=re.compile(sys.argv[1] if len(sys.argv)>1 else '.')
for f,clss in sorted(tf.items()):
    # the __tf of class X references X's name and its base's name (via calling base __tf, no) -> pick names; a fn referencing multiple names is a __tf for the one... ambiguous; use all
    pat=struct.pack('<I',f); i=img.find(pat)
    while i!=-1:
        a=i+BASE
        if a%4==0 and u32(a-4)==0:
            ents=[]
            for k in range(1,80):
                d=u32(a-4+8*k); p=u32(a+8*k)
                if d!=0 or not(0x100000<=p<0x3d0000) or p&3: break
                ents.append(p)
            if len(ents)>=2:
                names=[c for c in clss if rx.search(c)]
                if names: print(f"VT {'/'.join(sorted(names,key=len))} tf={f:08x} vtable={a-4:08x} n={len(ents)} "+' '.join(f'{p:08x}' for p in ents))
        i=img.find(pat,i+1)
