phoboslab/pl_mpeg c871f2be022ece7ef4f64230b4fb8e1fb9eb6023
https://github.com/phoboslab/pl_mpeg
MIT license is retained at top of pl_mpeg.h. Unmodified upstream.
Only elementary MPEG-1 video API is used; PCM is decoded offline.

RE4DC local option (route cutscenes, 2026-09-23): `PLM_VIDEO_TWO_FRAMES`, off
unless defined. For I/P-only elementary streams (the offline profile encodes
`-bf 0`) the decoder ping-pongs two reference frames instead of three and skips
B pictures; with `plm_video_set_no_delay(1)` the returned frame is the newest
picture. Saves one 320x240 frame (115,200 bytes). Upstream behaviour is
unchanged when the macro is not defined.

Local option `PLM_RE4DC_FAST` (off unless defined; the route player defines it):
word-at-a-time `plm_buffer_read` when the bits are buffered, VLC tree walk
without per-bit refill checks when 32 bits are buffered, IDCT all-zero-AC
column/row shortcuts (the full transform yields the same values), and motion
compensation with constant 16/8 block sizes plus aligned full-pel word copies.
Output is bit-identical: every frame of r100s40, r100s20, r101s30 and r120s00
hashes the same with and without the option (host test, FNV-1a per frame).
