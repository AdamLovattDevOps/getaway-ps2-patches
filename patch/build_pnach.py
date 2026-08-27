#!/usr/bin/env python3
"""Right-stick camera for The Getaway (SCUS-97133, CRC E21404E2) — v2 (GTA-style).
Persistent orbit angle: angle += -rx*|rx|*RATE*dt (clamped ±pi); stick centred -> decays at RETURN/s.
Hooks the final-yaw sin() call in CarCameraController::Update (f23) and PlayerCameraController (f22).
Cave = libpad error strings 0x3d6d58..0x3d6e4c (only ever read on a libpad failure path)."""
import struct
SIN=0x308048; AXES_PTR=0x3dc288; DT=0x3741fc
CAVE=0x3d6d58; CAVE_END=0x3d6e4c
CAVE_B=0x3d6eb0; CAVE_B_END=0x3d6f88     # libcdvd debug printf strings, unreferenced
SITE_CAR=0x13d164; SITE_FOOT=0x144e48
RATE=0xc0600000   # -3.5 rad/s at full deflection (negative = fixes the flipped direction)
RETURN=0x40c00000 # 6.0 /s return-to-centre
DEAD=0x3dcccccd   # 0.1
def hi(a): return (a>>16)+(1 if a&0x8000 else 0)
def lo(a): return a&0xffff
def lui(rt,imm): return 0x3c000000|(rt<<16)|(imm&0xffff)
def ori(rt,rs,imm): return 0x34000000|(rs<<21)|(rt<<16)|(imm&0xffff)
def lw(rt,off,base): return 0x8c000000|(base<<21)|(rt<<16)|(off&0xffff)
def lwc1(ft,off,base): return 0xc4000000|(base<<21)|(ft<<16)|(off&0xffff)
def swc1(ft,off,base): return 0xe4000000|(base<<21)|(ft<<16)|(off&0xffff)
def mtc1(rt,fs): return 0x44800000|(rt<<16)|(fs<<11)
def fpu(op,fd,fs,ft): return 0x46000000|(ft<<16)|(fs<<11)|(fd<<6)|op
def clt(fs,ft): return 0x46000034|(ft<<16)|(fs<<11)
def bc1t(off): return 0x45010000|(off&0xffff)
def beq(rs,rt,off): return 0x10000000|(rs<<21)|(rt<<16)|(off&0xffff)
def b(off): return beq(0,0,off)
def j(t): return 0x08000000|((t>>2)&0x3ffffff)
def jal(t): return 0x0c000000|((t>>2)&0x3ffffff)
def jr(rs): return 0x00000008|(rs<<21)
def move(rd,rs): return 0x00000025|(rs<<21)|(rd<<11)
ADD,SUB,MUL,ABS,MOV,NEG,MIN,MAX=0,1,2,5,6,7,0x29,0x28  # EE: 0x28=max.s 0x29=min.s
ZERO,AT,T0,T1,T8,T9,RA=0,1,8,9,24,25,31
NOP=0
# ---- compute: f1 = updated angle ----
comp=[]; L={}
def lab(n): L[n]=len(comp)
def emit(*w): comp.extend(w)
emit(lui(T0,hi(AXES_PTR)), lw(T0,lo(AXES_PTR),T0))
emit(lui(T1,0))                     # patched below with STATE hi
STATE_LUI=len(comp)-1
emit(lwc1(4,0,T1))                  # f4 = angle   (offset patched)
STATE_LWC=len(comp)-1
emit(lui(AT,hi(DT)), lwc1(3,lo(DT),AT))                 # f3 = dt
emit(beq(T0,ZERO,0), NOP); BEQ_NOPAD=len(comp)-2
emit(lwc1(1,0,T0))                  # f1 = rx
emit(fpu(ABS,2,1,0))                # f2 = |rx|
emit(lui(AT,DEAD>>16), ori(AT,AT,DEAD&0xffff), mtc1(AT,5))
emit(clt(2,5), NOP, bc1t(0), NOP); BC1T_DEAD=len(comp)-2
emit(fpu(MUL,1,1,2))                # rx*|rx|
emit(lui(AT,RATE>>16), mtc1(AT,6), fpu(MUL,1,1,6), fpu(MUL,1,1,3))
emit(fpu(ADD,4,4,1))
emit(lui(AT,0x4049), ori(AT,AT,0x0fdb), mtc1(AT,6))    # pi
emit(fpu(MIN,4,4,6), fpu(NEG,6,6,0), fpu(MAX,4,4,6))
emit(b(0), NOP); B_STORE=len(comp)-2
lab('decay')
emit(lui(AT,RETURN>>16), mtc1(AT,6), fpu(MUL,6,6,3))   # dt*RETURN
emit(lui(AT,0x3f80), mtc1(AT,5), fpu(SUB,5,5,6))       # 1-dt*RETURN
emit(mtc1(ZERO,6), fpu(MAX,5,5,6), fpu(MUL,4,4,5))
lab('store')
emit(swc1(4,0,T1)); STATE_SWC=len(comp)-1
emit(fpu(MOV,1,4,0), jr(RA), NOP)
# branch fixups (offset from instr after branch)
comp[BEQ_NOPAD]=beq(T0,ZERO,L['decay']-(BEQ_NOPAD+1))
comp[BC1T_DEAD]=bc1t(L['decay']-(BC1T_DEAD+1))
comp[B_STORE]=b(L['store']-(B_STORE+1))
COMPUTE=CAVE
def stub(freg,target=None):  # entered via jal from game (delay slot already did mov.S f12,freg)
    return [move(T9,RA), jal(target or COMPUTE), NOP, fpu(ADD,freg,freg,1), fpu(MOV,12,freg,0), move(RA,T9), j(SIN), NOP]
STUB_FOOT=COMPUTE+4*len(comp); s_foot=stub(22)
s_car=[move(T9,RA), jal(COMPUTE), NOP, fpu(ADD,23,23,1),          # small stick offset (STATE resets each frame)
       jal(CAVE_B), NOP, fpu(ADD,23,23,1),                        # + L2/R2 eased view angle
       fpu(MOV,12,23,0), move(RA,T9), j(SIN), NOP]
STUB_CAR=None  # placed in cave B below
STATE=STUB_FOOT+4*len(s_foot)
assert STATE+4<=CAVE_END, hex(STATE)
comp[STATE_LUI]=lui(T1,hi(STATE)); comp[STATE_LWC]=lwc1(4,lo(STATE),T1); comp[STATE_SWC]=swc1(4,lo(STATE),T1)
# ---- car: GTA3-style fixed views. L2 -> +pi/2, R2 -> -pi/2, both -> pi, none -> 0; angle eases to target ----
CAVE_B=0x3d6eb0; CAVE_B_END=0x3d6f88     # libcdvd debug printf strings, unreferenced
BUTTONS=0x3dc240                          # u16 held-buttons word of pad0 state (bit0=L2, bit1=R2)
STATE2=CAVE_B_END-4
SNAP=0x41400000                           # 12.0 /s ease rate (min(dt*SNAP,1))
def lhu(rt,off,base): return 0x94000000|(base<<21)|(rt<<16)|(off&0xffff)
def andi(rt,rs,imm): return 0x30000000|(rs<<21)|(rt<<16)|(imm&0xffff)
def xori(rt,rs,imm): return 0x38000000|(rs<<21)|(rt<<16)|(imm&0xffff)
def bne(rs,rt,off): return 0x14000000|(rs<<21)|(rt<<16)|(off&0xffff)
cc=[]; CL={}
def clab(n): CL[n]=len(cc)
cc+=[lui(T0,hi(BUTTONS)), lhu(T0,lo(BUTTONS),T0)]
cc+=[lui(T1,hi(STATE2)), lwc1(4,lo(STATE2),T1)]          # f4 = angle
cc+=[lui(AT,hi(DT)), lwc1(3,lo(DT),AT)]                    # f3 = dt
cc+=[mtc1(ZERO,5)]                                          # f5 = target 0
cc+=[andi(AT,T0,1), beq(AT,ZERO,0), NOP]; B_L2=len(cc)-2
cc+=[lui(AT,0x3fc9), ori(AT,AT,0x0fdb), mtc1(AT,5)]        # +pi/2
clab('l2done')
cc+=[andi(AT,T0,2), beq(AT,ZERO,0), NOP]; B_R2=len(cc)-2
cc+=[lui(AT,0xbfc9), ori(AT,AT,0x0fdb), mtc1(AT,6), fpu(ADD,5,5,6)]   # -pi/2
clab('r2done')
cc+=[andi(AT,T0,3), xori(AT,AT,3), bne(AT,ZERO,0), NOP]; B_BOTH=len(cc)-2
cc+=[lui(AT,0x4049), ori(AT,AT,0x0fdb), mtc1(AT,5)]        # both -> pi
clab('ease')
cc+=[lui(AT,SNAP>>16), mtc1(AT,6), fpu(MUL,6,6,3)]         # dt*SNAP
cc+=[lui(AT,0x3f80), mtc1(AT,7), fpu(MIN,6,6,7)]           # min(.,1)
cc+=[fpu(SUB,7,5,4), fpu(MUL,7,7,6), fpu(ADD,4,4,7)]       # angle += (target-angle)*k
cc+=[swc1(4,lo(STATE2),T1), fpu(MOV,1,4,0), jr(RA), NOP]
cc[B_L2]=beq(AT,ZERO,CL['l2done']-(B_L2+1)); cc[B_R2]=beq(AT,ZERO,CL['r2done']-(B_R2+1)); cc[B_BOTH]=bne(AT,ZERO,CL['ease']-(B_BOTH+1))
COMPUTE_CAR=CAVE_B
assert hi(STATE2)==0x3d and COMPUTE_CAR+4*len(cc)<=STATE2
STUB_CAR=COMPUTE_CAR+4*len(cc)
assert STUB_CAR+4*len(s_car)<=STATE2, hex(STUB_CAR+4*len(s_car))
words=[(COMPUTE_CAR+4*i,w) for i,w in enumerate(cc)]+[(STUB_CAR+4*i,w) for i,w in enumerate(s_car)]+[(STATE2,0)]
words+=[(COMPUTE+4*i,w) for i,w in enumerate(comp)]+[(STUB_FOOT+4*i,w) for i,w in enumerate(s_foot)]+[(STATE,0)]
# ---- on-foot pitch: camera height = player.y + 20.0 + RY*PITCH_K (looks at player, so height = pitch) ----
CAVE_C=0x3d6fa8; CAVE_C_END=0x3d6fe8      # libcdvd "Scmd fail"/"bind err S cmd" strings, error path only
SITE_PITCH=0x144e70                        # lwc1 f4,-0x13d8(a2)  (a2=0x360000 -> DAT_0035ec28)
PITCH_K=0x41c80000                         # 25.0 units at full deflection
A2=6
pc=[lwc1(4,-0x13d8,A2),                    # original instruction
    lui(AT,hi(AXES_PTR)), lw(AT,lo(AXES_PTR),AT), beq(AT,ZERO,6), NOP,   # -> jr ra
    lwc1(5,4,AT),                          # f5 = RY
    lui(AT,PITCH_K>>16), mtc1(AT,6), fpu(MUL,5,5,6), fpu(ADD,4,4,5),
    jr(RA), NOP]
assert CAVE_C+4*len(pc)<=CAVE_C_END
words+=[(CAVE_C+4*i,w) for i,w in enumerate(pc)]
patches=[(SITE_CAR,jal(STUB_CAR)),(SITE_FOOT,jal(STUB_FOOT)),(SITE_PITCH,jal(CAVE_C))]+words
lines=["gametitle=The Getaway (USA) SCUS-97133","comment=Right analog stick camera (car + on foot), GTA-style rate orbit with auto-return. getaway-decomp v2",
       "[Right-stick car camera]","author=adam","description=On foot: right stick orbits (L/R) and pitches (U/D) the camera. In car: right stick nudges the view, L2/R2 look left/right, both = look behind."]
lines+=[f"patch={0 if a==STATE2 else 1},EE,{a:08x},word,{w:08x}" for a,w in patches]   # STATE: once at boot, never reset
# --- cutscene skip: runner FUN_0027edc0 allows skip only if (just-pressed 0x400) && seen-before(cutsceneId)
lines+=["","[Skip cutscenes with Start]","author=adam","description=Cutscenes can be skipped with Start on first viewing (game normally allows it only on replays).",
        "patch=1,EE,0027f6bc,word,24050c00",   # li a1,0x400 -> li a1,0xc00  (Start | original)
        "patch=1,EE,0027f6d8,word,24020001"]   # jal seen_before() -> li v0,1
open('patch/E21404E2.pnach','w').write("\n".join(lines)+"\n")
d=bytearray(open('disc/SCUS_971.33','rb').read())
for a,w in patches: struct.pack_into('<I',d,a-0x100000+0x1000,w)
open('patch/SCUS_971.33.patched','wb').write(d)
print(f"compute_car={COMPUTE_CAR:08x} ({len(cc)} w) state2={STATE2:08x}  compute={COMPUTE:08x} ({len(comp)} w) stub_car={STUB_CAR:08x} stub_foot={STUB_FOOT:08x} state={STATE:08x} patches={len(patches)}")
