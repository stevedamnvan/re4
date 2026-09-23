#!/bin/bash
# Build a bootable Dreamcast disc image (CUE/BIN) from an ELF plus a data
# directory.  [TEXDIRS=dir[:dir]] [MESHDIRS=dir[:dir]] #   mkdisc.sh <elf> <datadir> <outdir> [fixturesdir]
# (overlays: see "Optional overlays" below)
#
# Deliberately a single-session CD-R layout rather than a GD-ROM (GDI) image.
# KOS mounts /cd by reading the *low density* table of contents
# (fs_iso9660.c calls cdrom_read_toc(&toc, false)) and taking the last data
# track it finds there. In a GDI the payload track lives in the high density
# area, so KOS never sees it and every fs_open("/cd/...") returns -1 even
# though the same image boots: the bootstrap reads the high density track
# directly. A CD-R image keeps the one data track where KOS looks for it.
set -e
ELF="$1"
DATA="$2"
OUTDIR="$3"
KOS=/root/work/kos
WORK=/root/discwork

rm -rf "$WORK" "$OUTDIR"
mkdir -p "$WORK/cdroot" "$OUTDIR"

# 1ST_READ.BIN: raw binary from the ELF.
bash "$KOS/utils/elf2bin/elf2bin" "$ELF" "$WORK/prog.bin" >/dev/null 2>&1 || {
  sh-elf-objcopy -R .stack -O binary "$ELF" "$WORK/prog.bin"; }
# A CD-R bootstrap expects 1ST_READ.BIN scrambled, and descrambles it on load;
# that holds for the real BIOS and for Flycast's replacement alike. (A GD-ROM
# image is the other way round, which is why an unscrambled binary booted from
# the earlier GDI and produces a wedged machine here.)
if [ "$SCRAMBLE" = "0" ]; then
  cp "$WORK/prog.bin" "$WORK/cdroot/1ST_READ.BIN"
else
  chmod +x "$KOS/utils/scramble/scramble" 2>/dev/null || true
  "$KOS/utils/scramble/scramble" "$WORK/prog.bin" "$WORK/cdroot/1ST_READ.BIN"
fi

cat > "$WORK/ip.txt" <<'IPTXT'
Hardware ID   : SEGA SEGAKATANA
Maker ID      : SEGA ENTERPRISES
Device Info   : 0000 CD-ROM1/1
Area Symbols  : JUE
Peripherals   : E000F10
Product No    : T0000
Version       : V1.000
Release Date  : 20260920
Boot Filename : 1ST_READ.BIN
SW Maker Name : RE4DC
Game Title    : RE4DC ROOM
IPTXT
chmod +x "$KOS/utils/makeip/makeip" 2>/dev/null || true
"$KOS/utils/makeip/makeip" -f "$WORK/ip.txt" "$WORK/IP.BIN" >/dev/null

if [ -d "$DATA" ]; then
  # the whole tree: the game target keeps the GameCube directory layout
  cp -r "$DATA"/. "$WORK/cdroot/" 2>/dev/null || true
fi
# Optional fixtures directory (port/dreamcast/fixtures): scripted input and
# other Dreamcast-only test files, published under /cd/dc/.
EXTRA="$4"
if [ -n "$EXTRA" ] && [ -d "$EXTRA" ]; then
  mkdir -p "$WORK/cdroot/dc"
  cp -r "$EXTRA"/. "$WORK/cdroot/dc/"
fi
# Optional overlays, applied to this run's copy after the fixtures so the data
# and fixtures directories (often shared or hard-linked) are never written.
# Each variable is a colon-separated list of directories, applied in order.
#   TEXDIRS   texture packages <crc>-<fnv>.re4tex -> /cd/dc/tex/. Each must
#             replace a texture the fixtures already publish: the name is the
#             GC source image identity the runtime looks up, so a replacement
#             under a new name would never be read (e.g. the PS2 tree bark,
#             tools/ps2_tree_texture.py, replaces GC R100.TPL image 0).
#   MESHDIRS  native mesh packages *.re4mesh -> /cd/dc/native/${MESHROOM:-r100}/
#             (e.g. convert_room_bins.py --lod output), added or replaced.
overlay() {
  local var="$1" dest="$2" pattern="$3" must_replace="$4" dir f n
  local IFS=:
  for dir in ${!var:-}; do
    [ -n "$dir" ] || continue
    if [ ! -d "$dir" ]; then
      echo "mkdisc: $var directory $dir missing" >&2
      exit 1
    fi
    n=0
    mkdir -p "$dest"
    for f in "$dir"/$pattern; do
      [ -e "$f" ] || continue
      if [ "$must_replace" = 1 ] && [ ! -e "$dest/$(basename "$f")" ]; then
        echo "mkdisc: $var: $(basename "$f") replaces no published texture (key must be a source identity)" >&2
        exit 1
      fi
      cp "$f" "$dest/"
      n=$((n + 1))
    done
    if [ "$n" = 0 ]; then
      echo "mkdisc: $var directory $dir holds no $pattern" >&2
      exit 1
    fi
    echo "mkdisc: $var $dir: $n file(s) -> ${dest#"$WORK/cdroot"}"
  done
}
overlay TEXDIRS "$WORK/cdroot/dc/tex" '*.re4tex' 1
overlay MESHDIRS "$WORK/cdroot/dc/native/${MESHROOM:-r100}" '*.re4mesh' 0

# One MODE1/2048 data track starting at LBA 0, with IP.BIN occupying the first
# sixteen sectors. Rock Ridge and Joliet both carry the real (lower case, long)
# names; KOS reads either.
genisoimage -quiet -G "$WORK/IP.BIN" -r -J -l \
  -input-charset iso8859-1 -V RE4DCROOM -o "$OUTDIR/disc.bin" "$WORK/cdroot"

cat > "$OUTDIR/disc.cue" <<'CUE'
FILE "disc.bin" BINARY
  TRACK 01 MODE1/2048
    INDEX 01 00:00:00
CUE

echo "built $OUTDIR/disc.cue"
ls -l "$OUTDIR"
