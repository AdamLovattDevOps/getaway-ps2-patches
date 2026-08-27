# getaway-ps2-patches

Quality-of-life patches for **The Getaway** (PS2, SCUS-97133, CRC `E21404E2`) on PCSX2, plus the
reverse-engineering notes and tooling used to make them.

This is **not a decompilation** (yet). It is binary patching: a few dozen words of hand-assembled
MIPS in unused space in the original executable, applied at runtime via PCSX2's pnach system.
The RE notes are the groundwork for a possible native port later; that work lives in `NOTES.md`.

No game data is in this repo. You need your own disc image.

## What the patch does (`patch/E21404E2.pnach`)

**Right-stick car camera** (group 1)
- On foot: right stick orbits the follow camera.
- In car: right stick nudges the view; **L2** = look left, **R2** = look right, **L2+R2** = look behind
  (GTA III style), eased in and out.
- Implemented as two code caves in unreferenced libpad/libcdvd debug strings, hooked at the final
  `sin(yaw)` call of `CarCameraController::Update` (`0x13d164`) and `PlayerCameraController` (`0x144e48`).
  The right stick was completely unread by the original game.

**Skip cutscenes with Start** (group 2)
- The game only lets you skip a cutscene you have already seen. Two words widen the skip button mask
  to include Start and short-circuit the seen-before check.

## Install
```
cp patch/E21404E2.pnach ~/.config/PCSX2/cheats/
```
Then enable the cheat groups for the game in PCSX2 (Game Properties → Cheats), or put this in
`~/.config/PCSX2/gamesettings/SCUS-97133_E21404E2.ini`:
```
[EmuCore]
EnableCheats = true

[Cheats]
Enable = Right-stick car camera
Enable = Skip cutscenes with Start
```
`patch/build_pnach.py` regenerates the pnach (a tiny MIPS assembler with the tuning constants at the top).

## Legion Go 2 note
Lenovo firmware ships with the short-term power limit (19 W) *below* the sustained one (23 W), which
pins the APU at ~20 W and PCSX2 at 40–65% speed. `tools/getaway-launch.sh` sets the gamezone profile
to `custom` and PL1/PL2 to 30/32 W before launching; the game then holds 100% at native res, and
60 FPS with PCSX2's bundled 60 FPS patch + EE overclock.

## RE tooling (`scripts/`)
Ghidra headless scripts (needs [ghidra-emotionengine-reloaded](https://github.com/chaoticgd/ghidra-emotionengine-reloaded))
for dumping functions/strings/xrefs, decompiling by name, and `rtti_scan.py` for recovering GCC 2.9x
vtables (8-byte `{delta, fptr}` entries, `__tf` in slot 0). See `NOTES.md` for everything learned.
