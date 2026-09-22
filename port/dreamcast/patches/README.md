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

Run focused checks in `port/dreamcast/tests`:
`python3 -m unittest test_native_stream test_native_model test_pvr_geometry test_native_ui`.

KallistiOS is copyright 1997-2024 KallistiOS Contributors, including Megan Potter,
Lawrence Sebald and the contributors identified in upstream `AUTHORS` and source
notices. The modified `pvr_irq.c` retains Megan Potter's 2002/2004 notice. This
patch is provided under the same [KOS License](LICENSE.KOS); keep that notice and
license with redistributed source or binary documentation. Upstream pinned
[AUTHORS](https://github.com/KallistiOS/KallistiOS/blob/804b3195ebd1a06a27cc2b3a5eacf7a2429040a3/AUTHORS).
