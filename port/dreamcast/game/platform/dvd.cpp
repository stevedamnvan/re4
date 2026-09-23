// DVD interface over the KOS file system: the game's disc tree lives under
// /cd/ with the GameCube paths (lower-cased); entry numbers index a table of
// paths the game asked for; reads are performed synchronously and complete
// through the SDK callback. The source queue-step guard below keeps competing
// source pumps from re-entering its synchronous read before step bookkeeping.
#include <kos.h>
#include <stdio.h>
#include <string.h>
#include <ctype.h>

#include "re4dc_platform.h"
#include "native_io.h"
#ifndef RE4DC_IO_PROBE
#define RE4DC_IO_PROBE 0
#endif

namespace {
void* dvd_step_owner;
kthread_t* dvd_step_thread;
unsigned dvd_step_depth;
}
extern "C" void* re4dc_dvd_step_begin(){
    const int irq=irq_disable();
    if(dvd_step_owner && dvd_step_thread!=thd_current){
        irq_restore(irq);thd_sleep(1);return nullptr;
    }
    // The outer borrow protects shared header save/use/restore. Individual
    // source Read steps on that same thread may enter it recursively. A
    // competing pump yields; IRQs remain enabled while native I/O is active.
    void* token=re4dc_io_begin();
    if(!dvd_step_owner){dvd_step_owner=token;dvd_step_thread=thd_current;}
    ++dvd_step_depth;
    irq_restore(irq);
    return token;
}
extern "C" void re4dc_dvd_step_end(void* token){
    const int irq=irq_disable();
    if(!token || dvd_step_owner!=token || dvd_step_thread!=thd_current || !dvd_step_depth){
        re4dc_missing("DVD source-step owner mismatch");irq_restore(irq);return;
    }
    if(--dvd_step_depth==0){dvd_step_owner=nullptr;dvd_step_thread=nullptr;}
    re4dc_io_end(token);irq_restore(irq);
}

typedef signed char s8;
typedef unsigned char u8;
typedef signed long s32;
typedef unsigned long u32;
typedef int BOOL;

struct DVDDiskID {
    char gameName[4];
    char company[2];
    u8 diskNumber;
    u8 gameVersion;
    u8 streaming;
    u8 streamingBufSize;
    u8 padding[22];
};

struct DVDCommandBlock;
typedef void (*DVDCBCallback)(s32 result, DVDCommandBlock* block);
struct DVDCommandBlock {
    DVDCommandBlock* next;
    DVDCommandBlock* prev;
    u32 command;
    s32 state;
    u32 offset;
    u32 length;
    void* addr;
    u32 currTransferSize;
    u32 transferredSize;
    DVDDiskID* id;
    DVDCBCallback callback;
    void* userData;
};

struct DVDFileInfo;
typedef void (*DVDCallback)(s32 result, DVDFileInfo* fileInfo);
struct DVDFileInfo {
    DVDCommandBlock cb;
    u32 startAddr;
    u32 length;
    DVDCallback callback;
};

enum { DVD_STATE_END = 0, DVD_STATE_BUSY = 1, DVD_RESULT_FATAL = -1, DVD_RESULT_CANCELED = -3 };

#define MAX_ENTRIES 512
static char g_entryPath[MAX_ENTRIES][64];
static s32 g_entrySize[MAX_ENTRIES];  // -1: not on the disc
static int g_entryCount;
static DVDDiskID g_diskId = {{'G', '4', 'B', 'E'}, {'0', '8'}, 0, 0, 0, 0, {0}};
static const char* g_root = "/cd/";

#if RE4DC_IO_PROBE
// Time a game thread spent blocked on a source DVD read (the whole synchronous read, or
// with DISC_ASYNC the wait for an overlapped read to land). Door-transition telemetry.
static unsigned g_blockN, g_blockWorst;
static unsigned long long g_blockTotal;
static void note_block(unsigned long long us)
{
    ++g_blockN; g_blockTotal += us; if (us > g_blockWorst) g_blockWorst = (unsigned) us;
}
extern "C" void re4dc_dvd_block_stats(unsigned* n, unsigned long long* total_us, unsigned* worst_us, int reset)
{
    *n = g_blockN; *total_us = g_blockTotal; *worst_us = g_blockWorst;
    if (reset) { g_blockN = 0; g_blockTotal = 0; g_blockWorst = 0; }
}
#endif


static void normalise(const char* in, char* out, size_t n)
{
    size_t i = 0;
    while (*in == '/' || *in == '\\') in++;
    for (; *in && i + 1 < n; in++) {
        char c = *in;
        if (c == '\\') c = '/';
        out[i++] = (char) tolower((unsigned char) c);
    }
    out[i] = 0;
}

static s32 fileSize(const char* rel)
{
    Re4dcIoScope io;
    char full[96];
    snprintf(full, sizeof(full), "%s%s", g_root, rel);
    re4dc_set_stage(0x2000);
    file_t f = fs_open(full, O_RDONLY);
    re4dc_set_stage(0x2001);
    if (f < 0) {
        return -1;
    }
    s32 size = (s32) fs_total(f);
    re4dc_set_stage(0x2002);
    fs_close(f);
    re4dc_set_stage(0x2003);
    return size;
}

extern "C" {

void re4dc_dvd_set_root(const char* root) { g_root = root; }

int re4dc_dvd_native_path(const char* name, char* output, unsigned capacity)
{
    if (!name || !output || !capacity) return 0;
    const int n = snprintf(output, capacity, "%s%s", g_root, name);
    return n >= 0 && (unsigned) n < capacity;
}

s32 DVDConvertPathToEntrynum(const char* path)
{
    char rel[64];
    normalise(path, rel, sizeof(rel));
    for (int i = 0; i < g_entryCount; i++) {
        if (strcmp(g_entryPath[i], rel) == 0) {
            return g_entrySize[i] >= 0 ? i : -1;
        }
    }
    if (g_entryCount >= MAX_ENTRIES) {
        re4dc_log("DVDConvertPathToEntrynum: table full (%s)\n", rel);
        return -1;
    }
    int i = g_entryCount++;
    strcpy(g_entryPath[i], rel);
    g_entrySize[i] = fileSize(rel);
    if (g_entrySize[i] < 0) {
        re4dc_log("dvd: not on disc: %s\n", rel);
        return -1;
    }
    return i;
}

BOOL DVDFastOpen(s32 entrynum, DVDFileInfo* fi)
{
    if (entrynum < 0 || entrynum >= g_entryCount || g_entrySize[entrynum] < 0) {
        return 0;
    }
    memset(fi, 0, sizeof(*fi));
    fi->startAddr = (u32) entrynum;  // the entry doubles as the "disc offset"
    fi->length = (u32) g_entrySize[entrynum];
    fi->cb.state = DVD_STATE_END;
    return 1;
}

BOOL DVDOpen(const char* fileName, DVDFileInfo* fi)
{
    return DVDFastOpen(DVDConvertPathToEntrynum(fileName), fi);
}

BOOL DVDClose(DVDFileInfo* fi)
{
    fi->cb.state = DVD_STATE_END;
    return 1;
}

s32 DVDReadAsyncPrio(DVDFileInfo* fi, void* addr, s32 length, s32 offset, DVDCallback callback, s32 prio)
{
    Re4dcIoScope io;  // includes callback completion before cancellation can drain
    (void) prio;
    int entry = (int) fi->startAddr;
    char full[96];
    snprintf(full, sizeof(full), "%s%s", g_root, g_entryPath[entry]);
    fi->cb.addr = addr;
    fi->cb.offset = (u32) offset;
    fi->cb.length = (u32) length;
    fi->cb.state = DVD_STATE_BUSY;
    fi->cb.currTransferSize = (u32) length;
    fi->cb.transferredSize = 0;
    fi->callback = callback;
#if RE4DC_IO_PROBE
    const unsigned long long io_t0 = timer_us_gettime64();
#endif
    s32 result = DVD_RESULT_FATAL;
    file_t f = fs_open(full, O_RDONLY);
    if (f >= 0) {
        s32 avail = (s32) fi->length - offset;
        if (avail < 0) avail = 0;
        s32 want = length < avail ? length : avail;
        fs_seek(f, offset, SEEK_SET);
        s32 got = 0;
        while (got < want) {
            ssize_t r = fs_read(f, (u8*) addr + got, (size_t) (want - got));
            if (r <= 0) {
                break;
            }
            got += (s32) r;
        }
        fs_close(f);
        // The SDK reports the requested (32-byte aligned) length on success.
        result = got == want ? length : got;
    } else {
        re4dc_log("DVDReadAsyncPrio: open failed %s\n", full);
    }
#if RE4DC_IO_PROBE
    { const unsigned long long io_t1 = timer_us_gettime64(); note_block(io_t1 > io_t0 ? io_t1 - io_t0 : 0); }
#endif
    fi->cb.transferredSize = result > 0 ? (u32) result : 0;
    fi->cb.state = DVD_STATE_END;
    if (callback) {
        callback(result, fi);
    }
    return 1;
}

s32 DVDGetTransferredSize(DVDFileInfo* fi) { return (s32) fi->cb.transferredSize; }
s32 DVDGetCommandBlockStatus(const DVDCommandBlock* block) { return block->state; }
s32 DVDGetDriveStatus(void) { return 0; }  // DVD_STATE_END: ready
void* DVDGetFSTLocation(void)
{
    // dvd.cpp Init computes FstSize = SimulatedMemSize - (fst - 0x80000000); give it 1 MB.
    return (void*) (0x80000000u + 0x01800000u - 0x100000u);
}

int DVDCancelAsync(DVDCommandBlock* block, DVDCBCallback callback)
{
    block->state = DVD_STATE_END;
    if (callback) {
        callback(0, block);
    }
    return 1;
}

s32 DVDCancelAll(void)
{
    return 0;
}

DVDDiskID* DVDGetCurrentDiskID(void) { return &g_diskId; }

DVDDiskID* DVDGenerateDiskID(DVDDiskID* id, const char* game, const char* company, u8 diskNum, u8 version)
{
    memset(id, 0, sizeof(*id));
    memcpy(id->gameName, game, 4);
    memcpy(id->company, company, 2);
    id->diskNumber = diskNum;
    id->gameVersion = version;
    return id;
}

int DVDCompareDiskID(const DVDDiskID* a, const DVDDiskID* b)
{
    if (memcmp(a->gameName, b->gameName, 4) != 0) return 0;
    if (memcmp(a->company, b->company, 2) != 0) return 0;
    if (a->diskNumber != b->diskNumber) return 0;
    if (b->gameVersion != 0xFF && a->gameVersion != b->gameVersion) return 0;
    return 1;
}

int DVDChangeDiskAsync(DVDCommandBlock* block, DVDDiskID* id, DVDCBCallback callback)
{
    re4dc_log("DVDChangeDiskAsync: disc %d requested (single-disc build)\n", id->diskNumber);
    block->state = DVD_STATE_END;
    if (callback) {
        callback(0, block);
    }
    return 1;
}

}  // extern "C"
