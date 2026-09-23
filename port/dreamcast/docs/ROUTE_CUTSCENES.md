# Route cutscenes (PS2-inspired presentation profile)

Build flag `ROUTE_MOVIES=1` (default 0; default images carry none of this).
Each story event on the route r120 -> r100 -> r101 -> r103 is **presented** by the
PS2 prerecorded movie of the same event, while the GameCube source caller still
performs **every gameplay effect** in source order. Collision, events and
sequencing stay source-authoritative; only the evd playback (bodies, camera,
lights, messages) is replaced.

## Pieces

| Piece | Role |
|---|---|
| `game/platform/native_movie.cpp` | Player: R4FMV003 reader, pl_mpeg I/P decoder (two frames), YUV->UYVY strips, AICA stream. Never touches source state. |
| `game/platform/native_movie_stream.c` | Private compile of the pinned KOS `snd_stream.c`; its separation buffer is staged from the source heap. |
| `game/platform/native_ui.cpp` (hook) | Owns the 512x256 YUV422 texture (movie width/height up to 320x240, multiples of 16). `re4dc_ui_movie_present_now` draws one scene holding only the movie quad and presents it; `upload_begin` first discards an open (hidden) game scene. |
| `game/platform/pad.cpp` (hook) | `re4dc_pad_movie_buttons` (port-0 START/B/A plus the fixture script) lets the player poll skip while no game frame runs; a delivered skip is latched until its buttons are released, so it cannot leak into the game. |
| `game/route_movie_bridge.cpp` | `RouteMoviePlay`: the lasting parts of `Event::ExeBeginEvt`, `RunEvtCancel` and `ExeEndEvt` around the movie. |
| `src/game/game.cpp`, `src/st1/r100.cpp`, `src/st1/r101.cpp` | Call sites. r100 uses one wrapper block after `freeEvent`: `#define readEvent r100RouteReadEvent` maps the waiting `readEvent(no, 1)` calls to their movies and falls through to the source for everything else, so no r100 call site is edited. |
| `tools/convert_route_movies.py` | PS2 `BIO4MOV.AFS` SFD -> `.seq` (private output, never Git). |

## Presentation and cadence

The movie owns presentation. `re4dc_movie_play` runs inside the source task that
called `RouteMoviePlay` and never sleeps it, so the cooperative scheduler runs no
game frame until the movie ends: game time is frozen for the movie's length (as
the source event would have held the player; see the s20 note below).
Picture k is due at vblank v0 + 2k (29.97 pictures/s on NTSC 480i, one picture
per two fields). It is submitted when `now + 1 >= due` and dropped only if it is
two fields late; decoding picture k+1 overlaps the display of picture k, and the
PCM ring is topped up before every poll.

Cadence needs an asynchronous present: build with `PVR_PIPELINE=1` (or 2).
With `PVR_PIPELINE=0` the KOS manual flip blocks the player about 22 ms per
picture and pictures drop to 14-15 per second; the Makefile warns about it.
Every movie logs `route movie cost` (decode/convert/upload/present averages and
maxima) and `route movie cadence` (shown, dropped, late, two-field intervals).

Measured in Flycast (ROUTE_MOVIES=1 PVR_PIPELINE=1 PVR_FAST_WAKE=1, evidence
cutscenes-c9): r120 s00 1971/1971, r120 s01 2360/2360 and r100 s40 1175/1175
pictures shown, 0 dropped, every interval exactly two fields. Per picture:
decode 13.9-15.0 ms average (36 ms I-frame maximum), convert 3.4 ms, upload
0.7 ms, present 0.04 ms. The decoder uses `PLM_RE4DC_FAST` (bit-exact).
At the 1.65x hardware model that is about 30-32 ms of the 33.4 ms picture
budget: steady state fits, and an I-frame over the budget drops one picture.

### PVR YUV converter (default, `ROUTE_MOVIE_YUV=1`)

Movies are encoded full range: the converter applies the player's former per-pixel
studio->full mapping before encoding, and header word 7 bit 0 marks it. The PVR
YUV422 texture decodes full-range YUV, so each decoded picture goes straight to the
TA YUV converter as YUV420 macroblocks (store-queue bursts, zero dummy macroblocks
to fill the 512-wide texture row) and the PVR writes the texture itself; the player
waits on `PVR_YUV_STAT` before submitting the quad. `ROUTE_MOVIE_YUV=0` keeps the
software UYVY path (identity mapping for full-range movies). `ROUTE_MOVIE_TEXHASH=1`
logs the texture FNV of pictures 0/1/30/300, read back from VRAM.

Flycast (r120 s00/s01): convert 0.71 ms (was 3.37), upload 0 (was 0.69), decode
14.6-15.0 ms, 0 dropped. Hardware estimate at 1.65x: ~26 ms of 33.4 ms per picture.
Output: all 8 read-back texture hashes equal the host model; luma PSNR against the
software path is 39.3-44.4 dB and chroma above 50 dB, and against the encoder input
the converter path is equal or better on every movie.

## RouteMoviePlay contract

1. No media (`/cd/dc/movie/rRRRsEE.seq` missing/invalid) -> `UNHANDLED`, the source path runs unchanged.
2. Begin (ExeBeginEvt): `SceEventStart(0)`; Status_flg[2] |= 0x80000|0x10000; Status_flg[3] &= ~0x01000000; `Func(0)`; System_flg |= 0x400; `SndEventInit` unless the caller's sndFlag bit31.
3. Presentation: Disp_flg = all ones (cSofdec::initWork display contract) and restored after; Stop_flg stays as the source event set it. Skip is a new press of START (0x1000), the pad button behind the source event cancel key (Key bit 0x20000000 through Key_type_tbl[0][29]); the r120 intro uses the cSofdec movie mask (START or B, 0x1200). A button already held when the movie opens does not skip.
4. Skip (RunEvtCancel): Status_flg[3] |= 0x01000000; `Func(3)`.
5. End (ExeEndEvt): `zeroPartsPosInit` unless the caller keeps the pose (StatusFlag 0x800); Disp_flg &= ~0x800; `Func(2)`; System_flg |= 0x40; `SndEventEnd`; clear the Status_flg[2] bits; `SceEventEnd(0)`.
6. An error after begin still runs the end (the game never hangs on media).

Per-cut `Func(1)` hooks are driven by picture index: cut k starts at picture sum over j<k of (maxFrame_j + 1), where maxFrame is the first u16 of each camera fcv in the PS2 evd (s03: 1444 + 21 = 1465 = movie frames).

## Event table

| Event | Movie | Caller | Effects kept in the caller / bridge |
|---|---|---|---|
| r120 s00, s01 | 0x12000, 0x12001 | `nativeSkipOpeningRoom` | Both natural -> Scenario_flg[0] &= ~0x10 (r100 plays s40); any skip -> \|= 0x10 (source cancel of Evt_R120S0x_Func). |
| r100 s40 | 0x10040 | `r100_StartEvent` | Evt_R100S40_Func (skip -> Scenario 0x10), freeEvent(9), FadeSetW; OpeSetOpenTerm etc. unchanged. |
| r100 s03 | 0x10003 | `r100_Sce_look` | Evt_R100S03_Func, freeEvent(0); caller repositions the player. |
| r100 s20 | 0x10020 | `r100_Sce_zombi_dead` | KEEP_POSE; tick at picture 150 (cut 2): ems[1], ems[2] setNoSuspend(1); freeEvent(3). |
| r100 s30 | 0x10030 | `r100_GakeEvent` | freeEvent(4). |
| r100 s41, s43, s44 | 0x10041/43/44 | `MesCar00/01`, `EventBrige` | sndFlag bit31 (no SndEvent); freeEvent as source. |
| r101 s00 | 0x10100 | `Event00` | Replaces the waitLoadOk/MemorySwap block; the rest runs. |
| r101 s21 | 0x10121 | `Event20` | Tick at picture 635 (cut 0xA frame 0x20): window 0 SetBreakModel; Rsf 8, setEm 0x3C-0x46, ladders, player reposition unchanged. |
| r101 s30 | 0x10130 | `Event30` | InitModule(em15) kept; SceAtDataReset(0/2), EmListSetAlive, ladders unchanged. |

r100c00 is not referenced by any GC event and stays unmapped. r103 has no events.

`ROUTE_MOVIES=1` also sets `R100_DEFER_EVENTS=0`: s03 and s20 are presented by
their movies, not by the deferred evd path. Because the game frame is paused,
the Ganados that s20's tick releases (NoSuspend on ems[1] and ems[2]) start
walking when the movie ends, not during it.

## Budget

Route movies are 288x192 MPEG-1 (I/P, GOP 15, 650k/900k) + PCM16 stereo 32 kHz,
about 0.21 MB/s from disc (GDEMU target 1.5-3 MB/s). The player stages about
250 KB from the current source heap for the duration of the movie (two frames
166 KB, video 32 KB, read 16 KB, PCM 16 KB, AICA separation 8 KB, callback
8 KB, strip 4.5 KB), plus 256 KB VRAM and 16 KB AICA RAM; everything returns
at the terminal. r100's entry event has 311 KB of source heap free.

## Source hang detector

`postVSyncCallback` -> `haltExecCheck` (main.cpp) HALTs when 3600 vsyncs (60 s) pass without a
presented game frame. A movie owns the frame, so r120 s00 (66.5 s) tripped it at
main.cpp(548). The HALT's store to 0x11111111 was harmless log spam on the software UYVY path
(cutscenes-c9/c12 log ~5,200 HALT lines and play on); with the PVR YUV converter
(`ROUTE_MOVIE_YUV=1`, b50cfa3) it wedges the player, and the game stops ~60 s into the intro
(m1-intro-w10-r0). The player now zeroes `vsync_cnt` for every presented picture: a picture
counts as a presented frame. Timing only (frame pacing and the interrupt task resume); the
detector stays armed outside movies.

## Known gaps

- PS2 evd `Mes` packets (subtitles) are not shown; r101 s30's chapter-title overlay is not drawn.
- After s41, s43 and r101 s30 the GC game would move the player to the event body's final pose; the PS2 evds have no body, so the player stays in place (PS2 behaviour).
