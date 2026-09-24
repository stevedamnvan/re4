# Optional KOS patch for source-controlled presentation

`kos-804b319-manual-flip.patch` applies only to KallistiOS commit
`804b3195ebd1a06a27cc2b3a5eacf7a2429040a3`. It leaves automatic flipping as
the default, adding explicit present/discard for one serialized normal-frame
owner. It is required only by the opt-in game `PVR_STREAM=1` experiment.
Do not replace or patch the shared KOS checkout used by accepted references.

From the RE4 root, create a separate KOS worktree (choose unused paths):

```bash
git -C /root/work/kos worktree add --detach /root/work/kos-re4dc-d336 804b3195ebd1a06a27cc2b3a5eacf7a2429040a3
git -C /root/work/kos-re4dc-d336 apply --check "$PWD/port/dreamcast/patches/kos-804b319-manual-flip.patch"
git -C /root/work/kos-re4dc-d336 apply "$PWD/port/dreamcast/patches/kos-804b319-manual-flip.patch"
export RE4DC_KOS_BASE=/root/work/kos-re4dc-d336
source port/dreamcast/kos-env.sh
make -C "$KOS_BASE" -j4
make -C port/dreamcast/game -j4 CORE_RESIDENT_BYTES=1360608 PLAYER_RESIDENT_BYTES=846656 WEAPON_RESIDENT_BYTES=247776 PARTS_DEMAND=1 MODELINFO_DEMAND=1 OBJECT_DEMAND=1 PVR_STREAM=1
```

Do not reapply to an already patched worktree. Inspect its status/HEAD first.
`PVR_STREAM=0` plus the original RE4DC_KOS_BASE retains the bounded reference.
The build requires real defined KOS symbols; missing functions cannot become
generated success stubs. One scene must complete TA/render before resolve;
no next queued scene or concurrent renderer is supported. Resolve timeout keeps
the completed buffer hidden. Source hold, black and resource-retirement behavior
are tested separately. See the D336 checkpoint for actual capacity and fidelity
limits; in particular Flycast zero TA-usage values do not prove hardware fit.

## Async present (D367)

`kos-804b319-async-present.patch` applies on top of the manual-flip patch at the same
KOS commit. It adds `pvr_present_async()` / `pvr_present_wait()` /
`pvr_present_pending()`: the frame owner records its present or discard decision at scene
submit, and the render-done IRQ carries it out. The CPU no longer blocks on render
completion before starting the next frame. It is required only by the opt-in game
`PVR_PIPELINE=2` (the D367 default recipe). Use its own worktree; do not patch the d336 one:

```bash
git -C /root/work/kos worktree add --detach /root/work/kos-re4dc-d367 804b3195ebd1a06a27cc2b3a5eacf7a2429040a3
git -C /root/work/kos-re4dc-d367 apply "$PWD/port/dreamcast/patches/kos-804b319-manual-flip.patch"
git -C /root/work/kos-re4dc-d367 apply "$PWD/port/dreamcast/patches/kos-804b319-async-present.patch"
git -C /root/work/kos-re4dc-d367 apply "$PWD/port/dreamcast/patches/kos-804b319-vbuf-switch.patch"
RE4DC_KOS_BASE=/root/work/kos-re4dc-d367 bash -c 'source port/dreamcast/kos-env.sh && make -C "$KOS_BASE" -j8'
```

`port/dreamcast/tools/d367/build.sh` selects `/root/work/kos-re4dc-d367` automatically when
`EXTRA_MAKE` contains `PVR_PIPELINE=2` (unless `RE4DC_KOS_BASE` is set). Check that the library
defines `_pvr_present_async`, `_pvr_present_wait` and `_pvr_present_pending`.

## TA double-buffer switch (D367)

`kos-804b319-vbuf-switch.patch` applies on top of async-present in the same worktree. It adds
`pvr_set_vbuf_doublebuf(bool)` in a new object (`hardware/pvr/pvr_vbuf.c`): TA vertex double
buffering switched at run time, only between scenes (-1 while a scene is open or in the TA, a
render runs or a present decision is pending). The game's `TA_DOUBLEBUF=1` with `SUBSCREEN=1`
needs it: the sub-screen backing borrows bank 1's vertex buffer while a sub screen is open, and
the TA runs on bank 0 for that time (design-doublebuf). subscreen.mk checks the library defines
`_pvr_set_vbuf_doublebuf`. Programs that never call it link nothing new (the other library
members are byte-identical).

Run focused checks in `port/dreamcast/tests`:
`python3 -m unittest test_native_stream test_native_model test_pvr_geometry test_native_ui`.

KallistiOS is copyright 1997-2024 KallistiOS Contributors, including Megan Potter,
Lawrence Sebald and the contributors identified in upstream `AUTHORS` and source
notices. The modified `pvr_irq.c` (both patches) retains Megan Potter's 2002/2004 notice. These
patches are provided under the same [KOS License](LICENSE.KOS); keep that notice and
license with redistributed source or binary documentation. Upstream pinned
[AUTHORS](https://github.com/KallistiOS/KallistiOS/blob/804b3195ebd1a06a27cc2b3a5eacf7a2429040a3/AUTHORS).
