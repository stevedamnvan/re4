# D313: remove redundant PowerPC module residency

2026-09-21. Keep as a selectable equivalent storage optimization. The reference
mirror remains /root/re4data-le; candidate /root/re4data-le-static. No source
assets, motion coverage, pools, event behavior or image quality were reduced.

## Existing path, compact representation

`le_mirror.py --compact-static-rel` uses the existing native module registry,
Makefile selection and source module IDs. Only qualified whole files for those
IDs are eligible. Unknown bindings or incomplete neighbors stay on the reference
path. The original conversion remains the default; toggling back regenerates a
previously compacted output rather than trusting its cache.

The compact 64-byte OSModuleHeader preserves ID and BSS size, marks its native
version, and removes unused PPC section/code/relocation data. The existing
OSLink binder rejects malformed descriptors/unknown IDs, installs real compiled
entry points, and permits a valid rebind. This does not fix the earlier static
BSS/constructor/reload lifecycle debt. The PPC .sym reader now rejects modules
without a PPC section table; ELF/nm remains the native diagnostic reference.
PowerPC preprocessed exception.cpp tokens are unchanged (not full ProDG).

DRS slot count, tags, asset offsets and every asset byte remain unchanged.
Only the tail module becomes a descriptor. The nested sound container is copied
byte-for-byte and its top-level offset is rebased. Report offsets/sizes follow
that relocation; conversion still requires every source dependency to qualify.
There is no second archive loader or decoder, and no compressed geometry buffer.

## Actual before/after

Same 55-second boot fixture as D312; five missing stubs still explicit.
D313 successfully binds the compact stage module and executes the native handgun
prolog, then reaches the same incomplete source room state.

| Quantity | D312 | D313 |
|---|---:|---:|
| Game OSAlloc arena | 8,929,280 bytes | 8,929,280 bytes |
| Free at block-model request | 419,456 | 465,920 |
| Required block-model request | 1,126,272 | 1,126,272 |
| First em12 body request | 4,006,016 | 3,577,728 |
| Free at first em12 request | 409,152 | 455,616 |
| Free after TexRender allocation | 343,552 | 390,016 |
| ELF text | 2,229,860 | 2,230,132 |
| ELF data / BSS | 71,960 / 569,484 | unchanged |

**46,464 bytes of live heap recovered**, including allocator rounding, from
removing the loaded stage PPC image. Em12 demand falls 428,288 bytes; it still
fails, so those bytes are avoided demand rather than already-recovered live RAM.
The handgun disc body shrinks 22,240 bytes but its fixed reservation does not;
no corresponding main-RAM saving is claimed. Other compacted files are not all
resident at this point. No frame-time, peak-memory or audio improvement claimed.

25 mirror tests and the actual 32-bit native binder fixture pass. Fixtures cover
asset/sound preservation, unknown/incomplete inputs, BSS retention, mode switching,
malformed headers, unknown bindings and repeated binding. Actual required mirror
gate passes; full report retains seven outside-fixture errors, including r101 EVS.
Actual data verification compares assets and nested sound against the reference.
This is not visual, manual gameplay or physical-hardware acceptance.

## Next bounded resource task

Both block and enemy allocations still fail. Do not count the sleeping source
room tasks as successful room initialization. ID/effect errors, native graphics
and audio integration and event ARAM residency remain open.

Private inventory reuses the existing mirror's TPL traversal and convert_tpl.py
size calculation, counting unique image addresses (base level only):

| Archive | Base source image bytes | All images expanded to 16-bit base bytes |
|---|---:|---:|
| Core | 1,744,832 | 4,892,548 |
| r100 | 1,830,048 | 6,474,272 |
| Leon | 209,920 | 649,216 |
| Handgun | 37,888 | 88,576 |
| Ganado | 697,344 | 2,327,552 |

These are capacity leads, not guaranteed reclaimable bytes or the actual active
texture set. They exclude mipmaps/palettes and do not approve format conversion.
An upload-all 16-bit scheme exceeds VRAM. Next recover the source-active texture
set/lifetimes and connect bounded native ownership using existing Package/storage
sharing, upload-success and retirement mechanisms. Keep source structures and
texture identities authoritative; a viewer package cannot replace the room ARC.
Preserve palette/alpha/filter/mip semantics and CPU readers. Reclaim bytes only
after successful native ownership and a compacted backing allocation. Source
block residency/ARAM transport and event working sets must also remain accounted.
No new compressor, arbitrary pool cuts or PS2 substitution is justified here.

## Reproduction and exact evidence

Private folder: C:\Flycast-Evidence\re4-dreamcast\d313-static-module-storage.
It retains ELF/disc, all asset hashes, reports, dirty runtime patch, script/logs,
byte comparisons, source check and test logs. Prior D312 evidence remains intact.

```
source port/dreamcast/kos-env.sh
make -C port/dreamcast/game -j4
python3 port/dreamcast/tools/le_mirror.py /root/re4data /root/re4data-le-static \
  --native-rooms --compact-static-rel --require /root/probe/d312-required.txt
bash port/dreamcast/tools/mkdisc.sh port/dreamcast/game/re4dc-game.elf \
  /root/re4data-le-static /root/probe/d313-disc /root/probe/d292-fixtures
```

- ELF SHA256: c6b9b3c1a9814310c90aa613f786697be892f66e6a8bb554c62eccf2f1be7c68
- Disc SHA256: 8c21cf38434ed703237e571d39e1ba695dd390c684cfe109d5174e49b1e9203d
- Flycast SHA256: 64491c005db917cc643b50e312f78c5b04ccfa77acebbe1cd07ad6371d422c8a
- r100 DAR unchanged: 1f80accf5be62432b45a1b7b7e3b7ee630af6449183f1afc582e2155ae6b7739
- KOS: 804b3195ebd1a06a27cc2b3a5eacf7a2429040a3; SH GCC 15.2.0.
