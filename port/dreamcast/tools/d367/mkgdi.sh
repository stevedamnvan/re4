#!/bin/bash
# D367 W10: GDEMU image (GDI) from the same inputs as mkdisc-hardlink.sh.
#   [SECTOR=2352|2048] [PERIPHERALS=0799810] [PRODUCT=T0000] [TITLE=..] \
#     mkgdi.sh <elf> <datadir> <outdir> [fixturesdir]
#
# Standard three-track GD-ROM layout, the one GDEMU and Flycast expect:
#   track01  LBA 0       MODE1 data, low-density area: small ISO9660 placeholder
#   track02  LBA 756     audio, 302 sectors of silence (the "warning" track slot)
#   track03  LBA 45000   MODE1 data, high-density area: IP.BIN in the 16 system
#                        sectors, then the ISO9660 game tree. Directory extents
#                        are absolute LBAs (genisoimage -C 0,45000).
# The game tree is built exactly as mkdisc-hardlink.sh builds it (data tree
# hard-linked, fixtures under /dc/), so the CUE and the GDI carry the same files.
#
# Boot chain differences from the CD-R image:
#   - 1ST_READ.BIN is NOT scrambled. The boot ROM descrambles only on a CD-ROM
#     (MIL-CD) disc; on a GD-ROM it loads the binary as is.
#   - IP.BIN Device Info is "GD-ROM1/1".
#   - KOS mounts /cd from the low-density TOC; the game's cdrom_read_toc wrap
#     (game/platform/gdrom_mount.cpp) redirects that to track 3 on a GD-ROM.
#     An ELF built without that wrap boots this image and then cannot open /cd.
#
# SECTOR=2352 (default) writes raw MODE1 tracks with EDC/ECC (tools/d367/mode1raw.c,
# built with the host cc), the Redump/TOSEC form every GDEMU firmware reads.
# SECTOR=2048 writes .iso data tracks (Flycast reads both; smaller on the SD card).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
ELF=${1:?usage: mkgdi.sh <elf> <datadir> <outdir> [fixturesdir]}
DATA=${2:?usage: mkgdi.sh <elf> <datadir> <outdir> [fixturesdir]}
OUTDIR=${3:?usage: mkgdi.sh <elf> <datadir> <outdir> [fixturesdir]}
EXTRA=${4:-}
KOS=${KOS_TOOLS_BASE:-/root/work/kos}
SECTOR=${SECTOR:-2352}
# Peripherals (makeip README bit table): VGA box, memory card (VMU),
# Start+A+B+directions, X, Y, analog L/R triggers, analog stick. Add 0x200
# (0799A10) to declare jump pack support once the game drives one.
PERIPHERALS=${PERIPHERALS:-0799810}
PRODUCT=${PRODUCT:-T0000}
TITLE=${TITLE:-RE4DC}
HD_LBA=45000
T1_SECTORS=606   # track02 then starts at 756 after its 150-sector pregap
T2_SECTORS=302   # 4 s minimum audio track
case "$SECTOR" in 2352|2048) ;; *) echo "mkgdi: SECTOR must be 2352 or 2048" >&2; exit 1 ;; esac
[ -d "$DATA" ] || { echo "mkgdi: data directory $DATA missing" >&2; exit 1; }
[ -z "$EXTRA" ] || [ -d "$EXTRA" ] || { echo "mkgdi: fixtures directory $EXTRA missing" >&2; exit 1; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/re4dc-gdi.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
rm -rf "$OUTDIR"
mkdir -p "$WORK/cdroot" "$WORK/t1root" "$OUTDIR"

# 1ST_READ.BIN: raw binary, unscrambled.
if ! bash "$KOS/utils/elf2bin/elf2bin" "$ELF" "$WORK/prog.bin" >/dev/null 2>&1; then
  sh-elf-objcopy -R .stack -O binary "$ELF" "$WORK/prog.bin"
fi
test -s "$WORK/prog.bin"
cp "$WORK/prog.bin" "$WORK/cdroot/1ST_READ.BIN"

cat > "$WORK/ip.txt" <<IPTXT
Hardware ID   : SEGA SEGAKATANA
Maker ID      : SEGA ENTERPRISES
Device Info   : 0000 GD-ROM1/1
Area Symbols  : JUE
Peripherals   : $PERIPHERALS
Product No    : $PRODUCT
Version       : V1.000
Release Date  : 20260920
Boot Filename : 1ST_READ.BIN
SW Maker Name : RE4DC
Game Title    : $TITLE
IPTXT
chmod +x "$KOS/utils/makeip/makeip" 2>/dev/null || true
"$KOS/utils/makeip/makeip" -f "$WORK/ip.txt" "$WORK/IP.BIN" >/dev/null
test "$(stat -c %s "$WORK/IP.BIN")" -eq 32768
# Fail here rather than on the console if a field did not land.
for want in "SEGA SEGAKATANA" "SEGA ENTERPRISES" "GD-ROM1/1" "1ST_READ.BIN"; do
  head -c 256 "$WORK/IP.BIN" | grep -aq "$want" || { echo "mkgdi: IP.BIN lacks '$want'" >&2; exit 1; }
done

# Game tree, as mkdisc-hardlink.sh builds it.
cp -al "$DATA"/. "$WORK/cdroot/"
if [ -n "$EXTRA" ]; then
  mkdir -p "$WORK/cdroot/dc"
  cp -r "$EXTRA"/. "$WORK/cdroot/dc/"
fi

# track03: IP.BIN + ISO9660 at LBA 45000 (absolute extents), written straight
# to OUTDIR because it is the big file. Rock Ridge and Joliet carry the real
# lower-case long names, as on the CD-R image.
genisoimage -quiet -C 0,$HD_LBA -G "$WORK/IP.BIN" -r -J -l \
  -input-charset iso8859-1 -V RE4DCROOM -o "$OUTDIR/track03.iso" "$WORK/cdroot"
# Per-file absolute LBAs (isoinfo -N: the image starts at LBA 45000).
if command -v isoinfo >/dev/null; then
  isoinfo -N $HD_LBA -R -l -i "$OUTDIR/track03.iso" > "$OUTDIR/track03-files.txt" 2>/dev/null || true
fi

# track01: placeholder ISO in the low-density area, padded to T1_SECTORS.
printf 'RE4DC GD-ROM image. The game is in the high-density area (track 3).\r\n' > "$WORK/t1root/README.TXT"
genisoimage -quiet -G "$WORK/IP.BIN" -V RE4DCLD -input-charset iso8859-1 \
  -o "$WORK/track01.iso" "$WORK/t1root"
t1=$(( $(stat -c %s "$WORK/track01.iso") / 2048 ))
[ "$t1" -le "$T1_SECTORS" ] || { echo "mkgdi: track01 is $t1 sectors" >&2; exit 1; }
truncate -s $((T1_SECTORS * 2048)) "$WORK/track01.iso"

if [ "$SECTOR" = 2352 ]; then
  cc -O2 -o "$WORK/mode1raw" "$here/mode1raw.c"
  "$WORK/mode1raw" "$WORK/track01.iso" "$OUTDIR/track01.bin" 0
  "$WORK/mode1raw" "$OUTDIR/track03.iso" "$OUTDIR/track03.bin" $HD_LBA
  rm -f "$OUTDIR/track03.iso"
  t1f=track01.bin; t3f=track03.bin
else
  mv "$WORK/track01.iso" "$OUTDIR/track01.iso"
  t1f=track01.iso; t3f=track03.iso
fi
head -c $((T2_SECTORS * 2352)) /dev/zero > "$OUTDIR/track02.raw"
t2_lba=$((T1_SECTORS + 150))
printf '3\r\n1 0 4 %s %s 0\r\n2 %s 0 2352 track02.raw 0\r\n3 %s 4 %s %s 0\r\n' \
  "$SECTOR" "$t1f" "$t2_lba" "$HD_LBA" "$SECTOR" "$t3f" > "$OUTDIR/disc.gdi"
cp "$WORK/IP.BIN" "$OUTDIR/IP.BIN"

# Layout report: track sizes, GD-ROM capacity, and each file's LBA in track 3.
t3_sectors=$(( $(stat -c %s "$OUTDIR/$t3f") / SECTOR ))
hd_cap=$((549150 - HD_LBA))   # GD-ROM high-density area ends at LBA 549150 (~1.03 GB of user data)
{
  echo "sector_bytes $SECTOR"
  echo "track01 lba 0 sectors $T1_SECTORS bytes $(stat -c %s "$OUTDIR/$t1f")"
  echo "track02 lba $t2_lba sectors $T2_SECTORS bytes $(stat -c %s "$OUTDIR/track02.raw")"
  echo "track03 lba $HD_LBA sectors $t3_sectors bytes $(stat -c %s "$OUTDIR/$t3f") user_bytes $((t3_sectors * 2048))"
  echo "hd_capacity_sectors $hd_cap user_bytes $((hd_cap * 2048)) used_pct $((100 * t3_sectors / hd_cap))"
} | tee "$OUTDIR/layout.txt"
echo "built $OUTDIR/disc.gdi"
ls -l "$OUTDIR"
