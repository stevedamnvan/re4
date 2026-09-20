# R4c: one-pass actor strips (DCA3 audit item A1a)

Status: kept.

The actor direct-strip path walked each strip twice: once to decide whether
every vertex was inside the depth range, then again to fetch the same records
and emit the packet. It now walks each strip once, assembling speculatively and
rewinding the whole strip on the first ineligible vertex.

Result: 0.429 ms off the CPU frame, from 61.229 ms to 60.791 ms at p50,
with a byte-identical submitted vertex stream and unchanged memory.

## What changed

`draw_character()` in `room/main.cpp`. The old shape, per strip:

    for each vertex: load primitive_indices[], load draw_vertices[].position,
                     load projected[].depth, test
    if ineligible -> fallback
    reserve capacity
    for each vertex: load primitive_indices[], load draw_vertices[],
                     load colors[], load projected[].x/.y/.z, store packet

The new shape reserves capacity first, then does one loop that loads
`primitive_indices[]`, `draw_vertices[]` and the projected record once each,
tests the depth from the record it already holds, and stores the packet from the
same record. Three loads per vertex disappear, and the projected position is
touched once instead of twice.

Capacity is reserved before the first speculative write. That is what makes the
rewind safe: no flush can happen inside a strip, so a rejected strip is undone
by restoring the saved `submit_count` and nothing partial ever reaches the tile
accelerator. `direct_strip` already required the strip to fit the buffer, so a
single flush before the loop is always enough. This is the same rewindable
assembly the room side accepted in R3x, applied to actors.

The fallback accounting is unchanged: a strip with opcode 0x98 that is rejected
for any reason still counts one `character_strip_fallbacks` and still goes
through `submit_triangle_range()`. Non-strip primitives are untouched.

One behavioural difference is worth stating plainly. The old code flushed only
after deciding a strip was eligible; the new code may flush before discovering a
strip is ineligible, which moves a submission boundary. It cannot change the
byte stream the tile accelerator receives, because header state is sticky and
vertex order is preserved, and in this route it cannot happen at all:
`actor_strip_fallbacks` is zero for every frame of the measured window.

## Measurements

Flycast, 640x480, r100 autoplay, matched window (simulation ticks 165-1194).
Three arms run back to back in one session, baseline first and last, so host
drift cannot be mistaken for the effect.

| Metric (p50, us) | baseline | A1a | baseline repeat | change |
|---|---:|---:|---:|---:|
| frame_us | 61,220 | 60,791 | 61,223 | -429 |
| opaque_actor_us | 11,789 | 11,430 | 11,789 | -359 |
| translucent_actor_hud_us | 1,760 | 1,690 | 1,760 | -70 |
| opaque_room_us | 21,981 | 21,981 | 21,981 | 0 |
| submit_us | 38,319 | 37,890 | 38,320 | -429 |

The two baseline arms differ by 3 us, so the noise floor is a few microseconds
and the 429 us saving is two orders of magnitude above it. The room stages are
untouched to the microsecond, which is the control this experiment needs: only
the actor path changed. The saving splits across both actor passes, 359 us in
the opaque pass and 70 us in the translucent actor and HUD pass, which is where
the actor draw runs.

Per-frame work is identical: 1,333 direct strips, 0 fallbacks, 15,674 actor
vertex records, 11,900 actor triangles, 370 submit calls and 972,928 submitted
bytes at p50 in both arms. Memory is unchanged: PVR free after textures
1,521,128 B, main RAM free 5,357,568 B, heap used 135,004 B.

Against the budget table, this moves the accepted frame from 61.229 ms to
60.791 ms.

## Correctness

Framebuffer capture at fixed simulation ticks is not a sound check for this
change. The candidate renders faster, so a given tick is sampled at a different
point in the frame and the actor appears at a slightly different animation
phase; four of six captured buffers differed inside an actor-sized bounding box
for that reason alone. Comparing them would have measured cadence, not
correctness.

So the check is phase-independent instead. A new `SUBMIT_DIGEST` build
accumulates an FNV-1a checksum over every byte handed to the tile accelerator
and publishes it per frame beside the simulation tick, as telemetry v15 in a
384-byte layout. The simulation is tick-driven and deterministic, so any tick
both builds rendered must produce the same stream. Running the baseline and the
candidate under that build and comparing digests per tick gives a direct
statement about the emitted geometry regardless of when a frame lands.

Over 524 simulation ticks rendered by both builds, every digest matched.
Zero mismatches. The two builds emit the same bytes to the tile
accelerator, so the change is a pure removal of redundant loads.

The digest build is diagnostic only. It reads back every submitted byte and is
far too slow to time with, exactly like the existing submit-profile and
cull-audit builds.

## Evidence

- `d263-r4c-a1a-timing` — bracketed baseline, candidate, baseline timing.
- `d264-r4c-a1a-visual` — framebuffer captures, retained to show why they are
  not the acceptance evidence here.
- `d265-r4c-a1a-digest` — the per-tick stream digest comparison.

## What this leaves open

A1b, emitting compact actor draw recipes offline and comparing a pre-resolved
occurrence stream against a bounded local corner cache, is only worth doing if
assembly is still material after this. A1c, conservative pose-aware bounds to
select the no-clipping kernel without testing every vertex, is untouched; note
that with zero fallbacks on this route the depth test never rejects anything, so
A1c would remove the test itself rather than the second walk. Neither is
scheduled here.
