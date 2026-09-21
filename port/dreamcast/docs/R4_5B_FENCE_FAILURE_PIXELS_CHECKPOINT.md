# R4 5B — retirement fence, failure coverage, pixel evidence

Status: **kept.** Three follow-ups to 5A, no architecture change.
Evidence: `C:\Flycast-Evidence\re4-dreamcast\d275-r4-5b-fence-pixels\`.

## 1. The GPU retirement fence was wrong

`pvr_wait_ready()` waits on `pvr_state.ta_busy`
(`kernel/arch/dreamcast/hardware/pvr/pvr_scene.c:374`), which the pinned KOS
clears when queued rendering *starts*. 5A freed room textures on that signal, so
a render could still have been reading them. `pvr_wait_render_done()`
(`:414`) waits on `render_busy`, which is the signal that actually means the
render is finished.

`retire_room()` now calls `room_gpu_quiesced()` as its first act: TA readiness,
then render completion, both return values checked. A timeout is not mistaken
for an idle GPU — it returns false, **nothing is freed**, the room stays fully
resident and playable, and the cycle is abandoned and counted in
`room_retire_fence_failures`. The fence lives inside the single retirement entry
point rather than at the call site, so a later caller cannot omit it;
`retire_room()` returns `bool` and both call sites handle it. The comments that
described `pvr_wait_ready()` as a render fence are corrected.

Observed: 0 fence failures over 30 retirements.

## 2. Failure injection now covers partial installs

5A only injected a missing file before any room resource was loaded, which
proved the cheapest case. There are now four bounded points, rotated one per
cycle with a clean load in between:

| point | injected after | what retirement has to undo |
|---|---|---|
| 1 | nothing loaded | arena mark only |
| 2 | room, collision and route adopted | 2.4 MB of arena, three package views |
| 3 | the room texture upload succeeded | the above plus owned VRAM |
| 4 | the eight derived arrays allocated | the above plus arrays nothing points into yet |

Over 3,103 frames: 17 loads, 30 retirements, **13 injected failures — 4, 3, 3
and 3 at points 1 to 4** — and every one followed by a clean retirement and a
successful retry. Across all 18 generations the tuple (heap used, heap free,
VRAM free, AICA free, arena used) took exactly **one** value,
(133,236, 245,336, 3,030,856, 1,378,336, 5,671,872), including the generations
that failed after owning VRAM. Persistent resources are untouched throughout:
enemy audio is unloaded sample by sample, never `snd_sfx_unload_all()`, and
R4e's ownership flags keep each shared texture payload freed exactly once.

Arena capacity 5,767,168, used and high water 5,671,872, retirement 1,240 us.

## 3. Pixel evidence, and what it does and does not show

5A compared counters. Counters can match while pixels do not, so this
checkpoint compares images.

Flycast does not write the finished frame back into emulated VRAM — read-backs
through `vram_s` returned the cleared buffer and read-backs through a
`pvr_ptr_t` returned bank-interleaved texture memory, under both the DirectX and
the software renderer. So the guest cannot photograph itself. Instead, in the
`FB_SNAPSHOT` build it **holds a frame still**: at six route ticks it stops
advancing the simulation for 2.5 s while rendering continues, and publishes
which route tick and generation is on screen. The host waits for that, captures
the window and compares on its own. The accepted build at `431f650` was given
the identical snapshot block in a worktree, so both freeze at the same ticks
with the same code.

Window captures include the title bar, which is cropped before comparison; the
first comparison run showed the *only* difference between the two builds at five
of six ticks was the window caption text.

**Against the accepted presentation**, same boot entry, same route ticks:

| tick | 40 | 80 | 120 | 170 | 220 | 270 |
|---|---|---|---|---|---|---|
| identical | no | **yes** | **yes** | **yes** | **yes** | **yes** |

Five of six comparison points are **pixel-identical** — room materials, both
characters, the HUD and the transparent passes included, since those are what is
on screen at those ticks.

**Across reloads**, generations 1 upward (the reload entry), 41 of 47
comparisons are pixel-identical. The six that are not are single generations:
tick 170 gens 8 and 9 differ in 104 pixels and tick 220/270 gen 3 in 135 and
137, all inside the actor's bounding box; tick 40 and tick 80 gen 3 differ
across the whole frame.

Reading that honestly: the whole-frame cases are a one-tick phase offset, not a
rendering difference — the diff covers the entire scene uniformly, which is what
a camera one step away looks like, and tick 40 is an unstable sampling point
that also differs between the accepted build and 5A. The actor-local cases are
animation phase. **This is not a claim of full visual parity.** It is: at five
of six sampled states the image is identical to the accepted build, and across
reloads the image is identical in 41 of 47 comparisons with the remainder
confined to actor and camera phase.

While setting this up, one real defect surfaced: the reloaded room resumed the
autoplay script **mid-phase**, so no two generations reached the same state at
the same tick — 5A's claim of "the same controlled room-entry state" was not
actually true across generations. Re-entering the room now restarts the script
that drives the encounter, alongside `reset_encounter()`. Before that fix, zero
of nine cross-reload comparisons matched at tick 120; after it, nine of nine do.

Also found: Flycast's serial console works. `dbgio_dev_select("scif")` plus
`Debug.SerialConsoleEnabled = yes` opens a second window carrying the guest's
`printf`, which is a far better diagnostic channel than polling guest memory.

## Still pending

* **The representative human gameplay check.** `make r100-cycle` builds the
  lifecycle with autoplay off for it. Nothing here replaces it.
* **Physical hardware.** All of the above is Flycast.
* `room_loads` counts lifecycle reloads; the boot load goes through `main()`.
