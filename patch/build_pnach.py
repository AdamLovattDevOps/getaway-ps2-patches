#!/usr/bin/env python3
"""Right-stick camera for The Getaway (SCUS-97133, CRC E21404E2) — v2 (GTA-style).
Persistent orbit angle: angle += -rx*|rx|*RATE*dt (clamped ±pi); stick centred -> decays at RETURN/s.
Hooks the final-yaw sin() call in CarCameraController::Update (f23) and PlayerCameraController (f22).
Cave = libpad error strings 0x3d6d58..0x3d6e4c (only ever read on a libpad failure path)."""
import struct
SIN=0x308048; AXES_PTR=0x3dc288; DT=0x3741fc
CAVE=0x3d6d58; CAVE_END=0x3d6e4c
CAVE_B=0x3d6eb0; CAVE_B_END=0x3d6f88     # libcdvd debug printf strings, unreferenced
FLAGS=0x3d6fd8; REQ=0x3d6fdc; MAGIC=0x3d6fe0; MAGICV=0x600DF00D   # spare words after cave C; REQ written by pnach groups, latched into FLAGS each frame
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
def lbu(rt,off,base): return 0x90000000|(base<<21)|(rt<<16)|(off&0xffff)
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
assert CAVE_C+4*len(pc)<=FLAGS
words+=[(CAVE_C+4*i,w) for i,w in enumerate(pc)]
patches=[(SITE_CAR,jal(STUB_CAR)),(SITE_FOOT,jal(STUB_FOOT)),(SITE_PITCH,jal(CAVE_C))]+words   # + on-foot free-look hook added below
lines=["gametitle=The Getaway (USA) SCUS-97133","comment=Right analog stick camera (car + on foot), GTA-style rate orbit with auto-return. getaway-decomp v2",
       "[Right-stick car camera]","author=adam","description=On foot: right stick orbits (L/R) and pitches (U/D) the camera. In car: right stick nudges the view, L2/R2 look left/right, both = look behind."]
lines+=[f"patch={0 if a==STATE2 else 1},EE,{a:08x},word,{w:08x}" for a,w in patches]   # STATE: once at boot, never reset

# ===================== TRAINER (toggles) =====================
# Per-frame tick hooked at 0x1f10cc (lui v1,0x37 in frame fn FUN_001f0eb0; ra stack-saved, t0 LIVE, v0/v1/a* live).
# R1 held + newly-pressed: Square -> god (bit0), Cross -> ammo+no-reload (bit1), Triangle -> 60fps (bit2). Rumble ack.
CAVE_D=0x3d6fe8; CAVE_D_END=0x3d71ec          # sce libcdvd error strings (error path only)
SITE_TICK=0x1f10cc; TICK_RET=0x1f10d0
SITE_60=0x1f10e8; W60_ON=0x1000000b; W60_OFF=0x1500000b
SITE_GOD=0x174ba0; GOD_RESUME=0x174ba8; GAME_PTR=0x3aae48
SITE_AMMO=0x1751b0; SITE_RELOAD1=0x1ad92c; SITE_RELOAD2=0x1ad9c8
RUMBLE=0x26da30; RUMBLE_KIND=3
R1,SQUARE,CROSS,TRIANGLE=0x0008,0x0080,0x0040,0x0010
T2,T3,T4,T5,T6,T7,V0,V1,A0,A1,A2,A3=10,11,12,13,14,15,2,3,4,5,6,7
def sw(rt,off,base): return 0xac000000|(base<<21)|(rt<<16)|(off&0xffff)
def lhu(rt,off,base): return 0x94000000|(base<<21)|(rt<<16)|(off&0xffff)
def andi(rt,rs,imm): return 0x30000000|(rs<<21)|(rt<<16)|(imm&0xffff)
def xori(rt,rs,imm): return 0x38000000|(rs<<21)|(rt<<16)|(imm&0xffff)
def bne(rs,rt,off): return 0x14000000|(rs<<21)|(rt<<16)|(off&0xffff)
def nor(rd,rs,rt): return 0x00000027|(rs<<21)|(rt<<16)|(rd<<11)
def and_(rd,rs,rt): return 0x00000024|(rs<<21)|(rt<<16)|(rd<<11)
def addiu(rt,rs,imm): return 0x24000000|(rs<<21)|(rt<<16)|(imm&0xffff)
class Asm:
    def __init__(s,base): s.base=base; s.w=[]; s.lab={}; s.fix=[]
    def pc(s): return s.base+4*len(s.w)
    def emit(s,*ws): s.w.extend(ws)
    def label(s,n): s.lab[n]=len(s.w)
    def br(s,kind,n,*a):   # branch to label, delay slot nop appended by caller
        s.fix.append((len(s.w),kind,n,a)); s.w.append(0)
    def jto(s,n): s.fix.append((len(s.w),'j',n,())); s.w.append(0)
    def done(s):
        for i,kind,n,a in s.fix:
            if kind=='j': s.w[i]=j(s.base+4*s.lab[n]); continue
            off=s.lab[n]-(i+1)
            s.w[i]={'beq':lambda:beq(a[0],a[1],off),'bne':lambda:bne(a[0],a[1],off),'bc1t':lambda:bc1t(off)}[kind]()
        return s.w
D=Asm(CAVE_D)
BUZZ=TICK=0
# ---- god: entered by `j` from ApplyDamage+0 (delay slot 'clear f1' ran). a0 = character ----
D.label('god'); GOD=D.pc()
D.emit(lui(T2,0x3d), lbu(T2,lo(FLAGS),T2), xori(T2,T2,1)); D.br('bne','normal',T2,ZERO); D.emit(NOP)   # god byte == 1
D.emit(lui(T3,hi(GAME_PTR)), lw(T3,lo(GAME_PTR),T3)); D.br('beq','normal',T3,ZERO); D.emit(NOP)
D.emit(lw(T3,0x10,T3)); D.br('bne','normal',T3,A0); D.emit(NOP)
D.emit(jr(RA), NOP)                                           # player + god: no damage
D.label('normal'); D.emit(addiu(29,29,-0x20), j(GOD_RESUME), NOP)
# ---- ammo: hook lw a0,0(a1) @0x1751b0; delay slot did subu v1,v1,v0; next insn v1 = a0 - v1 ----
D.label('ammo'); AMMO=D.pc()
D.emit(lw(A0,0,A1), lui(AT,0x3d), lbu(AT,lo(FLAGS+1),AT), xori(AT,AT,1)); D.br('bne','ammo_ret',AT,ZERO); D.emit(NOP)   # ammo byte == 1
D.emit(addiu(V1,ZERO,0)); D.label('ammo_ret'); D.emit(jr(RA), NOP)
# ---- reload1: hook lw v1,0(a0) @0x1ad92c (delay slot addiu v1,-1 on stale v1, we redo) ----
D.label('rl1'); RL1=D.pc()
D.emit(lw(V1,0,A0), lui(AT,0x3d), lbu(AT,lo(FLAGS+1),AT), xori(AT,AT,1)); D.br('beq','rl1_ret',AT,ZERO); D.emit(NOP)
D.emit(addiu(V1,V1,-1)); D.label('rl1_ret'); D.emit(jr(RA), NOP)
# ---- reload2: hook lw v0,0(v1) @0x1ad9c8 ----
D.label('rl2'); RL2=D.pc()
D.emit(lw(V0,0,V1), lui(AT,0x3d), lbu(AT,lo(FLAGS+1),AT), xori(AT,AT,1)); D.br('beq','rl2_ret',AT,ZERO); D.emit(NOP)
D.emit(addiu(V0,V0,-1)); D.label('rl2_ret'); D.emit(jr(RA), NOP)
# ---- on-foot free-look: hook lwc1 f0,-0x13c4(s3) @0x144aa4 (max yaw deviation from facing, 0.1 rad).
#      Stick deflected -> clamp = pi (free 360); released -> clamp eases back to 0.1 at 3 rad/s. f2-f6 free here.
CLAMP=0x3d6fe4; SITE_FREE=0x144aa4; S3=19; EASE=0x40400000  # 3.0
D.label('foot_free'); FOOT_FREE=D.pc()
D.emit(lwc1(0,-0x13c4,S3), lui(AT,0x3d), lwc1(4,lo(CLAMP),AT))
D.emit(lui(AT,0x4049), ori(AT,AT,0x0fdb), mtc1(AT,3), fpu(MAX,4,4,0), fpu(MIN,4,4,3))      # C in [0.1,pi]
D.emit(lui(AT,hi(AXES_PTR)), lw(AT,lo(AXES_PTR),AT)); D.br('beq','ff_rel',AT,ZERO); D.emit(NOP)
D.emit(lwc1(2,0,AT), fpu(ABS,2,2,0), clt(2,0), NOP); D.br('bc1t','ff_rel'); D.emit(NOP)      # |rx| < 0.1 -> release
D.emit(fpu(MOV,4,3,0)); D.br('beq','ff_st',ZERO,ZERO); D.emit(NOP)                          # held: C = pi
D.label('ff_rel'); D.emit(lui(AT,hi(DT)), lwc1(2,lo(DT),AT), lui(AT,EASE>>16), mtc1(AT,3), fpu(MUL,2,2,3), fpu(SUB,4,4,2), fpu(MAX,4,4,0))
D.label('ff_st'); D.emit(lui(AT,0x3d), swc1(4,lo(CLAMP),AT), fpu(MOV,0,4,0), jr(RA), NOP)
dw=D.done()
SAVE=CAVE_D+4*len(dw); assert SAVE<=CAVE_D_END, hex(SAVE)
TRAINER_ENABLED=True    # joker mode (PS2-era cheat-device style): no per-frame code hook; pnach D-codes watch the pad word and write flag bytes
trainer=[(CAVE_D+4*i,w) for i,w in enumerate(dw)]
trainer+=[(SITE_GOD,j(GOD)),(SITE_AMMO,jal(AMMO)),(SITE_RELOAD1,jal(RL1)),(SITE_RELOAD2,jal(RL2))]   # tick hook (0x1f10cc) REMOVED: it caused several-x game speed
# free-look belongs to the camera group: emit its words + hook there
FF=[(FOOT_FREE+4*i,dw[(FOOT_FREE-CAVE_D)//4+i]) for i in range(len(dw)-(FOOT_FREE-CAVE_D)//4)]
trainer=[t for t in trainer if not (FOOT_FREE<=t[0]<SAVE)]
patches+= FF+[(SITE_FREE,jal(FOOT_FREE))]
if not TRAINER_ENABLED: trainer=[]
trainer_state=[]   # state self-inits via MAGIC
if TRAINER_ENABLED:
    # Menu-driven (PCSX2 pause menu -> Game Properties -> Cheats). pnach lines apply in file order every vsync:
    # core zeroes the flag bytes, an enabled toggle group re-writes 1 after it. Disable the group -> stays 0.
    lines+=["","[Trainer core (needed by God mode / Infinite ammo)]","author=adam","description=Hooks + flag reset. Toggle the cheats below from the pause menu (L3)."]
    lines+=[f"patch=1,EE,{a:08x},word,{w:08x}" for a,w in trainer]
    lines+=[f"patch=1,EE,{FLAGS:08x},byte,00000000", f"patch=1,EE,{FLAGS+1:08x},byte,00000000"]
    lines+=["","[God mode]","author=adam","description=Player takes no damage.", f"patch=1,EE,{FLAGS:08x},byte,00000001"]
    lines+=["","[Infinite ammo + no reload]","author=adam","description=Ammo and clip never decrease.", f"patch=1,EE,{FLAGS+1:08x},byte,00000001"]
EXTRA=trainer+trainer_state
print(f"trainer: foot_free={FOOT_FREE:08x} god={GOD:08x} ammo={AMMO:08x} rl1={RL1:08x} rl2={RL2:08x} save={SAVE:08x} words={len(dw)}")

# --- cutscene skip: runner FUN_0027edc0 allows skip only if (just-pressed 0x400) && seen-before(cutsceneId)
lines+=["","[Skip cutscenes with Start]","author=adam","description=Cutscenes can be skipped with Start on first viewing (game normally allows it only on replays).",
        "patch=1,EE,0027f6bc,word,24050c00",   # li a1,0x400 -> li a1,0xc00  (Start | original)
        "patch=1,EE,0027f6d8,word,24020001"]   # jal seen_before() -> li v0,1
d=bytearray(open('disc/SCUS_971.33','rb').read())
for a,w in patches+EXTRA: struct.pack_into('<I',d,a-0x100000+0x1000,w)
print(f"compute_car={COMPUTE_CAR:08x} ({len(cc)} w) state2={STATE2:08x}  compute={COMPUTE:08x} ({len(comp)} w) stub_car={STUB_CAR:08x} stub_foot={STUB_FOOT:08x} state={STATE:08x} patches={len(patches)}")

open('patch/E21404E2.pnach','w').write("\n".join(lines)+"\n")
open('patch/SCUS_971.33.patched','wb').write(d)
