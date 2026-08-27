#!/bin/bash
# The Getaway (PS2) on PCSX2 with the getaway-decomp patch set.
# Legion Go 2: Lenovo firmware ships PL2(19W) < PL1(23W), clamping the APU to ~20W -> 30-65% speed.
# PPT tunables only accept writes while the gamezone profile is "custom".
ISO="${GETAWAY_ISO:-$HOME/Emulation/roms/ps2/Getaway, The (USA) (En,Fr,De,Es,It).iso}"
if pgrep -x "pcsx2-Qt.AppIma" >/dev/null; then echo "PCSX2 already running"; exit 1; fi
GZ=$(for p in /sys/class/platform-profile/*/; do [ "$(cat $p/name)" = lenovo-wmi-gamezone ] && echo $p; done)
A=/sys/class/firmware-attributes/lenovo-wmi-other-0/attributes
[ -n "$GZ" ] && echo custom | sudo -n tee $GZ/profile >/dev/null 2>&1
echo 30 | sudo -n tee $A/ppt_pl1_spl/current_value  >/dev/null 2>&1
echo 32 | sudo -n tee $A/ppt_pl2_sppt/current_value >/dev/null 2>&1
echo "PPT: pl1=$(cat $A/ppt_pl1_spl/current_value)W pl2=$(cat $A/ppt_pl2_sppt/current_value)W"
exec ~/Applications/pcsx2-Qt.AppImage -fullscreen "$ISO"
