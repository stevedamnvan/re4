# R4d: build policy (DCA3 audit item A2)

Status: kept, `-O3` with link-time optimization.

The room build asked for `-O2` and left everything else to KallistiOS. DCA3
ships `-Os` with a per-file `-O3` list, a no-fast-math list for camera units and
link-time optimization, which the audit flagged as a cheap experiment with an
uncertain outcome. The outcome here is the largest single frame saving since
R3r, and it required no source change at all.

Result: 2.839 ms off the CPU frame, 60.791 ms to 57.951 ms at p50, with a
byte-identical submitted vertex stream. The saving is not uniform: every drawing
and submission stage improves while actor lighting gets 2.018 ms worse, which is
itself the evidence for the follow-up experiment.

## The effective flags, first

The audit says to read the real compile and link commands before assuming a
setting is absent. They are:

    kos-c++ -std=c++20 -O2 -Wall -Wextra -Werror -I../include \
            -DRE4DC_SCENE_R100 -DRE4DC_480P -c main.cpp -o main.o
    kos-c++ -o re4dc-room-viewer.elf <objects>

`KOS_CFLAGS` contributes include paths, `-Wall` and `-g`; the `kos-c++` wrapper
supplies the architecture flags. There was no optimization setting on the link
line at all, so link-time optimization could not have been in effect.

`ROOM_OPT` and `ROOM_LTO` are now Makefile variables, applied to both the
compile and the link, so an arm is selected on the command line and never by
editing. Rebuilding with `ROOM_OPT=-O2 ROOM_LTO=` reproduced the previously
accepted ELF hash byte-for-byte, which is the control this needed: the
restructuring itself changes no code generation.

## Arms

Flycast, 640x480, r100 autoplay, matched window (ticks 165-1194), one session.
Assets, KallistiOS revision and toolchain identical across all four.

| Arm | frame p50 | frame p95 | opaque room p50 | opaque actor p50 | `submit_us` p50 | ELF text | main RAM free |
|---|---:|---:|---:|---:|---:|---:|---:|
| `-O2` (previous default) | 60,790 | 60,873 | 21,981 | 11,430 | 37,890 | 8,822,089 | 5,357,568 |
| `-O3` | 58,184 | 58,251 | 19,496 | 10,031 | 33,651 | 8,832,597 | 5,349,376 |
| `-O2` + LTO | 60,817 | 60,905 | 21,950 | 11,585 | 37,968 | 8,820,585 | 5,357,568 |
| `-O3` + LTO | **57,951** | **58,015** | 19,464 | 9,900 | 33,391 | 8,829,485 | 5,353,472 |

`-O3` alone is worth 2.606 ms. Link-time optimization on top of it adds a
further 0.233 ms. Link-time optimization on its own is worth nothing: the
`-O2` + LTO arm is 27 us *slower* than plain `-O2`, which is inside the few
microseconds of run-to-run noise measured in R4c, so it is best read as no
effect rather than a regression. The two effects are not additive in the way a
naive reading would suggest, and only the combination was adopted.

The result is not uniform, and the exception matters more than the headline.
Every drawing and submission stage improves, and actor lighting gets worse:

| Stage p50 (us) | `-O2` | `-O3` | `-O3` + LTO | change |
|---|---:|---:|---:|---:|
| `submit_us` | 37,890 | 33,651 | 33,391 | -4,499 |
| opaque room | 21,981 | 19,496 | 19,464 | -2,517 |
| opaque actor draw | 11,430 | 10,031 | 9,900 | -1,530 |
| actor pose | 5,820 | 5,422 | 5,494 | -326 |
| translucent room | 2,735 | 2,505 | 2,499 | -236 |
| translucent actor and HUD | 1,690 | 1,562 | 1,471 | -219 |
| **actor lighting** | **14,189** | **16,240** | **16,207** | **+2,018** |
| actor normals | 1,831 | 1,831 | 1,831 | 0 |
| room visibility | 806 | 806 | 806 | 0 |

Actor lighting is 2.018 ms slower at `-O3`, split as 1.541 ms on Leon and
0.479 ms on the Ganado, and link-time optimization does not recover it. The net
is still 2.839 ms better, so the arm is kept, but the frame is now carrying a
stage that was actively harmed by the setting that helped everything else.

That is the case for the per-file policy DCA3 uses, and it arrives as evidence
rather than as a preference. Moving the prepared-light evaluators into their own
translation unit compiled at `-O2`, leaving the rest at `-O3`, is worth up to a
further 2 ms if the stage returns to its `-O2` cost. It is queued as the next
experiment rather than folded in here, because it is a source change with its
own correctness obligation and this one is not.

Two stages are bit-for-bit unmoved, actor normals at 1,831 us and room
visibility at 806 us, which is a useful sanity check on the measurement: they
are the stages whose cost is dominated by memory traffic the optimizer cannot
remove.

Costs are small and bounded. ELF text grows 7,396 bytes, which is 0.08% of the
image and under 2% of the roughly 381 KB that is actual code rather than the
embedded ROM disk. Free main RAM falls by 4,096 bytes, one page, leaving
5,353,472 bytes. Heap use is unchanged at 135,004 bytes.

## Correctness

Higher optimization can legitimately change floating-point results, because
GCC's default `-ffp-contract=fast` lets it form different contractions, so this
needed the same phase-independent proof R4c used rather than an assumption.

A `SUBMIT_DIGEST` build of the accepted arm was compared against the `-O2`
digest run tick by tick: 508 simulation ticks rendered by both builds, every
checksum equal, zero mismatches. The emitted vertex stream is byte-identical,
so the optimization level changed how the work is done and not what was
produced. Per-frame counters agree independently: 1,333 direct strips and
15,674 actor vertex records at p50 in all four arms.

Host tests pass with zero failures.

## What was deliberately not done

No `-ffast-math`, no `-fmerge-all-constants`, no altered floating-point modes
and no assertion removal. The audit is explicit that those are a separate
rendering-only candidate needing its own numerical validation, and the result
above was obtained without them, so there is no reason to reach for them now.

A per-file optimization policy is *not* dismissed, and the stage table above is
why. The plan before measuring was to reject it, on the grounds that RE4DC has
seven translation units with nearly all frame work in one. The actor lighting
regression overturns that: there is now a named, measured 2 ms reason to split
one kernel out and compile it differently. That is the next experiment.

## Evidence

`d266-a2-build-policy` holds the four arms and their telemetry.
`d265-r4c-a1a-digest` holds the stream-digest comparison.
